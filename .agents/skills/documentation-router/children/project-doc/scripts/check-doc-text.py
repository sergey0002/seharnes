#!/usr/bin/env python3
"""Check doc.md section texts for task-doc quality rules.

Exit 0: no errors (warnings allowed).
Exit 1: errors found.
Exit 2: input missing or invalid.

With --baseline only sections whose sha256 differs from the accepted baseline
are checked, so legacy text does not block a new stage. --write-baseline records
the accepted state after a human or agent review.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

FORBIDDEN_CHARS = ("—", "–", "«", "»")
FENCE = re.compile(r"```[\s\S]*?```")
INLINE = re.compile(r"`[^`\n]*`")
QUOTED = re.compile(r"«[^»\n]*»|\"[^\"\n]*\"")
VAGUE = re.compile(
    r"\b(как правило|обычно|при необходимости|по возможности|может быть)\b", re.I)
STRUCT_COMMENT = re.compile(
    r"<!--\s*(?:meta\b|generated from\b|updated:|task-dir:|project-root:)"
    r"[\s\S]*?-->")
HTML_COMMENT = re.compile(r"<!--")
ARRAY_LEAK = re.compile(r"\bArray\b(?!\s*\.)")
TASK_REF = re.compile(r"(?<!\]\()#(\d{3,5})\b")


def sections(text: str) -> dict[str, str]:
    result = {}
    current = "preamble"
    buffer = []
    for line in text.splitlines():
        if line.startswith("## "):
            result[current] = "\n".join(buffer).strip()
            current = line[3:].strip()
            buffer = []
        else:
            buffer.append(line)
    result[current] = "\n".join(buffer).strip()
    return result


def section_hashes(text: str) -> dict[str, str]:
    hashes = {}
    for title, body in sections(text).items():
        if title == "preamble":
            continue
        hashes[title] = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return hashes


def _mask_block(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def _clean_line(line: str) -> str:
    return QUOTED.sub("", INLINE.sub("", line))


def _append_error(errors: list[dict], code: str, line: int, section: str,
                  snippet: str, **extra: object) -> None:
    item = {"code": code, "line": line, "section": section,
            "snippet": snippet.strip()[:160]}
    item.update(extra)
    errors.append(item)


def check(task_id: str, path: Path, baseline: Path | None = None,
          write_baseline: Path | None = None) -> dict:
    errors: list[dict] = []
    warnings: list[dict] = []
    if not path.is_file():
        return {"task": task_id, "status": "missing",
                "errors": [{"code": "file_not_found", "path": str(path)}],
                "warnings": []}

    text = path.read_text(encoding="utf-8", errors="replace")
    section_map = section_hashes(text)
    accepted = {}
    if baseline is not None and baseline.is_file():
        try:
            accepted = json.loads(baseline.read_text(encoding="utf-8"))
            accepted = accepted.get("sections", {})
        except (OSError, json.JSONDecodeError):
            accepted = {}

    changed = {title for title, digest in section_map.items()
               if accepted.get(title) != digest}
    check_all = not accepted

    prose = _mask_block_blocks(text)

    current = "preamble"
    for lineno, raw in enumerate(prose.splitlines(), 1):
        if raw.startswith("## "):
            current = raw[3:].strip()
            continue
        if not check_all and current not in changed:
            continue
        cleaned = _clean_line(raw)
        for char in FORBIDDEN_CHARS:
            if char in cleaned:
                _append_error(errors, "forbidden_char", lineno, current, raw,
                              char=char)
        if ARRAY_LEAK.search(cleaned):
            _append_error(errors, "php_array_leak", lineno, current, raw)
        if HTML_COMMENT.search(raw):
            _append_error(errors, "html_comment", lineno, current, raw)
        for match in VAGUE.finditer(cleaned):
            warnings.append({"code": "vague_word", "value": match.group(0),
                             "line": lineno, "section": current})

    parsed = sections(text)
    for title, body in parsed.items():
        if title == "preamble":
            continue
        if not body:
            warnings.append({"code": "empty_section", "section": title})
            continue
        if not check_all and title not in changed:
            continue
        if title == "Краткое описание":
            plain = re.sub(r"[*`_#>\[\]()]", "", body)
            if len(plain) < 80:
                warnings.append({"code": "short_summary", "length": len(plain),
                                 "section": title})
            if "```" in body:
                warnings.append({"code": "summary_has_code", "section": title})
        if title in ("Подводные камни", "История решений"):
            if "Симптом" not in body or "Решение" not in body:
                warnings.append({"code": "finding_without_structure",
                                 "section": title})
        if title == "Связанные задачи":
            for line in body.splitlines():
                if line.strip().startswith(("-", "*")):
                    refs = TASK_REF.findall(line)
                    if refs and "](" not in line:
                        warnings.append({"code": "plain_task_ref",
                                         "line": line.strip()[:120],
                                         "section": title})
        if title.startswith("Покрытие условий"):
            for line in body.splitlines():
                if not line.strip().startswith("|"):
                    continue
                cells = [cell.strip()
                         for cell in line.strip().strip("|").split("|")]
                if len(cells) < 3 or cells[0] in ("Условие", "---"):
                    continue
                condition = cells[0]
                if "`" in condition or "::" in condition or "->" in condition \
                        or "→" in condition:
                    _append_error(errors, "condition_has_code",
                                  _line_of(text, line), title, condition,
                                  condition=condition[:120])
        if title == "История изменений":
            for line in body.splitlines():
                stripped = line.strip()
                if stripped.startswith("-") and stripped not in ("-", "---") \
                        and not re.match(r"-\s+\d{4}-\d{2}-\d{2}", stripped):
                    warnings.append({"code": "history_entry_format",
                                     "line": stripped[:120],
                                     "section": title})

    result = {
        "task": task_id,
        "file": str(path),
        "status": "failed" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "baseline": str(baseline) if baseline is not None else None,
        "checked_sections": len(section_map) if check_all
        else len(changed & set(section_map)),
        "skipped_sections": 0 if check_all
        else len(set(section_map) - changed),
    }
    if write_baseline is not None:
        write_baseline.parent.mkdir(parents=True, exist_ok=True)
        write_baseline.write_text(json.dumps(
            {"schema_version": "1.0", "task": task_id,
             "sections": section_map}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        result["baseline_written"] = str(write_baseline)
        result["status"] = "ok"
    return result


def _mask_block_blocks(text: str) -> str:
    masked = STRUCT_COMMENT.sub(_mask_block, text)
    return FENCE.sub(_mask_block, masked)


def _line_of(text: str, needle: str) -> int:
    for index, line in enumerate(text.splitlines(), 1):
        if line == needle:
            return index
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--task")
    parser.add_argument("--file")
    parser.add_argument("--baseline")
    parser.add_argument("--write-baseline")
    args = parser.parse_args()
    if not args.task and not args.file:
        print(json.dumps({"status": "error",
                          "error": "use --task N or --file PATH"}))
        return 2
    root = Path(args.root).resolve()
    if args.file:
        path = Path(args.file)
        if not path.is_absolute():
            path = root / path
        task_id = args.task or path.parent.name
    else:
        task_id = str(args.task)
        path = root / ".doc" / "tasks" / task_id / "doc.md"
    baseline = Path(args.baseline) if args.baseline else None
    if baseline is not None and not baseline.is_absolute():
        baseline = root / baseline
    write_baseline = Path(args.write_baseline) if args.write_baseline else None
    if write_baseline is not None and not write_baseline.is_absolute():
        write_baseline = root / write_baseline
    result = check(task_id, path, baseline=baseline,
                   write_baseline=write_baseline)
    print(json.dumps(result, ensure_ascii=False))
    if result.get("status") == "missing":
        return 2
    if result.get("baseline_written"):
        return 0
    return 1 if result.get("errors") else 0


if __name__ == "__main__":
    sys.exit(main())
