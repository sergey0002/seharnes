"""Deterministic markdown views for published JSONdoc documents (J03).

Renders a document dict into the compatible .md view (plan sections 4.4,
7.4-7.9, 16 J03): byte-identical output for equal documents, atomic
publication, manual edits of a published view guarded by the receipt
view_sha256 (VIEW_CONFLICT, no overwrite). Works on plain dicts and files
only and never imports the store: the receipt beside the view is read and
updated directly while data_revision/data_sha256/operation_id stay owned
by the store and are preserved verbatim.
"""

import hashlib
import json
import os
from pathlib import Path

RENDERER_VERSION = "1.0.0-J03"

_GENERATOR_NOTE = "doc_render.py"


class RenderError(Exception):
    def __init__(self, code, message="", path=None, expected=None, actual=None):
        super().__init__("{0}: {1}".format(code, message) if message else code)
        self.code = code
        self.path = path
        self.expected = expected
        self.actual = actual


def _unknown(value):
    return "unknown" if value is None else str(value)


def _join_list(items):
    if not items:
        return "unknown"
    return ", ".join(_unknown(item) for item in items)


def _block(title, entries):
    return ["## " + title, ""] + list(entries)


def _na_block(title):
    return _block(title, ["_N/A_"])


def _table(rows):
    return list(rows)


def _section_lines(section):
    try:
        level = int(section.get("level") or 2)
    except (TypeError, ValueError):
        level = 2
    level = max(1, min(6, level))
    lines = ["{0} {1}".format("#" * level, _unknown(section.get("title")))]
    anchor = section.get("anchor")
    if anchor:
        lines.append('<a id="{0}"></a>'.format(anchor))
    body = section.get("body_markdown") or ""
    body = body.strip("\n")
    if body:
        lines.append(body)
    return lines


def _finding_entry(finding):
    lines = ["- **{0} {1}** ({2}, {3}): {4}".format(
        _unknown(finding.get("id")), _unknown(finding.get("title")),
        _unknown(finding.get("kind")), _unknown(finding.get("status")),
        finding.get("statement") or "")]
    for key in ("symptom", "cause", "resolution"):
        value = finding.get(key)
        if value is not None:
            lines.append("  - {0}: {1}".format(key, value))
    return "\n".join(lines)


def _decision_entry(decision):
    lines = ["- **{0} {1}**: {2}".format(
        _unknown(decision.get("id")), _unknown(decision.get("title")),
        decision.get("choice") or "")]
    context = decision.get("context")
    if context is not None:
        lines.append("  - context: {0}".format(context))
    return "\n".join(lines)


def _files_block(files):
    if not files:
        return _na_block("Файлы")
    rows = ["| id | path | role | state |", "|---|---|---|---|"]
    for item in files:
        rows.append("| {0} | {1} | {2} | {3} |".format(
            _unknown(item.get("id")), _unknown(item.get("path")),
            _unknown(item.get("role")), _unknown(item.get("state"))))
    return _block("Файлы", _table(rows))


def _relations_block(relations):
    if not relations:
        return _na_block("Связанные задачи")
    rows = ["| target | kind | reason | status |", "|---|---|---|---|"]
    for item in relations:
        target = item.get("target") or {}
        rows.append("| {0} | {1} | {2} | {3} |".format(
            _unknown(target.get("document_id")), _unknown(item.get("kind")),
            _unknown(item.get("reason")), _unknown(item.get("status"))))
    return _block("Связанные задачи", _table(rows))


def _tags_block(tags):
    if not tags:
        return _na_block("Теги")
    return _block("Теги", ["- {0}: {1}".format(
        _unknown(tag.get("tag_id")), tag.get("reason") or "")
        for tag in tags])


def _stages_block(stages):
    if not stages:
        return _na_block("Стадии")
    rows = ["| number | status | title |", "|---|---|---|"]
    for stage in stages:
        rows.append("| {0} | {1} | {2} |".format(
            _unknown(stage.get("number")), _unknown(stage.get("status")),
            _unknown(stage.get("title"))))
    return _block("Стадии", _table(rows))


def _git_events_block(events):
    if not events:
        return _na_block("Git")
    return _block("Git", ["- {0}: {1} {2} on {3} -> {4} at {5}".format(
        _unknown(event.get("id")), _unknown(event.get("action")),
        _unknown(event.get("commit")), _unknown(event.get("branch")),
        _unknown(event.get("remote")), _unknown(event.get("observed_at")))
        for event in events])


def _tracker_block(tracker):
    return _block("Tracker", [
        "- issue: {0}".format(_unknown(tracker.get("issue_key"))),
        "- exported_at: {0}".format(_unknown(tracker.get("exported_at"))),
        "- exporter: {0}".format(_unknown(tracker.get("exporter"))),
        "- availability: {0}".format(_unknown(tracker.get("availability"))),
    ])


def _git_state_block(state):
    return _block("Git state", [
        "- checked_at: {0}".format(_unknown(state.get("checked_at"))),
        "- commit: {0}".format(_unknown(state.get("commit"))),
        "- fetch_status: {0}".format(_unknown(state.get("fetch_status"))),
        "- pushed_to: {0}".format(_join_list(state.get("pushed_to"))),
        "- contained_in: {0}".format(_join_list(state.get("contained_in"))),
        "- release_branches: {0}".format(_join_list(state.get("release_branches"))),
        "- not_pushed_refs: {0}".format(_join_list(state.get("not_pushed_refs"))),
    ])


def _jira_report_block(report):
    return _block("Jira report", [
        "- updated_at: {0}".format(_unknown(report.get("updated_at"))),
        "- release: {0}".format(_unknown(report.get("release"))),
        "",
        report.get("text") or "",
    ])


def _history_block(history):
    if not history:
        return _na_block("История")
    return _block("История", ["- {0} {1}: {2}".format(
        _unknown(entry.get("at")), _unknown(entry.get("actor")),
        entry.get("summary") or "") for entry in history])


def _task_blocks(doc):
    blocks = []
    findings = doc.get("findings") or []
    if findings:
        blocks.append(_block("Находки", [_finding_entry(f) for f in findings]))
    else:
        blocks.append(_na_block("Находки"))
    decisions = doc.get("decisions") or []
    if decisions:
        blocks.append(_block("Решения", [_decision_entry(d) for d in decisions]))
    else:
        blocks.append(_na_block("Решения"))
    blocks.append(_files_block(doc.get("files") or []))
    blocks.append(_relations_block(doc.get("relations") or []))
    blocks.append(_tags_block(doc.get("tags") or []))
    blocks.append(_stages_block(doc.get("stages") or []))
    blocks.append(_git_events_block(doc.get("git_events") or []))
    tracker = doc.get("tracker")
    if tracker:
        blocks.append(_tracker_block(tracker))
    git_state = doc.get("git_state")
    if git_state:
        blocks.append(_git_state_block(git_state))
    jira_report = doc.get("jira_report")
    if jira_report:
        blocks.append(_jira_report_block(jira_report))
    blocks.append(_history_block(doc.get("history") or []))
    return blocks


def render_markdown(doc):
    """Full deterministic markdown view of a task or architecture document."""
    meta = doc.get("metadata") or {}
    blocks = [
        ["<!-- generated from {0} by {1}; do not edit -->".format(
            _unknown(doc.get("id")), _GENERATOR_NOTE)],
        ["# {0}".format(_unknown(meta.get("title")))],
        ["task {0} - status {1} - branch {2} - release {3}".format(
            _unknown(meta.get("task_id")), _unknown(meta.get("status")),
            _unknown(meta.get("branch")), _unknown(meta.get("release")))],
    ]
    sections = {s.get("id"): s for s in doc.get("sections") or []}
    for section_id in doc.get("section_order") or []:
        section = sections.get(section_id)
        if section is not None:
            blocks.append(_section_lines(section))
    if doc.get("kind") == "task":
        blocks.extend(_task_blocks(doc))
    text = "\n\n".join("\n".join(block) for block in blocks if block)
    return text.rstrip("\n") + "\n"


def view_path(docs_dir, kind, key):
    """Published view path for a document kind and key."""
    if kind == "task":
        return Path(docs_dir) / "tasks" / key / "doc.md"
    if kind == "architecture":
        return Path(docs_dir) / "architecture" / "{0}.md".format(key)
    raise RenderError("UNSUPPORTED_KIND",
                      "unsupported document kind: {0}".format(kind))


def receipt_path(docs_dir, kind, key):
    """Receipt path in the internal _jsondoc zone beside the view."""
    if kind == "task":
        return Path(docs_dir) / "tasks" / key / "_jsondoc" / "receipt.json"
    if kind == "architecture":
        return Path(docs_dir) / "architecture" / "_jsondoc" / key / "receipt.json"
    raise RenderError("UNSUPPORTED_KIND",
                      "unsupported document kind: {0}".format(kind))


def _load_receipt(path):
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _receipt_bytes(receipt):
    return (json.dumps(receipt, ensure_ascii=False, sort_keys=True,
                       indent=2) + "\n").encode("utf-8")


def _fsync_dir(directory):
    try:
        fd = os.open(str(directory), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def _atomic_write(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    _fsync_dir(path.parent)


def render_document(root, docs_dir, kind, key, doc, first_publish=False):
    """Render and publish the view with receipt-guarded conflict detection.

    Writes the view atomically only when the target is missing or its bytes
    differ from the fresh render AND the current bytes still match the
    receipt view_sha256 (or the view is missing). Otherwise raises
    RenderError('VIEW_CONFLICT') and leaves the file untouched.
    """
    md = render_markdown(doc)
    data = md.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    target = view_path(docs_dir, kind, key)
    receipt_file = receipt_path(docs_dir, kind, key)
    current = target.read_bytes() if target.exists() else None
    receipt = _load_receipt(receipt_file)
    if current is not None and current != data and not first_publish:
        actual = hashlib.sha256(current).hexdigest()
        expected = receipt.get("view_sha256") if receipt else None
        if expected != actual:
            raise RenderError(
                "VIEW_CONFLICT",
                "view {0}: expected sha256 {1}, actual {2}; manual view edits "
                "must go through the JSON document".format(
                    target, "unknown" if expected is None else expected, actual),
                path=target, expected=expected, actual=actual)
        status = "written"
    elif current is None or current != data:
        status = "written"
    else:
        status = "noop"
    if status == "written":
        _atomic_write(target, data)
    updated = dict(receipt) if receipt else {}
    updated["view_sha256"] = digest
    updated["renderer_version"] = RENDERER_VERSION
    if updated != receipt:
        _atomic_write(receipt_file, _receipt_bytes(updated))
    return {"status": status, "view_sha256": digest}
