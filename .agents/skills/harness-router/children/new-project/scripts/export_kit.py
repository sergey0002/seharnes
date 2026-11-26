#!/usr/bin/env python3
"""Kit export engine: one walker, three modes, no per-adapter copy lists.

The file set comes from `assets/kit.json` through `kit_selection`, so the
dry-run preview and the real transfer always report the same paths. Generated
environment views are rendered in the target by the trusted generator, never
copied from the source. DSH is not part of the kit: the environment is disabled
and its files are absent from `kit.json`.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "lib"))

import kit_adapt
import kit_selection
from transfer_merge import MergeError, merge_agents
from transfer_modes import MODES, resolve
from transfer_plan import _root_path

STATE_DIR = Path(".doc/web/state/transfer")
MARKER = Path(".doc/.rebase-kit.json")
BACKUP_ROOT = Path(".doc/.rebase-backup")
NEXT_STEPS = Path("EXPORT_NEXT_STEPS.md")

MANAGED_ROOTS = (".cursor", ".codex", ".agents", ".kilo", ".opencode", ".omp", ".serena",
                 ".doc/harnes", ".doc/web", ".doc/qa", ".tools/codeception", ".tools/mcp-servers",
                 ".tools/scripts")

PROTECTED_PREFIXES = (".doc/skil_data", ".doc/tasks", ".doc/temp", ".doc/tmp", ".doc/web/state",
                      ".doc/architecture", ".doc/web/config", ".serena/memories", ".git",
                      ".kilo", ".opencode", ".omp")
PROTECTED_NAMES = ("mcp.env", "config.env", ".env")

RUNTIME_DIRS = (".tools/mcp-servers/php-toolchain/node_modules",
                ".cursor/tools/vendor", ".codex/tools/vendor",
                ".tools/codeception/vendor")
RUNTIME_FILES = (".tools/mcp-servers/php-toolchain/package.json",
                 ".tools/mcp-servers/php-toolchain/package-lock.json",
                 ".cursor/tools/composer.json", ".cursor/tools/composer.lock",
                 ".codex/tools/composer.json", ".codex/tools/composer.lock",
                 ".tools/codeception/composer.lock")

CORE_ONLY_MUST = (".doc/web/router.php",)
BASE_MUST = ("AGENTS.md", ".cursor/mcp.json", ".doc/harnes/doc_rules.md",
             ".doc/harnes/state/canon-paths.yaml",
             ".agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml",
             ".agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml",
             ".agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh",
             ".agents/skills/harness-router/children/mirror/SKILL.md",
             ".serena/project.yml", "EXPORT_NEXT_STEPS.md")
ENV_MUST = {
    "codex": (".codex/config.toml", ".codex/rules-index.md"),
    "kilo": (".kilo/kilo.jsonc", ".kilo/rules-index.md"),
    "opencode": ("opencode.json", ".opencode/rules-index.md"),
    "omp": (".omp/mcp.json",),
}
FORBIDDEN = (".doc/dump.sql", ".cursor/tools/codeprism-ai/venv", ".doc/qa/tmp-runs",
             ".agents/skills/login-as-user", "DSH-RULES.md", ".dsh")

NEXT_STEPS_TEXT = """# Export next steps

Target: `{target}`
Profile: `{profile}`
Mode: `{mode}`

1. Fill secrets: `.cursor/mcp.env` and `.codex/mcp.env` (created from the example).
2. Verify the harness: `python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py doctor`.
3. Re-run view sync after any canon edit:
   `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh --local-only`
4. Configure MCP, ports and indexes:
   `python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --check`
5. Fill `.doc/architecture/index.md` and project documentation with the project-doc skill.
6. Remove `EXPORT_NEXT_STEPS.md` when the target is configured.
"""


class ExportError(ValueError):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(message)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_receipt(target: Path) -> dict[str, list[str]]:
    path = target / MARKER
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    files = data.get("files") if isinstance(data, dict) else None
    if not isinstance(files, dict):
        return {}
    return {key: value for key, value in files.items()
            if isinstance(key, str) and isinstance(value, list) and len(value) == 2}


def _installed_map(target: Path, files: list[str], source_digests: dict[str, str],
                   local_paths: set[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in files:
        full = target / path
        if full.is_file():
            source_sha = None if path in local_paths else source_digests.get(path)
            result[path] = [source_sha, _sha256(full)]
    return result


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


def _validate(source: Path, target: Path) -> tuple[Path, Path]:
    source = _root_path(source, must_exist=True)
    target = _root_path(target, must_exist=False)
    if source == target:
        raise ExportError("invalid_target", "source and target must differ")
    if str(source).startswith(str(target) + os.sep) or str(target).startswith(str(source) + os.sep):
        raise ExportError("invalid_target", "source and target must not overlap")
    return source, target


def _preflight_core_policy(source: Path) -> None:
    """Validate source policy declarations with the installed trusted reader."""
    scripts = HERE.parents[2] / "harness-core/scripts"
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    try:
        from canon_paths import load_preliminary_policies
    except ImportError as error:
        raise ExportError("POLICY_READER_MISSING", f"trusted policy reader is missing: {error}") from error
    load_preliminary_policies(Path(source))


def _extra_files(source: Path, profile: str, runtime_deps: bool) -> list[str]:
    result: list[str] = []
    if runtime_deps:
        for relative in RUNTIME_DIRS:
            base = source / relative
            if base.is_dir():
                for path in base.rglob("*"):
                    if path.is_file() and "__pycache__" not in path.parts:
                        result.append(path.relative_to(source).as_posix())
        for relative in RUNTIME_FILES:
            if (source / relative).is_file():
                result.append(relative)
    examples = source / ".doc/skil_data"
    if examples.is_dir():
        for path in examples.rglob("*"):
            if path.is_file() and ".example." in path.name:
                result.append(path.relative_to(source).as_posix())
    return result


def _target_files(target: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not target.is_dir():
        return result
    for root in MANAGED_ROOTS:
        base = target / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc" or ".pytest_cache" in path.parts:
                continue
            relative = path.relative_to(target).as_posix()
            result[relative] = _sha256(path)
    return result


def _generated(relative: str, prefixes: tuple[str, ...]) -> bool:
    return any(relative == item or relative.startswith(item.rstrip("/") + "/") for item in prefixes)


def _protected(relative: str) -> bool:
    if relative.rsplit("/", 1)[-1] in PROTECTED_NAMES:
        return True
    return any(relative == item or relative.startswith(item.rstrip("/") + "/")
               for item in PROTECTED_PREFIXES)


def _merge_mcp_bytes(current: bytes, incoming: bytes) -> bytes:
    """Keep target-only servers, let the canon win on shared names."""
    try:
        target_doc = json.loads(current.decode("utf-8"))
        source_doc = json.loads(incoming.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise MergeError("invalid MCP JSON") from error
    if not isinstance(target_doc, dict) or not isinstance(source_doc, dict):
        raise MergeError("MCP JSON must be an object")
    merged = dict(source_doc)
    merged_servers = dict(merged.get("mcpServers") or {})
    for name, server in (target_doc.get("mcpServers") or {}).items():
        merged_servers.setdefault(name, server)
    merged["mcpServers"] = merged_servers
    for key, value in target_doc.items():
        merged.setdefault(key, value)
    return (json.dumps(merged, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _backup(target: Path, backup_dir: Path, relative: str) -> None:
    source = target / relative
    if not source.is_file():
        return
    destination = backup_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _copy_file(source: Path, target: Path, relative: str) -> None:
    destination = target / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / relative, destination)


def _scaffold(target: Path, project_name: str) -> None:
    for relative in (".doc/architecture/_map", ".doc/tasks/_map", ".doc/qa/reports",
                     ".doc/skil_data/yadisk-screenshot/imd"):
        (target / relative).mkdir(parents=True, exist_ok=True)
    index = target / ".doc/architecture/index.md"
    if not index.is_file():
        _write_text(index, f"""# Architecture index

<!-- meta
type: index
status: draft
updated: {datetime.now():%Y-%m-%d}
related: [../harnes/doc_rules.md]
tags: [architecture, index]
-->

---

## Суть

Оглавление архитектуры проекта `{project_name}`. Заполнить скилом project-doc.
""")


def _create_mcp_env(target: Path, project_name: str) -> None:
    for relative in (".cursor/mcp.env", ".codex/mcp.env"):
        example = target / (relative + ".example")
        destination = target / relative
        if destination.is_file() or not example.is_file():
            continue
        text = example.read_text(encoding="utf-8")
        text = re.sub(r"(?m)^#?\s*GRAPHITI_GROUP_ID=.*$",
                      f"GRAPHITI_GROUP_ID={project_name}", text)
        if "GRAPHITI_GROUP_ID=" not in text:
            text += f"\nGRAPHITI_GROUP_ID={project_name}\n"
        _write_text(destination, text)


def _render(target: Path) -> dict:
    """Deploy enabled environment views and write the parity manifest."""
    scripts = target / ".agents/skills/harness-router/children/environment-sync/scripts"
    sync = scripts / "sync-agent-views.sh"
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["HARNESS_SYNC_NO_PROMPT"] = "1"
    bash = shutil.which("bash")
    if sync.is_file() and bash:
        result = subprocess.run([bash, str(sync), "--local-only"], cwd=target, env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=900)
        return {"status": "synced" if result.returncode == 0 else "sync_failed",
                "returncode": result.returncode,
                "output": result.stdout.decode("utf-8", "replace")[-2000:]}
    renderer = scripts / "render_agent_views.py"
    if not renderer.is_file():
        return {"status": "skipped", "reason": "renderer is missing"}
    result = subprocess.run([sys.executable, str(renderer), "--root", str(target)],
                            cwd=target, env=env, stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600)
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {"status": "failed", "stderr": result.stderr.decode("utf-8", "replace")[-2000:]}
    payload["returncode"] = result.returncode
    return payload


def _must_check(target: Path, source: Path, profile: str, runtime_deps: bool) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    forbidden: list[str] = []
    required = list(BASE_MUST)
    if profile == "core":
        required.extend(CORE_ONLY_MUST)
    for env in kit_selection.enabled_environments(target):
        required.extend(ENV_MUST.get(env, ()))
    if runtime_deps:
        required.extend((
            ".tools/mcp-servers/php-toolchain/node_modules/@modelcontextprotocol/sdk/package.json",
            ".cursor/tools/vendor/bin/phpstan",
        ))
        if profile != "core":
            required.append(".tools/codeception/vendor/autoload.php")
    for relative in required:
        if not (target / relative).exists():
            missing.append(relative)
    for relative in FORBIDDEN:
        if (target / relative).exists():
            forbidden.append(relative)
    if (target / ".doc/tasks").is_dir():
        for child in (target / ".doc/tasks").iterdir():
            if child.is_dir() and child.name.isdigit():
                forbidden.append(f".doc/tasks/{child.name}")
                break
    source_forms = {str(source), str(source).replace("\\", "/"), str(source).replace("/", "\\")}
    for relative in ("AGENTS.md", ".cursor/mcp.json", ".codex/config.toml", ".kilo/kilo.jsonc",
                     "opencode.json", "mcp.index.md"):
        path = target / relative
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if any(form and form in text for form in source_forms):
            forbidden.append(f"{relative}: contains source path")
    return missing, forbidden


def _report(target: Path, source: Path, profile: str, mode: str, counts: dict,
            preserved: list[str], deleted: list[str], adapt: kit_adapt.AdaptReport,
            missing: list[str], forbidden: list[str]) -> None:
    conflicts = {
        "schema": 1, "mode": mode, "timestamp": datetime.now().strftime("%Y%m%d-%H%M%S"),
        "counts": counts, "deleted": deleted,
        "missing": missing, "forbidden": forbidden,
    }
    _write_text(target / ".doc/.rebase-conflicts.json",
                json.dumps(conflicts, indent=2, ensure_ascii=False) + "\n")
    _write_text(target / ".doc/.rebase-preserved.txt",
                "# Files in Target that are absent from the kit. Export keeps them.\n\n"
                + ("\n".join(preserved) + "\n" if preserved else "(none)\n"))
    lines = [
        "# Kit export report", "",
        f"Target: `{target}`", f"Source: `{source}`", f"Profile: `{profile}`",
        f"Mode: `{mode}`", f"Date: {datetime.now().isoformat(timespec='seconds')}", "",
        "## Counts", "",
        f"Added: {counts.get('added', 0)}",
        f"Overwritten: {counts.get('overwritten', 0)}",
        f"Unchanged: {counts.get('same', 0)}",
        f"Deleted (mirror): {counts.get('deleted', 0)}",
        f"Kept outside kit: {counts.get('preserved', 0)}", "",
        "## Checks", "",
        f"Missing: {len(missing)}", f"Forbidden: {len(forbidden)}",
        f"Rewritten files: {adapt.files_rewritten}",
        f"Document links outside kit: {len(adapt.doc_links)}", "",
    ]
    if adapt.warnings:
        lines += ["## Warnings", ""] + [f"- {item}" for item in adapt.warnings] + [""]
    _write_text(target / ".doc/.rebase-report.md", "\n".join(lines))
    _write_text(target / ".doc/.rebase-report.json",
                json.dumps({"schema": 1, "target": str(target), "source": str(source),
                            "profile": profile, "mode": mode, "counts": counts,
                            "missing": missing, "forbidden": forbidden,
                            "warnings": adapt.warnings,
                            "doc_links": adapt.doc_links}, indent=2, ensure_ascii=False) + "\n")


def _matches(relative: str, patterns: tuple[str, ...]) -> bool:
    return any(relative == item or relative.startswith(item.rstrip("/") + "/")
               for item in patterns)


def export(source: Path, target: Path, profile: str, mode: str, *,
           project_name: str = "", runtime_deps: bool = True, skip_tools: bool = False,
           exclude: tuple[str, ...] = (), keep: tuple[str, ...] = (),
           dry_run: bool = False) -> dict:
    if profile not in ("core", "developer", "project"):
        raise ExportError("invalid_profile", f"unknown profile: {profile}")
    if mode not in MODES:
        raise ExportError("invalid_mode", f"unknown mode: {mode}")
    source, target = _validate(Path(source), Path(target))
    if profile == "core":
        _preflight_core_policy(source)
    selected, generated = kit_selection.select(source, profile)
    if skip_tools:
        selected = [path for path in selected if not path.startswith(".tools/")]
        runtime_deps = False
    files = sorted(set(selected) | set(_extra_files(source, profile, runtime_deps)))
    if exclude:
        files = [path for path in files if not _matches(path, exclude)]
    existing = _target_files(target)
    for path in files:
        if path not in existing and (target / path).is_file():
            existing[path] = _sha256(target / path)
    receipt = _load_receipt(target)

    counts = {"added": 0, "overwritten": 0, "same": 0, "deleted": 0, "preserved": 0}
    source_set = set(files)
    generated_prefixes = kit_selection.generated_prefixes(source)
    source_digests = {path: _sha256(source / path) for path in files}
    plan = {"files": [
        {"path": path,
         "target": {"sha256": existing[path], "mode": 0o644} if path in existing else None,
         "incoming": {"sha256": source_digests[path], "mode": 0o644},
         "proposal": {"requires_review": path in existing and existing[path] != source_digests[path],
                      "action": "review" if path in existing else "add"}}
        for path in files
    ] + [
        {"path": path, "target": {"sha256": existing[path], "mode": 0o644}, "incoming": None,
         "proposal": {"requires_review": False, "action": "none"}}
        for path in sorted(existing)
        if path not in source_set and not _protected(path) and not _generated(path, generated_prefixes)
    ]}
    decisions, mode_report = resolve(plan, mode)
    deletes = mode_report.deletes if mode == "mirror" else []
    preserved = sorted(path for path in existing if path not in source_set
                       and not _protected(path) and not _generated(path, generated_prefixes))
    counts["preserved"] = len(preserved)

    if dry_run:
        for path in files:
            recorded = receipt.get(path)
            unmodified = bool(recorded) and recorded[1] == existing.get(path)
            if path not in existing:
                counts["added"] += 1
            elif existing[path] == source_digests[path]:
                counts["same"] += 1
            elif recorded and recorded[0] == source_digests[path] and unmodified:
                counts["same"] += 1
            elif mode == "install" and not unmodified:
                counts["preserved"] += 1
            else:
                counts["overwritten"] += 1
        counts["deleted"] = len(deletes)
        return {"status": "dry-run", "profile": profile, "mode": mode, "target": str(target),
                "counts": counts, "generated": len(generated),
                "overwritten": [p for p in files if p in existing and existing[p] != source_digests[p]][:30],
                "added": [p for p in files if p not in existing][:30],
                "kept": preserved[:30], "deleted": deletes[:30],
                "warnings": mode_report.warnings}

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = target / BACKUP_ROOT / stamp
    target.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    kept_local: list[str] = []
    for path in files:
        destination = target / path
        source_file = source / path
        src_sha = source_digests[path]
        recorded = receipt.get(path)
        if destination.is_file():
            current_sha = existing.get(path)
            if recorded and recorded[0] == src_sha and current_sha == recorded[1]:
                counts["same"] += 1
                continue
            if current_sha == src_sha:
                counts["same"] += 1
                continue
            if path in (".cursor/mcp.json", "AGENTS.md"):
                try:
                    incoming_bytes = source_file.read_bytes()
                    if path == ".cursor/mcp.json":
                        merged = _merge_mcp_bytes(destination.read_bytes(), incoming_bytes)
                    else:
                        merged, _ = merge_agents(destination.read_bytes(), incoming_bytes)
                except MergeError as error:
                    mode_report.warnings.append(f"merge refused, file kept: {path}: {error}")
                    kept_local.append(path)
                    continue
                current_bytes = destination.read_bytes()
                if merged == current_bytes:
                    counts["same"] += 1
                    continue
                _backup(target, backup_dir, path)
                destination.write_bytes(merged)
                counts["overwritten"] += 1
                written.append(path)
                continue
            if mode == "install":
                if recorded and current_sha == recorded[1]:
                    _backup(target, backup_dir, path)
                    _copy_file(source, target, path)
                    counts["overwritten"] += 1
                    written.append(path)
                    continue
                kept_local.append(path)
                mode_report.warnings.append(f"existing file kept as local: {path}")
                continue
            _backup(target, backup_dir, path)
            counts["overwritten"] += 1
        else:
            counts["added"] += 1
        _copy_file(source, target, path)
        written.append(path)

    deleted: list[str] = []
    if mode == "mirror":
        for path in deletes:
            if _protected(path) or path in set(files) or (keep and _matches(path, keep)):
                continue
            _backup(target, backup_dir, path)
            (target / path).unlink(missing_ok=True)
            deleted.append(path)
        counts["deleted"] = len(deleted)
    preserved = sorted(set(preserved) | set(kept_local))
    preserved = [path for path in preserved if path not in set(deleted)]
    counts["preserved"] = len(preserved)

    _scaffold(target, project_name or target.name)
    _create_mcp_env(target, project_name or target.name)

    adapt = kit_adapt.AdaptReport()
    code_paths = [path for path in files if not path.startswith(".doc/")]
    kit_adapt.rewrite_source_paths(target, source, target, code_paths, adapt)
    kit_adapt.scrub_mcp_config(target, adapt)
    kit_adapt.prune_missing_mcp(target, adapt)
    kit_adapt.disable_mcp_servers(target, adapt)
    kit_adapt.set_serena_project_name(target, project_name or target.name, adapt)
    kit_adapt.prune_registry(target, adapt)
    kit_adapt.prune_skill_manifests(target, adapt)
    kit_adapt.normalize_doc_links(target, files, adapt)
    kit_adapt.write_doc_link_report(target, adapt)

    render = _render(target)
    if render.get("status") not in ("passed", "rendered", "synced"):
        adapt.warnings.append(f"environment sync failed: {render.get('status')}")

    _write_text(target / NEXT_STEPS,
                NEXT_STEPS_TEXT.format(target=target, profile=profile, mode=mode))
    missing, forbidden = _must_check(target, source, profile, runtime_deps)
    _report(target, source, profile, mode, counts, preserved, deleted, adapt, missing, forbidden)

    status = "passed" if not missing and not forbidden else "failed"
    installed = _installed_map(target, files, source_digests, set(kept_local))
    _write_text(target / MARKER, json.dumps({
        "schema": 1, "status": status, "mode": mode, "source": str(source),
        "profile": profile, "project_name": project_name or target.name,
        "installed_at": datetime.now().isoformat(timespec="seconds"),
        "conflicts": ".doc/.rebase-conflicts.json",
        "report": ".doc/.rebase-report.md",
        "files": installed,
    }, indent=2, ensure_ascii=False) + "\n")
    return {"status": status, "profile": profile, "mode": mode, "target": str(target),
            "counts": counts, "missing": missing, "forbidden": forbidden,
            "warnings": adapt.warnings, "render": render.get("status"),
            "written": len(written), "deleted": len(deleted)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("."))
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--profile", choices=("core", "developer", "project"), default="developer")
    parser.add_argument("--mode", choices=MODES, default="install")
    parser.add_argument("--project-name", default="")
    parser.add_argument("--skip-runtime-deps", action="store_true")
    parser.add_argument("--skip-tools", action="store_true")
    parser.add_argument("--exclude", action="append", default=[],
                        help="relative path or prefix to leave out; repeatable")
    parser.add_argument("--keep", action="append", default=[],
                        help="relative path or prefix owned by the target; repeatable")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = export(args.source, args.target, args.profile, args.mode,
                        project_name=args.project_name,
                        runtime_deps=not args.skip_runtime_deps,
                        skip_tools=args.skip_tools,
                        exclude=tuple(args.exclude), keep=tuple(args.keep),
                        dry_run=args.dry_run)
    except (ExportError, ValueError, OSError) as error:
        code = getattr(error, "code", "export_failed")
        print(json.dumps({"status": "failed", "code": code, "reason": str(error)},
                         ensure_ascii=False))
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if args.dry_run:
        return 0
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
