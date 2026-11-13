"""Prompt budget metric for skills.

Counts words in each SKILL.md and its references so a reviewer can see which
skills load a large prompt. This is a read-only metric: it never edits a skill
and never changes routing. Large SKILL.md files are flagged, not truncated.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SKILL_LIMIT = 2500


def _words(path: Path) -> int:
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").split())
    except OSError:
        return 0


def measure(skill_dir: Path, limit: int = SKILL_LIMIT) -> dict:
    skill_md = skill_dir / "SKILL.md"
    refs = skill_dir / "references"
    refs_words = sum(_words(p) for p in refs.rglob("*.md")) if refs.is_dir() else 0
    prompt_words = _words(skill_md)
    return {
        "skill": skill_dir.name,
        "prompt_words": prompt_words,
        "refs_words": refs_words,
        "over_limit": prompt_words > limit,
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Skill prompt-word budget")
    ap.add_argument("--skills", type=Path, default=Path(".agents/skills"))
    ap.add_argument("--limit", type=int, default=SKILL_LIMIT)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    rows = []
    for skill_md in sorted(args.skills.rglob("SKILL.md")):
        rows.append(measure(skill_md.parent, args.limit))

    if args.json:
        print(json.dumps({"limit": args.limit, "rows": rows,
                          "over": [r["skill"] for r in rows if r["over_limit"]]},
                         ensure_ascii=False, indent=2))
    else:
        for r in rows:
            flag = "OVER" if r["over_limit"] else "ok"
            print(f"{flag}\t{r['prompt_words']}\t{r['refs_words']}\t{r['skill']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
