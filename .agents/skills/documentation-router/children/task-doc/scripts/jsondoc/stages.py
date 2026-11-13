"""Stage projection and stage diff adapter (J06/J07).

stages_view computes the read-only stage projection of one task document
per plan 15.2: single explicit active stage, ambiguity warning instead of
max-number guess, placeholder-aware allocation, dependency-gated next
actionable stages. resolve_stage_artifacts and legacy_stage_folders give
scope-exact artifact resolution and inventory of existing stage{K} /
stage{K}v{M} folders without writes.

The diff part (J07) builds verifiable stage diff manifests from fixed
read-only Git argv lists (no shell strings), hashes per-commit patches in
the given order and separates stage scope from the root task diff.
Stdlib only, Python 3.9+.
"""

import hashlib
import re
import shlex
import subprocess
import time
from pathlib import Path

SELECTION_MODES = ("commits", "range", "workspace_delta")
ACTIVE_CANDIDATE_STATUSES = ("planned", "active", "blocked")
TERMINAL_DEP_STATUSES = ("closed", "verified", "superseded")

_STAGE_ID_RE = re.compile(r"^stage:([0-9]+)$")
_SCOPE_RE = re.compile(r"^(task|stage:[0-9]+)$")
_STAGE_DIR_RE = re.compile(r"^stage([0-9]+)(?:v([0-9]+))?$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_UTC_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")


class StagesError(Exception):
    def __init__(self, code, payload=None):
        super().__init__(code)
        self.code = code
        self.payload = dict(payload or {})


def _utc_now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def stages_view(doc):
    stages_list = doc.get("stages") or []
    by_number = sorted(stages_list, key=lambda s: s.get("number", 0))
    warnings = []
    notes = []

    def superseded(stage):
        return stage.get("status") == "superseded" or stage.get(
            "superseded_by") is not None

    active_stages = [s for s in by_number
                     if s.get("status") == "active" and not superseded(s)]
    if len(active_stages) == 1:
        active_stage_id = active_stages[0]["id"]
    else:
        active_stage_id = None
    ambiguous_active_ids = [s["id"] for s in active_stages] \
        if len(active_stages) > 1 else []
    requires_explicit_stage = len(active_stages) > 1
    if requires_explicit_stage:
        warnings.append("STAGE_AMBIGUOUS")

    active_candidates = [
        {"id": s["id"], "number": s["number"], "status": s["status"]}
        for s in by_number
        if s.get("status") in ACTIVE_CANDIDATE_STATUSES
        and not s.get("placeholder") and not superseded(s)
    ]

    documented = [s for s in by_number
                  if not s.get("placeholder")
                  and s.get("plan_artifact_id") is not None]
    latest_documented_stage_id = documented[-1]["id"] if documented else None

    status_by_id = {s["id"]: s.get("status") for s in by_number}
    next_actionable = []
    for stage in by_number:
        if stage.get("status") != "planned" or stage.get("placeholder"):
            continue
        if superseded(stage):
            continue
        deps = stage.get("depends_on") or []
        if all(status_by_id.get(dep) in TERMINAL_DEP_STATUSES
               for dep in deps):
            next_actionable.append(stage["id"])

    numbers = [s.get("number", 0) for s in by_number]
    next_allocatable_number = max(numbers) + 1 if numbers else 1

    for stage in by_number:
        if stage.get("placeholder"):
            notes.append({
                "code": "placeholder_reserved",
                "stage_id": stage["id"],
                "number": stage["number"],
                "detail": (f"stage {stage['number']} is occupied by a "
                           f"placeholder; resume stage {stage['number']} "
                           f"explicitly instead of allocating a new stage"),
            })

    cards = [{
        "id": s["id"],
        "number": s["number"],
        "status": s["status"],
        "placeholder": s.get("placeholder", False),
        "title": s.get("title"),
        "plan_artifact_id": s.get("plan_artifact_id"),
        "diffs": len(s.get("diff_artifact_ids") or []),
        "test_runs": len(s.get("test_run_ids") or []),
    } for s in by_number]

    coverage = {
        "stages_total": len(by_number),
        "placeholders": sum(1 for s in by_number if s.get("placeholder")),
        "superseded": sum(1 for s in by_number
                          if s.get("status") == "superseded"),
    }

    return {
        "active_stage_id": active_stage_id,
        "ambiguous_active_ids": ambiguous_active_ids,
        "requires_explicit_stage": requires_explicit_stage,
        "active_candidates": active_candidates,
        "latest_documented_stage_id": latest_documented_stage_id,
        "next_actionable_stage_ids": next_actionable,
        "next_allocatable_number": next_allocatable_number,
        "stages": cards,
        "coverage": coverage,
        "warnings": warnings,
        "notes": notes,
    }


def stage_scope(scope):
    if not isinstance(scope, str) or not _SCOPE_RE.match(scope):
        raise StagesError("invalid_scope", {"scope": repr(scope)})
    if scope == "task":
        return {"kind": "task", "number": None}
    match = _STAGE_ID_RE.match(scope)
    return {"kind": "stage", "number": int(match.group(1))}


def resolve_stage_artifacts(doc, stage_id):
    stages_list = doc.get("stages") or []
    stage = next((s for s in stages_list if s.get("id") == stage_id), None)
    if stage is None:
        raise StagesError("unknown_stage", {"stage_id": stage_id})
    number = stage["number"]
    scope = f"stage:{number}"
    artifacts = doc.get("artifacts") or []
    plan = next((a for a in artifacts
                 if a.get("scope") == scope and a.get("role") == "plan"), None)
    diffs = [a for a in artifacts
             if a.get("scope") == scope
             and a.get("role") in ("diff", "diff_files")]
    tests = [a for a in artifacts
             if a.get("scope") == scope
             and a.get("role") in ("test_run", "test_spec")]
    manifest_id = stage.get("diff_manifest_id")
    manifest = next((a for a in artifacts if a.get("id") == manifest_id),
                    None) if manifest_id else None
    return {"plan": plan, "diffs": diffs, "manifest": manifest, "tests": tests}


def legacy_stage_folders(docs_dir, task_key):
    base = Path(docs_dir) / "tasks" / str(task_key)
    if not base.is_dir():
        return []
    records = []
    for entry in sorted(base.iterdir()):
        if not entry.is_dir():
            continue
        match = _STAGE_DIR_RE.match(entry.name)
        if match is None:
            continue
        variant = match.group(2)
        records.append({
            "path": entry,
            "number": int(match.group(1)),
            "variant": int(variant) if variant else None,
        })
    records.sort(key=lambda r: (r["number"], r["variant"] or 0))
    return records


def artifact_diff_id(task_key, stage_no, files_sha256):
    if not isinstance(files_sha256, str) or not _SHA256_RE.match(files_sha256):
        raise StagesError("invalid_files_sha256",
                          {"files_sha256": repr(files_sha256)})
    return f"artifact:{task_key}:stage:{stage_no}:diff:{files_sha256[:12]}"


# ---------------------------------------------------------------- git (J07)

def _run_git(repo, argv):
    return subprocess.run(["git"] + list(argv), cwd=str(repo),
                          capture_output=True)


def _git_out(repo, argv):
    proc = _run_git(repo, argv)
    if proc.returncode != 0:
        raise StagesError("git_error", {
            "argv": list(argv),
            "stderr": proc.stderr.decode("utf-8", "replace").strip()[:400]})
    return proc.stdout


def git_repo_ok(repo):
    """True only when the repo dir itself owns the git dir (no parent discovery)."""
    import os
    env = dict(os.environ)
    env["GIT_CEILING_DIRECTORIES"] = str(Path(repo).resolve().parent)
    proc = subprocess.run(["git", "rev-parse", "--git-dir"],
                          cwd=str(repo), capture_output=True, env=env)
    return proc.returncode == 0


def resolve_oid(repo, ref):
    proc = _run_git(repo, ["rev-parse", str(ref)])
    if proc.returncode != 0:
        return None
    lines = proc.stdout.decode("utf-8", "replace").splitlines()
    return lines[0].strip() if lines else None


def commits_between(repo, base, head, path_scope=None):
    argv = ["git", "log", "--no-merges", "--reverse",
            "--format=%H%x09%s", f"{base}..{head}"]
    paths = _normalize_paths(path_scope)
    if paths:
        argv += ["--"] + paths
    out = _git_out(repo, argv[1:])
    commits = []
    for line in out.decode("utf-8", "replace").splitlines():
        if not line.strip():
            continue
        oid, _, subject = line.partition("\t")
        commits.append({"oid": oid, "subject": subject})
    return commits


def workspace_delta(repo):
    out = _git_out(repo, ["status", "--porcelain"])
    paths = []
    for line in out.decode("utf-8", "replace").splitlines():
        if len(line) < 4:
            continue
        status = line[:2]
        if status == "??":
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        if path not in paths:
            paths.append(path)
    return paths


def _normalize_paths(path_scope):
    if path_scope is None:
        return []
    if isinstance(path_scope, str):
        return [path_scope]
    return [str(p) for p in path_scope]


def _subject_of(repo, oid):
    out = _git_out(repo, ["show", "-s", "--format=%s", oid])
    return out.decode("utf-8", "replace").strip()


def _commit_patch(repo, oid):
    return _git_out(repo, ["show", "--no-color", oid])


def _paths_from_patch(patch_bytes):
    paths = []
    for line in patch_bytes.decode("utf-8", "replace").splitlines():
        if not line.startswith("diff --git "):
            continue
        rest = line[len("diff --git "):]
        try:
            parts = shlex.split(rest)
        except ValueError:
            parts = rest.split(" ")
        target = None
        for prefix in ("b/", "a/"):
            for token in parts:
                if token.startswith(prefix):
                    target = token[len(prefix):]
                    break
            if target:
                break
        if target and target != "/dev/null" and target not in paths:
            paths.append(target)
    return paths


def _owned_subject(task_key):
    pattern = re.compile(
        rf"(?<![0-9]){re.escape(str(task_key))}(?![0-9])")
    return lambda subject: bool(pattern.search(subject))


def _uncommitted_entries(repo, paths):
    entries = []
    for path in paths:
        proc = _run_git(repo, ["show", f"HEAD:{path}"])
        old = _sha256(proc.stdout) if proc.returncode == 0 else None
        target = Path(repo) / path
        new = (_sha256(target.read_bytes())
               if target.is_file() else None)
        entries.append({"path": path, "old_sha256": old, "new_sha256": new})
    return entries


def build_stage_diff_manifest(repo, task_key, stage_no, selection_mode,
                              commit_oids=None, base=None, head=None,
                              path_scope=None, uncommitted=None,
                              source_plan_sha256=None, exclusions=None):
    task_id = str(task_key)
    if not re.fullmatch(r"[0-9]+", task_id):
        raise StagesError("invalid_task_key", {"task_key": repr(task_key)})
    if not isinstance(stage_no, int) or isinstance(stage_no, bool) \
            or stage_no < 1:
        raise StagesError("invalid_stage_number",
                          {"stage_no": repr(stage_no)})
    if selection_mode not in SELECTION_MODES:
        raise StagesError("invalid_selection_mode",
                          {"selection_mode": repr(selection_mode),
                           "allowed": list(SELECTION_MODES)})
    if source_plan_sha256 is not None and (
            not isinstance(source_plan_sha256, str)
            or not _SHA256_RE.match(source_plan_sha256)):
        raise StagesError("invalid_source_plan_sha256",
                          {"source_plan_sha256": repr(source_plan_sha256)})
    paths = _normalize_paths(path_scope)
    excluded_set = {str(oid) for oid in (exclusions or [])}

    base_oid = None
    head_oid = None
    net_diff_sha256 = None
    empty_reason = None

    if selection_mode == "commits":
        selected = [str(oid) for oid in (commit_oids or [])]
        if not selected:
            raise StagesError("commits_required", {
                "reason": "selection_mode=commits requires commit_oids"})
        selected = [oid for oid in selected if oid not in excluded_set]
        if not selected:
            empty_reason = "all_commits_excluded"
    elif selection_mode == "range":
        if not base or not head:
            raise StagesError("range_refs_required", {
                "reason": "selection_mode=range requires base and head"})
        base_oid = resolve_oid(repo, base)
        head_oid = resolve_oid(repo, head)
        if base_oid is None or head_oid is None:
            raise StagesError("range_ref_unresolved",
                              {"base": base, "head": head,
                               "base_oid": base_oid, "head_oid": head_oid})
        in_range = commits_between(repo, base_oid, head_oid, paths or None)
        is_owned = _owned_subject(task_id)
        unowned = [c for c in in_range
                   if c["oid"] not in excluded_set
                   and not is_owned(c["subject"])]
        if unowned:
            raise StagesError("stage_diff_range_mixed", {
                "unowned": unowned,
                "hint": "provide explicit exclusions oid list or narrow "
                        "the range"})
        selected = [c["oid"] for c in in_range if c["oid"] not in excluded_set]
        if not selected:
            empty_reason = ("no_owned_commits_after_exclusions"
                            if excluded_set else "no_owned_commits_in_range")
    else:
        base_oid = resolve_oid(repo, "HEAD")
        head_oid = None
        delta_paths = list(uncommitted) if uncommitted is not None \
            else workspace_delta(repo)
        selected = []
        if not delta_paths:
            empty_reason = "empty_workspace_delta"

    patches = []
    if selection_mode in ("commits", "range"):
        for oid in selected:
            patches.append(_commit_patch(repo, oid))
    else:
        delta_paths = delta_paths if selection_mode == "workspace_delta" \
            else []
        for path in delta_paths:
            patches.append(_git_out(repo, ["diff", "HEAD", "--", path]))

    concatenated = b"".join(patches)
    diff_sha256 = _sha256(concatenated)
    files = []
    for patch in patches:
        for path in _paths_from_patch(patch):
            if path not in files:
                files.append(path)
    files_sha256 = _sha256("\n".join(sorted(files)).encode("utf-8"))

    if selection_mode == "range":
        argv = ["diff", base_oid, head_oid]
        if paths:
            argv += ["--"] + paths
        net_diff_sha256 = _sha256(_git_out(repo, argv))

    if uncommitted is not None:
        uncommitted_paths = list(uncommitted)
    elif selection_mode == "workspace_delta":
        uncommitted_paths = delta_paths
    else:
        uncommitted_paths = []
    uncommitted_records = _uncommitted_entries(repo, uncommitted_paths) \
        if uncommitted_paths else []

    subjects = {}
    unowned_selected = []
    if selection_mode in ("commits", "range"):
        is_owned = _owned_subject(task_id)
        for oid in selected:
            subject = _subject_of(repo, oid)
            subjects[oid] = subject
            if not is_owned(subject):
                unowned_selected.append(oid)

    excluded_in_selection = sorted(oid for oid in excluded_set)
    manifest = {
        "schema_version": "1.0",
        "task_id": task_id,
        "stage_id": f"stage:{stage_no}",
        "selection_mode": selection_mode,
        "base_oid": base_oid,
        "head_oid": head_oid,
        "commit_oids": selected,
        "path_scope": paths,
        "uncommitted": uncommitted_records,
        "source_plan_sha256": source_plan_sha256,
        "generated_at": _utc_now(),
        "diff_sha256": diff_sha256,
        "files_sha256": files_sha256,
        "files": sorted(files),
        "ownership_evidence": {
            "rule": "task_number_in_subject",
            "task_key": task_id,
            "subjects": subjects,
            "unowned_commit_oids": unowned_selected,
            "excluded_commit_oids": excluded_in_selection,
            "explicit_selection": selection_mode == "commits",
        },
        "coverage": {
            "commits_selected": len(selected),
            "paths_touched": len(files),
            "uncommitted_files": len(uncommitted_records),
            "excluded_commits": excluded_in_selection,
        },
    }
    if net_diff_sha256 is not None:
        manifest["net_diff_sha256"] = net_diff_sha256
    if empty_reason is not None:
        manifest["empty_reason"] = empty_reason
    if not _UTC_RE.match(manifest["generated_at"]):
        raise StagesError("generated_at_invalid")
    return manifest
