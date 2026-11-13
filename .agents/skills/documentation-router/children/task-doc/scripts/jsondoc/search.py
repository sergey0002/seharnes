"""Read-only query engine: get/select/limit/cursor/search with coverage (J04).

Never writes, never renders, never rebuilds indexes. All results are plain
dicts; the CLI wraps them into the single JSON envelope (plan section 6).
"""

import json
import re
import unicodedata
from pathlib import Path

SEARCHABLE_FIELDS = ("metadata.title", "summary", "sections.body_markdown",
                     "findings.statement", "decisions.choice", "notes.text",
                     "tags.reason")
DEFAULT_LIMIT = 10
DEFAULT_MAX_BYTES = 16384


class QueryError(ValueError):
    def __init__(self, code, message=None):
        super().__init__(f"{code}" + (f": {message}" if message else ""))
        self.code = code


def document_path(docs, kind, key):
    if kind == "task":
        if not re.fullmatch(r"[0-9]+", str(key)):
            raise QueryError("invalid_task_key", str(key))
        return docs / "tasks" / str(key) / "task.json"
    if kind == "architecture":
        if not re.fullmatch(r"[a-z0-9-]+", str(key)):
            raise QueryError("invalid_arch_key", str(key))
        return docs / "architecture" / f"{key}.json"
    raise QueryError("unknown_kind", kind)


def load_document(docs, kind, key):
    path = document_path(docs, kind, key)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise QueryError("invalid_document_json", str(path)) from None


def card(doc):
    meta = doc.get("metadata", {})
    return {
        "id": doc.get("id"),
        "kind": doc.get("kind"),
        "revision": doc.get("revision"),
        "title": meta.get("title"),
        "status": meta.get("status"),
        "branch": meta.get("branch"),
        "release": meta.get("release"),
        "tags": [t.get("tag_id") for t in doc.get("tags", [])],
        "counts": {name: len(doc.get(name, []))
                   for name in ("sections", "files", "findings", "decisions",
                                "requirements", "stages", "relations",
                                "artifacts", "checks", "notes")},
    }


def _parse_pointer(pointer):
    if not pointer.startswith("/"):
        raise QueryError("invalid_pointer", pointer)
    tokens = []
    for token in pointer[1:].split("/"):
        tokens.append(token.replace("~1", "/").replace("~0", "~"))
    return tokens


def _walk(doc, tokens):
    node = doc
    for token in tokens:
        if isinstance(node, dict):
            if token not in node:
                raise QueryError("FIELD_NOT_FOUND", "/" + "/".join(tokens))
            node = node[token]
        elif isinstance(node, list):
            matched = [item for item in node
                       if isinstance(item, dict) and str(item.get("id")) == token]
            if len(matched) == 1:
                node = matched[0]
            elif not matched:
                raise QueryError("FIELD_NOT_FOUND", "/" + "/".join(tokens))
            else:
                raise QueryError("ambiguous_record_id", token)
        else:
            raise QueryError("FIELD_NOT_FOUND", "/" + "/".join(tokens))
    return node


def _bound(value, limit, path):
    """Apply per-collection limit; return (payload, truncated, total)."""
    if isinstance(value, list):
        total = len(value)
        if limit is None:
            limit = DEFAULT_LIMIT
        if limit == 0:
            return value, False, total
        window = value[:limit]
        return window, total > len(window), total
    if isinstance(value, str) and len(value) > 4000:
        return value[:4000], True, len(value)
    return value, False, None


def get(docs, kind, key, pointers=None, record_limit=None, keys_only=False):
    doc = load_document(docs, kind, key)
    if doc is None:
        return {"status": "not_found", "kind": kind, "key": str(key),
                "errors": [{"code": "NOT_FOUND"}], "exit": 1}
    if keys_only:
        data = {"keys": sorted(doc.keys()),
                "card": card(doc)}
        return {"status": "ok", "data": data, "exit": 0}
    if not pointers:
        return {"status": "ok", "data": card(doc), "exit": 0}
    results = {}
    truncated = {}
    totals = {}
    for pointer in pointers:
        tokens = _parse_pointer(pointer)
        value = _walk(doc, tokens)
        payload, was_truncated, total = _bound(value, record_limit, pointer)
        results[pointer] = payload
        if was_truncated:
            truncated[pointer] = True
        if total is not None:
            totals[pointer] = total
    return {"status": "ok", "data": results, "page": {"truncated": truncated,
                                                       "totals": totals},
            "snapshot_revision": doc.get("revision"), "exit": 0}


# ------------------------------------------------------------------ search

def _iter_documents(docs):
    tasks_dir = docs / "tasks"
    if tasks_dir.is_dir():
        for path in sorted(tasks_dir.iterdir()):
            if path.is_dir() and path.name.isdigit():
                candidate = path / "task.json"
                if candidate.is_file():
                    yield "task", path.name, candidate
                else:
                    yield "task", path.name, None
    arch_dir = docs / "architecture"
    if arch_dir.is_dir():
        for path in sorted(arch_dir.glob("*.json")):
            if path.stem == "index":
                continue
            yield "architecture", path.stem, path


def _normalize(text):
    return unicodedata.normalize("NFC", str(text)).casefold()


def _tokens(query):
    return [_normalize(tok) for tok in query.split()]


def _field_values(doc, field):
    parts = field.split(".")
    if len(parts) == 1:
        yield doc.get(field)
        return
    head, tail = parts[0], parts[1]

    def walk(node):
        if isinstance(node, list):
            for item in node:
                if isinstance(item, dict):
                    yield item.get(tail)
        elif isinstance(node, dict):
            yield node.get(tail)

    yield from walk(doc.get(head))


def _matches(doc, toks):
    haystack = " \n ".join(
        _normalize(value) for field in SEARCHABLE_FIELDS
        for value in _field_values(doc, field) if value is not None)
    return all(tok in haystack for tok in toks)


def _tag_filter(doc, wanted, mode):
    have = {t.get("tag_id") for t in doc.get("tags", [])
            if t.get("status") == "confirmed"}
    if mode == "all":
        return wanted <= have
    return bool(wanted & have)


def _file_filter(doc, path):
    norm = str(path)
    for item in doc.get("files", []):
        if item.get("path") == norm:
            return True
    return False


def search(docs, kind=None, text=None, tags=(), tag_mode="all", file=None,
           release=None, branch=None, tasks=(), limit=None):
    from jsondoc.tags_resolver import resolve_tags  # lazy (J05)

    wanted_tags = {resolve_tags(docs, t) for t in tags}
    toks = _tokens(text) if text else []
    matched = []
    coverage = {"discovered": 0, "converted": 0, "legacy": 0,
                "missing": 0, "invalid": 0, "complete": True}
    for doc_kind, key, path in _iter_documents(docs):
        coverage["discovered"] += 1
        if kind and doc_kind != kind:
            continue
        if tasks and not (doc_kind == "task" and key in {str(t) for t in tasks}):
            continue
        if path is None:
            coverage["legacy"] += 1
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            coverage["invalid"] += 1
            continue
        coverage["converted"] += 1
        if toks and not _matches(doc, toks):
            continue
        if wanted_tags and not _tag_filter(doc, wanted_tags, tag_mode):
            continue
        if file and not _file_filter(doc, file):
            continue
        if release and doc.get("metadata", {}).get("release") != release:
            continue
        if branch:
            have = doc.get("metadata", {}).get("branch")
            if have != branch and not (have and have.endswith(branch)):
                continue
        matched.append({"kind": doc_kind, "key": key, "card": card(doc),
                        "path": str(path.relative_to(docs.parent))})
    matched.sort(key=lambda hit: (hit["kind"], int(hit["key"])
                                  if hit["key"].isdigit() else 0))
    total = len(matched)
    if limit is None:
        limit = DEFAULT_LIMIT
    window = matched if limit == 0 else matched[:limit]
    coverage["complete"] = coverage["invalid"] == 0
    return {"status": "ok",
            "data": window,
            "counts": {"matched": total, "returned": len(window)},
            "page": {"truncated": total > len(window)},
            "coverage": coverage,
            "exit": 0}


# ------------------------------------------------------------- related (J05)

_DISCOVERY_WEIGHTS = {
    "relation": 100,
    "file": (40, 80),
    "arch": (20, 40),
    "process": (12, 24),
    "component": (8, 16),
    "domain": (3, 6),
}


def _capped(points, capped):
    step, cap = capped
    return min(step * points, cap)


def related_discovery(docs, task_key, limit=None, tags_enabled=True):
    """discovery-v1: confirmed signals only, per plan section 5.2."""
    origin = load_document(docs, "task", task_key)
    if origin is None:
        return {"status": "not_found", "errors": [{"code": "NOT_FOUND"}],
                "exit": 1}
    origin_files = {f.get("path") for f in origin.get("files", [])}
    origin_archs = {r["target"]["document_id"] for r in origin.get("relations", [])
                    if r.get("target", {}).get("document_id", "").startswith("arch:")}
    explicit = {r["target"]["document_id"].split(":", 1)[1]
                for r in origin.get("relations", [])
                if r.get("target", {}).get("document_id", "").startswith("task:")
                and r.get("status") == "confirmed"}
    from collections import defaultdict
    scores = defaultdict(lambda: {"score": 0, "signals": [], "candidate_only": True})

    def add(key, kind, points, detail):
        entry = scores[key]
        entry["score"] += points
        entry["signals"].append({"kind": kind, "detail": detail})
        if kind != "tag":
            entry["candidate_only"] = False

    for _, key, path in _iter_documents(docs):
        if path is None or key == str(task_key):
            continue
        doc = json.loads(path.read_text(encoding="utf-8"))
        if doc.get("kind") != "task":
            continue
        if key in explicit:
            add(key, "relation", _DISCOVERY_WEIGHTS["relation"], "explicit relation")
        overlap = origin_files & {f.get("path") for f in doc.get("files", [])}
        if overlap:
            add(key, "file", _capped(len(overlap), _DISCOVERY_WEIGHTS["file"]),
                sorted(overlap)[:5])
        doc_archs = {r["target"]["document_id"] for r in doc.get("relations", [])
                     if r.get("target", {}).get("document_id", "").startswith("arch:")}
        shared_archs = origin_archs & doc_archs
        if shared_archs:
            add(key, "arch", _capped(len(shared_archs), _DISCOVERY_WEIGHTS["arch"]),
                sorted(shared_archs)[:5])
        if tags_enabled:
            for tag in doc.get("tags", []):
                if tag.get("status") != "confirmed":
                    continue
                kind = tag["tag_id"].split(":", 1)[0]
                if kind in ("process", "component", "domain"):
                    if any(t["tag_id"] == tag["tag_id"] and
                           t.get("status") == "confirmed"
                           for t in origin.get("tags", [])):
                        add(key, "tag", _capped(1, _DISCOVERY_WEIGHTS[kind]),
                            tag["tag_id"])

    ranked = sorted(scores.items(), key=lambda kv: (-kv[1]["score"], int(kv[0])))
    hits = [{"id": key, "score": entry["score"], "signals": entry["signals"],
             "candidate": entry["candidate_only"],
             "task_path": f".doc/tasks/{key}/task.md"}
            for key, entry in ranked]
    total = len(hits)
    if limit is None:
        limit = DEFAULT_LIMIT
    window = hits if limit == 0 else hits[:limit]
    return {"status": "ok", "profile": "discovery-v1",
            "data": window, "counts": {"matched": total, "returned": len(window)},
            "page": {"truncated": total > len(window)}, "exit": 0}


def related_legacy(docs, arch_key, limit=None):
    """legacy-v1: byte-compatible scoring with find-related-tasks.ps1 (J11).

    Weights (from the PS1 source): TSV file match +40 per file, arch link in
    root doc.md/plan.md/diff.files.md/task.md +50 once, filename mention +20
    (only without link), code overlap in doc.md+diff.files.md
    min(30, 6*hits) with extension filter, already linked from arch +10.
    Sort score desc, task id asc, default limit 8.
    """
    arch_dir = Path(docs) / "architecture"
    arch_md = arch_dir / f"{arch_key}.md"
    if not arch_md.is_file():
        return {"status": "not_found", "errors": [{"code": "NOT_FOUND"}],
                "profile": "legacy-v1", "exit": 1}
    arch_text = arch_md.read_text(encoding="utf-8")
    already = set(re.findall(r"\.\./tasks/(\d+)/", arch_text))

    tsv = Path(docs) / "tasks" / "_map" / "file-to-tasks.tsv"
    file_hits = {}
    if tsv.is_file():
        for line in tsv.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) != 3:
                continue
            path, ids, _titles = parts
            base = Path(path).name
            if path in arch_text or base in arch_text:
                for task_id in ids.split(","):
                    if task_id.isdigit():
                        file_hits.setdefault(task_id, 0)
                        file_hits[task_id] += 1

    results = {}
    tasks_dir = Path(docs) / "tasks"
    scanned = ("doc.md", "plan.md", "diff.files.md", "task.md")
    overlap_ext = {".php", ".vue", ".js", ".ts", ".tpl", ".sql"}
    if tasks_dir.is_dir():
        for entry in sorted(tasks_dir.iterdir()):
            if not entry.is_dir() or not entry.name.isdigit():
                continue
            task_id = entry.name
            score = 0
            reasons = []
            count = file_hits.get(task_id, 0)
            if count:
                score += 40 * count
                reasons.append(f"tsv:{count} file(s)")
            linked = False
            mentioned = False
            for name in scanned:
                path = entry / name
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                if arch_key in text:
                    if name in ("doc.md", "plan.md") or name in ("task.md",):
                        linked = True
                    else:
                        mentioned = True
                    if name == "diff.files.md":
                        mentioned = mentioned or True
            if linked:
                score += 50
                reasons.append("arch link")
            elif mentioned:
                score += 20
                reasons.append("arch mention")
            if score == 0 and task_id not in already:
                continue  # overlap augments existing candidacy only
            hits_count = 0
            for name in ("doc.md", "diff.files.md"):
                path = entry / name
                if not path.is_file():
                    continue
                text = path.read_text(encoding="utf-8", errors="replace")
                if name == "doc.md":
                    for token in re.findall(r"`([^`]+)`", text):
                        if Path(token).suffix.lower() in overlap_ext:
                            hits_count += 1
                else:
                    for line in text.splitlines():
                        token = line.strip().strip("`")
                        if Path(token).suffix.lower() in overlap_ext:
                            hits_count += 1
            if hits_count:
                score += min(30, 6 * hits_count)
                reasons.append(f"overlap:{hits_count}")
            if task_id in already:
                score += 10
                reasons.append("already in arch")
            if score:
                results[task_id] = {"score": score, "reasons": reasons}
    ranked = sorted(results.items(), key=lambda kv: (-kv[1]["score"],
                                                      int(kv[0])))
    if limit is None:
        limit = 8
    window = ranked[:limit] if limit else ranked
    hits = [{"id": task_id, "score": payload["score"],
             "reasons": payload["reasons"],
             "hasDoc": (tasks_dir / task_id / "doc.md").is_file(),
             "hasTask": (tasks_dir / task_id / "task.md").is_file(),
             "taskPath": f".doc/tasks/{task_id}/task.md",
             "docPath": f".doc/tasks/{task_id}/doc.md"
             if (tasks_dir / task_id / "doc.md").is_file() else None,
             "alreadyInArch": task_id in already}
            for task_id, payload in window]
    return {"status": "ok", "profile": "legacy-v1", "data": hits,
            "counts": {"matched": len(results), "returned": len(hits)},
            "exit": 0}


def _arch_match(path, arch_key):
    base = Path(path).name
    return base == arch_key or base == f"{arch_key}.md" or path == arch_key


def related(docs, profile, task=None, arch=None, limit=None):
    if profile == "discovery-v1":
        if not task:
            return {"status": "error",
                    "errors": [{"code": "task_required"}], "exit": 2}
        return related_discovery(docs, task, limit=limit)
    if profile == "legacy-v1":
        if not arch:
            return {"status": "error",
                    "errors": [{"code": "arch_required"}], "exit": 2}
        return related_legacy(docs, arch, limit=limit)
    return {"status": "error", "errors": [{"code": "unknown_profile"}], "exit": 2}
