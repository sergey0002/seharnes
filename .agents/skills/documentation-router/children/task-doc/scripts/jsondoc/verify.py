"""Execution state machine, selftest runner and stage verification (J00).

Reads/writes only under .doc/skil_data/task-doc/{state,runs,implementation}.
Never executes commands or prompts stored in any document.
"""

import json
import os
import subprocess
import sys
import time
import unittest
from pathlib import Path

STAGE_ORDER = [f"J{i:02d}" for i in range(18)]
HARNESS_PATTERNS = [
    "jsondoc.py", "jsondoc", "tests", "schemas",
]


def _canonical_bytes(data):
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(_canonical_bytes(data))
    os.replace(tmp, path)


def _read_json(path, default=None):
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _scripts_dir(docs):
    return docs / "skil_data" / "task-doc"


def execution_state_path(docs):
    return _scripts_dir(docs) / "state" / "execution.json"


def load_execution(docs):
    state = _read_json(execution_state_path(docs), default=None)
    if state is None:
        state = {
            "schema_version": "1.0",
            "stages": {stage: {"status": "pending", "updated_at": None}
                       for stage in STAGE_ORDER},
            "updated_at": _now(),
        }
    return state


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def execution_next(root, docs):
    state = load_execution(docs)
    nxt = None
    for stage in STAGE_ORDER:
        entry = state["stages"].get(stage, {"status": "pending"})
        if entry.get("status") != "passed":
            nxt = stage
            break
    return {
        "status": "ok",
        "next_stage": nxt,
        "next_action": f"implement {nxt}" if nxt else "all stages passed",
        "stages": {k: v.get("status") for k, v in state["stages"].items()},
        "exit": 0,
    }


def execution_verify_stage(root, docs, stage):
    if stage not in STAGE_ORDER:
        return {"status": "error", "errors": [{"code": "unknown_stage", "stage": stage}], "exit": 2}
    state = load_execution(docs)
    entry = state["stages"].get(stage, {})
    errors = []
    idx = STAGE_ORDER.index(stage)
    for dep in STAGE_ORDER[:idx]:
        dep_entry = state["stages"].get(dep, {})
        if dep_entry.get("status") != "passed":
            errors.append({"code": "dependency_not_passed", "stage": dep})
    stage_file = _scripts_dir(docs) / "implementation" / stage / "stage.json"
    record = _read_json(stage_file, default=None)
    if record is None:
        errors.append({"code": "missing_stage_record"})
    else:
        if not record.get("test_run_refs"):
            errors.append({"code": "missing_test_evidence"})
        if record.get("status") not in ("passed", "failed", "blocked"):
            errors.append({"code": "invalid_stage_status"})
        if record.get("status") != "passed":
            errors.append({"code": "stage_not_passed", "current": record.get("status")})
    status = "blocked" if errors else "ok"
    return {
        "status": status,
        "stage": stage,
        "recorded_status": (record or {}).get("status"),
        "dependencies": STAGE_ORDER[:idx],
        "errors": errors,
        "next_action": "resolve_blockers" if errors else "proceed_next_stage",
        "exit": 2 if errors else 0,
    }


def _suite_modules(docs, stage=None, through=None, suite=None):
    suites = _read_json(_scripts_dir(docs) / "tests" / "suites.json", default={})
    modules = []
    if suite:
        entry = suites.get("suites", {}).get(suite)
        if not entry:
            return None, f"unknown_suite:{suite}"
        modules = list(entry.get("modules", []))
    elif through:
        if through not in STAGE_ORDER:
            return None, "unknown_stage"
        for st in STAGE_ORDER[: STAGE_ORDER.index(through) + 1]:
            modules.extend(suites.get("stages", {}).get(st, []))
    elif stage:
        if stage not in STAGE_ORDER:
            return None, "unknown_stage"
        modules = list(suites.get("stages", {}).get(stage, []))
    else:
        return None, "selector_required"
    return [m for m in dict.fromkeys(modules)], None


def run_selftest(root, docs, stage=None, through=None, suite=None, run_id=None):
    selectors = sum(1 for x in (stage, through, suite) if x)
    if selectors != 1:
        return {"status": "error",
                "errors": [{"code": "selector_required",
                            "message": "exactly one of --stage/--through/--suite"}],
                "exit": 2}
    modules, err = _suite_modules(docs, stage=stage, through=through, suite=suite)
    if err:
        return {"status": "error", "errors": [{"code": err}], "exit": 2}
    if not modules:
        return {"status": "error",
                "errors": [{"code": "empty_suite",
                            "message": "no test modules bound to selector yet"}],
                "exit": 2}

    run_dir = _scripts_dir(docs) / "runs" / run_id
    sandbox = run_dir / "sandbox"
    sandbox.mkdir(parents=True, exist_ok=True)
    tests_dir = _scripts_dir(docs) / "tests"

    loader = unittest.TestLoader()
    suite_obj = unittest.TestSuite()
    for module in modules:
        try:
            loaded = loader.loadTestsFromName(module)
        except ImportError as exc:
            return {"status": "error", "run": run_id,
                    "errors": [{"code": "module_import_failed",
                                "module": module, "message": str(exc)}], "exit": 2}
        suite_obj.addTests(loaded)

    env = dict(os.environ)
    for var in ("TMPDIR", "TEMP", "TMP"):
        env[var] = str(sandbox)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # support module resolves sandbox relative to docs; expose run id to tests
    env["JSONDOC_RUN_DIR"] = str(run_dir)

    runner_result_path = run_dir / "unittest.json"
    argv = [sys.executable, "-m", "unittest", "-v"] + [
        f"{module}" for module in modules]
    proc = subprocess.run(argv, cwd=str(tests_dir),
                          env=env, capture_output=True, text=False, timeout=600)
    stdout = proc.stdout.decode("utf-8", "replace")
    stderr = proc.stderr.decode("utf-8", "replace")

    results = {
        "schema_version": "1.0",
        "run": run_id,
        "selector": {"stage": stage, "through": through, "suite": suite},
        "modules": modules,
        "exit_code": proc.returncode,
        "passed": proc.returncode == 0,
        "ran_lines": [ln for ln in stderr.splitlines() if ln.startswith(("ok", "FAIL", "ERROR", "Ran "))],
        "timestamp": _now(),
    }
    _write_json(runner_result_path, results)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs" / "stdout.txt").write_text(stdout, encoding="utf-8")
    (run_dir / "logs" / "stderr.txt").write_text(stderr, encoding="utf-8")

    if proc.returncode != 0:
        failures = [ln for ln in stderr.splitlines()
                    if ln.startswith(("FAIL:", "ERROR:"))]
        return {"status": "failed", "run": run_id, "failures": failures,
                "results_path": str(runner_result_path.relative_to(root)),
                "next_action": "fix_failures_and_rerun", "exit": 2}

    return {
        "status": "passed",
        "run": run_id,
        "modules": modules,
        "results_path": str(runner_result_path.relative_to(root)),
        "next_action": "record_stage_evidence",
        "exit": 0,
    }


def capture_baseline(root, docs, run_id):
    """Hash the real tool package (location of this module) for J-level diffs."""
    scripts = Path(__file__).resolve().parents[1]
    out_root = _scripts_dir(docs)
    entries = {}
    for path in sorted(scripts.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(scripts).as_posix()
        if rel.startswith(("runs/", "__pycache__/")) or rel.endswith(".pyc"):
            continue
        entries[rel] = _sha256_file(path)
    baseline = {
        "schema_version": "1.0",
        "run": run_id,
        "captured_at": _now(),
        "files": entries,
    }
    out = out_root / "runs" / run_id / "baseline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    _write_json(out, baseline)
    return {"status": "ok", "files": len(entries),
            "path": str(out.relative_to(root)), "exit": 0}


def _sha256_file(path):
    import hashlib
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
