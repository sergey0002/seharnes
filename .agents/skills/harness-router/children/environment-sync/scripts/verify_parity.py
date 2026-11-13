#!/usr/bin/env python3
"""Verify generated agent views against the Cursor canonical source.

Compares whole directory trees (skills, scripts) byte-for-byte after line-ending
normalization, and rules by document body with the Cursor frontmatter stripped
(Codex and Kilo mirror `.mdc` as plain `.md`).

`--check` writes nothing and fails when the stored manifest is missing, failed
or stale against the current canon. Use it as an external gate (pre-commit, CI)
to catch "canon edited, sync not run". The sync itself always rewrites the
manifest, so a freshness check placed right after it proves nothing.
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

import rule_model

IGNORED_RELATIVE_NAMES = {"ADAPTERS.local.md"}

# Binary payloads are compared raw: normalizing them would corrupt the hash
# source and hide real drift.
BINARY_SUFFIXES = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".woff", ".woff2",
    ".ttf", ".eot", ".zip", ".pyc", ".pdf",
}

RULE_SUFFIXES = {".md", ".mdc"}

# Same contract as the Codex/Kilo generators: the leading YAML block is Cursor
# metadata and is intentionally absent from the mirror.
FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.S)


def _normalized_bytes(data: bytes) -> bytes:
    return data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _read_bytes_normalized(path: Path) -> bytes:
    """Read file bytes with CRLF normalized to LF for text comparison.

    Parity must not fail on line-ending-only drift between canon and views
    (editors on different OS). Binary extensions are compared raw.
    """
    data = path.read_bytes()
    if path.suffix.lower() in BINARY_SUFFIXES:
        return data
    return _normalized_bytes(data)


def _relative_posix(path: Path, root: Path) -> str:
    """Relative key with forward slashes so the hash is OS independent."""
    return path.relative_to(root).as_posix()


def manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not root.is_dir():
        return result
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.endswith(".pyc") or path.name in IGNORED_RELATIVE_NAMES:
            continue
        # Dotted paths are local state (generated data, caches), not canon text.
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        result[_relative_posix(path, root)] = hashlib.sha256(_read_bytes_normalized(path)).hexdigest()
    return result


# Canon trees that participate in freshness. Skills alone are not enough: a rule
# or MCP edit used to leave the manifest "fresh" while the mirrors drifted.
CANON_PARTS = ("skills", "rules", "mcp.json", "mcp.env.example")


def resolve_canon_roots(
    canonical: Path,
    rules_canonical: Path | None = None,
    mcp_canonical: Path | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Resolves actual canonical roots for skills, rules, mcp.json and mcp.env.example."""
    if canonical.name == "skills" and canonical.parent.name == ".agents":
        repo_root = canonical.parent.parent
    elif canonical.name == ".cursor" or canonical.parent.name == ".cursor":
        repo_root = canonical.parent if canonical.name == ".cursor" else canonical.parent.parent
    else:
        repo_root = canonical.parent

    skills_path = canonical if canonical.name == "skills" else (repo_root / ".agents" / "skills")

    if rules_canonical is not None:
        rules_path = rules_canonical
    elif (repo_root / ".cursor" / "rules").is_dir():
        rules_path = repo_root / ".cursor" / "rules"
    else:
        rules_path = canonical.parent / "rules" if canonical.name == "skills" else canonical / "rules"

    if mcp_canonical is not None:
        mcp_path = mcp_canonical
    elif (repo_root / ".cursor" / "mcp.json").is_file():
        mcp_path = repo_root / ".cursor" / "mcp.json"
    else:
        mcp_path = canonical.parent / "mcp.json" if canonical.name == "skills" else canonical / "mcp.json"

    env_path = repo_root / ".cursor" / "mcp.env.example"
    if not env_path.is_file():
        env_path = canonical.parent / "mcp.env.example" if canonical.name == "skills" else canonical / "mcp.env.example"

    return skills_path, rules_path, mcp_path, env_path


def canon_hash(
    canonical: Path,
    rules_canonical: Path | None = None,
    mcp_canonical: Path | None = None,
) -> str:
    """Single hash over the whole canon manifest (for staleness checks)."""
    skills_path, rules_path, mcp_path, env_path = resolve_canon_roots(canonical, rules_canonical, mcp_canonical)
    payload: dict[str, dict[str, str]] = {}
    if skills_path.is_dir():
        payload["skills"] = manifest(skills_path)
    if rules_path.is_dir():
        payload["rules"] = manifest(rules_path)
    if mcp_path.is_file():
        payload["mcp.json"] = {mcp_path.name: hashlib.sha256(_read_bytes_normalized(mcp_path)).hexdigest()}
    if env_path.is_file():
        payload["mcp.env.example"] = {env_path.name: hashlib.sha256(_read_bytes_normalized(env_path)).hexdigest()}
    packed = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(packed).hexdigest()


JSONC_COMMENT_RE = re.compile(r'(?m)^\s*//.*$')
TOML_SECTION_RE = re.compile(r'^\[mcp_servers\.([A-Za-z0-9_-]+)\]\s*$', re.MULTILINE)


def mcp_server_names(path: Path) -> list[str]:
    """Server names from any MCP view format, or [] when unreadable.

    Handles three shapes that actually exist in this repo: Cursor JSON
    (`mcpServers`), Kilo JSONC (`mcp`, `//` comments), Codex TOML
    (`[mcp_servers.<name>]`). A malformed or absent file yields [] so callers
    can report drift instead of crashing.
    """
    if not path.is_file():
        return []
    text = _read_bytes_normalized(path).decode("utf-8", "surrogateescape")
    if path.suffix.lower() == ".toml":
        # Sub-tables such as [mcp_servers.mysql.env] must not count as servers:
        # the character class above already excludes dotted names.
        return sorted(set(TOML_SECTION_RE.findall(text)))
    try:
        data = json.loads(JSONC_COMMENT_RE.sub("", text))
    except json.JSONDecodeError:
        return []
    servers = data.get("mcpServers") or data.get("mcp") or {}
    return sorted(servers) if isinstance(servers, dict) else []


def body_hash(path: Path) -> str:
    """Hash of the document body with Cursor frontmatter and BOM removed."""
    text = _read_bytes_normalized(path).decode("utf-8", "surrogateescape")
    if text.startswith("\ufeff"):
        text = text[1:]
    text = FRONTMATTER_RE.sub("", text, count=1)
    return hashlib.sha256(text.encode("utf-8", "surrogateescape")).hexdigest()


def compare(canonical: Path, view: Path, allow_extra: bool = False) -> list[str]:
    expected = manifest(canonical)
    actual = manifest(view)
    errors = []
    for relative, digest in expected.items():
        if relative not in actual:
            errors.append(f"{view}: missing {relative}")
        elif actual[relative] != digest:
            errors.append(f"{view}: mismatch {relative}")
    if not allow_extra:
        for relative in sorted(set(actual) - set(expected)):
            errors.append(f"{view}: extra {relative}")
    return errors


def _rule_files(directory: Path, canonical: bool = False) -> dict[str, Path]:
    """Map canonical rule key to file; nested and flat Antigravity views match."""
    files: dict[str, Path] = {}
    if not directory.is_dir():
        return files
    for path in sorted(directory.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in RULE_SUFFIXES:
            continue
        key = path.relative_to(directory).with_suffix("").as_posix()
        if not canonical and "/" not in key and key.startswith("mcp-"):
            key = "mcp/" + key[4:]
        files[key] = path
    return files


def compare_rules(canonical: Path, view: Path, allow_extra: bool = False) -> list[str]:
    """Compare rule sets by canonical key and body, tolerating `.mdc` to `.md` mirroring."""
    expected = _rule_files(canonical, canonical=True)
    actual = _rule_files(view)
    errors = []
    for stem, path in expected.items():
        if stem not in actual:
            errors.append(f"{view}: rules missing {stem}")
        else:
            expected_body = rule_model.rebase_links(
                FRONTMATTER_RE.sub("", _read_bytes_normalized(path).decode("utf-8"), count=1), path, actual[stem])
            actual_body = FRONTMATTER_RE.sub("", _read_bytes_normalized(actual[stem]).decode("utf-8"), count=1)
            expected_body = rule_model.rebase_links(expected_body, actual[stem], actual[stem])
            actual_body = rule_model.rebase_links(actual_body, actual[stem], actual[stem])
            if expected_body != actual_body:
                errors.append(f"{view}: rules mismatch {stem}")
    if not allow_extra:
        for stem in sorted(set(actual) - set(expected)):
            errors.append(f"{view}: rules extra {stem}")
    return errors


def _write_atomic(path: Path, payload: str) -> None:
    """Write the manifest atomically so a crash cannot leave half JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
        os.replace(temp_name, path)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def check_freshness(
    manifest_path: Path,
    canonical: Path,
    rules_canonical: Path | None = None,
    mcp_canonical: Path | None = None,
) -> list[str]:
    """Read-only gate: stored manifest must exist, pass, and match current canon."""
    if not manifest_path.is_file():
        return [f"manifest missing: {manifest_path}"]
    try:
        stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [f"manifest unreadable: {manifest_path}: {error}"]

    errors: list[str] = []
    if stored.get("status") != "passed":
        errors.append(f"manifest status is {stored.get('status')!r}, expected 'passed'")
    if stored.get("canon_hash") != canon_hash(canonical, rules_canonical, mcp_canonical):
        errors.append("manifest is stale: canon changed after the last sync")
    mcp = stored.get("mcp") or {}
    for message in mcp.get("errors", []):
        errors.append(f"mcp drift recorded in manifest: {message}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--canonical", required=True, type=Path, help="canonical tree, e.g. .agents/skills")
    parser.add_argument("--view", action="append", default=[], type=Path, help="mirror tree to compare (repeatable)")
    parser.add_argument("--manifest", type=Path, help="write the parity report here")
    parser.add_argument("--rules-canonical", type=Path, help="canonical rules directory, e.g. .cursor/rules")
    parser.add_argument("--rules-view", action="append", default=[], type=Path, help="mirror rules directory (repeatable)")
    parser.add_argument("--check", action="store_true", help="verify --manifest freshness without writing anything")
    parser.add_argument(
        "--allow-extra",
        action="store_true",
        help="treat files present only in a view as local additions, not drift",
    )
    parser.add_argument("--mcp-canonical", type=Path, help="canonical MCP json, e.g. .cursor/mcp.json")
    parser.add_argument("--mcp-view", action="append", default=[], type=Path, help="mirror MCP json (repeatable)")
    args = parser.parse_args()

    if args.check:
        if args.manifest is None:
            parser.error("--check requires --manifest")
        errors = check_freshness(args.manifest, args.canonical, args.rules_canonical, args.mcp_canonical)
        view_drift_errors = []
        if args.view:
            for view_path in args.view:
                if not view_path.exists():
                    view_drift_errors.append(f"missing view: {view_path}")
                elif view_path.is_dir():
                    diffs = compare(args.canonical, view_path, args.allow_extra)
                    if diffs:
                        view_drift_errors.append(f"view drift: {view_path} has {len(diffs)} differences")
        if args.rules_view:
            _, rules_p, _, _ = resolve_canon_roots(args.canonical, args.rules_canonical, args.mcp_canonical)
            for r_view in args.rules_view:
                if not r_view.exists():
                    view_drift_errors.append(f"rules missing view: {r_view}")
                elif r_view.is_dir():
                    diffs = compare_rules(rules_p, r_view, args.allow_extra)
                    if diffs:
                        view_drift_errors.append(f"rules view drift: {r_view} has {len(diffs)} differences")
        all_errors = errors + view_drift_errors
        report = {
            "mode": "check",
            "manifest": str(args.manifest),
            "canonical": str(args.canonical),
            "errors": all_errors,
            "status": "passed" if not all_errors else "failed",
            "canon_hash": canon_hash(args.canonical, args.rules_canonical, args.mcp_canonical),
        }
        print(json.dumps(report, indent=2))
        return 0 if not all_errors else 1

    if not args.canonical.is_dir():
        parser.error(f"--canonical is not a directory: {args.canonical}")
    if not args.view:
        parser.error("at least one --view is required unless --check is used")
    if args.rules_view and args.rules_canonical is None:
        parser.error("--rules-view requires --rules-canonical")
    if args.rules_canonical is not None and not args.rules_canonical.is_dir():
        parser.error(f"--rules-canonical is not a directory: {args.rules_canonical}")

    errors: list[str] = []
    for view in args.view:
        if view.exists():
            errors.extend(compare(args.canonical, view, args.allow_extra))
        else:
            errors.append(f"{view}: missing view")
    for view in args.rules_view:
        if view.exists():
            errors.extend(compare_rules(args.rules_canonical, view, args.allow_extra))
        else:
            errors.append(f"{view}: rules missing view")

    report = {
        "canonical": str(args.canonical),
        "views": [str(view) for view in args.view],
        "errors": errors,
        "status": "passed" if not errors else "failed",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "canon_hash": canon_hash(args.canonical, args.rules_canonical, args.mcp_canonical),
    }
    if args.rules_canonical is not None:
        report["rules_canonical"] = str(args.rules_canonical)
        report["rules_views"] = [str(view) for view in args.rules_view]
    if args.mcp_canonical is not None:
        canon_servers = mcp_server_names(args.mcp_canonical)
        report["mcp"] = {"canonical": str(args.mcp_canonical), "servers": len(canon_servers), "names": canon_servers}
    if args.mcp_view:
        view_errors: list[str] = []
        for view in args.mcp_view:
            names = mcp_server_names(view)
            if not names:
                view_errors.append(f"{view}: mcp view missing or unreadable")
                continue
            if args.mcp_canonical is not None:
                missing = sorted(set(mcp_server_names(args.mcp_canonical)) - set(names))
                if missing:
                    view_errors.append(f"{view}: mcp servers missing {', '.join(missing)}")
        report.setdefault("mcp", {})["views"] = [str(view) for view in args.mcp_view]
        report["mcp"]["errors"] = view_errors
        errors.extend(view_errors)
        report["status"] = "passed" if not errors else "failed"
    if args.manifest:
        _write_atomic(args.manifest, json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
