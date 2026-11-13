#!/usr/bin/env python3
"""Collect task requirements from a conversation and save them as one task document.

The script keeps every draft in `.doc/skil_data/task-spec/{id}/`:
`notes.md` holds the user's remarks verbatim, `attachments/` holds screenshots and
files, `task.md` is the final task statement and `meta.json` is the draft state.

Subcommands:
  start    create a new draft with a unique id
  add      append a remark, bug report or decision
  attach   copy a screenshot or file into the draft
  show     print the draft notes and attachment list
  finalize validate attachment links and publish task.md
  current  print the active draft
  use      switch the active draft
  list     list drafts
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote

DATA_REL = Path(".doc") / "skil_data" / "task-spec"
CURRENT = "current.json"
INDEX = "index.json"
META = "meta.json"
NOTES = "notes.md"
TASK = "task.md"
ATTACHMENTS = "attachments"
LINK_RE = re.compile(r"!?\[[^\]]*\]\(\.?/?(attachments/[^)\s]+)\)")

TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def fail(message: str, code: int = 1) -> "NoReturn":
    print(json.dumps({"status": "error", "error": message}, ensure_ascii=False))
    raise SystemExit(code)


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")


def now_id() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def slugify(value: str, fallback: str) -> str:
    value = (value or "").strip().lower()
    parts: list[str] = []
    for char in value:
        if char in TRANSLIT:
            parts.append(TRANSLIT[char])
        elif char.isascii() and char.isalnum():
            parts.append(char)
        elif char in " _-./":
            parts.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(parts)).strip("-")
    return (slug or fallback)[:48].strip("-") or fallback


def read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def data_dir(root: Path) -> Path:
    return root / DATA_REL


def active_id(root: Path) -> str:
    current = read_json(data_dir(root) / CURRENT)
    value = current.get("id")
    return str(value) if value else ""


def resolve(root: Path, draft_id: str | None) -> Path:
    data = data_dir(root)
    value = draft_id or active_id(root)
    if not value:
        fail("нет активного черновика. Выполните: task_spec.py start", 2)
    draft = data / value
    if not (draft / META).is_file():
        fail(f"черновик не найден: {value}", 2)
    return draft


def notes_header(meta: dict) -> str:
    return (
        "# Черновик постановки задачи\n\n"
        "<!-- meta\n"
        "type: draft\n"
        f"status: {meta.get('status', 'collecting')}\n"
        f"created: {meta.get('created', '')}\n"
        "-->\n\n"
        "## Замечания\n\n"
        "## Вложения\n"
    )


def append_section(path: Path, heading: str, block: str) -> None:
    text = path.read_text(encoding="utf-8") if path.is_file() else ""
    marker = f"\n## {heading}\n"
    position = text.find(marker)
    if position == -1:
        text = text.rstrip() + f"\n\n## {heading}\n\n{block}\n"
    else:
        start = position + len(marker)
        next_heading = text.find("\n## ", start)
        insert_at = len(text.rstrip()) if next_heading == -1 else next_heading
        before = text[:insert_at].rstrip()
        after = text[insert_at:]
        text = before + "\n\n" + block + "\n" + after
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def touch(meta_path: Path) -> None:
    meta = read_json(meta_path)
    meta["updated"] = now()
    write_json(meta_path, meta)


def collect_index(data: Path, root: Path) -> list[dict]:
    items: list[dict] = []
    if not data.is_dir():
        return items
    for draft in sorted(data.iterdir(), key=lambda item: item.name, reverse=True):
        if not draft.is_dir():
            continue
        meta = read_json(draft / META)
        if not meta:
            continue
        attachments = draft / ATTACHMENTS
        count = len([p for p in attachments.iterdir() if p.is_file()]) if attachments.is_dir() else 0
        items.append({
            "id": draft.name,
            "title": meta.get("title", ""),
            "status": meta.get("status", "collecting"),
            "created": meta.get("created", ""),
            "updated": meta.get("updated", ""),
            "path": relative(root, draft),
            "attachments": count,
            "has_task": (draft / TASK).is_file(),
        })
    return items


def update_index(data: Path, root: Path) -> None:
    write_json(data / INDEX, {"version": 1, "drafts": collect_index(data, root)})


def cmd_start(root: Path, args: argparse.Namespace) -> None:
    data = data_dir(root)
    data.mkdir(parents=True, exist_ok=True)
    title = (args.title or "").strip()
    slug = slugify(args.slug or title, "task")
    stamp = now_id()
    draft_id = f"{stamp}-{slug}"
    suffix = 2
    while (data / draft_id).exists():
        draft_id = f"{stamp}-{slug}-{suffix}"
        suffix += 1
    draft = data / draft_id
    (draft / ATTACHMENTS).mkdir(parents=True)
    meta = {
        "id": draft_id,
        "title": title,
        "slug": slug,
        "status": "collecting",
        "created": now(),
        "updated": now(),
    }
    write_json(draft / META, meta)
    (draft / NOTES).write_text(notes_header(meta), encoding="utf-8")
    write_json(data / CURRENT, {"id": draft_id, "updated": now()})
    update_index(data, root)
    print(json.dumps({
        "status": "collecting",
        "id": draft_id,
        "dir": relative(root, draft),
        "task": relative(root, draft / TASK),
    }, ensure_ascii=False))


def command_text(args: argparse.Namespace) -> str:
    if getattr(args, "stdin", False) or args.text == "-":
        return sys.stdin.read()
    return args.text or ""


def cmd_add(root: Path, args: argparse.Namespace) -> None:
    draft = resolve(root, args.id)
    text = command_text(args).strip()
    if not text:
        fail("пустой текст замечания", 2)
    notes = draft / NOTES
    existing = notes.read_text(encoding="utf-8") if notes.is_file() else ""
    number = len(re.findall(r"(?m)^### R-", existing)) + 1
    quoted = "\n".join("> " + line if line.strip() else ">" for line in text.splitlines())
    block = f"### R-{number:04d} ({now()}, {args.kind})\n\n{quoted}"
    append_section(notes, "Замечания", block)
    touch(draft / META)
    update_index(data_dir(root), root)
    print(json.dumps({"status": "recorded", "id": draft.name, "remark": f"R-{number:04d}"}, ensure_ascii=False))


def cmd_attach(root: Path, args: argparse.Namespace) -> None:
    draft = resolve(root, args.id)
    source = Path(args.path).expanduser()
    if not source.is_file():
        fail(f"файл не найден: {source}", 2)
    source = source.resolve()
    attachments = draft / ATTACHMENTS
    attachments.mkdir(parents=True, exist_ok=True)
    existing = [p for p in attachments.iterdir() if p.is_file()]
    number = len(existing) + 1
    suffix = re.sub(r"[^a-z0-9.]", "", source.suffix.lower())
    stem = slugify(source.stem, "file")
    name = f"{number:03d}-{stem}{suffix}"
    unique = 2
    while (attachments / name).exists():
        name = f"{number:03d}-{stem}-{unique}{suffix}"
        unique += 1
    shutil.copy2(source, attachments / name)
    caption = (args.caption or "").strip()
    line = f"- [A-{number:04d}] [{name}](attachments/{name})"
    if caption:
        line += f" - {caption}"
    append_section(draft / NOTES, "Вложения", line)
    touch(draft / META)
    update_index(data_dir(root), root)
    print(json.dumps({
        "status": "attached",
        "id": draft.name,
        "attachment": f"A-{number:04d}",
        "path": relative(root, attachments / name),
        "link": f"attachments/{name}",
    }, ensure_ascii=False))


def cmd_show(root: Path, args: argparse.Namespace) -> None:
    draft = resolve(root, args.id)
    attachments = draft / ATTACHMENTS
    files = sorted(p.name for p in attachments.iterdir() if p.is_file()) if attachments.is_dir() else []
    print(json.dumps({
        "id": draft.name,
        "dir": relative(root, draft),
        "meta": read_json(draft / META),
        "notes": (draft / NOTES).read_text(encoding="utf-8") if (draft / NOTES).is_file() else "",
        "attachments": files,
        "task_exists": (draft / TASK).is_file(),
    }, ensure_ascii=False))


def cmd_finalize(root: Path, args: argparse.Namespace) -> None:
    draft = resolve(root, args.id)
    source = Path(args.file).expanduser()
    if not source.is_file():
        fail(f"файл задачи не найден: {source}", 2)
    source = source.resolve()
    text = source.read_text(encoding="utf-8")
    links = sorted({unquote(link) for link in LINK_RE.findall(text)})
    missing = [link for link in links if not (draft / link).is_file()]
    if missing:
        fail("ссылки на отсутствующие вложения: " + ", ".join(missing), 1)
    target = draft / TASK
    if source != target:
        shutil.copy2(source, target)
    notes = draft / NOTES
    if notes.is_file():
        notes.write_text(
            re.sub(r"(?m)^status: collecting$", "status: formulated", notes.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
    meta = read_json(draft / META)
    meta["status"] = "formulated"
    meta["formulated_at"] = now()
    meta["updated"] = now()
    if args.title:
        meta["title"] = args.title.strip()
    write_json(draft / META, meta)
    update_index(data_dir(root), root)
    print(json.dumps({
        "status": "formulated",
        "id": draft.name,
        "dir": relative(root, draft),
        "task": relative(root, target),
        "attachments": len([p for p in (draft / ATTACHMENTS).iterdir() if p.is_file()]) if (draft / ATTACHMENTS).is_dir() else 0,
        "links": len(links),
    }, ensure_ascii=False))


def cmd_current(root: Path, args: argparse.Namespace) -> None:
    draft_id = active_id(root)
    if not draft_id:
        print(json.dumps({"current": None}, ensure_ascii=False))
        return
    draft = data_dir(root) / draft_id
    if not (draft / META).is_file():
        print(json.dumps({"current": None, "stale": draft_id}, ensure_ascii=False))
        return
    print(json.dumps({"current": draft_id, "dir": relative(root, draft), "meta": read_json(draft / META)}, ensure_ascii=False))


def cmd_use(root: Path, args: argparse.Namespace) -> None:
    draft = data_dir(root) / args.id
    if not (draft / META).is_file():
        fail(f"черновик не найден: {args.id}", 2)
    write_json(data_dir(root) / CURRENT, {"id": args.id, "updated": now()})
    print(json.dumps({"status": "active", "id": args.id, "dir": relative(root, draft)}, ensure_ascii=False))


def cmd_list(root: Path, args: argparse.Namespace) -> None:
    print(json.dumps({"drafts": collect_index(data_dir(root), root)}, ensure_ascii=False))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    sub = parser.add_subparsers(dest="command", required=True)

    start = sub.add_parser("start", help="create a new draft")
    start.add_argument("--title", default="")
    start.add_argument("--slug", default="")

    add = sub.add_parser("add", help="append a remark")
    add.add_argument("--text", default="", help="remark text, or - to read stdin")
    add.add_argument("--stdin", action="store_true", help="read remark text from stdin")
    add.add_argument("--kind", default="remark", choices=["remark", "bug", "requirement", "decision", "question"])
    add.add_argument("--id", default="")

    attach = sub.add_parser("attach", help="copy a screenshot or file")
    attach.add_argument("--path", required=True)
    attach.add_argument("--caption", default="")
    attach.add_argument("--id", default="")

    show = sub.add_parser("show", help="print the draft")
    show.add_argument("--id", default="")

    finalize = sub.add_parser("finalize", help="validate links and publish task.md")
    finalize.add_argument("--file", required=True)
    finalize.add_argument("--title", default="")
    finalize.add_argument("--id", default="")

    current = sub.add_parser("current", help="print the active draft")
    current.set_defaults()

    use = sub.add_parser("use", help="switch the active draft")
    use.add_argument("--id", required=True)

    sub.add_parser("list", help="list drafts")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    commands = {
        "start": cmd_start,
        "add": cmd_add,
        "attach": cmd_attach,
        "show": cmd_show,
        "finalize": cmd_finalize,
        "current": cmd_current,
        "use": cmd_use,
        "list": cmd_list,
    }
    commands[args.command](root, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
