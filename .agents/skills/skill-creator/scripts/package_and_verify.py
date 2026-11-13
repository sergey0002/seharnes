#!/usr/bin/env python3
"""Deterministic .skill packager and 17-agent preflight verifier (stdlib + optional PyYAML / sibling skill-auditor)."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
ALLOWED_TOP_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
    "disable-model-invocation",
    "user-invocable",
    "context",
    "agent",
    "model",
    "hooks",
}
DISCOURAGED_TOP_KEYS = {"version", "author", "category", "tags", "platform", "when_to_use"}
NON_CANONICAL_DIRS = {"workflows", "commands", "guides", "prompts", "docs"}
EXCLUDED_DIR_NAMES = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".pytest_cache", ".mypy_cache"}
EXCLUDED_PREFIXES = ("." + "env", "id_" + "rsa", "id_" + "ed25519", "id_" + "ecdsa")
EXCLUDED_SUFFIXES = (".pyc", ".pyo", ".ds_store", ".pem", ".key", ".p12")
SCRIPT_EXTS = {".sh", ".py", ".ts", ".js", ".mjs", ".cjs", ".rb"}
MD_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#\s]+)")
INLINE_BANG_RE = re.compile(r"(?<![\\`])!`[^`\n]+`")
USER_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])(/(?:Users|home)/[A-Za-z0-9._-]+)")


def parse_frontmatter_basic(text: str) -> tuple[dict[str, Any], str, str | None]:
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        return {}, text, "SKILL.md is missing opening YAML frontmatter '---'."
    lines = text.splitlines(keepends=True)
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}, text, "SKILL.md YAML frontmatter is missing closing '---'."
    raw_yaml = "".join(lines[1:end_idx])
    body = "".join(lines[end_idx + 1 :])

    if yaml is not None:
        try:
            loaded = yaml.safe_load(raw_yaml) or {}
            if not isinstance(loaded, dict):
                return {}, body, "Frontmatter YAML root must be a mapping."
            return loaded, body, None
        except Exception as exc:
            return {}, body, f"Invalid YAML frontmatter: {exc}"

    # Minimal stdlib fallback parser when PyYAML is unavailable.
    data: dict[str, Any] = {}
    current_map_key: str | None = None
    for raw_line in raw_yaml.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if raw_line.startswith((" ", "\t")) and current_map_key == "metadata":
            sub = raw_line.strip()
            if ":" in sub:
                sk, sv = sub.split(":", 1)
                data.setdefault("metadata", {})[sk.strip()] = sv.strip().strip('"').strip("'")
            continue
        current_map_key = None
        if ":" in raw_line:
            k, v = raw_line.split(":", 1)
            key = k.strip()
            val = v.strip()
            if not val:
                data[key] = {}
                current_map_key = key
            elif val.lower() == "true":
                data[key] = True
            elif val.lower() == "false":
                data[key] = False
            else:
                data[key] = val.strip('"').strip("'")
    return data, body, None


def is_excluded(path: Path, skill_root: Path) -> bool:
    rel_parts = path.relative_to(skill_root).parts
    if any(part in EXCLUDED_DIR_NAMES for part in rel_parts):
        return True
    name_low = path.name.lower()
    if name_low.startswith(EXCLUDED_PREFIXES):
        return True
    return name_low.endswith(EXCLUDED_SUFFIXES)


def validate_openai_yaml(skill_dir: Path, name: str, user_invoked: bool) -> tuple[list[dict[str, str]], list[str]]:
    issues: list[dict[str, str]] = []
    warnings: list[str] = []
    openai_path = skill_dir / "agents" / "openai.yaml"
    if not openai_path.exists():
        return issues, ["agents/openai.yaml not present (optional Codex UI metadata)."]

    raw = openai_path.read_text(encoding="utf-8", errors="replace")
    parsed: dict[str, Any] = {}
    if yaml is not None:
        try:
            loaded = yaml.safe_load(raw) or {}
            if isinstance(loaded, dict):
                parsed = loaded
        except Exception as exc:
            issues.append({"severity": "ERROR", "code": "OPENAI-YAML-SYNTAX", "message": f"Invalid agents/openai.yaml: {exc}"})
            return issues, warnings
    else:
        parsed = {}
        section = None
        for ln in raw.splitlines():
            s = ln.strip()
            if not s or s.startswith("#"):
                continue
            if not ln.startswith((" ", "\t")) and s.endswith(":"):
                section = s[:-1].strip()
                parsed[section] = {}
            elif section and ":" in s:
                k, v = s.split(":", 1)
                val: Any = v.strip().strip('"').strip("'")
                if val == "true":
                    val = True
                elif val == "false":
                    val = False
                parsed[section][k.strip()] = val

    iface = parsed.get("interface", {})
    if isinstance(iface, dict):
        short_desc = str(iface.get("short_description", "")).strip()
        if short_desc and not (25 <= len(short_desc) <= 64):
            warnings.append(
                f"agents/openai.yaml interface.short_description length is {len(short_desc)} (Codex prefers 25-64 chars)."
            )
        default_prompt = str(iface.get("default_prompt", ""))
        if default_prompt and f"${name}" not in default_prompt:
            warnings.append(f"agents/openai.yaml interface.default_prompt should mention '${name}'.")

    policy = parsed.get("policy", {})
    if isinstance(policy, dict) and "allow_implicit_invocation" in policy:
        allow_impl = policy.get("allow_implicit_invocation")
        if user_invoked and allow_impl is True:
            issues.append(
                {
                    "severity": "ERROR",
                    "code": "INVOCATION-DRIFT",
                    "message": "SKILL.md sets disable-model-invocation: true, but agents/openai.yaml allows implicit invocation.",
                }
            )
        elif not user_invoked and allow_impl is False:
            warnings.append(
                "agents/openai.yaml sets allow_implicit_invocation: false while SKILL.md enables model invocation."
            )

    return issues, warnings


def run_builtin_preflight(skill_dir: Path) -> dict[str, Any]:
    errors: list[dict[str, str]] = []
    warnings: list[str] = []

    if not skill_dir.is_dir():
        return {
            "status": "FAIL",
            "errors": [{"severity": "ERROR", "code": "MISSING-DIR", "message": f"Skill directory not found: {skill_dir}"}],
            "warnings": [],
        }

    skill_md = skill_dir / "SKILL.md"
    exact_entries = {p.name for p in skill_dir.iterdir()}
    if "SKILL.md" not in exact_entries:
        errors.append(
            {
                "severity": "ERROR",
                "code": "MISSING-SKILL-MD",
                "message": "Exact uppercase 'SKILL.md' not found at skill root.",
            }
        )
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    content = skill_md.read_text(encoding="utf-8", errors="replace")
    fm, body, fm_err = parse_frontmatter_basic(content)
    if fm_err:
        errors.append({"severity": "ERROR", "code": "FRONTMATTER-PARSE", "message": fm_err})
        return {"status": "FAIL", "errors": errors, "warnings": warnings}

    name = str(fm.get("name", "")).strip()
    if not name or not NAME_RE.match(name):
        errors.append(
            {
                "severity": "ERROR",
                "code": "INVALID-NAME",
                "message": f"Frontmatter 'name' ({name!r}) must match ^[a-z0-9]+(-[a-z0-9]+)*$.",
            }
        )
    elif name != skill_dir.name:
        errors.append(
            {
                "severity": "ERROR",
                "code": "NAME-DIR-MISMATCH",
                "message": f"Frontmatter name '{name}' does not match folder name '{skill_dir.name}'.",
            }
        )

    desc = fm.get("description")
    if not isinstance(desc, str) or not desc.strip():
        errors.append(
            {
                "severity": "ERROR",
                "code": "MISSING-DESCRIPTION",
                "message": "Frontmatter 'description' must be a non-empty string (required by Pi, OpenCode, Codex, Claude).",
            }
        )

    for key in fm:
        if key in DISCOURAGED_TOP_KEYS:
            errors.append(
                {
                    "severity": "ERROR",
                    "code": "PORT-FRONTMATTER-DRIFT",
                    "message": f"Move top-level key '{key}' under metadata as a quoted string for 17-agent portability.",
                }
            )
        elif key not in ALLOWED_TOP_KEYS:
            warnings.append(f"Non-standard top-level frontmatter key '{key}' may be rejected by strict parsers (OpenCode/Pi).")

    metadata = fm.get("metadata")
    if metadata is not None:
        if not isinstance(metadata, dict):
            errors.append({"severity": "ERROR", "code": "PORT-METADATA-NONMAP", "message": "'metadata' must be a key-value mapping."})
        else:
            for mk, mv in metadata.items():
                if not isinstance(mv, str):
                    errors.append(
                        {
                            "severity": "ERROR",
                            "code": "PORT-METADATA-NONSTRING",
                            "message": f"metadata['{mk}'] must be a string (OpenCode requires map[string]string), got {type(mv).__name__}.",
                        }
                    )

    for sub in skill_dir.iterdir():
        if sub.is_dir() and sub.name in NON_CANONICAL_DIRS:
            errors.append(
                {
                    "severity": "ERROR",
                    "code": "PORT-NONCANONICAL-DIR",
                    "message": f"Non-canonical directory '{sub.name}/' found; place docs in 'references/' or templates in 'assets/'.",
                }
            )

    if INLINE_BANG_RE.search(body):
        errors.append(
            {
                "severity": "ERROR",
                "code": "PORT-VENDOR-LOCK",
                "message": "Inline Claude preprocessing macro (`!...`) breaks portability across the other 16 agents.",
            }
        )

    if USER_PATH_RE.search(body):
        warnings.append("Detected hardcoded user-home path (/Users/... or /home/...); use relative paths instead.")

    for match in MD_LINK_RE.finditer(body):
        target = match.group(1)
        if target.startswith(("http://", "https://", "mailto:")):
            continue
        resolved = (skill_dir / target).resolve()
        if skill_dir.resolve() not in resolved.parents and resolved != skill_dir.resolve():
            errors.append(
                {
                    "severity": "ERROR",
                    "code": "LINK-PATH-TRAVERSAL",
                    "message": f"Relative link escapes skill root: {target}",
                }
            )
        elif not resolved.exists():
            errors.append(
                {
                    "severity": "ERROR",
                    "code": "BROKEN-LINK",
                    "message": f"Broken relative link in SKILL.md: {target}",
                }
            )

    user_invoked = bool(fm.get("disable-model-invocation", False))
    oai_errors, oai_warnings = validate_openai_yaml(skill_dir, name or skill_dir.name, user_invoked)
    errors.extend(oai_errors)
    warnings.extend(oai_warnings)

    for root, dirs, files in os.walk(skill_dir, followlinks=False):
        root_path = Path(root)
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIR_NAMES]
        for fname in files:
            fpath = root_path / fname
            if fpath.is_symlink():
                target_res = fpath.resolve()
                if skill_dir.resolve() not in target_res.parents and target_res != skill_dir.resolve():
                    errors.append(
                        {
                            "severity": "ERROR",
                            "code": "SYMLINK-ESCAPE",
                            "message": f"Symlink points outside skill directory: {fpath.relative_to(skill_dir)}",
                        }
                    )
        if root_path.name == "scripts":
            for fname in files:
                fpath = root_path / fname
                if fpath.suffix in SCRIPT_EXTS and not os.access(fpath, os.X_OK):
                    warnings.append(f"Script lacks executable bit (+x): scripts/{fname}")

    return {
        "status": "PASS" if not errors else "FAIL",
        "skill_name": name or skill_dir.name,
        "line_count": len(content.splitlines()),
        "description_chars": len(desc) if isinstance(desc, str) else 0,
        "errors": errors,
        "warnings": warnings,
    }


def find_sibling_auditor(explicit_path: str | None) -> Path | None:
    if explicit_path:
        p = Path(explicit_path).resolve()
        return p if p.is_file() else None
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "skill-auditor" / "scripts" / "static_audit.py",
        Path.cwd() / "skill-auditor" / "scripts" / "static_audit.py",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def run_external_auditor(static_audit_path: Path, skill_dir: Path) -> dict[str, Any]:
    cmd = [sys.executable, str(static_audit_path), str(skill_dir)]
    if (skill_dir / "SKILL.md").exists() and skill_dir.name == "skill-auditor":
        cmd.append("--self-audit-safe")
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    try:
        parsed = json.loads(proc.stdout)
    except Exception:
        return {
            "status": "ERROR",
            "returncode": proc.returncode,
            "stderr": proc.stderr[-800:],
        }

    coverage = parsed.get("coverage") or {}
    tier_info = parsed.get("tier_classification") or {}
    link_graph = parsed.get("link_graph") or {}
    plat = parsed.get("platform_compatibility") or {}
    univ = plat.get("universal_portability") or {}

    return {
        "status": "COMPLETE" if coverage.get("complete") else "INCOMPLETE",
        "returncode": proc.returncode,
        "detected_tier": tier_info.get("detected_tier"),
        "portability_score_pct": univ.get("portability_score_pct"),
        "ready_warn_fail": (
            f"{univ.get('format_ready_count', 0)}/{univ.get('format_warn_count', 0)}/{univ.get('format_fail_count', 0)}"
        ),
        "broken_links_count": len(link_graph.get("broken_links", [])),
        "orphan_files_count": len(link_graph.get("orphan_files", [])),
        "smells_count": len(parsed.get("static_smells", [])),
        "security_findings_count": len(parsed.get("security_findings", [])),
    }


def package_skill(skill_dir: Path, out_dir: Path) -> dict[str, Any]:
    skill_root = skill_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    archive_path = (out_dir / f"{skill_root.name}.skill").resolve()

    packed_files: list[str] = []
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(skill_root, followlinks=False):
            root_path = Path(root)
            dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIR_NAMES)
            for fname in sorted(files):
                fpath = root_path / fname
                if fpath.resolve() == archive_path:
                    continue
                if is_excluded(fpath, skill_root):
                    continue
                if fpath.is_symlink():
                    target = fpath.resolve()
                    if skill_root not in target.parents and target != skill_root:
                        raise ValueError(f"Refusing to pack symlink escaping root: {fpath}")
                rel = fpath.relative_to(skill_root)
                arcname = f"{skill_root.name}/{rel.as_posix()}"
                info = zipfile.ZipInfo(arcname)
                st = fpath.stat()
                mode = stat.S_IFREG | (st.st_mode & 0o777)
                if fpath.parent.name == "scripts" and fpath.suffix in SCRIPT_EXTS:
                    mode |= 0o111
                info.external_attr = (mode & 0xFFFF) << 16
                zf.writestr(info, fpath.read_bytes())
                packed_files.append(arcname)

    return {
        "archive_path": str(archive_path),
        "archive_bytes": archive_path.stat().st_size,
        "files_packed": len(packed_files),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify 17-agent portability and package a skill into .skill archive.")
    parser.add_argument("skill_dir", help="Path to the skill folder")
    parser.add_argument("--output-dir", default=None, help="Directory for <skill-name>.skill output (defaults to parent dir)")
    parser.add_argument("--verify-only", action="store_true", help="Run verification without writing .skill archive")
    parser.add_argument("--auditor-script", default=None, help="Explicit path to skill-auditor/scripts/static_audit.py")
    parser.add_argument("--no-external-auditor", action="store_true", help="Skip sibling skill-auditor invocation")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    skill_dir = Path(args.skill_dir).resolve()
    preflight = run_builtin_preflight(skill_dir)

    external_report: dict[str, Any] | None = None
    if not args.no_external_auditor and preflight["status"] == "PASS":
        auditor = find_sibling_auditor(args.auditor_script)
        if auditor is not None:
            external_report = run_external_auditor(auditor, skill_dir)

    package_info: dict[str, Any] | None = None
    if preflight["status"] == "PASS" and not args.verify_only:
        out_dir = Path(args.output_dir).resolve() if args.output_dir else skill_dir.parent
        package_info = package_skill(skill_dir, out_dir)

    exit_code = 0 if preflight["status"] == "PASS" else 1
    if external_report and external_report.get("security_findings_count", 0) > 0:
        exit_code = 1

    payload = {
        "preflight": preflight,
        "external_skill_auditor": external_report,
        "package": package_info,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        print(f"Preflight [{preflight.get('skill_name', skill_dir.name)}]: {preflight['status']}")
        for err in preflight["errors"]:
            print(f"  [ERROR] {err['code']}: {err['message']}")
        for warn in preflight["warnings"]:
            print(f"  [WARN]  {warn}")
        if external_report:
            print(
                f"Skill Auditor: status={external_report.get('status')} tier={external_report.get('detected_tier')} "
                f"portability={external_report.get('portability_score_pct')}% ({external_report.get('ready_warn_fail')}) "
                f"smells={external_report.get('smells_count')} security={external_report.get('security_findings_count')}"
            )
        if package_info:
            print(f"Packaged: {package_info['archive_path']} ({package_info['files_packed']} files, {package_info['archive_bytes']} bytes)")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
