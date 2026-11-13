"""Lossless staging migration of legacy doc.md/architecture MD (J09).

Split into byte spans, extract explicit structure only, keep everything
else as sections origin=opaque, prove reconstruct round-trip by hash
(plan sections 8, 19.5). Never writes over live sources; cutover goes
through store.create + render.
"""

import hashlib
import json
import os
import re
from pathlib import Path

MAX_SPAN = 4096


class MigrateError(ValueError):
    def __init__(self, code, message=None):
        super().__init__(f"{code}" + (f": {message}" if message else ""))
        self.code = code


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _atomic(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, dict):
        data = json.dumps(data, ensure_ascii=False, sort_keys=True,
                          indent=2).encode("utf-8") + b"\n"
    tmp.write_bytes(data)
    os.replace(tmp, path)


# ------------------------------------------------------------- inventory

KNOWN_FILES = {
    "task.md": "source_only", "doc.md": "migrate", "plan.md": "migrate_root",
    "diff.md": "source_only", "diff.files.md": "source_only",
    "test.md": "source_only", "ac-matrix.json": "source_only",
    "jira-report.md": "source_only", "gototask-state.json": "queue_state",
    "stages.json": "queue_state", "audit.md": "source_only",
}


def classify_path(rel):
    parts = rel.split("/")
    name = parts[-1]
    if parts[0].startswith("stage"):
        if re.fullmatch(r"stage\d+", parts[0]):
            return "migrate_stage" if name == "plan.md" else "state"
        if re.fullmatch(r"stage\d+v\d+", parts[0]):
            return "migrate_stage_rev" if name == "plan.md" else "state"
        return "state"
    if name in KNOWN_FILES:
        return KNOWN_FILES[name]
    if parts[0] in ("test-runs", "reports", "tests", "_jsondoc"):
        return "state"
    if parts[0] == "_map" and name.endswith(".tsv"):
        return "queue_state"
    if name.endswith((".png", ".svg", ".html", ".jpg", ".jpeg")):
        return "attachment"
    if parts[0] in ("_context-base.md", "_priority.md", "index.md"):
        return "migrate"
    return "source_only"


def inventory(docs_dir):
    docs = Path(docs_dir)
    tasks = {}
    arch = []
    tasks_root = docs / "tasks"
    if tasks_root.is_dir():
        for entry in sorted(tasks_root.iterdir()):
            if not entry.is_dir() or not entry.name.isdigit():
                continue
            files = []
            for path in sorted(entry.rglob("*")):
                if path.is_dir():
                    continue
                rel = path.relative_to(entry).as_posix()
                role = classify_path(rel)
                item = {"path": rel, "role": role}
                if role.startswith("migrate_stage"):
                    match = re.fullmatch(r"stage(\d+)(?:v(\d+))?",
                                         rel.split("/")[0])
                    item["number"] = int(match.group(1))
                    item["variant"] = int(match.group(2)) if match.group(2) else None
                    if not any(p.exists() for p in [entry / rel]) or \
                            all(p.is_dir() for p in [entry / rel]):
                        pass
                if role == "state" and path.is_dir():
                    continue
                if role == "queue_state" and not path.is_file():
                    continue
                files.append(item)
            # placeholder stage dirs (empty)
            for path in sorted(entry.iterdir()):
                if path.is_dir() and re.fullmatch(r"stage\d+", path.name) and \
                        not any(path.iterdir()):
                    files.append({"path": path.name, "role": "state",
                                  "number": int(path.name[5:]),
                                  "placeholder": True})
            tasks[entry.name] = {"files": files}
    arch_root = docs / "architecture"
    if arch_root.is_dir():
        for path in sorted(arch_root.glob("*.md")):
            arch.append({"path": path.relative_to(docs).as_posix(),
                         "stem": path.stem, "role": "migrate"})
    counts = {}
    for task in tasks.values():
        for item in task["files"]:
            counts[item["role"]] = counts.get(item["role"], 0) + 1
    counts["arch"] = len(arch)
    return {"tasks": tasks, "arch": arch, "counts": counts}


# ----------------------------------------------------------------- spans

def split_spans(data):
    spans = []
    start = 0
    position = 0
    fence = False
    while position < len(data):
        chunk_end = min(position + MAX_SPAN, len(data))
        # keep fenced blocks whole
        window = data[position:chunk_end]
        fences = window.count(b"```")
        if fence and fences % 2 == 0:
            fence = False
        limit = chunk_end
        if not fence and fences % 2 == 1:
            limit = chunk_end
            fence = True
        # prefer boundary at blank line
        if limit < len(data):
            boundary = data.rfind(b"\n\n", position, limit)
            if boundary > position:
                limit = boundary + 2 if fence is False else limit
                if not fence:
                    limit = boundary + 2
        spans.append({"id": f"sp-{len(spans):04d}", "start": start,
                      "end": limit, "order": len(spans)})
        position = limit
        start = limit
    if spans and spans[-1]["end"] < len(data):
        spans.append({"id": f"sp-{len(spans):04d}", "start": start,
                      "end": len(data), "order": len(spans)})
    return spans


# ------------------------------------------------------------- structure

RECOGNIZED_HEADINGS = {
    "подводные камни": "pitfalls",
    "принятые решения": "decisions",
    "затронутые файлы": "files",
    "связанные задачи": "relations",
    "связи": "links",
    "история изменений": "history",
}


def _anchor_of(title):
    return title.strip().lower().replace(" ", "-")


def _semantic_of(title):
    """Match recognized sections even with emoji/prefix decorations."""
    cleaned = re.sub(r"[^\w\sа-яё-]+", " ", title.strip().lower())
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for key, semantic in RECOGNIZED_HEADINGS.items():
        if key in cleaned:
            return semantic
    return None


def extract_structure(text, kind, key):
    sections = []
    findings, decisions, relations = [], [], []
    files_entries = []
    lines = text.splitlines()
    index = 0
    meta = {"title": None, "status": "unknown", "updated": None}
    match = re.search(r"<!--\s*meta(.*?)-->", text, re.S)
    if match:
        for line in match.group(1).splitlines():
            pair = line.split(":", 1)
            if len(pair) == 2:
                name, value = pair[0].strip(), pair[1].strip()
                if name == "status":
                    meta["status"] = value
                elif name == "updated":
                    meta["updated"] = value
    current = None
    for line in lines:
        heading = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            # record-style subheadings stay inside their semantic section
            record = re.match(r"^(ПК-\d+|Р-\d+|П-\d+)\s*[:：]\s*(.*)$", title)
            if record and current is not None:
                entry = {"id": record.group(1),
                         "section_id": current["id"],
                         "title": record.group(2).strip() or record.group(1),
                         "statement": record.group(2).strip() or record.group(1),
                         "choice": record.group(2).strip() or record.group(1)}
                if record.group(1).startswith("Р-"):
                    decisions.append(entry)
                else:
                    findings.append(entry)
                continue
            if meta["title"] is None and level == 1:
                meta["title"] = re.sub(r"^[^:]*:\s*", "", title)
            current = {"id": f"s{len(sections)}",
                       "title": title, "level": level, "parent_id": None,
                       "anchor": _anchor_of(title), "anchor_aliases": [],
                       "body": [], "origin": "opaque",
                       "semantic": _semantic_of(title)}
            if current["semantic"]:
                current["origin"] = "imported"
            sections.append(current)
            continue
        if current is None:
            continue
        current["body"].append(line)
        body_line = line.strip()
        parent_semantic = current.get("semantic")
        # heading-style records: ### ПК-N: title / ### Р-N: title
        heading_rec = re.match(r"^#{3,6}\s+(ПК-\d+|Р-\d+)\s*[:：]\s*(.*)$",
                               line)
        if heading_rec and parent_semantic in ("pitfalls", "decisions"):
            record = {"id": heading_rec.group(1),
                      "section_id": current["id"],
                      "title": heading_rec.group(2).strip() or heading_rec.group(1),
                      "statement": heading_rec.group(2).strip()}
            if parent_semantic == "pitfalls":
                findings.append(record)
            else:
                decisions.append(record)
            continue
        if parent_semantic == "pitfalls":
            m = re.match(r"-\s+\*\*(ПК-\d+)\*?\*?\s*(.+)", body_line)
            if m:
                findings.append({"id": m.group(1), "section_id": current["id"],
                                 "title": m.group(2), "statement": body_line})
        elif parent_semantic == "decisions":
            m = re.match(r"-\s+\*\*(Р-\d+)\*?\*?\s*(.+)", body_line)
            if m:
                decisions.append({"id": m.group(1), "section_id": current["id"],
                                  "title": m.group(2), "choice": m.group(2)})
        elif current["semantic"] == "relations":
            m = re.search(r"#(\d+)\s*[-:]\s*(.+)", body_line)
            if m:
                relations.append({"id": f"rel-{m.group(1)}",
                                  "target": {"document_id": f"task:{m.group(1)}",
                                             "record_id": None, "anchor": None},
                                  "reason": m.group(2)})
        elif current["semantic"] == "files":
            m = re.match(r"\|\s*`([^`]+)`\s*\|", body_line)
            if m:
                files_entries.append({"path": m.group(1)})
            else:
                m2 = re.match(r"^\s*-\s+`([^`]+)`", body_line)
                if m2:
                    files_entries.append({"path": m2.group(1)})
    section_records = []
    for section in sections:
        section_records.append({
            "id": section["id"], "title": section["title"],
            "level": section["level"], "parent_id": None,
            "anchor": section["anchor"], "anchor_aliases": [],
            "body_markdown": "\n".join(section["body"]),
            "source_ids": [], "origin": section["origin"]})
    # dedupe relations by target task, merging reasons
    uniq_relations = {}
    for relation in relations:
        key = relation["target"]["document_id"]
        if key in uniq_relations:
            uniq_relations[key]["reason"] += " | " + relation["reason"]
        else:
            uniq_relations[key] = relation
    relations = list(uniq_relations.values())
    return {"meta": meta, "sections": section_records,
            "findings": findings, "decisions": decisions,
            "relations": relations, "files": files_entries,
            "section_order": [s["id"] for s in section_records]}


# -------------------------------------------------------------- staging

def build_candidate(data, kind, key, title_hint):
    if isinstance(data, str):
        data = data.encode("utf-8")
    text = data.decode("utf-8", "replace")
    extracted = extract_structure(text, kind, key)
    title = extracted["meta"]["title"] or title_hint or str(key)
    doc = {
        "schema_version": "1.0", "kind": kind,
        "id": f"{kind}:{key}" if kind != "task" else f"task:{key}",
        "revision": 1,
        "metadata": {
            "task_id": str(key) if kind == "task" else None,
            "title": title, "task_type": "unknown",
            "doc_type": "architecture" if kind == "architecture" else None,
            "branch": None, "release": None,
            "updated_at": "1970-01-01T00:00:00Z",
            "status": "unknown", "source_status": extracted["meta"]["status"],
        },
        "summary": None, "tags": [],
        "sections": extracted["sections"],
        "section_order": extracted["section_order"],
        "files": [{"id": f"F{i}", "path": f["path"], "role": None,
                   "change": None, "state": "historical", "source_ids": [],
                   "revision": None, "ranges": [], "previous_path": None}
                  for i, f in enumerate(extracted["files"], 1)],
        "findings": [{"id": f["id"], "kind": "pitfall", "title": f["title"],
                      "statement": f["statement"], "symptom": None,
                      "cause": None, "resolution": None, "status": "observed",
                      "severity": None, "file_ids": [], "source_ids": [],
                      "superseded_by": None, "section_id": f["section_id"]}
                     for f in extracted["findings"]],
        "decisions": [{"id": d["id"], "title": d["title"],
                       "context": d["choice"], "choice": d["choice"],
                       "alternatives": [], "status": "proposed",
                       "source_ids": [], "superseded_by": None,
                       "section_id": d["section_id"]}
                      for d in extracted["decisions"]],
        "requirements": [], "progress": [], "stages": [], "notes": [],
        "relations": [{"id": r["id"], "target": r["target"], "kind": "related",
                       "reason": r["reason"], "source_ids": [],
                       "status": "candidate", "availability": "present"}
                      for r in extracted["relations"]],
        "artifacts": [], "checks": [], "git_events": [],
        "tracker": None, "git_state": None, "jira_report": None,
        "sources": [{"id": "S-legacy", "kind": "doc",
                     "path": None, "pointer": None,
                     "sha256": _sha(data), "revision": None,
                     "observed_at": None, "observation": "legacy doc.md",
                     "availability": "present"}],
        "history": [],
    }
    spans = split_spans(data)
    coverage = {
        "byte_coverage": sum(s["end"] - s["start"] for s in spans) / len(data)
        if data else 1.0,
        "structural": {"sections": len(doc["sections"]),
                       "findings": len(doc["findings"]),
                       "decisions": len(doc["decisions"]),
                       "relations": len(doc["relations"]),
                       "files": len(doc["files"])},
        "ambiguous": [],
        "anchors_inventory": [s["anchor"] for s in doc["sections"]],
        "lines_total": text.count("\n") + 1,
    }
    return {"candidate": doc, "spans": spans, "coverage": coverage}


def staging_dir(docs_dir, kind, key, run):
    docs = Path(docs_dir)
    if kind == "task":
        return docs / "tasks" / str(key) / "_jsondoc" / "migrations" / run
    return docs / "architecture" / "_jsondoc" / str(key) / "migrations" / run


def write_staging(docs_dir, kind, key, run, data):
    if isinstance(data, str):
        data = data.encode("utf-8")
    base = staging_dir(docs_dir, kind, key, run)
    built = build_candidate(data, kind, key, None)
    _atomic(base / "original.md", data)
    _atomic(base / "candidate.json", json.dumps(
        built["candidate"], ensure_ascii=False, sort_keys=True,
        indent=2).encode("utf-8") + b"\n")
    span_records = []
    for span in built["spans"]:
        payload = data[span["start"]:span["end"]]
        name = f"spans/{span['id']}.bin"
        _atomic(base / name, payload)
        span_records.append({**span,
                             "payload_path": name,
                             "payload_sha256": _sha(payload),
                             "semantic_kind": "body"})
    _atomic(base / "coverage.json", built["coverage"])
    return {"dir": str(base), "spans": span_records,
            "coverage": built["coverage"],
            "original_sha256": _sha(data)}


def reconstruct(candidate_spans, spans_dir):
    spans_dir = Path(spans_dir)
    chunks = []
    for span in sorted(candidate_spans, key=lambda s: s["order"]):
        payload = (spans_dir / span["payload_path"]).read_bytes()
        if _sha(payload) != span["payload_sha256"]:
            raise MigrateError("span_hash_mismatch", span["id"])
        chunks.append(payload)
    return b"".join(chunks)


def check(docs_dir, kind, key, run):
    base = staging_dir(docs_dir, kind, key, run)
    if not (base / "original.md").is_file():
        return {"status": "error", "errors": [{"code": "staging_missing"}]}
    original = (base / "original.md").read_bytes()
    coverage = json.loads((base / "coverage.json").read_text(encoding="utf-8"))
    candidate = json.loads((base / "candidate.json").read_text(encoding="utf-8"))
    # span records reconstructed from files themselves
    span_records = []
    for path in sorted((base / "spans").glob("sp-*.bin")):
        span_records.append(path)
    rebuilt = b"".join(path.read_bytes() for path in span_records)
    byte_roundtrip = _sha(rebuilt) == _sha(original)
    complete = coverage.get("byte_coverage") == 1.0 and byte_roundtrip
    issues = []
    if not byte_roundtrip:
        issues.append("roundtrip_hash_mismatch")
    return {"status": "ok" if complete else "failed",
            "byte_roundtrip": byte_roundtrip,
            "coverage_complete": complete, "issues": issues,
            "candidate_sections": len(candidate.get("sections", []))}


def apply_cutover(store, render_mod, docs_dir, kind, key, run,
                  expected_revision=0):
    store_kind = "arch" if kind == "architecture" else kind
    base = staging_dir(docs_dir, kind, key, run)
    original = (base / "original.md").read_bytes()
    live = store.docs
    if kind == "task":
        live_path = live / "tasks" / str(key) / "doc.md"
    else:
        live_path = live / "architecture" / f"{key}.md"
    if live_path.is_file() and _sha(live_path.read_bytes()) != _sha(original):
        raise MigrateError("MIGRATION_SOURCE_CHANGED", str(live_path))
    if store.load(store_kind, key) is not None:
        return {"status": "duplicate"}
    candidate = json.loads((base / "candidate.json").read_text(encoding="utf-8"))
    from . import contract
    errors = contract.validate_document(candidate)
    if errors:
        return {"status": "error",
                "errors": [{"code": "candidate_invalid", "detail": errors}]}
    envelope = {"schema_version": "1.0",
                "operation_id": f"migrate-{kind}-{key}-{run}",
                "expected_revision": 0, "actor": "migration",
                "reason": "doc.md staging migration", "operations": [],
                "document": candidate}
    outcome = store.apply(store_kind, key, envelope)
    view = None
    if render_mod is not None:
        doc = store.load(store_kind, key)
        view = render_mod.render_document(store.root, store.docs, kind, key,
                                          doc, first_publish=True)
    return {"status": "applied", "revision": outcome.get("revision"),
            "view": view}
