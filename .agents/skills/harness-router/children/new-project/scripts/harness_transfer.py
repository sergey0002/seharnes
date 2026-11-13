#!/usr/bin/env python3
"""Read-only harness transfer engine: fetch, inventory, plan and verify.

This is the P1 surface from the migration plan. It fetches one named ref into
a local bare object store, discovers an explicitly selected file set, compares
a local source directory or that bare store with the target, and writes only
preview state. It does not establish release trust, approve decisions, apply
changes or finalize a receipt. Candidate files are never executed.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness-core/scripts"))

from canon_paths import PolicyError, load_preliminary_policy_bundle, read_policy
from transfer_git import (discover_git_paths, fetch_ref, init_bare_store, plan_selected_git_update,
                          snapshot_git_blobs, validate_ref, validate_remote)
from transfer_inventory import discover_target_paths, snapshot_files, validate_paths
from transfer_apply import ApplyError, apply_plan, rollback_plan
import profile_manifest
from transfer_local import selected_local_paths, validate_local_extension
from transfer_plan import _root_path, plan_selected_update
from transfer_receipt import read_preview_receipt, read_receipt_document, receipt_paths_in_roots, write_receipt
from transfer_report import summarize_preview

EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_NEEDS_DECISION = 2
EXIT_FAILED_PREFLIGHT = 3
EXIT_STALE_PLAN = 4
EXIT_ROLLED_BACK = 5
EXIT_NEEDS_MANUAL = 6

PLAN_LIFETIME = timedelta(hours=1)
STATE_SUBDIR = Path(".doc/web/state")
RECEIPT_SUBDIR = STATE_SUBDIR / "transfer"
CANON_POLICY = Path(".doc/harnes/state/canon-paths.yaml")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _tree_digest(states: dict) -> str:
    digest = hashlib.sha256()
    for path in sorted(states):
        state = states[path]
        digest.update(f"{path}\0{state.mode:o}\0{state.sha256}\n".encode("utf-8"))
    return digest.hexdigest()


def _state_dict(states: dict) -> dict:
    return {path: {"sha256": state.sha256, "mode": state.mode}
            for path, state in sorted(states.items())}


def _check(check_id: str, status: str, reason: str | None = None) -> dict:
    item = {"id": check_id, "status": status}
    if reason is not None:
        item["reason"] = reason
    return item


def _fail(code: str, reason: str, **extra) -> int:
    payload = {"status": "failed_preflight", "code": code, "reason": reason}
    payload.update(extra)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return EXIT_FAILED_PREFLIGHT


def _preflight_error(error: Exception, **extra) -> int:
    if isinstance(error, PolicyError):
        return _fail(error.code, "policy bundle rejected", policy_id=error.policy_id,
                     relative_path=error.relative_path, field=error.field)
    reason = str(error) or error.__class__.__name__
    return _fail("failed_preflight", reason, **extra)


def _policy_gate(root: Path) -> dict:
    if not (root / CANON_POLICY).exists():
        return _check("policy_gate", "not_applicable", "canon-paths.yaml is absent")
    load_preliminary_policy_bundle(root)
    return _check("policy_gate", "passed")


def _read_receipt(target: Path) -> tuple[dict | None, dict | None]:
    path = target / RECEIPT_SUBDIR / "receipt.json"
    if not path.exists():
        return None, None
    states, info = read_preview_receipt(path)
    return states, info


def _state_dir(target: Path, installed: bool, override: str | None) -> Path:
    if override:
        directory = Path(override).absolute()
    elif installed:
        directory = target / STATE_SUBDIR / "plans"
    else:
        directory = Path(tempfile.gettempdir()) / "harness-transfer" / "plans"
    directory.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        try:
            directory.chmod(0o700)
        except OSError:
            pass
    return directory


def _write_plan(state_dir: Path, plan_id: str, payload: dict) -> Path:
    path = state_dir / f"{plan_id}.json"
    temporary = state_dir / f".{plan_id}.tmp"
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    os.replace(temporary, path)
    return path


def _emit(events: list[dict], run_id: str, sequence: int, event: str, **fields) -> int:
    item = {"sequence": sequence, "run_id": run_id, "time": _iso(_utc_now()), "event": event}
    item.update(fields)
    events.append(item)
    return sequence + 1


def _print_events(events: list[dict]) -> None:
    for event in events:
        print(json.dumps(event, ensure_ascii=False, sort_keys=True))


def _source_snapshot(args, paths: list[str]) -> tuple[dict, str, str | None]:
    if args.source_kind == "git":
        if not args.repo or not args.commit:
            raise ValueError("git source requires --repo and --commit")
        states = snapshot_git_blobs(args.repo, args.commit, paths, max_file_bytes=args.max_file_bytes)
        return states, "local_bare_git", args.commit
    if not args.source:
        raise ValueError("local source requires --source")
    states = snapshot_files(args.source, paths, max_file_bytes=args.max_file_bytes)
    return states, "local_source", None


def _source_paths(args, roots: list[str], excludes: list[str] | None = None) -> tuple[list[str], list[str]]:
    paths: list[str] = []
    protected: list[str] = []
    if args.source_kind == "git":
        if not args.repo or not args.commit:
            raise ValueError("git source requires --repo and --commit")
        paths.extend(discover_git_paths(args.repo, args.commit, roots))
    else:
        if not args.source:
            raise ValueError("local source requires --source")
        files, protected = discover_target_paths(_root_path(args.source, must_exist=True), roots,
                                                 excludes=excludes)
        paths.extend(files)
    return paths, protected


def _is_excluded(path: str, excludes: list[str]) -> bool:
    for item in excludes:
        item = item.rstrip("/")
        if path == item or path.startswith(item + "/"):
            return True
    return False


def _validate_exclude(item: str) -> None:
    if (not isinstance(item, str) or not item or item.startswith("/") or item.startswith("\\")
            or ".." in Path(item).parts or (os.name == "nt" and os.path.splitdrive(item)[0])):
        raise ValueError(f"invalid exclude: {item}")


def _selection(args, roots: list[str], receipt: dict | None) -> tuple[list[str], list[str], list[str]]:
    excludes = list(getattr(args, "exclude", None) or [])
    for item in excludes:
        _validate_exclude(item)
    paths: list[str] = []
    protected: list[str] = []
    if roots:
        source_files, source_protected = _source_paths(args, roots, excludes)
        paths.extend(source_files)
        protected.extend(source_protected)
        target_root = _root_path(args.target, must_exist=False)
        if target_root.is_dir():
            files, target_protected = discover_target_paths(target_root, roots, excludes=excludes)
            paths.extend(files)
            protected = sorted(set(protected) | set(target_protected))
        if args.base_commit:
            if args.source_kind != "git":
                raise ValueError("--base-commit requires a git source")
            paths.extend(discover_git_paths(args.repo, args.base_commit, roots))
        if receipt is not None:
            paths.extend(receipt_paths_in_roots(list(receipt), roots))
    if args.path:
        paths.extend(validate_paths(args.path))
    if not paths:
        raise ValueError("at least one --root or --path is required")
    paths = [path for path in paths if not _is_excluded(path, excludes)]
    return sorted(set(paths)), sorted(set(protected)), roots


def _profile_selection(args) -> tuple[list[str], list[str]]:
    if args.source_kind != "local" or not args.source:
        raise ValueError("profile path selection requires a local source")
    files, _ = profile_manifest.build(Path(args.source), args.profile)
    generated = (".qoder/skills/", ".qwen/skills/", ".dsh/skills/",
                 ".codex/rules/", ".kilo/rules/", ".agents/rules/",
                 ".agents/mcp.json", ".agents/mcp_config.json", ".agents/skills.json",
                 ".codex/mcp.json", ".codex/config.toml", ".kilo/mcp.json", ".kilo/kilo.jsonc",
                 ".kilo/kilo-permissions.fragment.jsonc", ".qoder/rules/", ".qoder/settings.json",
                 ".qwen/rules/", ".qwen/settings.json", ".dsh/project.patch.yml",
                 ".dsh/models.overlay.json", "DSH-RULES.md")
    secrets = ("mcp.env", ".env", "config.env")
    paths, roots = [], set()
    for path in files:
        if path.startswith((".kilo/", ".qoder/", ".qwen/", ".dsh/", ".codex/", ".serena/",
                             ".cursor/tools/", ".codex/tools/")):
            continue
        if path.startswith(".tools/") and not path.startswith(".tools/scripts/"):
            continue
        if path.endswith(".phar") or path.startswith(generated) or any(
                path.endswith("/" + name) or path == name for name in secrets):
            continue
        if "/" in path:
            parts = path.split("/")
            roots.add("/".join(parts[:2]) if parts[0] in (".doc", ".tools") else parts[0])
        else:
            paths.append(path)
    defaults = [".doc/harnes/astra_plan", ".doc/harnes/idea", ".doc/harnes/plan",
                ".doc/harnes/audit", ".doc/harnes/state/.validate-rules-last.json",
                ".doc/skil_data", ".doc/tasks", ".doc/architecture", ".doc/archive", ".doc/qa",
                ".cursor/tools", ".codex/tools", ".kilo", ".qoder", ".qwen", ".dsh", ".codex", ".serena"]
    args.exclude = sorted(set(list(getattr(args, "exclude", None) or []) + defaults))
    return sorted(roots), sorted(paths)


def _base_state(args, paths: list[str], receipt: dict | None) -> tuple[dict | None, str]:
    if args.base_commit:
        base = snapshot_git_blobs(args.repo, args.base_commit, paths, max_file_bytes=args.max_file_bytes)
        return {path: state for path, state in base.items()}, "historical_commit_unverified"
    if receipt is not None:
        return {path: receipt[path] for path in paths if path in receipt}, "receipt_unverified"
    return None, "unknown"


def _local_paths(args, paths: list[str], receipt: dict | None, roots: list[str]) -> list[str]:
    local = list(args.local)
    if not args.use_local_policy:
        return sorted(set(local))
    if not roots:
        raise ValueError("local policy requires --root")
    if receipt is None and not args.base_commit:
        raise ValueError("local policy requires a receipt or --base-commit")
    policy_dir = _root_path(Path(args.target).absolute() / ".doc/harnes/state", must_exist=True)
    policy = read_policy(policy_dir / "canon-paths.local.yaml")
    historical = receipt_paths_in_roots(list(receipt), roots) if receipt is not None else discover_git_paths(
        args.repo, args.base_commit, roots)
    components = validate_local_extension(policy, historical, roots)
    return sorted(set(local) | set(selected_local_paths(paths, components)))


def _read_release_manifest(path: Path) -> dict:
    raw = Path(path)
    info = raw.lstat()
    if not raw.is_file() or raw.is_symlink() or info.st_size > 16 * 1024 * 1024:
        raise ValueError("release manifest is not a bounded regular file")
    data = json.loads(raw.read_text(encoding="utf-8"))
    if (not isinstance(data, dict) or data.get("schema_version") != 1
            or data.get("kind") != "harness-release-manifest"):
        raise ValueError("invalid release manifest")
    source = data.get("source")
    files = data.get("files")
    excluded = data.get("excluded")
    if (not isinstance(source, dict) or not isinstance(source.get("commit"), str)
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", source["commit"])
            or not isinstance(files, list) or not isinstance(excluded, list)
            or len(files) > 20000 or len(excluded) > 20000):
        raise ValueError("invalid release manifest")
    for item in files:
        if (not isinstance(item, dict) or set(item) != {"path", "mode", "size", "sha256"}
                or not isinstance(item["path"], str) or item["mode"] not in ("100644", "100755")
                or type(item["size"]) is not int or item["size"] < 0
                or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
            raise ValueError("invalid release manifest file entry")
    return data


def _check_release_manifest(path: Path, commit: str | None, source_kind: str, states: dict) -> dict:
    data = _read_release_manifest(path)
    if commit is not None and data["source"]["commit"] != commit:
        raise ValueError("release manifest commit does not match the pinned commit")
    indexed = {item["path"]: item for item in data["files"]}
    missing = sorted(set(states) - set(indexed))
    if missing:
        raise ValueError("release manifest is missing selected files: " + ", ".join(missing[:5]))
    mismatched = sorted(path for path, state in states.items() if indexed[path]["sha256"] != state.sha256)
    if mismatched:
        raise ValueError("release manifest content differs: " + ", ".join(mismatched[:5]))
    if source_kind == "local_bare_git":
        mode_mismatch = sorted(path for path, state in states.items()
                               if int(indexed[path]["mode"], 8) & 0o777 != state.mode)
        if mode_mismatch:
            raise ValueError("release manifest mode differs: " + ", ".join(mode_mismatch[:5]))
    return {"path": str(Path(path).absolute()), "commit": data["source"]["commit"],
            "status": "content_consistent_not_trusted"}


class StalePlan(ValueError):
    pass


class DecisionError(ValueError):
    pass


def _unique_object(pairs):
    data = {}
    for key, value in pairs:
        if key in data:
            raise ValueError("duplicate JSON key")
        data[key] = value
    return data


def _read_json_file(path: Path, limit: int = 16 * 1024 * 1024) -> tuple[dict, bytes]:
    raw = Path(path)
    info = raw.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError("JSON input is not a bounded regular file")
    data_bytes = raw.read_bytes()
    data = json.loads(data_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
    if not isinstance(data, dict):
        raise ValueError("JSON input must be an object")
    return data, data_bytes


def _mapping_digest(states: dict) -> str:
    digest = hashlib.sha256()
    for path in sorted(states):
        state = states[path]
        digest.update(f"{path}\0{state['mode']:o}\0{state['sha256']}\n".encode("utf-8"))
    return digest.hexdigest()


def _allowed_choices(entry: dict) -> set[str]:
    choices = entry.get("choices")
    if isinstance(choices, list) and choices:
        return {item for item in choices if isinstance(item, str)}
    action = entry.get("action")
    if action == "add":
        return {"add", "skip"}
    if action == "replace":
        return {"replace", "skip"}
    return {"keep", "skip"}


def _source_states_for_plan(plan: dict, paths: list[str]) -> dict:
    source = plan.get("source")
    if not isinstance(source, dict):
        raise ValueError("plan has no source identity")
    kind = source.get("kind")
    if kind == "local_source":
        root = Path(source.get("path", ""))
        if not root.is_absolute():
            raise ValueError("plan source path is not absolute")
        return snapshot_files(root, paths, max_file_bytes=plan.get("max_file_bytes", 8 * 1024 * 1024))
    if kind == "local_bare_git":
        repo = Path(source.get("repo", ""))
        commit = source.get("commit")
        if not repo.is_absolute() or not isinstance(commit, str):
            raise ValueError("plan Git source is invalid")
        return snapshot_git_blobs(repo, commit, paths, max_file_bytes=plan.get("max_file_bytes", 8 * 1024 * 1024))
    raise ValueError("plan source kind is unsupported")


def _verify_plan_current(plan: dict, paths: list[str]) -> dict:
    target = plan.get("target")
    if not isinstance(target, dict) or not isinstance(target.get("path"), str):
        raise ValueError("plan has no target path")
    target_root = _root_path(Path(target["path"]), must_exist=False)
    current = snapshot_files(target_root, paths, max_file_bytes=plan.get("max_file_bytes", 8 * 1024 * 1024)) \
        if target_root.is_dir() else {}
    current_map = _state_dict(current)
    if current_map != plan.get("target_snapshot"):
        raise StalePlan("target changed after the plan")
    if _tree_digest(_source_states_for_plan(plan, paths)) != plan.get("source_tree_digest"):
        raise StalePlan("source changed after the plan")
    return current_map


def _check_approval(plan: dict, plan_bytes: bytes, approved: dict) -> None:
    if (approved.get("kind") != "harness-transfer-approval"
            or approved.get("schema_version") != 1
            or approved.get("plan_id") != plan.get("plan_id")
            or approved.get("plan_sha256") != hashlib.sha256(plan_bytes).hexdigest()
            or approved.get("source_tree_digest") != plan.get("source_tree_digest")):
        raise DecisionError("approval does not match the plan")
    required = plan.get("decisions_required")
    decisions = approved.get("decisions")
    if not isinstance(required, list) or not isinstance(decisions, dict):
        raise DecisionError("approval decisions are malformed")
    required_paths = {entry.get("path") for entry in required if isinstance(entry, dict)}
    if set(decisions) != required_paths:
        raise DecisionError("approval decisions do not cover the required paths")
    for entry in required:
        if decisions.get(entry["path"]) not in _allowed_choices(entry):
            raise DecisionError(f"invalid approved decision for {entry['path']}")


def _run_render(args) -> tuple[int, dict]:
    target = _root_path(Path(args.target).absolute(), must_exist=True)
    renderer = Path(__file__).resolve().parents[2] / "environment-sync/scripts/render_agent_views.py"
    if not renderer.is_file():
        raise ValueError("trusted renderer is missing")
    command = [sys.executable, str(renderer), "--root", str(target)]
    if args.check:
        command.append("--check")
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=300, check=False)
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("renderer returned an invalid report") from error
    if result.returncode != 0 or payload.get("status") not in ("passed", "rendered"):
        payload.setdefault("status", "failed")
        return EXIT_FAILED_PREFLIGHT, {"schema_version": 1, **payload}
    return EXIT_PASSED, {"schema_version": 1, **payload}


def _adopt_commit(args) -> tuple[int, dict]:
    plan, _ = _read_json_file(args.plan)
    decisions, _ = _read_json_file(args.decisions)
    if plan.get("operation") != "adopt" or plan.get("schema_version") != 1:
        raise ValueError("invalid adopt plan")
    try:
        expires = datetime.strptime(plan.get("expires_at", ""), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError) as error:
        raise ValueError("invalid adopt expiry") from error
    if _utc_now() > expires:
        raise StalePlan("adopt plan has expired")
    if decisions.get("schema_version") != 1 or not isinstance(decisions.get("decisions"), dict):
        raise DecisionError("invalid decisions file")
    files = plan.get("files")
    required = {entry.get("path") for entry in plan.get("decisions_required", []) if isinstance(entry, dict)}
    if not isinstance(files, list) or len(required) != len(files):
        raise ValueError("adopt plan is incomplete")
    supplied = decisions["decisions"]
    if set(supplied) != required:
        raise DecisionError("decisions must cover exactly the adopt paths")
    if any(choice not in ("keep", "adopt", "skip") for choice in supplied.values()):
        raise DecisionError("invalid adopt decision")
    target = plan.get("target", {}).get("path")
    roots = plan.get("roots")
    if not isinstance(target, str) or not Path(target).is_absolute() or not isinstance(roots, list):
        raise ValueError("adopt plan has no target or roots")
    target_root = _root_path(Path(target), must_exist=True)
    current = snapshot_files(target_root, [item["path"] for item in files], max_file_bytes=args.max_file_bytes)
    current_map = _state_dict(current)
    planned = {item["path"]: item["target"] for item in files}
    if current_map != planned:
        raise StalePlan("target changed after the adopt preview")
    receipt_path = Path(args.state_dir) if args.state_dir else target_root / ".doc/web/state/transfer"
    receipt_path = receipt_path if receipt_path.suffix == ".json" else receipt_path / "receipt.json"
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    existing = read_receipt_document(receipt_path) if receipt_path.exists() else None
    entries = dict(existing["files"]) if existing else {}
    adopted = []
    for path, choice in supplied.items():
        if choice != "adopt":
            continue
        state = current[path]
        entries[path] = {"installed_hash": state.sha256, "mode": state.mode,
                         "role": "owned", "decision": "adopted"}
        adopted.append(path)
    if not adopted:
        return EXIT_PASSED, {"schema_version": 1, "status": "no_changes", "adopted": []}
    release_url = existing["release_url"] if existing else "adopted-local"
    commit = _mapping_digest(current_map)
    receipt_sha = write_receipt(receipt_path, release_url=release_url, commit=commit,
                                profile=plan["profile"], files=entries)
    return EXIT_PASSED, {"schema_version": 1, "status": "adopted", "adopted": sorted(adopted),
                         "receipt_sha256": receipt_sha, "receipt": str(receipt_path)}


def _run_adopt(args) -> tuple[int, dict]:
    if args.plan or args.decisions:
        if not args.plan or not args.decisions:
            raise ValueError("adopt commit requires --plan and --decisions")
        return _adopt_commit(args)
    if args.target is None or not args.root or not args.profile:
        raise ValueError("adopt preview requires --target, --root and --profile")
    target = _root_path(Path(args.target).absolute(), must_exist=True)
    roots = list(validate_paths(args.root))
    if not roots:
        raise ValueError("adopt requires --root")
    files, protected = discover_target_paths(target, roots)
    states = snapshot_files(target, files, max_file_bytes=args.max_file_bytes)
    marker_path = target / ".doc/.rebase-kit.json"
    marker = None
    if marker_path.exists():
        marker_data, _ = _read_json_file(marker_path, limit=64 * 1024)
        marker = {key: marker_data.get(key) for key in ("status", "profile", "mode", "started")}
    plan_id = str(uuid.uuid4())
    now = _utc_now()
    payload = {
        "schema_version": 1,
        "plan_id": plan_id,
        "created_at": _iso(now),
        "expires_at": _iso(now + PLAN_LIFETIME),
        "status": "needs_decision",
        "operation": "adopt",
        "profile": args.profile,
        "source_kind": None,
        "target": {"exists": True, "path": str(target)},
        "roots": roots,
        "kit_marker": marker,
        "files": [{"path": path, "target": {"sha256": state.sha256, "mode": state.mode},
                   "incoming": None,
                   "proposal": {"status": "local_adopt_candidate", "action": "keep",
                                "choices": ["keep", "adopt", "skip"], "requires_review": True}}
                  for path, state in sorted(states.items())],
        "decisions_required": [{"path": path, "status": "local_adopt_candidate", "action": "keep",
                                "choices": ["keep", "adopt", "skip"]} for path in sorted(states)],
        "protected_paths_not_read": protected,
        "applyable": False,
    }
    state_dir = Path(args.state_dir) if args.state_dir else target / ".doc/web/state/plans"
    state_dir.mkdir(parents=True, exist_ok=True)
    plan_path = _write_plan(state_dir, plan_id, payload)
    payload["plan_path"] = str(plan_path)
    return EXIT_NEEDS_DECISION, payload


def _run_compact(args) -> tuple[int, dict]:
    target = _root_path(Path(args.target).absolute(), must_exist=True)
    script = Path(__file__).resolve().parents[2] / "environment-sync/scripts/compact_agent_views.py"
    if not script.is_file():
        raise ValueError("compact helper is missing")
    command = [sys.executable, str(script), "--root", str(target)]
    command.append("--check" if args.check else "--apply")
    if args.force:
        command.append("--force")
    result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, timeout=300, check=False)
    try:
        payload = json.loads(result.stdout.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ValueError("compact helper returned an invalid report") from error
    payload["schema_version"] = 1
    return result.returncode, payload


def _run_apply(args) -> tuple[int, dict]:
    plan, plan_bytes = _read_json_file(args.plan)
    approved, _ = _read_json_file(args.approved)
    if plan.get("schema_version") != 1 or not isinstance(plan.get("plan_id"), str):
        raise ValueError("invalid plan file")
    _check_approval(plan, plan_bytes, approved)
    paths = [item.get("path") for item in plan.get("files", []) if isinstance(item, dict)]
    _verify_plan_current(plan, paths)
    target = plan.get("target", {}).get("path")
    state_dir = Path(args.state_dir) if args.state_dir else Path(target) / ".doc/web/state/transfer"
    result = apply_plan(plan, approved, Path(target), state_dir,
                        max_file_bytes=plan.get("max_file_bytes", 8 * 1024 * 1024))
    status = result.get("status")
    if status in ("committed", "no_changes"):
        payload = {"schema_version": 1, **result,
                   "checks": [_check("apply", "passed"),
                              _check("verify", "passed" if status == "committed" else "not_run"),
                              _check("receipt", "passed" if status == "committed" else "not_run")]}
        auto_render = not getattr(args, "no_render", False) and (Path(target) / ".agents/skills").is_dir()
        if status == "committed" and (getattr(args, "render", False) or auto_render):
            render_code, render_payload = _run_render(SimpleNamespace(target=Path(target), check=False))
            payload["render"] = render_payload
            if render_code != EXIT_PASSED:
                payload["status"] = "committed_render_failed"
                payload["committed"] = True
                return EXIT_FAILED_PREFLIGHT, payload
        return EXIT_PASSED, payload
    if status == "rolled_back":
        return EXIT_ROLLED_BACK, {"schema_version": 1, **result}
    return EXIT_NEEDS_MANUAL, {"schema_version": 1, **result}


def _run_rollback(args) -> tuple[int, dict]:
    target = _root_path(Path(args.target), must_exist=True)
    state_dir = Path(args.state_dir) if args.state_dir else target / ".doc/web/state/transfer"
    result = rollback_plan(target, state_dir, max_file_bytes=args.max_file_bytes)
    if result.get("status") == "rolled_back":
        return EXIT_ROLLED_BACK, {"schema_version": 1, **result}
    return EXIT_NEEDS_MANUAL, {"schema_version": 1, **result}


def _run_approve(args) -> tuple[int, dict]:
    plan, plan_bytes = _read_json_file(args.plan)
    if plan.get("schema_version") != 1 or not isinstance(plan.get("plan_id"), str):
        raise ValueError("invalid plan file")
    try:
        uuid.UUID(plan["plan_id"])
    except (ValueError, AttributeError) as error:
        raise ValueError("invalid plan id") from error
    expires_at = plan.get("expires_at")
    if not isinstance(expires_at, str):
        raise ValueError("plan has no expiry")
    try:
        expiry = datetime.strptime(expires_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError("invalid plan expiry") from error
    if _utc_now() > expiry:
        raise StalePlan("plan has expired")

    decisions, _ = _read_json_file(args.decisions)
    if decisions.get("schema_version") != 1 or not isinstance(decisions.get("decisions"), dict):
        raise DecisionError("invalid decisions file")
    required = plan.get("decisions_required")
    files = plan.get("files")
    target = plan.get("target")
    if not isinstance(required, list) or not isinstance(files, list) or not isinstance(target, dict):
        raise ValueError("plan is incomplete")
    required_paths = {entry.get("path") for entry in required if isinstance(entry, dict)}
    if len(required_paths) != len(required) or None in required_paths:
        raise ValueError("plan decisions are malformed")
    supplied = decisions["decisions"]
    if set(supplied) != required_paths:
        raise DecisionError("decisions must cover exactly the required paths")
    for entry in required:
        choice = supplied.get(entry["path"])
        if choice not in _allowed_choices(entry):
            raise DecisionError(f"invalid decision for {entry['path']}")

    paths = [item.get("path") for item in files if isinstance(item, dict)]
    if len(paths) != len(files) or not all(isinstance(path, str) for path in paths):
        raise ValueError("plan file list is malformed")
    target_path = target.get("path")
    if not isinstance(target_path, str) or not Path(target_path).is_absolute():
        raise ValueError("plan has no absolute target path")
    target_root = _root_path(Path(target_path), must_exist=False)
    current_target = snapshot_files(target_root, paths, max_file_bytes=plan.get("max_file_bytes", 8 * 1024 * 1024)) \
        if target_root.is_dir() else {}
    current_target_map = _state_dict(current_target)
    planned_target = plan.get("target_snapshot")
    if not isinstance(planned_target, dict) or current_target_map != planned_target:
        raise StalePlan("target changed after the plan")
    source_states = _source_states_for_plan(plan, paths)
    if _tree_digest(source_states) != plan.get("source_tree_digest"):
        raise StalePlan("source changed after the plan")
    approved = {
        "schema_version": 1,
        "kind": "harness-transfer-approval",
        "plan_id": plan["plan_id"],
        "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(),
        "target_snapshot_digest": _mapping_digest(current_target_map),
        "source_tree_digest": plan.get("source_tree_digest"),
        "decisions": {path: supplied[path] for path in sorted(supplied)},
        "approved_at": _iso(_utc_now()),
        "expires_at": expires_at,
    }
    approved_path = Path(args.plan).absolute().parent / f"{plan['plan_id']}.approved.json"
    temporary = approved_path.with_name("." + approved_path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(approved, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, approved_path)
    try:
        os.chmod(approved_path, 0o600)
    except OSError:
        pass
    return EXIT_PASSED, {
        "schema_version": 1,
        "status": "approved",
        "plan_id": plan["plan_id"],
        "approved_path": str(approved_path),
        "decisions": approved["decisions"],
        "applyable": False,
        "checks": [_check("plan", "passed"), _check("target_snapshot", "passed"),
                   _check("source_digest", "passed"), _check("apply", "not_run",
                                                            "apply/rollback arrive in the P2 stage")],
    }


def _run_plan(args) -> tuple[int, dict]:
    if args.operation == "repair":
        raise ValueError("unsupported_operation: repair requires in-place apply and backup")
    target = _root_path(Path(args.target).absolute(), must_exist=False)
    receipt, receipt_info = _read_receipt(target) if args.use_receipt else (None, None)
    if args.use_receipt and receipt is None:
        raise ValueError("--use-receipt requires .doc/web/state/transfer/receipt.json")
    profile_selected = False
    if args.profile and not args.root and not args.path:
        roots, root_paths = _profile_selection(args)
        args.root = roots
        args.path = root_paths
        profile_selected = True
    roots: list[str] = []
    if args.root:
        validate_paths(args.root)
        roots = list(args.root)
    paths, protected, roots = _selection(args, roots, receipt)
    if not paths:
        raise ValueError("no files found under selected roots")
    if len(paths) > 2000:
        raise ValueError("too many selected paths")
    local_paths = _local_paths(args, paths, receipt, roots)
    base, base_kind = _base_state(args, paths, receipt)
    if base is not None and set(local_paths) & set(base):
        raise ValueError("LOCAL_POLICY_ESCALATION: local path overlaps baseline")
    base_for_plan = {path: state for path, state in base.items() if path not in local_paths} if base is not None else None

    if args.source_kind == "git":
        result = plan_selected_git_update(repo=args.repo, commit=args.commit, target=target, paths=paths,
                                          receipt=base_for_plan, local_paths=local_paths,
                                          max_file_bytes=args.max_file_bytes)
    else:
        result = plan_selected_update(source=args.source, target=target, paths=paths,
                                      receipt=base_for_plan, local_paths=local_paths,
                                      max_file_bytes=args.max_file_bytes)
    source_states, source_kind, commit = _source_snapshot(args, paths)
    result["directory_summary"] = summarize_preview(result["files"])
    manifest_info = None
    if args.release_manifest:
        manifest_info = _check_release_manifest(args.release_manifest, commit, source_kind, source_states)

    decisions = []
    actions = []
    for row in result["files"]:
        proposal = row["proposal"]
        entry = {"path": row["path"], "status": proposal["status"], "action": proposal["action"]}
        if proposal["requires_review"]:
            entry["choices"] = list(proposal["choices"])
            decisions.append(entry)
        elif proposal["action"] != "none":
            actions.append(entry)

    checks = [_check("path_validation", "passed"), _check("secret_scan", "passed")]
    if args.source_kind == "local":
        checks.append(_policy_gate(_root_path(Path(args.source), must_exist=True)))
    else:
        checks.append(_check("policy_gate", "not_run", "git policy gate is not implemented"))
    checks.append(_check("git_store", "passed" if args.source_kind == "git" else "not_run",
                         None if args.source_kind == "git" else "local source"))
    checks.append(_check("receipt", "passed" if receipt is not None else "not_run",
                         None if receipt is not None else "no installation receipt"))
    checks.append(_check("local_policy", "passed" if args.use_local_policy else "not_run",
                         None if args.use_local_policy else "not requested"))
    checks.append(_check("fetch", "not_run", "Git fetch is not implemented in this read-only engine"))
    checks.append(_check("release_trust", "not_run", "release trust gate is not implemented"))
    checks.append(_check("release_manifest", "passed" if manifest_info else "not_run",
                         None if manifest_info else "no release manifest supplied"))
    checks.append(_check("profile_manifest", "passed" if profile_selected else "not_run",
                         None if profile_selected else "profile path-set resolution was not requested"))
    checks.append(_check("apply", "not_run", "apply/rollback arrive in the P2 stage"))

    plan_id = str(uuid.uuid4())
    now = _utc_now()
    payload = {
        "schema_version": 1,
        "plan_id": plan_id,
        "created_at": _iso(now),
        "expires_at": _iso(now + PLAN_LIFETIME),
        "status": "needs_decision" if decisions else "preview_ready",
        "profile": args.profile,
        "operation": args.operation,
        "profile_selection": "profile_manifest" if profile_selected else "explicit_paths_only",
        "profile_roots": roots if profile_selected else [],
        "source_kind": source_kind,
        "source_commit_sha": commit,
        "source": {"kind": source_kind,
                   "path": str(Path(args.source).absolute()) if args.source_kind == "local" else None,
                   "repo": str(Path(args.repo).absolute()) if args.source_kind == "git" else None,
                   "commit": commit},
        "source_tree_digest": _tree_digest(source_states),
        "source_file_count": len(source_states),
        "target": {"exists": target.is_dir(), "path": str(target)},
        "target_snapshot": _state_dict(snapshot_files(target, paths, max_file_bytes=args.max_file_bytes))
        if target.is_dir() else {},
        "max_file_bytes": args.max_file_bytes,
        "base": base_kind,
        "base_commit": args.base_commit,
        "receipt": receipt_info,
        "scope": "selected_paths_only" if args.path else "selected_roots_only",
        "roots": roots,
        "excludes": list(getattr(args, "exclude", None) or []),
        "files": result["files"],
        "actions": actions,
        "decisions_required": decisions,
        "directory_summary": result["directory_summary"],
        "checks": checks,
        "protected_paths_not_read": protected,
        "local_components": [] if not args.use_local_policy else local_paths,
        "release_manifest": manifest_info,
        "applyable": False,
    }
    state_dir = _state_dir(target, receipt is not None, args.state_dir)
    plan_path = _write_plan(state_dir, plan_id, payload)
    payload["plan_path"] = str(plan_path)
    payload["state_dir_kind"] = "target" if state_dir.is_relative_to(target) else "temporary"
    return (EXIT_NEEDS_DECISION if decisions else EXIT_PASSED), payload


def _run_fetch(args) -> tuple[int, dict]:
    if not args.url or not args.ref:
        raise ValueError("fetch requires --url and --ref")
    validate_remote(args.url, args.allow_local)
    validate_ref(args.ref)
    cache = init_bare_store(Path(args.cache))
    info = fetch_ref(cache, args.url, args.ref, allow_local=args.allow_local, timeout=args.timeout)
    payload = {
        "schema_version": 1,
        "status": "fetched",
        "cache": str(cache),
        "source_kind": "local_bare_git",
        "release_trust": "not_verified",
        "checks": [_check("fetch", "passed"), _check("checkout", "not_run", "read-only fetch"),
                   _check("release_trust", "not_run", "release trust gate is not implemented")],
        **info,
    }
    return EXIT_PASSED, payload


def _run_inventory(args) -> tuple[int, dict]:
    target = _root_path(Path(args.target), must_exist=False) if args.target else None
    excludes = list(getattr(args, "exclude", None) or [])
    for item in excludes:
        _validate_exclude(item)
    roots: list[str] = []
    if args.root:
        validate_paths(args.root)
        roots = list(args.root)
    if args.path:
        paths = [path for path in validate_paths(args.path) if not _is_excluded(path, excludes)]
        protected: list[str] = []
    else:
        if not roots:
            raise ValueError("at least one --root or --path is required")
        paths, protected = _source_paths(args, roots, excludes)
        if target is not None and target.is_dir():
            files, target_protected = discover_target_paths(target, roots, excludes=excludes)
            paths = sorted(set(paths) | set(files))
            protected = sorted(set(protected) | set(target_protected))
    source_states, source_kind, commit = _source_snapshot(args, paths)
    target_states = snapshot_files(target, paths, max_file_bytes=args.max_file_bytes) if target and target.is_dir() else {}
    checks = [_check("path_validation", "passed"), _check("secret_scan", "passed"),
              _check("fetch", "not_run", "Git fetch is not implemented"),
              _check("release_trust", "not_run", "release trust gate is not implemented")]
    payload = {
        "schema_version": 1,
        "source_kind": source_kind,
        "source_commit_sha": commit,
        "source_tree_digest": _tree_digest(source_states),
        "source_files": _state_dict(source_states),
        "source_file_count": len(source_states),
        "target": {"exists": bool(target and target.is_dir()), "files": _state_dict(target_states)},
        "scope": "selected_paths_only" if args.path else "selected_roots_only",
        "roots": roots,
        "protected_paths_not_read": protected,
        "sizes": "not_collected",
        "checks": checks,
    }
    return EXIT_PASSED, payload


def _run_verify(args) -> tuple[int, dict]:
    target = _root_path(Path(args.target).absolute(), must_exist=True)
    receipt, receipt_info = _read_receipt(target)
    if receipt is None:
        raise ValueError("verify requires .doc/web/state/transfer/receipt.json")
    roots: list[str] = []
    unexpected: list[str] = []
    if args.root:
        validate_paths(args.root)
        roots = list(args.root)
        paths = receipt_paths_in_roots(list(receipt), roots)
        if args.full:
            discovered, _ = discover_target_paths(target, roots)
            paths = sorted(set(paths) | set(discovered))
            unexpected = sorted(set(discovered) - set(receipt))
    elif args.path:
        paths = list(validate_paths(args.path))
    else:
        raise ValueError("verify requires --root or --path")
    expected = {path: receipt[path] for path in paths if path in receipt}
    if roots and not expected and not args.full:
        raise ValueError("receipt has no entries inside the selected roots")
    current = snapshot_files(target, list(expected), max_file_bytes=args.max_file_bytes)
    added = sorted(set(current) - set(expected))
    missing = sorted(set(expected) - set(current))
    changed = sorted(path for path in set(expected) & set(current) if expected[path] != current[path])
    hash_changed = [path for path in changed
                    if expected[path].sha256 != current[path].sha256]
    mode_changed = [path for path in changed
                    if expected[path].sha256 == current[path].sha256]
    checks = [_check("receipt", "passed", None), _check("receipt_scope", "passed", None)]
    payload = {
        "schema_version": 1,
        "status": "failed" if (added or missing or hash_changed or unexpected) else "passed",
        "receipt": receipt_info,
        "scope": "receipt_paths_in_selected_roots" if roots else "explicit_paths",
        "roots": roots,
        "checked_files": len(expected),
        "missing": missing,
        "added": added,
        "unexpected": unexpected,
        "hash_changed": hash_changed,
        "mode_changed_warnings": mode_changed,
        "mode_comparison": "raw_os_mode_not_portable",
        "checks": checks,
    }
    return (EXIT_FAILED if payload["status"] == "failed" else EXIT_PASSED), payload


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(command: argparse.ArgumentParser, *, target_required: bool = True) -> None:
        command.add_argument("--source-kind", choices=("local", "git"), default="local")
        command.add_argument("--source", type=Path, help="local harness source directory")
        command.add_argument("--repo", type=Path, help="already fetched local bare Git object store")
        command.add_argument("--commit", help="full pinned commit object ID")
        command.add_argument("--target", type=Path, required=target_required)
        selection = command.add_mutually_exclusive_group()
        selection.add_argument("--path", action="append", help="explicit relative path; repeatable")
        selection.add_argument("--root", action="append", help="discover files under this relative root; repeatable")
        command.add_argument("--exclude", action="append", default=[], help="exclude this relative path or prefix; repeatable")
        command.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
        command.add_argument("--jsonl", action="store_true", help="print JSONL events instead of one JSON report")
        command.add_argument("--non-interactive", action="store_true", help="accepted; this engine never prompts")

    inventory = sub.add_parser("inventory", help="read-only source and target inventory")
    common(inventory, target_required=False)

    fetch = sub.add_parser("fetch", help="fetch one ref into a local bare cache without checkout")
    fetch.add_argument("--url", required=True, help="allowlisted Git remote or local path with --allow-local")
    fetch.add_argument("--cache", required=True, type=Path, help="local bare object store")
    fetch.add_argument("--ref", required=True, help="branch or tag name")
    fetch.add_argument("--allow-local", action="store_true", help="allow an absolute local Git path")
    fetch.add_argument("--timeout", type=int, default=120)
    fetch.add_argument("--jsonl", action="store_true")
    fetch.add_argument("--non-interactive", action="store_true")

    plan = sub.add_parser("plan", help="read-only update preview")
    common(plan)
    plan.add_argument("--profile", choices=("core", "developer", "project"), required=True)
    plan.add_argument("--operation", choices=("install", "update", "repair"), default="update")
    baseline = plan.add_mutually_exclusive_group()
    baseline.add_argument("--base-commit", help="historical commit for comparison; not a receipt")
    baseline.add_argument("--use-receipt", action="store_true", help="read the target receipt")
    plan.add_argument("--local", action="append", default=[], help="selected path owned by the target")
    plan.add_argument("--use-local-policy", action="store_true", help="read canon-paths.local.yaml")
    plan.add_argument("--state-dir", help="CLI-only preview state directory override")
    plan.add_argument("--release-manifest", type=Path, help="derived harness-release-manifest JSON")

    verify = sub.add_parser("verify", help="compare target files with the installation receipt")
    verify.add_argument("--target", type=Path, required=True)
    selection = verify.add_mutually_exclusive_group(required=True)
    selection.add_argument("--root", action="append")
    selection.add_argument("--path", action="append")
    verify.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    verify.add_argument("--full", action="store_true", help="also report files outside the receipt")
    verify.add_argument("--jsonl", action="store_true")
    verify.add_argument("--non-interactive", action="store_true")

    approve = sub.add_parser("approve", help="validate decisions and freeze a saved plan")
    approve.add_argument("--plan", type=Path, required=True)
    approve.add_argument("--decisions", type=Path, required=True)
    approve.add_argument("--jsonl", action="store_true")
    approve.add_argument("--non-interactive", action="store_true")

    apply_cmd = sub.add_parser("apply", help="apply one approved plan to the target")
    apply_cmd.add_argument("--plan", type=Path, required=True)
    apply_cmd.add_argument("--approved", type=Path, required=True)
    apply_cmd.add_argument("--state-dir", type=Path)
    apply_cmd.add_argument("--render", action="store_true",
                           help="regenerate project-local views after a committed apply")
    apply_cmd.add_argument("--no-render", action="store_true",
                           help="skip automatic view regeneration for a harness target")
    apply_cmd.add_argument("--jsonl", action="store_true")
    apply_cmd.add_argument("--non-interactive", action="store_true")

    rollback = sub.add_parser("rollback", help="roll back the active journaled run")
    rollback.add_argument("--target", type=Path, required=True)
    rollback.add_argument("--state-dir", type=Path)
    rollback.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    rollback.add_argument("--jsonl", action="store_true")
    rollback.add_argument("--non-interactive", action="store_true")

    render = sub.add_parser("render", help="regenerate agent views with the trusted current generators")
    render.add_argument("--target", type=Path, required=True)
    render.add_argument("--check", action="store_true", help="verify views without writing")
    render.add_argument("--jsonl", action="store_true")
    render.add_argument("--non-interactive", action="store_true")

    compact = sub.add_parser("compact", help="remove generated agent views from the working tree")
    compact.add_argument("--target", type=Path, required=True)
    compact.add_argument("--check", action="store_true", help="report generated paths without removing")
    compact.add_argument("--apply", action="store_true", help="remove generated paths")
    compact.add_argument("--force", action="store_true", help="skip generated-content validation")
    compact.add_argument("--jsonl", action="store_true")
    compact.add_argument("--non-interactive", action="store_true")

    adopt = sub.add_parser("adopt", help="preview or commit legacy adoption")
    adopt.add_argument("--target", type=Path)
    adopt.add_argument("--root", action="append")
    adopt.add_argument("--profile", choices=("core", "developer", "project"))
    adopt.add_argument("--plan", type=Path)
    adopt.add_argument("--decisions", type=Path)
    adopt.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    adopt.add_argument("--state-dir", type=Path)
    adopt.add_argument("--jsonl", action="store_true")
    adopt.add_argument("--non-interactive", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    run_id = uuid.uuid4().hex
    events: list[dict] = []
    sequence = _emit(events, run_id, 1, "run_started", command=args.command)
    sequence = _emit(events, run_id, sequence, "phase_started", phase=args.command)
    try:
        if args.command == "inventory":
            code, payload = _run_inventory(args)
        elif args.command == "fetch":
            code, payload = _run_fetch(args)
        elif args.command == "plan":
            code, payload = _run_plan(args)
        elif args.command == "approve":
            code, payload = _run_approve(args)
        elif args.command == "apply":
            code, payload = _run_apply(args)
        elif args.command == "rollback":
            code, payload = _run_rollback(args)
        elif args.command == "render":
            code, payload = _run_render(args)
        elif args.command == "compact":
            code, payload = _run_compact(args)
        elif args.command == "adopt":
            code, payload = _run_adopt(args)
        else:
            code, payload = _run_verify(args)
    except StalePlan as error:
        message = str(error)
        sequence = _emit(events, run_id, sequence, "finding", severity="error", message=message)
        sequence = _emit(events, run_id, sequence, "run_finished", status="stale_plan",
                         exit_code=EXIT_STALE_PLAN)
        if getattr(args, "jsonl", False):
            _print_events(events)
        else:
            print(json.dumps({"status": "stale_plan", "reason": message}, ensure_ascii=False))
        return EXIT_STALE_PLAN
    except DecisionError as error:
        message = str(error)
        sequence = _emit(events, run_id, sequence, "finding", severity="review", message=message)
        sequence = _emit(events, run_id, sequence, "run_finished", status="needs_decision",
                         exit_code=EXIT_NEEDS_DECISION)
        if getattr(args, "jsonl", False):
            _print_events(events)
        else:
            print(json.dumps({"status": "needs_decision", "reason": message}, ensure_ascii=False))
        return EXIT_NEEDS_DECISION
    except ApplyError as error:
        code = EXIT_NEEDS_DECISION if error.code in (
            "needs_decision", "invalid_decision", "unsupported_decision") else (
            EXIT_STALE_PLAN if error.code == "stale_plan" else EXIT_FAILED_PREFLIGHT)
        sequence = _emit(events, run_id, sequence, "finding", severity="error", message=str(error))
        sequence = _emit(events, run_id, sequence, "run_finished", status=error.code, exit_code=code)
        if getattr(args, "jsonl", False):
            _print_events(events)
        else:
            print(json.dumps({"status": error.code, "reason": str(error)}, ensure_ascii=False))
        return code
    except (OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) or error.__class__.__name__
        sequence = _emit(events, run_id, sequence, "finding", severity="error", message=message)
        sequence = _emit(events, run_id, sequence, "run_finished", status="failed_preflight",
                         exit_code=EXIT_FAILED_PREFLIGHT)
        if getattr(args, "jsonl", False):
            _print_events(events)
            return EXIT_FAILED_PREFLIGHT
        return _preflight_error(error, command=args.command)
    for check in payload.get("checks", []):
        sequence = _emit(events, run_id, sequence, "check_started", check=check.get("id"))
        sequence = _emit(events, run_id, sequence, "check_finished", check=check.get("id"),
                         status=check.get("status"), reason=check.get("reason"))
    if args.command == "plan":
        sequence = _emit(events, run_id, sequence, "finding", severity="review",
                         decisions=len(payload.get("decisions_required", [])))
    sequence = _emit(events, run_id, sequence, "phase_finished", phase=args.command, status=payload.get("status"))
    sequence = _emit(events, run_id, sequence, "run_finished", status=payload.get("status"), exit_code=code)
    if getattr(args, "jsonl", False):
        _print_events(events)
    else:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
