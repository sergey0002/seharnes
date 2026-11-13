"""Read-only schema and link validation for JSONdoc documents (CLI validate)."""

import re
import urllib.parse
from pathlib import Path

from . import contract, render
from .store import Store

FENCE = re.compile(r"```[\s\S]*?```")
INLINE = re.compile(r"`[^`\n]*`")
LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
EXTERNAL = ("http://", "https://", "mailto:", "tel:", "#", "/", "data:",
            "ftp:", "file:")


def _strip_code(text: str) -> str:
    return INLINE.sub("", FENCE.sub("", text))


def broken_links(view: Path) -> list[str]:
    broken = []
    text = view.read_text(encoding="utf-8", errors="ignore")
    for target in LINK.findall(_strip_code(text)):
        value = target.strip()
        if value.startswith("<") and value.endswith(">"):
            continue
        if value.lower().startswith(EXTERNAL):
            continue
        local = urllib.parse.unquote(value.split("#", 1)[0])
        if not local:
            continue
        if not (view.parent / local).resolve().exists():
            broken.append(value)
    return broken


def validate_target(root: Path, docs: Path, kind: str, key: str,
                    links: bool = False) -> dict:
    store = Store(Path(root), Path(docs))
    doc = store.load(kind, key)
    if doc is None:
        return {"status": "not_found",
                "errors": [{"code": "NOT_FOUND"}], "exit": 1}
    errors = list(contract.validate_document(doc))
    warnings: list[dict] = []
    broken: list[str] = []
    if links:
        render_kind = "task" if kind == "task" else "architecture"
        view = render.view_path(docs, render_kind, key)
        if not view.is_file():
            warnings.append({"code": "view_missing", "path": str(view)})
        else:
            broken = broken_links(view)
    status = "failed" if errors or broken else "ok"
    return {"status": status, "kind": kind, "key": key,
            "revision": doc.get("revision"), "errors": errors,
            "warnings": warnings, "broken_links": broken,
            "exit": 0 if status == "ok" else 1}


def validate_all(root: Path, docs: Path, links: bool = False) -> dict:
    targets = []
    tasks_dir = Path(docs) / "tasks"
    if tasks_dir.is_dir():
        for path in sorted(tasks_dir.iterdir()):
            if path.is_dir() and (path / "task.json").is_file():
                targets.append(("task", path.name))
    arch_dir = Path(docs) / "architecture"
    if arch_dir.is_dir():
        for path in sorted(arch_dir.glob("*.json")):
            targets.append(("arch", path.stem))
    results = [validate_target(root, docs, kind, key, links=links)
               for kind, key in targets]
    failed = [item for item in results if item["status"] != "ok"]
    return {"status": "failed" if failed else "ok",
            "documents": results,
            "counts": {"total": len(results), "failed": len(failed)},
            "exit": 0 if not failed else 1}

