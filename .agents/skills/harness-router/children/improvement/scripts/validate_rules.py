#!/usr/bin/env python3
"""Statically validate agent rules and skills without claiming runtime behavior."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

SCRIPT_RE = re.compile(r"(?:[\w./-]+/scripts/[\w.-]+(?:\.py|\.ps1|\.sh)|[\w.-]+\.(?:py|ps1|sh)\b)")
SKILL_REF_RE = re.compile(r"(?:skills/)?([a-z0-9][a-z0-9-]*)/SKILL\.md", re.I)
TRIGGER_RE = re.compile(r"(?im)^\s*(?:triggers?|use for|ручные триггеры):\s*(.+)$")
CONTRADICTIONS = (("always", "never"), ("must", "must not"), ("required", "optional"), ("обязательно", "запрещено"))

# Mutual caller/callee links between skills and their rules are the normal
# shape of this harness (prepare-plan <-> git-task-blame, test-task <->
# browser-verify, ...). Only self-links and cycles of length >= 3 that do
# not pass through a known caller/callee pair are reported, as info.
KNOWN_CROSS_LINKS = frozenset({
    ("browser-verify", "test-task"), ("test-task", "browser-verify"),
    ("browser-verify", "login-as-user"), ("login-as-user", "browser-verify"),
    ("browser-verify", "prepare-task-test"), ("prepare-task-test", "browser-verify"),
    ("prepare-plan", "git-task-blame"), ("git-task-blame", "prepare-plan"),
    ("test-task", "prepare-plan"), ("prepare-plan", "test-task"),
    ("test-task", "prepare-task-test"), ("prepare-task-test", "test-task"),
    ("test-task", "login-as-user"), ("login-as-user", "test-task"),
    ("login-as-user", "browser-verify"), ("browser-verify", "login-as-user"),
})

# Host-level helpers that are never shipped with the harness (venv
# activation, OS chrome wrappers). Referenced by name only; visible as
# info, never warnings.
HOST_LEVEL_SCRIPTS = frozenset({"Activate.ps1", "activate", "deactivate"})

# Bare adapter names (no path separator) may live in another harness
# directory (.agents/skills/*/scripts, sibling skill scripts).
# Only references that look like real paths are resolved against the
# project tree; anything else stays a warning, never an error.


def _files(directory: Path, suffixes: tuple[str, ...]) -> list[Path]:
    return sorted((p for p in directory.rglob("*") if p.is_file() and p.suffix.lower() in suffixes), key=lambda p: p.as_posix())


def _issue(kind: str, severity: str, path: Path, message: str, **extra: object) -> dict[str, object]:
    result = {"kind": kind, "severity": severity, "path": path.as_posix(), "message": message}
    result.update(extra)
    return result


@lru_cache(maxsize=None)
def _name_index(root_value: str) -> dict[str, tuple[Path, ...]]:
    root = Path(root_value)
    index: dict[str, list[Path]] = {}
    if root.is_dir():
        for item in root.rglob("*"):
            if item.is_file():
                index.setdefault(item.name, []).append(item)
    return {name: tuple(paths) for name, paths in index.items()}


def _script_candidates(reference: str, path: Path, skills_dir: Path) -> list[Path]:
    project_root = skills_dir.parent.parent
    candidates = [path.parent / reference, path.parent / "scripts" / reference,
                   project_root / reference, project_root / "scripts" / reference,
                   skills_dir / reference,
                   project_root / ".cursor" / "scripts" / Path(reference).name,
                   project_root / ".tools" / "scripts" / Path(reference).name]
    if path.parent.name == "scripts":
        candidates.append(path.parent / reference)
    candidates.append(project_root / ".doc" / "qa" / "scripts" / Path(reference).name)
    name = Path(reference).name
    candidates.extend(_name_index(str(project_root / ".doc" / "skil_data")).get(name, ()))
    candidates.extend(_name_index(str(project_root / ".cursor" / "scripts")).get(name, ()))
    candidates.extend(_name_index(str(project_root / ".tools" / "scripts")).get(name, ()))
    # Venv activation and host-level helpers live outside the repo docs.
    candidates.append(Path.home() / ".local" / "chrome-for-testing" / name)
    candidates.append(project_root / "sourcegraph-local" / name)
    candidates.extend(_name_index(str(skills_dir)).get(name, ()))
    candidates.append(project_root / ".codex" / name)
    return candidates


def _skill_of(path: Path, skills_dir: Path) -> str | None:
    try:
        relative = path.relative_to(skills_dir)
    except ValueError:
        return None
    for index in range(len(relative.parts), 0, -1):
        candidate = skills_dir.joinpath(*relative.parts[:index])
        if (candidate / "SKILL.md").is_file():
            return candidate.name.lower()
    return None


def _is_expected_cross_link(cycle: list[str], skills_dir: Path) -> bool:
    skills = [_skill_of(Path(node), skills_dir) for node in cycle]
    if any(skill is None for skill in skills):
        return False
    pairs = list(zip(skills, skills[1:]))
    return bool(pairs) and all(pair in KNOWN_CROSS_LINKS for pair in pairs)


def validate(rules_dir: Path, skills_dir: Path) -> dict[str, object]:
    rules = _files(rules_dir, (".md", ".mdc")) if rules_dir.is_dir() else []
    skills = sorted({p.parent for p in skills_dir.rglob("SKILL.md")}, key=lambda p: p.as_posix()) if skills_dir.is_dir() else []
    skill_names = {p.name.lower() for p in skills if (p / "SKILL.md").exists()}
    issues: list[dict[str, object]] = []

    trigger_map: dict[str, list[str]] = {}
    always_apply = 0
    graph: dict[str, set[str]] = {}
    documents = rules + [p / "SKILL.md" for p in skills if (p / "SKILL.md").exists()]
    for path in documents:
        text = path.read_text(encoding="utf-8")
        node = path.as_posix()
        graph.setdefault(node, set())
        if path.parent == rules_dir and re.search(r"(?im)^alwaysApply:\s*true\s*$", text):
            always_apply += 1
        for match in SKILL_REF_RE.finditer(text):
            target = match.group(1).lower()
            if target not in skill_names:
                issues.append(_issue("missing_skill_link", "warning", path, f"skill does not exist: {target}", target=target))
            else:
                target_path = next(p / "SKILL.md" for p in skills if p.name.lower() == target)
                graph[node].add(target_path.as_posix())
        for match in SCRIPT_RE.finditer(text):
            reference = match.group(0).rstrip(".,;:)")
            if Path(reference).name in HOST_LEVEL_SCRIPTS:
                issues.append(_issue("host_script_reference", "info", path, f"host-level helper, not shipped: {reference}", reference=reference))
                continue
            candidates = [candidate.resolve() for candidate in _script_candidates(reference, path, skills_dir)]
            if not any(candidate.exists() for candidate in candidates):
                # Bare names in portable docs often refer to a project adapter, not a
                # file shipped with this skill. Only explicit relative paths are hard
                # errors; unresolved adapter names remain visible warnings.
                severity = "error" if ("/" in reference or "\\" in reference) and not reference.startswith("../") else "warning"
                issues.append(_issue("missing_script_reference", severity, path, f"script does not exist: {reference}", reference=reference))
        for match in TRIGGER_RE.finditer(text):
            for trigger in re.split(r"[,;|]", match.group(1)):
                trigger = trigger.strip().strip('`"').lower()
                if len(trigger) >= 4:
                    trigger_map.setdefault(trigger, []).append(node)
        # Naive substring contradiction checks ("must" inside "must not",
        # "always" inside policy prose) are noise on instruction-heavy docs.
        # Only report pairs whose both terms appear as standalone words.
        lowered = text.lower()
        for left, right in CONTRADICTIONS:
            left_hit = re.search(rf"(?<![\w-]){re.escape(left)}(?![\w-])", lowered)
            right_hit = re.search(rf"(?<![\w-]){re.escape(right)}(?![\w-])", lowered)
            if left_hit and right_hit:
                # "must not" contains "must": require a bare "must" outside it.
                if left in {"must", "always", "required"}:
                    bare = re.sub(rf"{re.escape(right)}", " ", lowered)
                    left_hit = re.search(rf"(?<![\w-]){re.escape(left)}(?![\w-])", bare)
                if left_hit:
                    issues.append(_issue("obvious_contradiction", "info", path, f"contains both terms: {left} / {right}", terms=[left, right]))

    for trigger, paths in sorted(trigger_map.items()):
        if len(paths) > 1:
            issues.append(_issue("duplicate_trigger", "warning", Path(paths[0]), f"trigger appears in multiple files: {trigger}", trigger=trigger, paths=sorted(paths)))

    visiting: list[str] = []
    visited: set[str] = set()
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        if node in visiting:
            cycle = tuple(visiting[visiting.index(node):] + [node])
            if cycle not in cycles:
                cycles.add(cycle)
                if len(cycle) == 2 or _is_expected_cross_link(list(cycle), skills_dir):
                    # Documented caller/callee shape: visible but not noise.
                    issues.append(_issue("cross_link", "info", Path(node), "documented skill cross-reference", cycle=list(cycle)))
                else:
                    issues.append(_issue("cyclic_reference", "warning", Path(node), "cyclic skill/rule reference detected", cycle=list(cycle)))
            return
        if node in visited:
            return
        visiting.append(node)
        for child in sorted(graph.get(node, ())):
            visit(child)
        visiting.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    issues.sort(key=lambda item: (str(item["kind"]), str(item["path"]), str(item["message"])))
    result = {"status": "passed" if not any(i["severity"] == "error" for i in issues) else "failed", "rules_dir": str(rules_dir), "skills_dir": str(skills_dir), "counts": {"rules": len(rules), "skills": len(skill_names), "alwaysApply": always_apply, "issues": len(issues)}, "issues": issues}
    result["delta"] = _delta(issues, rules_dir)
    return result


def _issue_key(item: dict[str, object]) -> str:
    packed = json.dumps({"kind": item.get("kind"), "path": item.get("path"), "message": item.get("message")}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(packed.encode("utf-8")).hexdigest()[:16]


def _baseline_path(rules_dir: Path) -> Path:
    """Where the previous run's issue keys are stored.

    The baseline must never land inside the canon (writing it next to
    `.cursor/rules` polluted the tree and broke parity hashes), so for the real
    canon it goes to `.doc/harnes/state/`. Any other rules dir - a temp dir in
    the regression test, for example - keeps its own baseline inside itself, so
    two callers cannot see each other's state.
    """
    try:
        resolved = rules_dir.resolve()
    except OSError:
        return rules_dir / ".validate-last.json"
    for parent in resolved.parents:
        if parent.joinpath(".cursor", "rules").is_dir():
            return parent / ".doc" / "harnes" / "state" / ".validate-rules-last.json"
    return resolved / ".validate-last.json"


def _delta(issues: list[dict[str, object]], rules_dir: Path) -> dict[str, object] | None:
    """Compare current issue keys against the previous run (P12).

    First run creates the baseline and returns delta None; later runs report
    added/removed/unchanged counts plus the added keys for review.
    """
    baseline_path = _baseline_path(rules_dir)
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    current = sorted(_issue_key(item) for item in issues)
    if not baseline_path.is_file():
        baseline_path.write_text(json.dumps({"keys": current}, ensure_ascii=False) + "\n", encoding="utf-8")
        return None
    try:
        previous = json.loads(baseline_path.read_text(encoding="utf-8")).get("keys", [])
    except (OSError, ValueError):
        previous = []
    prev_set, cur_set = set(previous), set(current)
    baseline_path.write_text(json.dumps({"keys": current}, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"added": sorted(cur_set - prev_set), "removed": sorted(prev_set - cur_set), "unchanged": len(cur_set & prev_set)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rules-dir", required=True, type=Path)
    parser.add_argument("--skills-dir", required=True, type=Path)
    args = parser.parse_args()
    report = validate(args.rules_dir, args.skills_dir)
    print(json.dumps(report, ensure_ascii=False, separators=(",", ":")))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
