#!/usr/bin/env python3
"""Apply task doc sections written as one JSON file.

The agent writes one JSON with a `sections` object or list. This script turns
it into JSONdoc section operations, keeps existing section ids and order, then
can finalize: apply, render, rebuild the task index and run doc checks.
It never writes the text of a section. Markdown with `## headings` is still
accepted as a legacy fallback.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

TAIL = 800


def read_text(path):
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def slugify(title):
    value = title.strip().lower()
    value = re.sub(r"[^\w\s-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s_]+", "-", value).strip("-")
    return value or "section"


def parse_sections(text):
    sections = []
    current = None
    fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fence = not fence
        if not fence and line.startswith("## "):
            if current and current["title"]:
                sections.append(current)
            current = {"title": line[3:].strip(), "body": []}
            continue
        if current is not None:
            current["body"].append(line)
    if current and current["title"]:
        sections.append(current)
    result = []
    for section in sections:
        body = "\n".join(section["body"]).strip()
        result.append({"title": section["title"], "body_markdown": body})
    return result


def parse_json_sections(text):
    try:
        data = json.loads(text)
    except ValueError as exc:
        raise ValueError(f"invalid JSON: {exc}") from exc
    if not isinstance(data, dict) or "sections" not in data:
        raise ValueError("expected an object with a sections key")
    raw = data["sections"]
    items = []
    if isinstance(raw, dict):
        for title, value in raw.items():
            if isinstance(value, str):
                items.append({"title": title, "body_markdown": value})
            elif isinstance(value, dict):
                body = value.get("body", value.get("body_markdown"))
                if not isinstance(body, str):
                    raise ValueError(f"section {title!r}: body must be a string")
                item = {"title": title, "body_markdown": body}
                if isinstance(value.get("source_ids"), list):
                    item["source_ids"] = value["source_ids"]
                items.append(item)
            else:
                raise ValueError(f"section {title!r}: expected string or object")
    elif isinstance(raw, list):
        for index, value in enumerate(raw):
            if not isinstance(value, dict):
                raise ValueError(f"section {index}: expected an object")
            title = value.get("title")
            body = value.get("body", value.get("body_markdown"))
            if not isinstance(title, str) or not title.strip():
                raise ValueError(f"section {index}: title is required")
            if not isinstance(body, str):
                raise ValueError(f"section {title!r}: body must be a string")
            item = {"title": title.strip(), "body_markdown": body}
            if isinstance(value.get("source_ids"), list):
                item["source_ids"] = value["source_ids"]
            items.append(item)
    else:
        raise ValueError("sections must be an object or a list")
    result = []
    for item in items:
        title = item["title"].strip()
        body = item["body_markdown"].strip()
        if not title:
            raise ValueError("section title must not be empty")
        if not body:
            raise ValueError(f"section {title!r}: body must not be empty")
        result.append({"title": title, "body_markdown": body,
                       "source_ids": item.get("source_ids", [])})
    return result


def load_sections(path):
    text = read_text(path)
    if not text.strip():
        raise ValueError("input is empty")
    if path.suffix.lower() == ".json" or text.lstrip().startswith("{"):
        return parse_json_sections(text)
    return parse_sections(text)


def build_operations(doc, parsed):
    existing = {item["title"].strip().lower(): item
                for item in doc.get("sections", [])}
    numbers = []
    for item in doc.get("sections", []):
        match = re.fullmatch(r"s([0-9]+)", item.get("id", ""))
        if match:
            numbers.append(int(match.group(1)))
    next_number = max(numbers, default=0) + 1
    order = list(doc.get("section_order", []))
    used_anchors = {item.get("anchor") for item in doc.get("sections", [])}
    operations = []
    for section in parsed:
        found = existing.get(section["title"].lower())
        if found:
            value = dict(found)
            value["body_markdown"] = section["body_markdown"]
            if section.get("source_ids"):
                value["source_ids"] = list(section["source_ids"])
        else:
            anchor = slugify(section["title"])
            base = anchor
            suffix = 2
            while anchor in used_anchors:
                anchor = f"{base}-{suffix}"
                suffix += 1
            used_anchors.add(anchor)
            value = {
                "id": f"s{next_number}",
                "title": section["title"],
                "level": 2,
                "parent_id": None,
                "anchor": anchor,
                "anchor_aliases": [],
                "origin": "authored",
                "source_ids": list(section.get("source_ids", [])),
                "body_markdown": section["body_markdown"],
            }
            next_number += 1
        operations.append({"op": "upsert", "collection": "sections",
                           "key": value["id"], "value": value})
        if value["id"] not in order:
            order.append(value["id"])
    operations.append({"op": "set", "collection": "section_order",
                       "key": "section_order", "value": order})
    return operations, order


def run(command, cwd, timeout):
    try:
        proc = subprocess.run(command, cwd=str(cwd), capture_output=True,
                              text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, type(exc).__name__ + ": " + str(exc)
    tail = (proc.stdout + proc.stderr).strip()
    return proc.returncode, tail[-TAIL:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--task", required=True, help="task number")
    parser.add_argument("--input", required=True, help="Markdown file with ## sections")
    parser.add_argument("--apply", action="store_true", help="apply and render")
    parser.add_argument("--finalize", action="store_true",
                        help="apply, render, rebuild index and run checks")
    parser.add_argument("--no-network", action="store_true",
                        help="kept for symmetry with orchestrator")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    if not re.fullmatch(r"[0-9]+", args.task or ""):
        print(json.dumps({"status": "error", "error": "task must be digits"},
                         ensure_ascii=False))
        return 2
    task_dir = root / ".doc" / "tasks" / args.task
    input_path = Path(args.input)
    if not input_path.is_file():
        print(json.dumps({"status": "error",
                          "error": f"input not found: {input_path}"},
                         ensure_ascii=False))
        return 2
    doc_path = task_dir / "task.json"
    if not doc_path.is_file():
        print(json.dumps({"status": "error",
                          "error": "task.json not found; run intake fetch first"},
                         ensure_ascii=False))
        return 2
    try:
        doc = json.loads(doc_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        print(json.dumps({"status": "error", "error": f"task.json: {exc}"},
                         ensure_ascii=False))
        return 2
    try:
        parsed = load_sections(input_path)
    except ValueError as exc:
        print(json.dumps({"status": "error", "error": str(exc)},
                         ensure_ascii=False))
        return 2
    if not parsed:
        print(json.dumps({"status": "error", "error": "no ## sections found"},
                         ensure_ascii=False))
        return 2
    titles = [item["title"].lower() for item in parsed]
    if len(titles) != len(set(titles)):
        print(json.dumps({"status": "error",
                          "error": "duplicate section titles"},
                         ensure_ascii=False))
        return 2

    if args.finalize:
        import intake_state
        identity = intake_state.build_state(root, args.task)["identity"]
        if identity.get("status") != "ok":
            print(json.dumps({"status": "error", "task": args.task,
                              "error": "identity gate failed", "identity": identity},
                             ensure_ascii=False, sort_keys=True))
            return 1

    operations, order = build_operations(doc, parsed)
    digest = hashlib.sha256(
        json.dumps(operations, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:16]
    envelope = {
        "schema_version": "1.0",
        "operation_id": f"doc-sections-{args.task}-{digest}",
        "expected_revision": doc.get("revision", 1),
        "actor": "task-doc",
        "reason": "Разделы документации из Markdown",
        "operations": operations,
        "document": None,
    }
    work = task_dir / "_jsondoc" / "work"
    work.mkdir(parents=True, exist_ok=True)
    envelope_path = work / "doc-sections-envelope.json"
    envelope_path.write_text(
        json.dumps(envelope, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")

    payload = {
        "status": "planned",
        "task": args.task,
        "sections": [item["title"] for item in parsed],
        "order": order,
        "envelope": str(envelope_path),
        "steps": [],
    }
    if not (args.apply or args.finalize):
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    jsondoc = root / ".agents" / "skills" / "documentation-router" / "children" / "task-doc" / "scripts" / "jsondoc.py"
    if not jsondoc.is_file():
        payload.update(status="error", errors=["jsondoc.py not found"])
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2

    code, tail = run([sys.executable, str(jsondoc), "--root", str(root),
                      "apply", "--task", args.task, "--input",
                      str(envelope_path)], root, 120)
    payload["steps"].append({"name": "apply", "status": "ok" if code == 0 else "failed",
                             "exit": code, "tail": tail if code else ""})
    if code != 0:
        payload["status"] = "error"
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    code, tail = run([sys.executable, str(jsondoc), "--root", str(root),
                      "render", "--task", args.task], root, 120)
    payload["steps"].append({"name": "render",
                             "status": "ok" if code == 0 else "failed",
                             "exit": code, "tail": tail if code else ""})
    if code != 0:
        payload["status"] = "error"
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 1

    if not args.finalize:
        payload["status"] = "applied"
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 0

    powershell = shutil.which("pwsh") or shutil.which("powershell")
    commands = [
        ("index", powershell, root / ".agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1",
         ["-AlsoTsv"], 300),
        ("text", sys.executable, root / ".agents/skills/documentation-router/children/project-doc/scripts/check-doc-text.py",
         ["--task", args.task], 120),
        ("structure", powershell, root / ".agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1",
         ["-Path", f".doc/tasks/{args.task}/doc.md"], 120),
    ]
    failures = 0
    for name, exe, script, extra, timeout in commands:
        if not exe or not script.is_file():
            payload["steps"].append({"name": name, "status": "skipped",
                                     "exit": 0, "tail": "script unavailable"})
            continue
        code, tail = run([exe, str(script), *extra], root, timeout)
        status = "ok" if code == 0 else "failed"
        if code != 0:
            failures += 1
        payload["steps"].append({"name": name, "status": status,
                                 "exit": code, "tail": tail if code else ""})

    payload["status"] = "error" if failures else "done"
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
