#!/usr/bin/env python3
"""Review local skills, rules and MCP after a harness migration.

Reads the conflict backup written by rebase_project.ps1, scans the target
project for local components and proposes safe installation steps.

Usage:
  python3 review_migration.py --root . --json
  python3 review_migration.py --root . --interactive
  python3 review_migration.py --root . --apply --yes
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

CONFLICT_REPORT = ".doc/.rebase-conflicts.json"
KIT_MARKER = ".doc/.rebase-kit.json"
MCP_BACKUP = ".doc/.rebase-mcp-backup/cursor.mcp.json"
MCP_CURRENT = ".cursor/mcp.json"
SCANNER = ".agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py"
ADD_SKILL = ".agents/skills/harness-router/children/add-skill/scripts/add_skill.py"
SYNC = ".agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh"
RULE_DIRS = (".agents/rules", ".codex/rules", ".qoder/rules", ".qwen/rules")


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def human_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def directory_stats(path: Path) -> dict:
    files = 0
    size = 0
    if path.is_dir():
        for item in path.rglob("*"):
            if item.is_file():
                files += 1
                try:
                    size += item.stat().st_size
                except OSError:
                    pass
    return {"exists": path.is_dir(), "files": files, "bytes": size, "size": human_size(size)}


def safe_inside(root: Path, path: Path) -> bool:
    try:
        resolved_root = root.resolve()
        resolved_path = path.resolve()
    except OSError:
        return False
    return str(resolved_path).startswith(str(resolved_root) + str(Path("/")))


def backup_summary(root: Path, conflicts: dict) -> dict:
    backup_rel = str(conflicts.get("backup_dir") or "")
    backup_dir = root / backup_rel if backup_rel else root / ".doc" / ".rebase-backup"
    backup_ok = bool(backup_rel) and safe_inside(root / ".doc" / ".rebase-backup", backup_dir)
    backup = directory_stats(backup_dir) if backup_ok else {"exists": False, "files": 0, "bytes": 0, "size": "0 B"}
    mcp_dir = root / ".doc" / ".rebase-mcp-backup"
    mcp = directory_stats(mcp_dir)
    entries = conflicts.get("backup_files") or conflicts.get("overwritten") or []
    categories = Counter(item.get("category", "other") for item in entries)
    return {
        "dir": backup_rel,
        "exists": backup["exists"],
        "files": backup["files"],
        "bytes": backup["bytes"],
        "size": backup["size"],
        "by_category": dict(sorted(categories.items())),
        "mcp_dir": ".doc/.rebase-mcp-backup" if mcp["exists"] else "",
        "mcp_files": mcp["files"],
        "mcp_bytes": mcp["bytes"],
        "mcp_size": mcp["size"],
        "removed": bool(conflicts.get("backup_removed")),
        "removed_at": conflicts.get("backup_removed_at", ""),
    }


def remove_backup(root: Path, report: dict, assume_yes: bool) -> bool:
    conflicts = read_json(root / CONFLICT_REPORT) or {}
    paths = []
    backup_rel = str(conflicts.get("backup_dir") or "")
    if backup_rel:
        candidate = root / backup_rel
        if safe_inside(root / ".doc" / ".rebase-backup", candidate) and candidate.is_dir():
            paths.append(candidate)
    mcp_dir = root / ".doc" / ".rebase-mcp-backup"
    if safe_inside(root / ".doc", mcp_dir) and mcp_dir.is_dir():
        paths.append(mcp_dir)
    if not paths:
        report["backup_removed"] = []
        return True
    if not assume_yes:
        if not sys.stdin.isatty():
            report["errors"].append("backup removal needs --yes in a non-interactive run")
            return False
        answer = input("Удалить бэкап миграции? [y/N] ").strip().lower()
        if answer not in {"y", "yes", "д", "да"}:
            report["backup_removed"] = []
            return True
    removed = []
    for path in paths:
        shutil.rmtree(path)
        removed.append(path.relative_to(root).as_posix())
    backup_parent = root / ".doc" / ".rebase-backup"
    if backup_parent.is_dir() and not any(backup_parent.iterdir()):
        backup_parent.rmdir()
    conflicts["backup_removed"] = True
    conflicts["backup_removed_at"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_json(root / CONFLICT_REPORT, conflicts)
    report["backup_removed"] = removed
    report["backup"]["removed"] = True
    report["backup"]["files"] = 0
    report["backup"]["bytes"] = 0
    report["backup"]["size"] = "0 B"
    report["backup"]["mcp_files"] = 0
    report["backup"]["mcp_bytes"] = 0
    report["backup"]["mcp_size"] = "0 B"
    return True


def run(command: list[str], cwd: Path, timeout: int = 300) -> tuple[int, str]:
    try:
        proc = subprocess.run(command, cwd=cwd, text=True, capture_output=True, timeout=timeout)
        return proc.returncode, (proc.stdout or "") + (proc.stderr or "")
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)


def scan_skills(root: Path) -> dict:
    scanner = root / SCANNER
    if not scanner.is_file():
        return {"status": "skipped", "reason": "add-skill scanner not found", "skills": []}
    code, output = run([sys.executable, str(scanner), "--root", str(root), "--json"], root)
    if code != 0:
        return {"status": "failed", "reason": output[-500:], "skills": []}
    try:
        payload = json.loads(output)
    except json.JSONDecodeError:
        return {"status": "failed", "reason": "scanner returned invalid JSON", "skills": []}
    proposals = []
    for item in payload.get("skills", {}).get("canon_local", []):
        proposals.append({
            "kind": "skill",
            "name": item["name"],
            "id": item["id"],
            "env": "agents",
            "path": item["path"],
            "action": "install",
            "reason": "skill exists in canon but not in the package manifest",
        })
    for item in payload.get("skills", {}).get("view_local", []):
        sources = item.get("sources") or []
        proposals.append({
            "kind": "skill",
            "name": item["name"],
            "id": item["id"],
            "env": sources[0]["env"] if sources else "",
            "path": sources[0]["path"] if sources else "",
            "action": "install",
            "reason": "skill exists only in an environment view",
        })
    for item in payload.get("skills", {}).get("conflict", []):
        proposals.append({
            "kind": "skill",
            "name": item["name"],
            "id": item["id"],
            "env": ",".join(source["env"] for source in item.get("sources", [])),
            "path": "",
            "action": "manual",
            "reason": "the same skill exists in several views with different files",
        })
    return {"status": "ok", "skills": proposals, "report": payload}


def skill_conflicts(conflicts: dict) -> list[dict]:
    result = []
    backup_dir = conflicts.get("backup_dir") or ""
    for item in conflicts.get("overwritten") or []:
        if item.get("category") != "skill":
            continue
        path = str(item.get("path", ""))
        if not path.endswith("/SKILL.md"):
            continue
        skill_path = path[: -len("/SKILL.md")]
        env = skill_path.split("/", 1)[0].lstrip(".")
        result.append({
            "kind": "skill",
            "name": skill_path.rsplit("/", 1)[-1],
            "id": skill_path.split("/skills/", 1)[-1],
            "env": env,
            "path": skill_path,
            "action": "manual",
            "reason": "target skill was overwritten by the kit; original copy is in the backup",
            "backup": f"{backup_dir}/{skill_path}" if backup_dir else str(item.get("backup", "")),
        })
    return result


def frontmatter_and_body(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    block = text[3:end]
    body = text[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    data = {}
    for line in block.splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            data[match.group(1)] = match.group(2).strip().strip("\"'")
    return data, body


def rule_name(front: dict[str, str], body: str, stem: str) -> str:
    name = front.get("name", "").strip()
    if name:
        return name
    heading = re.search(r"^#\s+(.+)$", body, re.M)
    return heading.group(1).strip() if heading else stem


def flat_rule_name(relative: Path) -> str:
    parts = relative.with_suffix("").parts
    if len(parts) == 1:
        return parts[0]
    if parts[0] == "mcp" and len(parts) == 2:
        return "mcp-" + parts[1]
    return "-".join(parts)


def scan_rules(root: Path, conflicts: dict, include_conflicts: bool = True) -> list[dict]:
    canon = root / ".cursor" / "rules"
    canon_names = set()
    if canon.is_dir():
        for path in canon.rglob("*.mdc"):
            relative = path.relative_to(canon)
            canon_names.add(path.stem)
            canon_names.add(flat_rule_name(relative))
    proposals = []
    seen = set()
    for relative in RULE_DIRS:
        base = root / relative
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.md")):
            stem = path.stem
            if stem in canon_names or stem in seen:
                continue
            seen.add(stem)
            proposals.append({
                "kind": "rule",
                "name": stem,
                "source": path.relative_to(root).as_posix(),
                "target": f".cursor/rules/{stem}.mdc",
                "action": "install",
                "reason": "local rule is not present in the canonical cursor rules",
            })
    if not include_conflicts:
        return proposals
    backup_dir = conflicts.get("backup_dir") or ""
    for item in conflicts.get("overwritten") or []:
        if item.get("category") != "rule":
            continue
        path = str(item.get("path", ""))
        stem = Path(path).stem
        proposals.append({
            "kind": "rule",
            "name": stem,
            "source": path,
            "target": "",
            "action": "manual",
            "reason": "target rule was overwritten by the kit; compare the backup and merge manually",
            "backup": f"{backup_dir}/{path}" if backup_dir else str(item.get("backup", "")),
        })
    return proposals


def mcp_servers(payload: dict | None) -> dict:
    if not isinstance(payload, dict):
        return {}
    servers = payload.get("mcpServers")
    return servers if isinstance(servers, dict) else {}


def scan_mcp(root: Path) -> list[dict]:
    original = mcp_servers(read_json(root / MCP_BACKUP))
    current = mcp_servers(read_json(root / MCP_CURRENT))
    proposals = []
    for name in sorted(original):
        if name not in current:
            proposals.append({
                "kind": "mcp",
                "name": name,
                "action": "install",
                "reason": "server exists in the original project config and is missing from the current canon",
            })
        elif json.dumps(original[name], sort_keys=True) != json.dumps(current[name], sort_keys=True):
            proposals.append({
                "kind": "mcp",
                "name": name,
                "action": "manual",
                "reason": "server exists in both configs with different settings; kit version is active",
            })
    for name in sorted(current):
        if name not in original:
            proposals.append({
                "kind": "mcp",
                "name": name,
                "action": "keep",
                "reason": "server comes from the kit",
            })
    return proposals


def install_skill(root: Path, proposal: dict, errors: list[str]) -> bool:
    script = root / ADD_SKILL
    if not script.is_file():
        errors.append("add-skill script not found")
        return False
    command = [sys.executable, str(script), "--root", str(root), "--name", proposal["name"], "--yes", "--no-sync"]
    if proposal.get("env") and proposal["env"] != "agents":
        command += ["--from", proposal["env"]]
    code, output = run(command, root)
    if code != 0:
        errors.append(f"skill {proposal['name']}: {output[-300:]}")
        return False
    return True


def install_rule(root: Path, proposal: dict, errors: list[str]) -> bool:
    source = root / proposal["source"]
    target = root / proposal["target"]
    if not source.is_file():
        errors.append(f"rule source not found: {proposal['source']}")
        return False
    if target.exists():
        errors.append(f"rule target already exists: {proposal['target']}")
        return False
    front, body = frontmatter_and_body(source.read_text(encoding="utf-8"))
    name = rule_name(front, body, proposal["name"])
    description = front.get("description") or f"Локальное правило {proposal['name']}."
    always = "true" if front.get("trigger") == "always_on" or front.get("alwaysApply", "").lower() == "true" else "false"
    lines = ["---", f'name: "{name}"', f'description: "{description}"', f"alwaysApply: {always}"]
    if front.get("globs"):
        lines.insert(3, f'globs: "{front["globs"]}"')
    lines.append("---")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("\n".join(lines) + "\n\n" + body.rstrip() + "\n", encoding="utf-8", newline="\n")
    return True


def install_mcp(root: Path, proposal: dict, errors: list[str]) -> bool:
    backup = read_json(root / MCP_BACKUP)
    current = read_json(root / MCP_CURRENT)
    if backup is None or current is None:
        errors.append("MCP backup or current config not found")
        return False
    original_servers = mcp_servers(backup)
    current_servers = mcp_servers(current)
    name = proposal["name"]
    if name not in original_servers:
        errors.append(f"server not found in original MCP: {name}")
        return False
    current_servers[name] = original_servers[name]
    current["mcpServers"] = current_servers
    write_json(root / MCP_CURRENT, current)
    return True


def run_sync(root: Path) -> tuple[int, str]:
    script = root / SYNC
    if not script.is_file():
        return 1, "sync-agent-views.sh not found"
    return run(["bash", str(script)], root, 600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--interactive", action="store_true", help="ask before applying safe proposals")
    parser.add_argument("--report-only", action="store_true", help="do not apply anything")
    parser.add_argument("--apply", action="store_true", help="apply all safe proposals")
    parser.add_argument("--apply-skills", action="store_true", help="apply safe skill proposals")
    parser.add_argument("--apply-rules", action="store_true", help="apply safe rule proposals")
    parser.add_argument("--apply-mcp", action="store_true", help="merge safe MCP proposals")
    parser.add_argument("--rm-backup", action="store_true", help="delete the migration backup after review")
    parser.add_argument("--yes", action="store_true", help="apply without an interactive prompt")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    marker = read_json(root / KIT_MARKER)
    conflicts = read_json(root / CONFLICT_REPORT) or {}
    mode = (marker or {}).get("mode") or conflicts.get("mode") or "migrate"
    skills = scan_skills(root)
    proposals = list(skills.get("skills", []))
    if mode != "update":
        proposals.extend(skill_conflicts(conflicts))
        proposals.extend(scan_rules(root, conflicts, include_conflicts=True))
        proposals.extend(scan_mcp(root))
    else:
        proposals.extend(scan_rules(root, conflicts, include_conflicts=False))
    backup = backup_summary(root, conflicts)
    counts = {
        "skills": len([item for item in proposals if item["kind"] == "skill"]),
        "rules": len([item for item in proposals if item["kind"] == "rule"]),
        "mcp": len([item for item in proposals if item["kind"] == "mcp"]),
        "manual": len([item for item in proposals if item.get("action") == "manual"]),
    }
    report = {
        "status": "ok",
        "root": str(root),
        "mode": mode,
        "marker": marker,
        "backup": {"report": CONFLICT_REPORT, **backup},
        "counts": counts,
        "proposals": proposals,
        "skill_scan": skills.get("status", "unknown"),
        "applied": [],
        "backup_removed": [],
        "errors": [],
    }
    if skills.get("reason"):
        report["skill_scan_reason"] = skills["reason"]

    apply_all = args.apply and not args.report_only
    apply_skills = (apply_all or args.apply_skills) and not args.report_only
    apply_rules = (apply_all or args.apply_rules) and not args.report_only
    apply_mcp = (apply_all or args.apply_mcp) and not args.report_only

    if args.interactive and not args.report_only and not args.yes and sys.stdin.isatty():
        answer = input("Применить безопасные предложения миграции? [y/N] ").strip().lower()
        if answer in {"y", "yes", "д", "да"}:
            apply_skills = apply_rules = apply_mcp = True

    if apply_skills:
        for item in proposals:
            if item["kind"] == "skill" and item.get("action") == "install":
                if install_skill(root, item, report["errors"]):
                    report["applied"].append({"kind": "skill", "name": item["name"]})
    if apply_rules:
        for item in proposals:
            if item["kind"] == "rule" and item.get("action") == "install":
                if install_rule(root, item, report["errors"]):
                    report["applied"].append({"kind": "rule", "name": item["name"]})
    if apply_mcp:
        for item in proposals:
            if item["kind"] == "mcp" and item.get("action") == "install":
                if install_mcp(root, item, report["errors"]):
                    report["applied"].append({"kind": "mcp", "name": item["name"]})

    if report["applied"]:
        code, output = run_sync(root)
        if code != 0:
            report["errors"].append("sync failed: " + output[-500:])
        else:
            report["sync"] = "passed"

    if args.rm_backup:
        if report["errors"]:
            report["errors"].append("backup removal skipped because the review has errors")
        else:
            remove_backup(root, report, args.yes)
    elif args.interactive and not args.report_only and sys.stdin.isatty():
        if backup["files"] or backup["mcp_files"]:
            answer = input("Удалить бэкап миграции? [y/N] ").strip().lower()
            if answer in {"y", "yes", "д", "да"}:
                remove_backup(root, report, True)

    report["status"] = "partial" if report["errors"] else "ok"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("Обзор миграции")
        print(f"  маркер kit: {'есть' if report['marker'] else 'нет'}")
        current_backup = report["backup"]
        if current_backup["removed"]:
            print("  бэкап: удален")
        elif current_backup["files"] or current_backup["mcp_files"]:
            print(f"  бэкап: {current_backup['dir'] or 'нет'} ({current_backup['files']} файлов, {current_backup['size']})")
            if current_backup["by_category"]:
                print("    категории: " + ", ".join(f"{key}={value}" for key, value in current_backup["by_category"].items()))
            if current_backup["mcp_files"]:
                print(f"    MCP: {current_backup['mcp_dir']} ({current_backup['mcp_files']} файлов, {current_backup['mcp_size']})")
            print("  удалить бэкап после проверки: python3 .agents/skills/harness-router/children/migration-review/scripts/review_migration.py --root . --rm-backup --yes")
        else:
            print("  бэкап: нет")
        print(f"  предложения: skills={counts['skills']}, rules={counts['rules']}, mcp={counts['mcp']}, manual={counts['manual']}")
        for item in proposals:
            print(f"  {item['kind']}: {item['name']} [{item.get('action')}] {item.get('reason', '')}")
        if report["applied"]:
            print("  применено: " + ", ".join(f"{item['kind']}:{item['name']}" for item in report["applied"]))
        if report["backup_removed"]:
            print("  бэкап удален: " + ", ".join(report["backup_removed"]))
        for error in report["errors"]:
            print("  ERROR " + error)
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
