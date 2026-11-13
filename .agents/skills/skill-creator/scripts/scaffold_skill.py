#!/usr/bin/env python3
"""Deterministic 17-agent skill scaffolder (stdlib only, optional PyYAML check)."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
VALID_ARCHETYPES = ("atomic", "script", "multi-agent", "user-invoked")
VALID_RESOURCES = {"scripts", "references", "assets", "agents", "evals"}


def validate_skill_name(name: str) -> str:
    if not name or not NAME_RE.match(name):
        raise ValueError(
            f"Invalid skill name '{name}': must match ^[a-z0-9]+(-[a-z0-9]+)*$."
        )
    return name


def title_from_slug(slug: str) -> str:
    return " ".join(part.capitalize() for part in slug.split("-"))


def fit_short_description(text: str, fallback_title: str) -> str:
    cleaned = " ".join(text.strip().split())
    if len(cleaned) < 25:
        cleaned = f"Portable agent skill for {fallback_title} workflows."
    if len(cleaned) > 64:
        cut = cleaned[:61].rstrip(" ,.;:-")
        cleaned = f"{cut}..."
    if len(cleaned) < 25:
        cleaned = (cleaned + " workflow helper.")[:64]
    return cleaned


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def build_skill_md(
    *,
    name: str,
    description: str,
    archetype: str,
    invocation: str,
    license_id: str,
    author: str,
    version: str,
    compatibility: str | None,
    resources: list[str],
    with_openai_yaml: bool = True,
) -> str:
    title = title_from_slug(name)
    user_only = invocation == "user"

    lines = [
        "---",
        f"name: {name}",
        f"description: {yaml_quote(description)}",
    ]
    if user_only:
        lines.append("disable-model-invocation: true")
    if license_id:
        lines.append(f"license: {license_id}")
    if compatibility:
        lines.append(f"compatibility: {yaml_quote(compatibility)}")

    lines.extend(
        [
            "metadata:",
            f"  author: {yaml_quote(author)}",
            f"  version: {yaml_quote(version)}",
        ]
    )
    if user_only:
        lines.append('  opencode/autoinvoke: "false"')
    lines.extend(["---", "", f"# {title}", ""])

    if archetype == "user-invoked" or user_only:
        lines.extend(
            [
                "Manual-invocation workflow. Confirm target environment and destructive diffs before applying changes.",
                "",
                "## Workflow",
                "1. Inspect the target workspace state and prerequisites -> Done when preflight passes with zero missing inputs.",
                "2. Present planned mutations to the user and obtain explicit confirmation -> Done when approved.",
                "3. Execute the operation and verify post-state -> Done when health/verification checks pass.",
            ]
        )
    elif archetype == "script":
        lines.extend(
            [
                "Combines deterministic script execution with frontier domain judgment.",
                "",
                "## Workflow",
                "1. Inspect inputs and target paths -> Done when scope and arguments are confirmed.",
                "2. Run [the deterministic helper](scripts/run_check.py):",
                "   ```bash",
                "   python3 scripts/run_check.py \"<target>\" --json",
                "   ```",
                "   -> Done when exit code is `0` and structured JSON output is reviewed.",
                "3. Apply domain analysis and remediate findings -> Done when re-running the check reports clean.",
            ]
        )
    elif archetype == "multi-agent":
        lines.extend(
            [
                "Orchestrates independent domain checks across isolated context windows.",
                "",
                "## Workflow",
                "1. Collect workspace context and dispatch independent reviewer/executor roles (use isolated sequential passes if the host lacks parallel subagent spawning) -> Done when all role artifacts return.",
                "2. Cross-check outputs against domain criteria -> Done when contradictions and gaps are resolved.",
                "3. Deliver verified summary citing observed files and command outputs.",
            ]
        )
    else:
        lines.extend(
            [
                "Focused workflow addressing domain rules and edge cases not obvious from defaults.",
                "",
                "## Workflow",
                "1. Inspect relevant workspace artifacts before proposing changes -> Done when evidence is gathered.",
                "2. Apply the domain rules below and verify edge cases -> Done when acceptance checks pass.",
            ]
        )

    resource_pointers: list[str] = []
    if "references" in resources:
        resource_pointers.append(
            "- Read [domain rules](references/domain-rules.md) before handling branch-specific edge cases."
        )
    if "assets" in resources:
        resource_pointers.append(
            "- Use [output template](assets/output-template.md) only when rendering the final deliverable."
        )
    if "agents" in resources and archetype != "multi-agent":
        resource_pointers.append(
            "- Delegate independent read-only review to [the reviewer role](agents/reviewer.md) when validating final output."
        )
    if "scripts" in resources and archetype != "script":
        resource_pointers.append(
            "- Run [the deterministic helper](scripts/run_check.py) (`python3 scripts/run_check.py \"<target>\" --json`) for validation."
        )
    if with_openai_yaml:
        resource_pointers.append(
            "- Optional UI discovery metadata lives in [Codex UI config](agents/openai.yaml)."
        )

    if resource_pointers:
        lines.extend(["", "## Resources", *resource_pointers])

    lines.extend(
        [
            "",
            "## Gotchas",
            "- **Replace starter placeholders:** verify every domain rule, example, and assertion reflects real observed failure modes before shipping.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_openai_yaml(
    *,
    name: str,
    display_name: str,
    short_description: str,
    invocation: str,
) -> str:
    allow_implicit = "false" if invocation == "user" else "true"
    default_prompt = f"Use ${name} to execute this task safely and verify the deliverable."
    return (
        "interface:\n"
        f"  display_name: {yaml_quote(display_name)}\n"
        f"  short_description: {yaml_quote(short_description)}\n"
        f"  default_prompt: {yaml_quote(default_prompt)}\n"
        "policy:\n"
        f"  allow_implicit_invocation: {allow_implicit}\n"
    )


def build_helper_script() -> str:
    return '''#!/usr/bin/env python3
"""Deterministic helper script template (replace with concrete deterministic logic)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Deterministic verification helper")
    parser.add_argument("target", help="Target file or directory path")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        payload = {"status": "ERROR", "reason": f"Target not found: {target}"}
        print(json.dumps(payload, indent=2) if args.json else payload["reason"], file=sys.stderr)
        return 1

    payload = {"status": "OK", "target": str(target), "is_dir": target.is_dir()}
    print(json.dumps(payload, indent=2) if args.json else f"OK: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def build_evals_json(name: str, archetype: str) -> str:
    mode = "WITH_SKILL_ONLY" if archetype == "script" else "AB_MEANINGFUL"
    data = {
        "skill_name": name,
        "default_eval_mode": mode,
        "evals": [
            {
                "id": 1,
                "eval_mode": mode,
                "prompt": f"Realistic primary task that should trigger {name}.",
                "expected_output": "Complete, verified artifact matching domain rules.",
                "files": [],
                "expectations": [
                    "Follows the documented workflow steps in order",
                    "Produces verifiable output grounded in observed workspace state",
                ],
            },
            {
                "id": 2,
                "eval_mode": mode,
                "prompt": f"Edge-case request with missing or conflicting inputs for {name}.",
                "expected_output": "Surfaces the ambiguity or missing precondition cleanly before acting.",
                "files": [],
                "expectations": [
                    "Flags missing input or ambiguous constraint explicitly",
                    "Avoids silent fabrication or unverified assumptions",
                ],
            },
        ],
    }
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def build_trigger_evals_json(name: str) -> str:
    samples = [
        {"query": f"Help me run the {name} workflow on this project.", "should_trigger": True},
        {"query": "Unrelated general coding question about sorting a Python list.", "should_trigger": False},
    ]
    return json.dumps(samples, indent=2, ensure_ascii=False) + "\n"


def build_reviewer_md() -> str:
    return (
        "---\n"
        "name: reviewer\n"
        "description: Independent read-only verifier checking generated artifacts against domain invariants.\n"
        "tools: Read, Grep, Glob\n"
        "readonly: true\n"
        "maxTurns: 10\n"
        "---\n\n"
        "# Read-Only Reviewer\n\n"
        "Inspect the produced artifacts in a clean context window and verify every requirement and edge case.\n"
        "Report concrete `file:line` issues and exact patches in JSON.\n"
    )


def create_cross_agent_mirrors(skill_dir: Path, project_root: Path, targets: list[str]) -> list[str]:
    created: list[str] = []
    project_resolved = project_root.resolve()
    skill_resolved = skill_dir.resolve()
    for rel_parent in targets:
        parent = (project_resolved / rel_parent).resolve()
        if project_resolved not in parent.parents and parent != project_resolved:
            raise ValueError(f"Mirror target escapes project root: {rel_parent}")
        parent.mkdir(parents=True, exist_ok=True)
        link_path = parent / skill_dir.name
        if link_path.exists() or link_path.is_symlink():
            if link_path.resolve() == skill_resolved:
                continue
            raise FileExistsError(f"Mirror destination already exists: {link_path}")
        rel_target = os.path.relpath(skill_resolved, parent)
        link_path.symlink_to(rel_target, target_is_directory=True)
        created.append(str(link_path))
    return created


def scaffold_skill(args: argparse.Namespace) -> dict[str, Any]:
    name = validate_skill_name(args.name)
    output_dir = Path(args.output_dir).resolve()
    skill_dir = output_dir / name

    if skill_dir.exists():
        if not args.force:
            raise FileExistsError(f"Destination already exists: {skill_dir} (use --force to overwrite)")

    resources: list[str] = []
    if args.resources:
        for item in args.resources.split(","):
            clean = item.strip().lower()
            if not clean:
                continue
            if clean not in VALID_RESOURCES:
                raise ValueError(f"Unsupported resource '{clean}'. Choose from: {sorted(VALID_RESOURCES)}")
            if clean not in resources:
                resources.append(clean)

    archetype = args.archetype
    invocation = args.invocation or ("user" if archetype == "user-invoked" else "model")

    if archetype == "script" and "scripts" not in resources:
        resources.append("scripts")
    if archetype == "multi-agent" and "agents" not in resources:
        resources.append("agents")

    description = args.description or (
        f"Handles {title_from_slug(name)} tasks cleanly. "
        f"Use when working on {name.replace('-', ' ')} workflows. "
        f"Do NOT use for unrelated general tasks."
    )
    skill_dir.mkdir(parents=True, exist_ok=True)
    written_files: list[str] = []

    skill_md_path = skill_dir / "SKILL.md"
    skill_md_path.write_text(
        build_skill_md(
            name=name,
            description=description,
            archetype=archetype,
            invocation=invocation,
            license_id=args.license,
            author=args.author,
            version=args.version,
            compatibility=args.compatibility,
            resources=resources,
            with_openai_yaml=args.with_openai_yaml,
        ),
        encoding="utf-8",
    )
    written_files.append(str(skill_md_path))

    if args.with_openai_yaml:
        agents_dir = skill_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        display_name = args.display_name or title_from_slug(name)
        short_desc = fit_short_description(args.short_description or description, display_name)
        openai_path = agents_dir / "openai.yaml"
        openai_path.write_text(
            build_openai_yaml(
                name=name,
                display_name=display_name,
                short_description=short_desc,
                invocation=invocation,
            ),
            encoding="utf-8",
        )
        written_files.append(str(openai_path))

    if "scripts" in resources:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        helper_path = scripts_dir / "run_check.py"
        helper_path.write_text(build_helper_script(), encoding="utf-8")
        helper_path.chmod(0o755)
        written_files.append(str(helper_path))

    if "references" in resources:
        refs_dir = skill_dir / "references"
        refs_dir.mkdir(exist_ok=True)
        ref_path = refs_dir / "domain-rules.md"
        ref_path.write_text(
            f"# {title_from_slug(name)} Domain Rules\n\n"
            "Keep branch-specific specifications and edge cases here (loaded on demand).\n",
            encoding="utf-8",
        )
        written_files.append(str(ref_path))

    if "assets" in resources:
        assets_dir = skill_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        tmpl_path = assets_dir / "output-template.md"
        tmpl_path.write_text(
            f"# {title_from_slug(name)} Output Template\n\n"
            "## Summary\n\n## Verified Evidence\n",
            encoding="utf-8",
        )
        written_files.append(str(tmpl_path))

    if "agents" in resources and archetype == "multi-agent":
        agents_dir = skill_dir / "agents"
        agents_dir.mkdir(exist_ok=True)
        rev_path = agents_dir / "reviewer.md"
        rev_path.write_text(build_reviewer_md(), encoding="utf-8")
        written_files.append(str(rev_path))

    if "evals" in resources:
        evals_dir = skill_dir / "evals"
        evals_dir.mkdir(exist_ok=True)
        evals_path = evals_dir / "evals.json"
        evals_path.write_text(build_evals_json(name, archetype), encoding="utf-8")
        written_files.append(str(evals_path))
        if invocation == "model":
            trig_path = evals_dir / "trigger_evals.json"
            trig_path.write_text(build_trigger_evals_json(name), encoding="utf-8")
            written_files.append(str(trig_path))

    mirrors: list[str] = []
    if args.mirror_project:
        mirror_targets = [t.strip() for t in args.mirror_targets.split(",") if t.strip()]
        mirrors = create_cross_agent_mirrors(skill_dir, Path(args.mirror_project), mirror_targets)

    return {
        "status": "SCAFFOLDED",
        "skill_name": name,
        "skill_dir": str(skill_dir),
        "archetype": archetype,
        "invocation": invocation,
        "files_created": written_files,
        "mirrors_created": mirrors,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scaffold a portable 17-agent Agent Skill package.")
    parser.add_argument("name", help="Kebab-case skill name")
    parser.add_argument("--output-dir", default=".", help="Parent directory where <name>/ will be created")
    parser.add_argument("--description", default="", help="Skill trigger description")
    parser.add_argument("--archetype", choices=VALID_ARCHETYPES, default="atomic", help="Starter structure")
    parser.add_argument("--invocation", choices=("model", "user"), default=None, help="Invocation mode override")
    parser.add_argument("--license", default="MIT", help="SPDX license identifier")
    parser.add_argument("--author", default="skill-author", help="metadata.author string value")
    parser.add_argument("--version", default="1.0.0", help="metadata.version string value")
    parser.add_argument("--compatibility", default=None, help="Optional compatibility note")
    parser.add_argument(
        "--resources",
        default="",
        help="Comma-separated optional subdirs: scripts,references,assets,agents,evals",
    )
    parser.add_argument("--no-openai-yaml", action="store_false", dest="with_openai_yaml", help="Skip agents/openai.yaml")
    parser.add_argument("--display-name", default=None, help="Codex UI display_name")
    parser.add_argument("--short-description", default=None, help="Codex UI short_description (25-64 chars)")
    parser.add_argument(
        "--mirror-project",
        default=None,
        help="Optional project root where relative symlinks into agent directories will be created",
    )
    parser.add_argument(
        "--mirror-targets",
        default=".claude/skills,.qoder/skills,.kiro/skills",
        help="Comma-separated mirror dirs under --mirror-project",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite existing destination directory")
    parser.add_argument("--json", action="store_true", help="Emit JSON result")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    try:
        args = parse_args(argv)
        result = scaffold_skill(args)
    except Exception as exc:
        err = {"status": "ERROR", "error": str(exc)}
        print(json.dumps(err, indent=2), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Scaffolded {result['skill_name']} at {result['skill_dir']}")
        for path in result["files_created"]:
            print(f"  + {path}")
        for m in result["mirrors_created"]:
            print(f"  -> mirror: {m}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
