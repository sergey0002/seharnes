#!/usr/bin/env python3
"""Find skills that exist outside the package baseline.

The package baseline is written by export or by --write-baseline. Without a
baseline the scan still reports view-only skills, but cannot tell a packaged
canonical skill from one added after migration.

Usage:
  python3 scan_local_skills.py --root .
  python3 scan_local_skills.py --root . --json
  python3 scan_local_skills.py --root . --write-baseline
"""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

CANON_ROOT = ".agents/skills"
DEFAULT_BASELINE = ".doc/skil_data/harness-core/kit-manifest.json"
VIEW_ROOTS = (
    ("codex", ".codex/skills"),
    ("qoder", ".qoder/skills"),
    ("qwen", ".qwen/skills"),
    ("kilo", ".kilo/skills"),
)
SKIP_PARTS = {".git", "__pycache__", ".data", ".state", "node_modules", "vendor"}
TEXT_EXTENSIONS = {
    ".md", ".mdc", ".markdown", ".json", ".jsonc", ".toml", ".yaml", ".yml",
    ".py", ".ps1", ".sh", ".js", ".mjs", ".cjs", ".ts", ".txt", ".env",
    ".example", ".dist", ".xml", ".html", ".css", ".tpl",
}


@dataclass(frozen=True)
class Skill:
    id: str
    name: str
    env: str
    path: str
    digest: str
    files: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "env": self.env,
            "path": self.path,
            "digest": self.digest,
        }


def file_hashes(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(path)
        if any(part in SKIP_PARTS or part.startswith(".") for part in relative.parts):
            continue
        data = item.read_bytes()
        if b"\0" not in data[:8192]:
            data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        result[relative.as_posix()] = hashlib.sha256(data).hexdigest()
    return result


def digest_hashes(hashes: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(hashes):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(hashes[relative]))
    return digest.hexdigest()


def digest_dir(path: Path) -> str:
    return digest_hashes(file_hashes(path))


def find_skills(root: Path, relative_root: str, env: str, include_generated: bool = False) -> list[Skill]:
    base = root / relative_root
    if not base.is_dir():
        return []
    result: list[Skill] = []
    for skill_md in sorted(base.rglob("SKILL.md")):
        if not skill_md.is_file():
            continue
        folder = skill_md.parent
        relative = folder.relative_to(base)
        ident = folder.name if relative == Path(".") else relative.as_posix()
        if env == "qwen" and not include_generated and folder.name.startswith("rule-"):
            continue
        hashes = file_hashes(folder)
        result.append(Skill(
            id=ident,
            name=folder.name,
            env=env,
            path=folder.relative_to(root).as_posix(),
            digest=digest_hashes(hashes),
            files=hashes,
        ))
    return result


def read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def load_baseline(path: Path) -> dict[str, dict] | None:
    data = read_json(path)
    if data is None:
        return None
    skills = data.get("skills")
    return skills if isinstance(skills, dict) else {}


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=str(path.parent), prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
        os.replace(temp_name, path)
    except BaseException:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
        raise


def baseline_payload(canonical: list[Skill], source: str) -> dict:
    return {
        "schema": 1,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": source,
        "skills": {
            skill.id: {"name": skill.name, "digest": skill.digest}
            for skill in sorted(canonical, key=lambda item: item.id)
        },
    }


def scan(root: Path, baseline_path: Path, include_generated: bool = False) -> dict:
    canonical = find_skills(root, CANON_ROOT, "agents", include_generated=True)
    canonical_by_id = {skill.id: skill for skill in canonical}
    canonical_by_name: dict[str, list[Skill]] = {}
    for skill in canonical:
        canonical_by_name.setdefault(skill.name, []).append(skill)

    baseline = load_baseline(baseline_path)
    baseline_skills = baseline or {}
    discovery = read_json(root / ".doc/skil_data/environment-sync/discovery.json") or {}
    skills: dict[str, list[dict]] = {
        "canon_local": [],
        "view_local": [],
        "package_view": [],
        "conflict": [],
        "package_modified": [],
        "mirror_drift": [],
        "name_collision": [],
        "missing": [],
    }

    for skill in canonical:
        if baseline is None:
            continue
        if skill.id not in baseline_skills:
            skills["canon_local"].append(skill.as_dict())
        elif skill.digest != str(baseline_skills[skill.id].get("digest", "")):
            skills["package_modified"].append(skill.as_dict())

    view_only: dict[str, list[Skill]] = {}
    for env, relative_root in VIEW_ROOTS:
        for skill in find_skills(root, relative_root, env, include_generated):
            wrapper_path = root / skill.path / "SKILL.md"
            receipt_key = f"{skill.path}/SKILL.md"
            same_name = canonical_by_name.get(skill.name, [])
            if env == "qwen" and len(same_name) == 1 and set(skill.files) == {"SKILL.md"}:
                raw = wrapper_path.read_bytes()
                canonical_path = f"{same_name[0].path}/SKILL.md"
                if (discovery.get(receipt_key) == hashlib.sha256(raw).hexdigest()
                        and b"<!-- generated discovery wrapper; do not edit -->" in raw
                        and f"Read `{canonical_path}`".encode("utf-8") in raw):
                    continue
            canonical_skill = canonical_by_id.get(skill.id)
            if canonical_skill is not None:
                subset = {
                    relative: skill.files[relative]
                    for relative in canonical_skill.files
                    if relative in skill.files
                }
                if subset != canonical_skill.files:
                    skills["mirror_drift"].append(skill.as_dict())
                continue
            if skill.name in canonical_by_name:
                skills["name_collision"].append(skill.as_dict())
                continue
            view_only.setdefault(skill.id, []).append(skill)

    for ident, items in sorted(view_only.items()):
        if ident in baseline_skills:
            for item in items:
                skills["package_view"].append(item.as_dict())
            continue
        entry = {
            "id": ident,
            "name": items[0].name,
            "sources": [item.as_dict() for item in sorted(items, key=lambda value: value.env)],
        }
        if len(items) > 1 and len({item.digest for item in items}) > 1:
            skills["conflict"].append(entry)
        else:
            skills["view_local"].append(entry)

    for ident in sorted(baseline_skills):
        if ident not in canonical_by_id:
            entry = baseline_skills[ident]
            skills["missing"].append({
                "id": ident,
                "name": entry.get("name", ident),
                "expected_digest": entry.get("digest", ""),
            })

    counts = Counter({key: len(value) for key, value in skills.items()})
    installable = [item["id"] for item in skills["canon_local"]]
    installable.extend(item["id"] for item in skills["view_local"])
    return {
        "status": "ok",
        "root": str(root),
        "baseline": {
            "path": str(baseline_path),
            "exists": baseline is not None,
            "skills": len(baseline_skills),
        },
        "canonical": len(canonical),
        "counts": dict(sorted(counts.items())),
        "skills": skills,
        "installable": sorted(set(installable)),
        "errors": [],
    }


def print_human(report: dict) -> None:
    baseline = report["baseline"]
    print("Проверка скилов вне пакета")
    print(f"  канон: {report['canonical']} скилов")
    print(f"  манифест пакета: {baseline['path']}")
    if not baseline["exists"]:
        print("  манифест не найден: канон нельзя отличить от пакета")
        print("  создать: python3 .agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py --write-baseline")
    counts = report["counts"]
    print(f"  в каноне, нет в пакете: {counts.get('canon_local', 0)}")
    print(f"  только в среде: {counts.get('view_local', 0)}")
    print(f"  пакетные скилы вне канона: {counts.get('package_view', 0)}")
    print(f"  конфликт версий: {counts.get('conflict', 0)}")
    print(f"  изменены относительно пакета: {counts.get('package_modified', 0)}")
    print(f"  зеркала расходятся с каноном: {counts.get('mirror_drift', 0)}")
    print(f"  имя занято другим скилом: {counts.get('name_collision', 0)}")
    print(f"  нет на диске: {counts.get('missing', 0)}")

    for key in ("canon_local", "package_modified", "mirror_drift", "name_collision"):
        for item in report["skills"][key]:
            print(f"  {key}: {item['id']} ({item['path']})")
    for key in ("view_local", "conflict"):
        for item in report["skills"][key]:
            sources = ", ".join(source["env"] for source in item["sources"])
            print(f"  {key}: {item['id']} ({sources})")
    for item in report["skills"]["missing"]:
        print(f"  missing: {item['id']}")

    if report["installable"]:
        names = " ".join(report["installable"])
        print("  установить: python3 .agents/skills/harness-router/children/add-skill/scripts/add_skill.py --name <name> --yes")
        print(f"  кандидаты: {names}")
    if report["skills"]["conflict"]:
        print("  конфликтующие версии требуют --from codex|qoder|qwen|kilo")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--baseline", default="", help=f"baseline path, default {DEFAULT_BASELINE}")
    parser.add_argument("--write-baseline", action="store_true", help="write baseline from the current canon")
    parser.add_argument("--include-generated", action="store_true", help="include Qwen rule-* skills")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    baseline_path = Path(args.baseline).resolve() if args.baseline else root / DEFAULT_BASELINE
    canonical = find_skills(root, CANON_ROOT, "agents", include_generated=True)
    if args.write_baseline:
        write_json_atomic(baseline_path, baseline_payload(canonical, "canon"))
        payload = {
            "status": "ok",
            "baseline": str(baseline_path),
            "skills": len(canonical),
        }
        print(json.dumps(payload, ensure_ascii=False) if args.json else f"baseline written: {baseline_path} ({len(canonical)} skills)")
        return 0

    report = scan(root, baseline_path, args.include_generated)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
