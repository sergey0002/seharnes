#!/usr/bin/env python3
"""Doc MCP - один скил и один документ на каждый активный MCP-сервер."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
CONFIG = ROOT / ".cursor" / "mcp.json"
SKILLS = ROOT / ".agents" / "skills"
LEGACY = ROOT / ".doc" / "harnes" / "mcp"
ARCHIVE = ROOT / ".doc" / "harnes" / "archive" / "mcp"

ALIASES = {
    "jira-task": "jira",
}


def load_servers() -> dict:
    data = json.loads(CONFIG.read_text(encoding="utf-8"))
    return data.get("mcpServers", {})


def skill_map() -> dict[str, Path]:
    found = {}
    for skill_md in SKILLS.rglob("SKILL.md"):
        found[skill_md.parent.name] = skill_md.parent
    return found


def resolve(server: str, skills: dict[str, Path]) -> Path | None:
    return skills.get(server) or skills.get(ALIASES.get(server, ""))


def paths(server: str, skill: Path | None) -> tuple[Path | None, Path]:
    legacy = LEGACY / f"{server}.md"
    target = skill / "docs" / "mcp" / f"{server}.md" if skill else None
    return target, legacy


def disabled_doc(server: str) -> Path | None:
    for candidate in (LEGACY / f"{server}.md", ARCHIVE / f"{server}.md"):
        if candidate.is_file():
            return candidate
    return None


def state(server: str, cfg: dict, skill: Path | None) -> str:
    target, legacy = paths(server, skill)
    if target and target.is_file() and legacy.is_file():
        return "doc-duplicate"
    if cfg.get("disabled"):
        if disabled_doc(server) or (target and target.is_file()):
            return "ok-disabled"
        return "disabled-doc-missing"
    if not skill:
        return "skill-missing"
    if target and target.is_file():
        return "ok"
    if legacy.is_file():
        return "needs-move"
    return "doc-missing"


def audit_document(doc: Path) -> list[str]:
    text = doc.read_text(encoding="utf-8")
    prose = re.sub(r"(?ms)^```[^\n]*\n.*?^```[^\n]*$", "", text)
    links = re.findall(r"\]\(([^)]+)\)", prose)
    related = re.search(r"^related:\s*\[([^\]]*)\]", prose, re.MULTILINE)
    if related:
        links.extend(item.strip() for item in related.group(1).split(","))
    errors = []
    for link in sorted(set(links)):
        path = link.split("#", 1)[0]
        if not path or re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", path):
            continue
        target_path = ROOT / path if path.startswith("/") else doc.parent / path
        if not target_path.exists():
            errors.append(f"DOC_BROKEN_LINK: {doc.relative_to(ROOT)} -> {link}")

    # Static inspection of local command script paths without executing them
    cmd_candidates = re.findall(
        r"(?:bash|sh|python3|python|node|pwsh|powershell|\.)\s+([./][a-zA-Z0-9_\-./]+\.[a-zA-Z0-9_]+)",
        text,
    )
    for cmd_str in sorted(set(cmd_candidates)):
        cmd_str_clean = cmd_str.strip().strip("`'\",;:)")
        if not cmd_str_clean or cmd_str_clean.startswith("<"):
            continue
        resolved_local = doc.parent / cmd_str_clean if cmd_str_clean.startswith("./") else ROOT / cmd_str_clean
        if not resolved_local.exists():
            errors.append(f"COMMAND_PATH_NOT_FOUND: {doc.relative_to(ROOT)} -> {cmd_str_clean}")

    return errors


def policy_mcp_suffix(template: str) -> tuple[str, ...]:
    """Allow an additional location under the owner; never replace docs/mcp."""
    prefix = '.agents/skills/{skill}/'
    if not isinstance(template, str) or not template.startswith(prefix):
        raise ValueError('MCP doc layout must stay inside the owning skill')
    parts = template[len(prefix):].split('/')
    if len(parts) < 2 or parts[0] != 'docs' or any(not re.fullmatch(r'[A-Za-z0-9_-]+', p) for p in parts):
        raise ValueError('unsafe MCP doc layout')
    return tuple(parts)


def extra_policy_doc(skill: Path, server: str, suffix: tuple[str, ...]) -> Path:
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', server) or server.endswith('.') or
            re.match(r'^(?:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', server, re.I)):
        raise ValueError('unsafe MCP server name')
    path = skill.joinpath(*suffix, server + '.md')
    current = skill
    for part in (*suffix, server + '.md'):
        current = current / part
        try:
            info = current.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise ValueError('linked MCP policy document path')
    try:
        path.resolve().relative_to(skill.resolve())
    except ValueError as error:
        raise ValueError('MCP policy document escapes owner') from error
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Doc MCP")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--move", action="store_true")
    parser.add_argument("--audit", action="store_true")
    parser.add_argument("--policy-root", help="проверить дополнительные пути документации MCP из политики проекта")
    args = parser.parse_args()

    suffix = None
    if args.policy_root:
        if not args.audit or args.move:
            print('ERROR POLICY: --policy-root requires --audit without --move', file=sys.stderr)
            return 2
        loader = Path(__file__).resolve().parents[2] / 'harness-core/scripts/canon_paths.py'
        spec = importlib.util.spec_from_file_location('trusted_mcp_doc_policy', loader)
        try:
            if spec is None or spec.loader is None:
                raise ValueError('policy reader unavailable')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            bundle = module.load_preliminary_policy_bundle(Path(args.policy_root))
            suffix = policy_mcp_suffix(bundle['layout']['docs']['mcp_skill'])
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f'ERROR POLICY: {error}', file=sys.stderr)
            return 1

    servers = load_servers()
    skills = skill_map()
    errors = []
    moved = 0

    for server, cfg in sorted(servers.items()):
        skill = resolve(server, skills)
        target, legacy = paths(server, skill)
        status = state(server, cfg, skill)

        if args.move and status == "needs-move" and skill and target:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(legacy), str(target))
            moved += 1
            status = "ok"

        if args.list:
            skill_rel = skill.relative_to(ROOT).as_posix() if skill else "MISSING"
            document = target if target and target.is_file() else (disabled_doc(server) or legacy)
            doc_rel = document.relative_to(ROOT).as_posix() if document.is_file() else "-"
            print(f"{server:24} skill={skill_rel:62} doc={doc_rel:50} {status}")
            if not args.audit:
                continue

        if args.audit:
            if status == "doc-duplicate":
                errors.append(f"DOC_DUPLICATE: {server} (документ есть в скиле и в .doc)")
            elif status == "skill-missing":
                errors.append(f"SKILL_MISSING: {server} (active MCP без скила)")
            elif status == "needs-move":
                errors.append(f"DOC_NOT_MOVED: {server} -> {target.relative_to(ROOT)}")
            elif status == "doc-missing":
                errors.append(f"DOC_MISSING: {server} -> {target.relative_to(ROOT)}")
            elif status == "disabled-doc-missing":
                expected = disabled_doc(server) or legacy
                errors.append(f"DISABLED_DOC_MISSING: {server} -> {expected.relative_to(ROOT)}")
            if skill and not cfg.get("disabled"):
                for filename in ("README.md", "skill.json"):
                    if not (skill / filename).is_file():
                        errors.append(f"SKILL_INCOMPLETE: {server} missing {filename}")
                if suffix is not None:
                    try:
                        policy_doc = extra_policy_doc(skill, server, suffix)
                        if not policy_doc.is_file():
                            errors.append(f"POLICY_DOC_MISSING: {server} -> {policy_doc.relative_to(ROOT)}")
                        elif target is None or policy_doc != target:
                            errors.extend(audit_document(policy_doc))
                    except (OSError, ValueError) as error:
                        errors.append(f"POLICY_DOC_UNSAFE: {server}: {error}")
            if status == "ok" and target:
                errors.extend(audit_document(target))

    if args.move and not args.list and not args.audit:
        print(f"moved: {moved}")
        return 0

    if args.audit:
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            print(f"errors: {len(errors)}", file=sys.stderr)
            return 1
        print(f"OK: {len(servers)} servers")
        return 0

    if args.list:
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
