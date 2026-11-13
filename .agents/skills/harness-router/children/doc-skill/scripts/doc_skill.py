#!/usr/bin/env python3
"""Doc Skill - аудит README скилов. Документация скила = его README."""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
SKILLS_ROOT = ROOT / ".agents" / "skills"
SKIP = {"__pycache__", "node_modules", "vendor", ".git", ".venv", "venv", "docs"}
DRAFT_PATTERNS = ["Заполнить:", "Описание уточняется", "Скил установлен"]


def iter_skills() -> list[Path]:
    skills = []
    for skill_md in SKILLS_ROOT.rglob("SKILL.md"):
        if any(part in SKIP for part in skill_md.parts):
            continue
        skills.append(skill_md.parent)
    return sorted(skills)


def audit_readme(skill: Path, extra_draft_patterns: tuple[str, ...] = ()) -> list[str]:
    readme = skill / "README.md"
    if not readme.is_file():
        return [f"README_MISSING: {skill}"]
    text = readme.read_text(encoding="utf-8", errors="ignore")
    errors = []

    if re.search(r"\[[^\]]+\]\([^)]+\)", text) or re.search(r"https?://", text):
        errors.append(f"README_HAS_LINKS: {readme}")
    if "## Связи" in text:
        errors.append(f"README_HAS_RELATIONS: {readme}")
    if not text.strip():
        errors.append(f"README_EMPTY: {readme}")
    for pattern in dict.fromkeys((*DRAFT_PATTERNS, *extra_draft_patterns)):
        if pattern in text:
            errors.append(f"README_PLACEHOLDER: {readme} '{pattern}'")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Doc Skill - README скилов")
    parser.add_argument("--skill", help="путь к папке скила от корня проекта")
    parser.add_argument("--audit", action="store_true", help="проверить все README")
    parser.add_argument("--list", action="store_true", help="показать скилы без README")
    parser.add_argument("--policy-root", help="добавить запрещённые шаблоны из политики проекта")
    args = parser.parse_args()

    extra_patterns = ()
    if args.policy_root:
        if not (args.audit or args.skill):
            print('ERROR POLICY: --policy-root requires --audit or --skill', file=sys.stderr)
            return 2
        loader = Path(__file__).resolve().parents[2] / 'harness-core/scripts/canon_paths.py'
        spec = importlib.util.spec_from_file_location('trusted_readme_policy', loader)
        try:
            if spec is None or spec.loader is None:
                raise ValueError('policy reader unavailable')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            policy = module.load_preliminary_policies(Path(args.policy_root))['component_docs']['rules']['CD01']
            if policy['filename'] != 'README.md':
                raise ValueError('policy may not change the trusted README filename')
            extra_patterns = policy['forbidden_literals']
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f'ERROR POLICY: {error}', file=sys.stderr)
            return 1

    if args.skill:
        skill = (ROOT / args.skill).resolve()
        if not (skill / "SKILL.md").is_file():
            print(f"not a skill: {args.skill}", file=sys.stderr)
            return 1
        errors = audit_readme(skill, extra_patterns)
        for error in errors:
            print(error, file=sys.stderr)
        return 1 if errors else 0

    skills = iter_skills()
    if args.list:
        for skill in skills:
            mark = "ok" if (skill / "README.md").is_file() else "no README"
            print(f"{skill.relative_to(ROOT)} {mark}")
        return 0

    if args.audit:
        errors = []
        for skill in skills:
            errors.extend(audit_readme(skill, extra_patterns))
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            print(f"errors: {len(errors)}", file=sys.stderr)
            return 1
        print(f"OK: {len(skills)} skills")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
