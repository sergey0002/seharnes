#!/usr/bin/env python3
"""Verify that every environment classifies rules the same way.

Canon `.cursor/rules/**/*.mdc` is classified by `rule_model.classify`:

  always           alwaysApply: true
  conditional      globs or paths
  agent_requested  description only
  manual           no signal

Each adapter must map that kind to its own trigger:

  Kilo         instructions list / rules index
  Qoder        always_on / glob / model_decision / manual
  Qwen         rules baseline / rules with paths / rule-* skill
  Antigravity  always_on / glob / model_decision / manual
  DSH          inline "(always)" / on-demand pointer table
  Codex        file copy only, no trigger engine

Exit 0 when every view agrees with the canon, 1 otherwise.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import rule_model

TRIGGER_BY_KIND = {
    rule_model.ALWAYS: "always_on",
    rule_model.CONDITIONAL: "glob",
    rule_model.AGENT_REQUESTED: "model_decision",
    rule_model.MANUAL: "manual",
}


def flat_stem(relative: Path) -> str:
    parts = relative.with_suffix("").parts
    if len(parts) == 1:
        return parts[0]
    if parts[0] == "mcp" and len(parts) == 2:
        return "mcp-" + parts[1]
    return "-".join(parts)


def flat_md(relative: Path) -> str:
    return flat_stem(relative) + ".md"


def read_kilo_instructions(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    payload = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("//")
    )
    return json.loads(payload)["instructions"]


def check_kilo(rel: str, kind: str, instructions: list[str], index: str, errors: list[str], rule: str) -> None:
    target = f".kilo/rules/{rel}"
    injected = target in instructions
    in_index = target in index
    if kind == rule_model.ALWAYS and not injected:
        errors.append(f"kilo {rule}: always rule missing from instructions")
    if kind == rule_model.ALWAYS and in_index:
        errors.append(f"kilo {rule}: always rule listed in rules-index")
    if kind != rule_model.ALWAYS and injected:
        errors.append(f"kilo {rule}: {kind} rule injected at start")
    if kind != rule_model.ALWAYS and not in_index:
        errors.append(f"kilo {rule}: {kind} rule missing from rules-index")


def check_trigger_file(path: Path, kind: str, errors: list[str], label: str, rule: str) -> dict:
    if not path.exists():
        errors.append(f"{label} {rule}: missing {path}")
        return {}
    front = rule_model.rule_frontmatter(path)
    expected = TRIGGER_BY_KIND[kind]
    actual = str(front.get("trigger", "")).strip()
    if actual != expected:
        errors.append(f"{label} {rule}: trigger {actual or '-'} != {expected}")
    if kind == rule_model.CONDITIONAL:
        if label == "antigravity" and not isinstance(front.get("globs", front.get("glob")), str):
            errors.append(f"{label} {rule}: globs must be a comma-separated string")
        globs = rule_model.rule_paths(front) or rule_model.as_list(front.get("glob"))
        if not globs:
            errors.append(f"{label} {rule}: conditional rule without globs")
    return front


def main() -> int:
    parser = argparse.ArgumentParser(description="Cross-environment rule trigger parity")
    parser.add_argument("--root", default=".")
    parser.add_argument("--canonical", default=".cursor/rules")
    parser.add_argument("--kilo", default=".kilo/kilo.jsonc")
    parser.add_argument("--kilo-index", default=".kilo/rules-index.md")
    parser.add_argument("--qoder", default=".qoder/rules")
    parser.add_argument("--qwen", default=".qwen/rules")
    parser.add_argument("--qwen-skills", default=".qwen/skills")
    parser.add_argument("--antigravity", default=".agents/rules")
    parser.add_argument("--dsh", default="DSH-RULES.md")
    parser.add_argument("--codex", default=".codex/rules")
    parser.add_argument("--codex-index", default=".codex/rules-index.md")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    canonical = root / args.canonical
    if not canonical.is_dir():
        print(f"canonical rules dir not found: {canonical}", file=sys.stderr)
        return 1

    instructions = read_kilo_instructions(root / args.kilo)
    index_path = root / args.kilo_index
    index = index_path.read_text(encoding="utf-8") if index_path.exists() else ""

    dsh_path = root / args.dsh
    dsh_text = dsh_path.read_text(encoding="utf-8") if dsh_path.exists() else ""
    dsh_head, _, dsh_tail = dsh_text.partition("## On-demand rules")

    codex_index_path = root / args.codex_index
    codex_text = codex_index_path.read_text(encoding="utf-8") if codex_index_path.exists() else ""
    codex_head, _, codex_tail = codex_text.partition("## По требованию")

    errors: list[str] = []
    counts = {kind: 0 for kind in rule_model.KINDS}
    gates = 0
    attach_globs = 0

    for rule_path in sorted(canonical.rglob("*.mdc")):
        relative = rule_path.relative_to(canonical)
        rel = relative.with_suffix(".md").as_posix()
        rule = relative.with_suffix("").as_posix()
        fields = rule_model.rule_frontmatter(rule_path)
        kind = rule_model.classify(fields)
        counts[kind] += 1
        if rule_model.is_gate(fields):
            gates += 1
        if rule_model.needs_glob(fields):
            attach_globs += 1

        check_kilo(rel, kind, instructions, index, errors, rule)

        flat = flat_md(relative)
        check_trigger_file(root / args.qoder / flat, kind, errors, "qoder", rule)
        check_trigger_file(root / args.antigravity / flat, kind, errors, "antigravity", rule)

        qwen_rule = root / args.qwen / flat
        qwen_skill = root / args.qwen_skills / ("rule-" + flat_stem(relative)) / "SKILL.md"
        if kind in (rule_model.ALWAYS, rule_model.CONDITIONAL, rule_model.MANUAL):
            if not qwen_rule.exists():
                errors.append(f"qwen {rule}: missing {qwen_rule}")
            else:
                front = rule_model.rule_frontmatter(qwen_rule)
                has_paths = bool(rule_model.rule_paths(front))
                if kind == rule_model.CONDITIONAL and not has_paths:
                    errors.append(f"qwen {rule}: conditional rule without paths")
                if kind == rule_model.ALWAYS and has_paths:
                    errors.append(f"qwen {rule}: always rule has paths")
        elif not qwen_skill.exists():
            errors.append(f"qwen {rule}: missing {qwen_skill}")

        key = rule.replace("/", "-")
        if kind == rule_model.ALWAYS:
            if f"<!-- rule: {key} (always) -->" not in dsh_head:
                errors.append(f"dsh {rule}: always rule not inlined")
        elif f".cursor/rules/{rel}" not in dsh_tail:
            errors.append(f"dsh {rule}: {kind} rule missing from on-demand table")

        if not (root / args.codex / rel).exists():
            errors.append(f"codex {rule}: missing rule copy")
        codex_target = f".codex/rules/{rel}"
        if kind == rule_model.ALWAYS and codex_target not in codex_head:
            errors.append(f"codex {rule}: always rule missing from rules-index")
        elif kind != rule_model.ALWAYS and codex_target not in codex_tail:
            errors.append(f"codex {rule}: {kind} rule missing from rules-index")

        # Visibility contract: a gate must be injected everywhere, and a path
        # trigger must keep working in environments that have no glob engine.
        if (rule_model.is_gate(fields)
                and rule_model.visibility_contract("kilo", fields) == "inline"
                and kind != rule_model.ALWAYS):
            errors.append(f"{rule}: gate rule must be alwaysApply true (got {kind})")
        if rule_model.needs_glob(fields):
            if kind != rule_model.CONDITIONAL:
                errors.append(f"{rule}: attach glob requires globs or paths (got {kind})")
            else:
                for label, text in (("kilo", index), ("codex", codex_tail), ("dsh", dsh_tail)):
                    if "<!-- glob-triggers -->" not in text:
                        errors.append(f"{label} {rule}: generated glob block missing")
                    for glob in rule_model.rule_paths(fields):
                        if glob not in text:
                            errors.append(f"{label} {rule}: glob {glob} missing from generated glob block")

    result = {
        "status": "passed" if not errors else "failed",
        "rules": sum(counts.values()),
        "kinds": counts,
        "gates": gates,
        "attach_globs": attach_globs,
        "errors": errors,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
