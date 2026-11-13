"""Shared test support: sandbox root, canonical JSON, fixtures (J00).

Sandbox is resolved under .doc/skil_data/task-doc/runs/{RUN}/sandbox (via
JSONDOC_RUN_DIR env set by verify.run_selftest) with a safe default for
direct unittest runs. Tests must not touch live task folders or /tmp.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


_CASE_COUNTER = [0]


def sandbox_root():
    run_dir = os.environ.get("JSONDOC_RUN_DIR")
    if run_dir:
        root = Path(run_dir) / "sandbox"
    else:
        root = Path(tempfile.mkdtemp(prefix="jsondoc-selftest-"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def make_docs(root=None):
    """Fresh isolated docs tree per call (unique case dir under sandbox)."""
    _CASE_COUNTER[0] += 1
    base = Path(root) if root else sandbox_root()
    root = base / f"case-{_CASE_COUNTER[0]}"
    docs = root / ".doc"
    (docs / "skil_data" / "task-doc").mkdir(parents=True, exist_ok=True)
    return root, docs


def canonical_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def write_canonical(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_bytes(data))
    return path


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def minimal_task(task_id="2612", title="Услуга архивации ОИС"):
    return {
        "schema_version": "1.0",
        "kind": "task",
        "id": f"task:{task_id}",
        "revision": 1,
        "metadata": {
            "task_id": task_id,
            "title": title,
            "task_type": "feature",
            "doc_type": None,
            "branch": f"features/#{task_id}",
            "release": None,
            "updated_at": "2026-09-25T15:00:00Z",
            "status": "unknown",
            "source_status": None,
        },
        "summary": None,
        "tags": [],
        "sections": [],
        "section_order": [],
        "files": [],
        "findings": [],
        "decisions": [],
        "requirements": [],
        "progress": [],
        "stages": [],
        "notes": [],
        "relations": [],
        "artifacts": [],
        "checks": [],
        "git_events": [],
        "tracker": None,
        "git_state": None,
        "jira_report": None,
        "sources": [],
        "history": [],
    }
