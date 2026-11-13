"""Ingest of external sources: Jira tracker snapshots and git containment (J08).

No network: tracker input arrives as an already-collected payload from the
existing exporters; git uses local read-only commands only (plan 19.2/19.3).
"""

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path

from . import contract
from .store import StoreError  # noqa: F401  (re-exported for callers)

SEMANTIC_EXCLUDE = {"exported_at", "checked_at"}
AVAILABILITY_STATES = {"present", "null_value", "not_returned", "forbidden",
                       "unsupported", "error"}


class IngestError(ValueError):
    def __init__(self, code, message=None):
        super().__init__(f"{code}" + (f": {message}" if message else ""))
        self.code = code


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def semantic_hash(payload):
    trimmed = {k: v for k, v in payload.items() if k not in SEMANTIC_EXCLUDE}
    return hashlib.sha256(_canonical(trimmed)).hexdigest()


# --------------------------------------------------------------- tracker

def validate_tracker_input(payload):
    errors = []
    if not isinstance(payload, dict):
        return None, [{"code": "invalid_payload"}]
    allowed = {"schema_version", "issue", "comments_pages", "changelog_pages",
               "exporter", "exported_at", "field_availability", "task_md_sha256"}
    unknown = set(payload) - allowed
    if unknown:
        return None, [{"code": "unknown_fields", "fields": sorted(unknown)}]
    if payload.get("schema_version") != "1.0":
        errors.append({"code": "schema_version"})
    if payload.get("exporter") not in ("gototask", "task-diff", "manual"):
        errors.append({"code": "exporter_enum"})
    if not re.fullmatch(r"[0-9T:Z-]{10,24}", str(payload.get("exported_at", ""))):
        errors.append({"code": "exported_at_utc"})
    issue = payload.get("issue")
    if not isinstance(issue, dict) or not issue.get("issue_key"):
        errors.append({"code": "issue_key_required"})
    if errors:
        return None, errors

    availability = {}
    for entry in payload.get("field_availability", []):
        if entry.get("state") not in AVAILABILITY_STATES:
            errors.append({"code": "availability_enum",
                           "field": entry.get("field_id")})
        availability[entry.get("field_id")] = entry.get("state")

    cleaned = json.loads(json.dumps(payload, ensure_ascii=False))
    # fields explicitly not returned are dropped from the semantic payload
    # but recorded in the availability map (null_value stays as None)
    for field_id, state in availability.items():
        if state in ("not_returned", "forbidden", "unsupported", "error"):
            parts = field_id.split(".")
            node = cleaned
            for part in parts[:-1]:
                node = node.get(part) if isinstance(node, dict) else None
                if node is None:
                    break
            if isinstance(node, dict):
                node.pop(parts[-1], None)
    cleaned["availability_map"] = availability
    return cleaned, errors


def entry_coverage(pages, key):
    retrieved = sum(len(page.get(key, [])) for page in pages)
    ids = [c.get("id") for page in pages for c in page.get(key, [])]
    unique = len(set(ids))
    total = pages[0].get("total") if pages else None
    termination = "no_pages" if not pages else None
    complete = bool(pages)
    if pages and total is None:
        termination = "missing_total"
        complete = False
    if unique != retrieved:
        termination = termination or "duplicate_ids"
        complete = False
    if len(pages) > 1 and not pages[-1].get(key) and \
            retrieved < (total if total is not None else float("inf")):
        termination = "early_empty_page"
        complete = False
    if total is not None and retrieved < total:
        termination = termination or "incomplete_traversal"
        complete = False
    if total is not None and retrieved > total:
        termination = "total_contradiction"
        complete = False
    return {"total_reported": total, "retrieved": retrieved,
            "unique_ids": unique, "termination": termination or "complete",
            "complete": complete, "missing_ranges": [] if complete else
            [[retrieved, total if total is not None else None]]}


def comment_coverage(pages):
    return entry_coverage(pages, "comments")


def changelog_coverage(pages):
    return entry_coverage(pages, "histories")


def snapshot_id_for(payload):
    return "tr-" + semantic_hash(payload)[:12]


def snapshot_dir(docs_dir, task_key, snapshot_id):
    return Path(docs_dir) / "tasks" / str(task_key) / "_jsondoc" / "tracker" / snapshot_id


def _atomic_write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if isinstance(data, bytes):
        tmp.write_bytes(data)
    else:
        tmp.write_bytes(_canonical(data) + b"\n")
    os.replace(tmp, path)


def write_tracker_snapshot(docs_dir, task_key, snapshot_id, payload):
    base = snapshot_dir(docs_dir, task_key, snapshot_id)
    written = []
    _atomic_write(base / "issue.json", payload.get("issue", {}))
    written.append("issue.json")
    for index, page in enumerate(payload.get("comments_pages", [])):
        name = f"comments/page-{index:03d}.json"
        _atomic_write(base / name, page)
        written.append(name)
    for index, page in enumerate(payload.get("changelog_pages", [])):
        name = f"changelog/page-{index:03d}.json"
        _atomic_write(base / name, page)
        written.append(name)
    manifest = {
        "snapshot_id": snapshot_id,
        "issue_key": payload.get("issue", {}).get("issue_key"),
        "exported_at": payload.get("exported_at"),
        "coverage": {
            "comments": comment_coverage(payload.get("comments_pages", [])),
            "changelog": changelog_coverage(payload.get("changelog_pages", [])),
        },
        "content_hashes": {
            name: hashlib.sha256((base / name).read_bytes()).hexdigest()
            for name in written
        },
        "task_md_sha256": payload.get("task_md_sha256"),
    }
    _atomic_write(base / "manifest.json", manifest)
    written.append("manifest.json")
    return {"snapshot_dir": str(base), "files": written, "manifest": manifest}


def _author_name(value):
    if not isinstance(value, dict):
        return None
    return value.get("displayName") or value.get("name")


def _comment_records(payload):
    records = []
    for page in payload.get("comments_pages", []):
        for comment in page.get("comments", []):
            records.append({
                "id": comment.get("id"),
                "author": _author_name(comment.get("author")),
                "created_at": comment.get("created_at"),
                "updated_at": comment.get("updated_at"),
                "text": comment.get("clean_text") or "",
                "body": comment.get("body"),
                "visibility": comment.get("visibility"),
            })
    return records


def _changelog_records(payload):
    records = []
    for page in payload.get("changelog_pages", []):
        for history in page.get("histories", []):
            records.append({
                "id": history.get("id"),
                "created_at": history.get("created"),
                "author": _author_name(history.get("author")),
                "items": history.get("items") or [],
            })
    return records


def _tracker_object(payload, snapshot_id, manifest):
    issue = payload.get("issue", {})
    return {
        "issue_key": issue.get("issue_key"),
        "exported_at": payload.get("exported_at"),
        "exporter": payload.get("exporter"),
        "availability": "present",
        "snapshot": {
            "snapshot_id": snapshot_id,
            "issue_key": issue.get("issue_key"),
            "coverage": manifest["coverage"],
            "source_dir": "internal",
            "created_at": issue.get("created"),
            "updated_at": issue.get("updated"),
            "summary": issue.get("summary"),
            "status": issue.get("status"),
            "resolution": issue.get("resolution"),
            "priority": issue.get("priority"),
            "assignee": _author_name(issue.get("assignee")),
            "reporter": _author_name(issue.get("reporter")),
            "fix_versions": [v.get("name") for v in issue.get("fix_versions", [])
                             if isinstance(v, dict)],
            "labels": issue.get("labels") or [],
            "components": [c.get("name") for c in issue.get("components", [])
                           if isinstance(c, dict)],
            "comments": _comment_records(payload),
            "changelog": _changelog_records(payload),
        },
        "source_ids": [],
    }


def _new_task_document(task_key):
    """Base task document for tracker create; defaults come from contract."""
    document = {
        "schema_version": "1.0",
        "kind": "task",
        "id": f"task:{task_key}",
        "revision": 1,
        "metadata": {
            "task_id": str(task_key),
            "title": f"Задача {task_key}",
            "task_type": "feature",
            "doc_type": None,
            "branch": None,
            "release": None,
            "updated_at": _now(),
            "status": "unknown",
            "source_status": None,
        },
        "business_logic": {"facts": [], "unconfirmed": [],
                           "linked_rule_ids": []},
    }
    return contract.fill_document_defaults(document)


def _derive_release_branch(payload, task_key, current_branch, task_type):
    release = None
    for version in payload.get("issue", {}).get("fix_versions", []):
        release = version.get("name")
        break
    branch = current_branch
    if task_type in ("feature", "bug"):
        branch = f"{'features' if task_type == 'feature' else 'bugfixes'}/#{task_key}"
    return release, branch


def ingest_tracker(store, task_key, payload, render=None):
    cleaned, errors = validate_tracker_input(payload)
    if errors:
        return {"status": "error", "errors": errors}
    snapshot_id = snapshot_id_for(cleaned)
    doc = store.load("task", task_key)
    existing = (doc or {}).get("tracker")
    if existing and existing.get("snapshot", {}).get("snapshot_id") == snapshot_id:
        return {"status": "noop", "snapshot_id": snapshot_id}

    manifest = write_tracker_snapshot(store.docs, task_key, snapshot_id, cleaned)["manifest"]
    tracker_obj = _tracker_object(cleaned, snapshot_id, manifest)
    if doc is None:
        document = _new_task_document(str(task_key))
        issue = cleaned.get("issue") if isinstance(cleaned.get("issue"), dict) else {}
        summary = issue.get("summary")
        if isinstance(summary, str) and summary.strip():
            document["metadata"]["title"] = summary.strip()
        kind = ((issue.get("issuetype") or {}).get("name") or "").strip().lower()
        task_type = "bug" if kind in ("баг", "bug") else "feature"
        document["metadata"]["task_type"] = task_type
        document["metadata"]["branch"] = (
            "bugfixes" if task_type == "bug" else "features") + f"/#{task_key}"
        document["tracker"] = tracker_obj
        release, branch = _derive_release_branch(
            cleaned, task_key, document["metadata"]["branch"],
            document["metadata"]["task_type"])
        document["metadata"]["release"] = release
        document["metadata"]["branch"] = branch
        document["metadata"]["updated_at"] = _now()
        envelope = {"schema_version": "1.0",
                    "operation_id": f"tracker-create-{task_key}-{snapshot_id[:8]}",
                    "expected_revision": 0, "actor": "gototask",
                    "reason": "tracker ingest create", "operations": [],
                    "document": document}
        outcome = store.apply("task", task_key, envelope)
    else:
        release, branch = _derive_release_branch(
            cleaned, task_key, doc["metadata"].get("branch"),
            doc["metadata"].get("task_type"))
        ops = [{"op": "set", "collection": "tracker", "key": "tracker",
                "value": tracker_obj}]
        if release != doc["metadata"].get("release"):
            ops.append({"op": "set", "collection": "metadata.release",
                        "key": "release", "value": release})
        if branch != doc["metadata"].get("branch"):
            ops.append({"op": "set", "collection": "metadata.branch",
                        "key": "branch", "value": branch})
        envelope = {"schema_version": "1.0",
                    "operation_id": f"tracker-{task_key}-{snapshot_id[:8]}",
                    "expected_revision": doc["revision"], "actor": "gototask",
                    "reason": "tracker ingest", "operations": ops,
                    "document": None}
        outcome = store.apply("task", task_key, envelope)
    if callable(render):
        try:
            from .render import render_document
            render_document(store.root, store.docs, "task", task_key,
                            store.load("task", task_key))
        except Exception:
            pass
    return {"status": "applied", "snapshot_id": snapshot_id,
            "revision": (outcome or {}).get("revision")}


# ------------------------------------------------------------------- git

class GitIngest:
    def __init__(self, repo):
        self.repo = Path(repo)

    def _git(self, argv):
        env = dict(os.environ)
        env["GIT_CEILING_DIRECTORIES"] = str(self.repo.resolve().parent)
        return subprocess.run(["git"] + argv, cwd=str(self.repo),
                              capture_output=True, env=env, timeout=60)

    def head_oid(self):
        proc = self._git(["rev-parse", "HEAD"])
        return proc.stdout.decode().strip() if proc.returncode == 0 else None

    def contained_refs(self, oid):
        result = {"local": [], "remote": []}
        proc = self._git(["branch", "--contains", oid])
        if proc.returncode == 0:
            result["local"] = [ln.strip().lstrip("* ").split(" ")[0]
                               for ln in proc.stdout.decode().splitlines()
                               if ln.strip()]
        proc = self._git(["branch", "-r", "--contains", oid])
        if proc.returncode == 0:
            result["remote"] = [ln.strip().lstrip("* ").split(" ")[0]
                                for ln in proc.stdout.decode().splitlines()
                                if ln.strip()]
        return result

    def remote_tip(self, ref):
        proc = self._git(["rev-parse", f"refs/remotes/{ref}"])
        if proc.returncode != 0:
            proc = self._git(["rev-parse", f"origin/{ref}"])
        return proc.stdout.decode().strip() if proc.returncode == 0 else None

    def is_ancestor(self, oid, tip):
        proc = self._git(["merge-base", "--is-ancestor", oid, tip])
        if proc.returncode == 0:
            return "present"
        if proc.returncode == 1:
            return "absent"
        return "unknown"

    def classify_release(self, refs, patterns):
        import fnmatch
        return [ref for ref in refs
                if any(fnmatch.fnmatch(ref, pat) for pat in patterns)]


def build_git_state(repo, commit_oids, patterns, fetch_status="unknown"):
    git = GitIngest(repo)
    if not commit_oids:
        raise IngestError("no_commits")
    all_local, all_remote = set(), set()
    for oid in commit_oids[:60]:
        refs = git.contained_refs(oid)
        all_local.update(refs["local"])
        all_remote.update(refs["remote"])
    pushed, not_pushed, unknown_refs = [], [], []
    for ref in sorted(all_remote):
        tip = git.remote_tip(ref)
        states = [git.is_ancestor(oid, tip) if tip else "unknown"
                  for oid in commit_oids[:60]]
        if any(state == "unknown" for state in states):
            unknown_refs.append(ref)
        elif all(state == "present" for state in states):
            pushed.append(ref)
        else:
            not_pushed.append(ref)
    contained = []
    for ref in sorted(all_local):
        states = [git.is_ancestor(oid, ref) for oid in commit_oids[:60]]
        if states and all(state == "present" for state in states):
            contained.append(ref)
    return {
        "checked_at": _now(),
        "commit": commit_oids[-1],
        "pushed_to": pushed,
        "contained_in": contained,
        "release_branches": git.classify_release(pushed + contained, patterns),
        "not_pushed_refs": not_pushed + unknown_refs,
        "unmatched_branches": [ref for ref in sorted(set(pushed + contained))
                               if not git.classify_release([ref], patterns)],
        "fetch_status": fetch_status,
        "source_ids": [],
    }


def ingest_git(store, task_key, repo, patterns, fetch_status="unknown",
               render=None):
    doc = store.load("task", task_key)
    if doc is None:
        return {"status": "not_found", "errors": [{"code": "NOT_FOUND"}]}
    commits = [event["commit"] for event in doc.get("git_events", [])
               if event.get("action") == "commit"]
    if not commits:
        return {"status": "unknown", "errors": [{"code": "no_commits"}]}
    state = build_git_state(repo, commits, patterns, fetch_status=fetch_status)
    semantic = {k: v for k, v in state.items() if k != "checked_at"}
    existing = doc.get("git_state") or {}
    existing_semantic = {k: v for k, v in existing.items() if k != "checked_at"}
    if existing_semantic == semantic:
        return {"status": "noop", "git_state": state}
    ops = [{"op": "set", "collection": "git_state", "key": "git_state",
            "value": state}]
    branch = None
    distinct = {event.get("branch") for event in doc.get("git_events", [])}
    if not doc["metadata"].get("branch") and len(distinct) == 1:
        branch = distinct.pop()
        ops.append({"op": "set", "collection": "metadata.branch",
                    "key": "branch", "value": branch})
    envelope = {"schema_version": "1.0",
                "operation_id": f"git-{task_key}-" +
                hashlib.sha256(_canonical(semantic)).hexdigest()[:10],
                "expected_revision": doc["revision"], "actor": "send-to-git",
                "reason": "git containment ingest", "operations": ops,
                "document": None}
    outcome = store.apply("task", task_key, envelope)
    if callable(render):
        try:
            from .render import render_document
            render_document(store.root, store.docs, "task", task_key,
                            store.load("task", task_key))
        except Exception:
            pass
    return {"status": "applied", "revision": (outcome or {}).get("revision"),
            "git_state": state}
