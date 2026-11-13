#!/usr/bin/env python3
"""Validate the harness directory layout and optionally list junk.

Checks are defined in .doc/harnes/state/canon-paths.yaml, section `layout`.

Usage:
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_structure.py
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_structure.py --junk
  python3 .agents/skills/harness-router/children/improvement/scripts/validate_structure.py --json --junk
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import stat
import sys
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT_EXTS = {".sh", ".bash", ".py", ".js", ".mjs", ".cjs", ".ps1", ".cmd", ".bat", ".php"}
DATA_EXTS = {".json", ".yaml", ".yml", ".env", ".md", ".txt", ".ini", ".toml", ".csv"}
JUNK_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini", ".directory"}
JUNK_SUFFIXES = {".bak", ".tmp", ".orig", ".rej", ".swp", ".swo", ".log", ".pyc", ".pyo", ".old"}
JUNK_DIRS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"}
RUNTIME_DIRS = {"data", "workspace", "logs", "volumes", "cache", "out", "_output", ".data", ".state"}
SKIP_DIRS = {".git", "node_modules", "vendor", "templates_c", ".venv", "venv", "mirror", "dialogs", "astra_plan"} | RUNTIME_DIRS
ALLOWED_EMPTY = {"scripts", "docs", "references", "assets", "tests", "children", "agents", "evals", "mcp"}

DEFAULT_LAYOUT = {
    "system": ".tools/scripts",
    "skill": ".agents/skills/{skill}/scripts",
    "stack": ".cursor/mcp-stack",
    "script_skill": ".agents/skills/{skill}/docs/scripts",
    "script_tools": ".agents/skills/harness-router/children/harness-core/docs/scripts/tools",
    "mcp_skill": ".agents/skills/{skill}/docs/mcp",
    "mcp_disabled": ".doc/harnes/archive/mcp",
    "state": ".doc/harnes/state",
    "tools_inventory": ".doc/harnes/state/26-tools.md",
    "forbidden_roots": [".cursor/scripts", ".agents/scripts", ".codex/scripts", ".kilo/scripts"],
    "skill_data": ".doc/skil_data/{skill}",
    "task_tests": ".doc/tasks/{task}/test-runs",
    "temp_dir": ".doc/temp",
    "test_path_markers": ["test", "browser-test", "test-run", "testrun", "test-result", "screenshot"],
}


def project_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
        if (candidate / ".cursor").is_dir() and (candidate / ".agents").is_dir():
            return candidate
    return start


ROOT = project_root(Path(__file__).resolve())


def read_canon_policy(path: Path) -> dict:
    loader_path = Path(__file__).resolve().parents[2] / "harness-core/scripts/canon_paths.py"
    spec = importlib.util.spec_from_file_location("trusted_canon_paths", loader_path)
    if spec is None or spec.loader is None:
        raise ValueError("canonical policy reader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.read_policy(path)


def require_preliminary_policies(root: Path) -> None:
    loader_path = Path(__file__).resolve().parents[2] / "harness-core/scripts/canon_paths.py"
    spec = importlib.util.spec_from_file_location("trusted_canon_paths", loader_path)
    if spec is None or spec.loader is None:
        raise ValueError("canonical policy reader unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_preliminary_policies(root)


def require_canonical_policy(root: Path) -> None:
    relative = ".doc/harnes/state/canon-paths.yaml"
    current = root
    for part in relative.split("/"):
        current = current / part
        try:
            info = current.lstat()
        except OSError as exc:
            raise ValueError("canonical layout policy or an ancestor is missing") from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError("canonical layout policy must not have linked ancestors")
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("canonical layout policy must be a regular file")
    policy = read_canon_policy(current)
    if type(policy.get("schema_version")) is not int or policy["schema_version"] != 1:
        raise ValueError("unsupported canonical policy schema version")
    manifest = policy.get("manifest")
    if not isinstance(manifest, dict) or set(manifest) != {"path", "role", "owner", "required_profiles"}:
        raise ValueError("invalid canonical manifest metadata")
    if (manifest.get("path") != relative or manifest.get("role") != "policy" or manifest.get("owner") != "harness-core"
            or manifest.get("required_profiles") != ["core", "developer", "project"]):
        raise ValueError("invalid canonical manifest identity or profiles")
    roots = policy.get("canonical_roots")
    if not isinstance(roots, dict) or roots.get("path_manifest") != relative:
        raise ValueError("path_manifest must identify this policy exactly once")
    require_preliminary_policies(root)


def load_layout(root: Path) -> dict:
    path = root / ".doc/harnes/state/canon-paths.yaml"
    layout = dict(DEFAULT_LAYOUT)
    if not path.is_file():
        return layout
    block = read_canon_policy(path).get("layout")
    if not isinstance(block, dict):
        raise ValueError("canon-paths.yaml must contain a layout mapping")
    groups = {"scripts": {"system", "skill", "stack"},
              "docs": {"script_skill", "script_tools", "mcp_skill", "mcp_disabled", "state"}}
    lists = {"forbidden_roots", "test_path_markers"}
    direct = set(DEFAULT_LAYOUT) - set().union(*groups.values()) - lists
    def add(key: str, value: str) -> None:
        if not isinstance(value, str) or not value or "\\" in value or value.startswith("/") or any(p in ("", ".", "..") for p in value.split("/")):
            raise ValueError(f"unsafe layout value for {key}")
        layout[key] = value

    for key, value in block.items():
        if key in direct:
            add(key, value)
        elif key in groups:
            if not isinstance(value, dict) or set(value) - groups[key]:
                raise ValueError(f"invalid layout mapping: {key}")
            for child, child_value in value.items():
                add(child, child_value)
        elif key in lists:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(f"invalid layout list: {key}")
            if len(set(value)) != len(value):
                raise ValueError(f"duplicate layout value for {key}")
            for item in value:
                if not item or "\\" in item or item.startswith("/") or any(p in ("", ".", "..") for p in item.split("/")):
                    raise ValueError(f"unsafe layout value for {key}")
            layout[key] = value
        else:
            raise ValueError(f"unknown layout key: {key}")
    return layout


def load_doc_script(root: Path):
    path = root / ".agents/skills/harness-router/children/doc-script/scripts/doc_script.py"
    spec = importlib.util.spec_from_file_location("doc_script_layout", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iter_files(base: Path, suffixes: set[str]):
    if not base.is_dir():
        return
    for path in base.rglob("*"):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix.lower() in suffixes:
            yield path


def collect(root: Path, layout: dict) -> tuple[list[dict], list[dict], list[dict]]:
    errors: list[dict] = []
    warnings: list[dict] = []
    junk: list[dict] = []

    def error(code: str, path: str, message: str, hint: str = "") -> None:
        errors.append({"code": code, "path": path, "message": message, "hint": hint})

    def warn(code: str, path: str, message: str, hint: str = "") -> None:
        warnings.append({"code": code, "path": path, "message": message, "hint": hint})

    def junk_item(path: str, reason: str, hint: str = "") -> None:
        junk.append({"path": path, "reason": reason, "hint": hint})

    # S01 forbidden script pools
    for relative in layout.get("forbidden_roots", []):
        target = root / relative
        if target.exists():
            error("S01", relative, "запрещенный корень скриптов", f"удалить {relative} и перенести содержимое по владельцам")

    # S03/S04 scripts and their docs
    doc_script = None
    try:
        doc_script = load_doc_script(root)
        for script in doc_script.iter_scripts():
            doc = doc_script.doc_path_for(script)
            if doc is None:
                error("S03", str(script.relative_to(root)), "не вычислен владелец документа")
            elif not doc.is_file():
                error("S03", str(script.relative_to(root)), "нет документа скрипта", f"создать {doc.relative_to(root)}")
        for doc in doc_script.find_orphan_docs():
            error("S04", str(doc.relative_to(root)), "документ без скрипта", "удалить документ или восстановить скрипт")
    except Exception as exc:  # noqa: BLE001
        error("S02", ".agents/skills/harness-router/children/doc-script/scripts/doc_script.py", f"не удалось построить карту скриптов: {exc}")

    # S05 .tools directories are described in the inventory document
    inventory = root / layout["tools_inventory"]
    inventory_text = inventory.read_text(encoding="utf-8", errors="ignore") if inventory.is_file() else ""
    tools_root = root / ".tools"
    if tools_root.is_dir():
        for item in sorted(tools_root.iterdir()):
            if item.is_dir() and item.name != "scripts":
                marker = f".tools/{item.name}"
                if marker not in inventory_text:
                    error("S05", marker, "каталог .tools не описан в 26-tools.md", f"добавить строку в {layout['tools_inventory']}")

    # S06 every skill script is declared in skill.json
    for skill_md in sorted((root / ".agents/skills").rglob("SKILL.md")):
        skill = skill_md.parent
        scripts_dir = skill / "scripts"
        manifest = skill / "skill.json"
        if not scripts_dir.is_dir() or not manifest.is_file():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        declared = set((data.get("resources") or {}).get("scripts") or [])
        for path in sorted(scripts_dir.rglob("*")):
            if not path.is_file() or any(part in SKIP_DIRS or part in JUNK_DIRS for part in path.parts):
                continue
            if path.suffix.lower() not in SCRIPT_EXTS:
                continue
            if doc_script is not None and doc_script.classify_script(path)[0] != "entrypoint":
                continue
            relative = path.relative_to(skill).as_posix()
            if relative not in declared:
                warn("S06", str(path.relative_to(root)), "скрипт не объявлен в skill.json.resources.scripts", f"добавить {relative}")

    # S07/S08 MCP command paths and disabled-server docs
    mcp_path = root / ".cursor/mcp.json"
    if mcp_path.is_file():
        try:
            mcp_data = json.loads(mcp_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            error("S07", ".cursor/mcp.json", f"не читается mcp.json: {exc}")
            mcp_data = {}
        for server, config in sorted((mcp_data.get("mcpServers") or {}).items()):
            if config.get("disabled"):
                archived = root / layout["mcp_disabled"] / f"{server}.md"
                skill_doc = root / ".agents/skills" / server / "docs/mcp" / f"{server}.md"
                if not archived.is_file() and not skill_doc.is_file():
                    error("S08", str(archived.relative_to(root)), f"нет документа отключенного MCP: {server}", "добавить документ в архив")
                continue
            values = [config.get("command")] + list(config.get("args") or [])
            for value in values:
                if not isinstance(value, str):
                    continue
                expanded = value.replace("${workspaceFolder}", str(root)).replace("${workspaceRoot}", str(root))
                if expanded.startswith("/var/www/html/"):
                    expanded = str(root / expanded[len("/var/www/html/"):])
                if not expanded.startswith(("/", ".")):
                    continue
                if Path(expanded).suffix.lower() not in SCRIPT_EXTS:
                    continue
                command_path = Path(expanded)
                if not command_path.is_absolute():
                    command_path = root / command_path
                if not command_path.exists():
                    error("S07", ".cursor/mcp.json", f"путь команды MCP не существует: {server}: {expanded}", "исправить путь или удалить сервер")

    # S09 stale paths in active rules and docs
    stale_roots = layout.get("forbidden_roots", [])
    active_bases = [root / ".cursor/rules", root / ".agents/skills", root / layout["state"]]
    for base in active_bases:
        is_state = base == root / layout["state"]
        for path in iter_files(base, {".md", ".mdc"}):
            if is_state and (
                re.search(r"-\d{4}-\d{2}-\d{2}\.md$", path.name)
                or re.search(r"(?mi)^status:\s*outdated\s*$", path.read_text(encoding="utf-8", errors="ignore")[:400])
            ):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if re.search(r"(?i)legacy|истори|history|устарел|2026-\d\d-\d\d", line):
                    continue
                for bad in stale_roots:
                    if bad in line:
                        if is_state:
                            warn("S09", f"{path.relative_to(root)}:{number}", f"устаревший путь {bad}", "обновить путь")
                        else:
                            error("S09", f"{path.relative_to(root)}:{number}", f"устаревший путь {bad}", "обновить путь")
                        break

    # S10/S11/S12 skill data roots and test evidence paths
    known_skills = {skill_md.parent.name for skill_md in (root / ".agents/skills").rglob("SKILL.md")}
    skill_data_pattern = re.compile(r"\.doc/skil_data/([A-Za-z0-9._-]+)((?:/[A-Za-z0-9._-]+)*)")
    markers = [str(marker).lower() for marker in layout.get("test_path_markers", [])]
    for base in (root / ".agents/skills", root / ".cursor/rules"):
        for path in iter_files(base, {".md", ".mdc"}):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                for match in skill_data_pattern.finditer(line):
                    declared, suffix = match.group(1), match.group(2)
                    location = f"{path.relative_to(root)}:{number}"
                    parts = [part.lower() for part in suffix.split("/") if part]
                    if set(declared) <= {"."}:
                        continue
                    if declared not in known_skills:
                        error("S10", location, f"данные скила лежат в неизвестном каталоге {declared}",
                              f"использовать {layout['skill_data']}")
                    if any(part in {"tmp", "temp"} for part in parts):
                        error("S11", location, "временные файлы лежат в каталоге данных скила",
                              f"перенести в {layout['temp_dir']}/")
                    if markers and any(marker in part for part in parts for marker in markers):
                        error("S12", location, "результаты тестов лежат вне каталога задачи",
                              f"перенести в {layout['task_tests']}")

    return errors, warnings, junk


def collect_junk(root: Path, layout: dict) -> list[dict]:
    junk: list[dict] = []
    seen: set[str] = set()

    def add(path: Path, reason: str, hint: str = "") -> None:
        relative = path.relative_to(root).as_posix()
        if relative not in seen:
            seen.add(relative)
            junk.append({"path": relative, "reason": reason, "hint": hint})

    for base_name in (".agents/skills", ".tools", ".cursor/rules", ".cursor/mcp-stack", layout["state"]):
        base = root / base_name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if path.name in JUNK_NAMES or path.suffix.lower() in JUNK_SUFFIXES or any(part in JUNK_DIRS for part in path.parts):
                add(path, "временный или системный файл", "удалить")
            if path.is_dir() and path.name not in ALLOWED_EMPTY:
                try:
                    is_empty = not any(path.iterdir())
                except (PermissionError, OSError):
                    continue
                if is_empty:
                    add(path, "пустой каталог", "удалить")

    for doc in (root / ".agents/skills").rglob("docs/scripts/*"):
        if "docs" not in doc.parts:
            continue
        if doc.is_file() and doc.suffix.lower() != ".md" and doc.name != ".gitkeep":
            add(doc, "лишний файл в docs/scripts", "перенести в правильный каталог или удалить")

    for path in (root / ".agents/skills").rglob("scripts/*"):
        if not path.is_file() or path.parent.name != "scripts":
            continue
        if path.suffix.lower() in SCRIPT_EXTS | DATA_EXTS or path.name.startswith("."):
            continue
        add(path, "лишний файл в scripts", "перенести данные в assets или references")

    for relative in layout.get("forbidden_roots", []):
        target = root / relative
        if target.exists():
            add(target, "запрещенный корень скриптов", "удалить после переноса")

    return sorted(junk, key=lambda item: item["path"])


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate harness directory layout")
    parser.add_argument("--root", default=".")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--warn-only", action="store_true")
    parser.add_argument("--junk", action="store_true", help="показать лишние файлы и каталоги")
    parser.add_argument("--fail-on-junk", action="store_true", help="вернуть код 1, если найден хлам")
    parser.add_argument("--require-policy", action="store_true", help="требовать канонический файл раскладки")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        if args.require_policy:
            require_canonical_policy(root)
        layout = load_layout(root)
    except (OSError, UnicodeError, ValueError) as exc:
        if args.json:
            print(json.dumps({"status": "failed", "errors": [{"code": "POLICY", "path": ".doc/harnes/state/canon-paths.yaml", "message": str(exc)}], "warnings": [], "junk": []}, ensure_ascii=False, indent=2))
        else:
            print(f"ERROR POLICY .doc/harnes/state/canon-paths.yaml: {exc}")
        return 1
    errors, warnings, _ = collect(root, layout)
    junk = collect_junk(root, layout) if args.junk else []

    if args.json:
        payload = {
            "status": "failed" if errors or (args.fail_on_junk and junk) else "passed",
            "errors": errors,
            "warnings": warnings,
            "junk": junk,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        for item in errors:
            print(f"ERROR {item['code']} {item['path']}: {item['message']}")
            if item.get("hint"):
                print(f"      hint: {item['hint']}")
        for item in warnings:
            print(f"WARN  {item['code']} {item['path']}: {item['message']}")
            if item.get("hint"):
                print(f"      hint: {item['hint']}")
        for item in junk:
            print(f"JUNK  {item['path']}: {item['reason']}")
            if item.get("hint"):
                print(f"      hint: {item['hint']}")
        print(f"errors: {len(errors)}, warnings: {len(warnings)}, junk: {len(junk)}")

    if errors and not args.warn_only:
        return 1
    if args.fail_on_junk and junk:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
