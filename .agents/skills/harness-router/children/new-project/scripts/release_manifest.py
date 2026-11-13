#!/usr/bin/env python3
"""Build a derived harness release manifest from one Git commit.

The manifest is a snapshot, not an authoring source. It reads tracked blobs
without checkout, validates the policy bundle at the same commit, excludes
private paths by policy, and reports sizes and SHA-256 digests.
"""
from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "harness-core/scripts"))
from canon_paths import PolicyError, load_preliminary_policy_bundle

CANON = ".doc/harnes/state/canon-paths.yaml"
POLICIES = (
    ".agents/skills/harness-router/children/harness-core/assets/policies/skill-format.yaml",
    ".agents/skills/harness-router/children/harness-core/assets/policies/component-docs.yaml",
)
PRIVATE_EXCEPTION = "private_path"


class ManifestError(ValueError):
    def __init__(self, code: str, message: str, path: str | None = None):
        self.code = code
        self.path = path
        super().__init__(message)


def _git_environment() -> dict[str, str]:
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0", "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0",
                "GIT_NO_REPLACE_OBJECTS": "1", "GIT_LITERAL_PATHSPECS": "1", "LC_ALL": "C"})
    return env


def _run(root: Path, *args: str, stdin: bytes = b"") -> bytes:
    git = shutil.which("git")
    if git is None:
        raise ManifestError("git_unavailable", "git is unavailable")
    try:
        result = subprocess.run([git, "-C", str(root), *args], env=_git_environment(), input=stdin,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ManifestError("git_failed", "Git execution failed") from error
    if result.returncode:
        raise ManifestError("git_failed", "Git command failed")
    return result.stdout


def _root(raw: Path) -> Path:
    root = Path(raw).absolute()
    top = _run(root, "rev-parse", "--show-toplevel").decode("utf-8", "strict").strip()
    if Path(top).resolve(strict=True) != root.resolve(strict=True):
        raise ManifestError("not_repository_root", "root must be the Git working tree root")
    return root


def _commit(root: Path, revision: str) -> str:
    if not isinstance(revision, str) or not revision or revision.startswith("-") or len(revision) > 256:
        raise ManifestError("invalid_revision", "invalid revision")
    output = _run(root, "rev-parse", "--verify", revision + "^{commit}").decode("ascii", "strict").strip()
    if not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", output):
        raise ManifestError("invalid_revision", "revision did not resolve to a commit")
    return output


def _blob(root: Path, commit: str, path: str) -> bytes:
    return _run(root, "cat-file", "blob", f"{commit}:{path}")


def _policy_bundle(root: Path, commit: str):
    with tempfile.TemporaryDirectory(prefix="harness-release-policy-") as directory:
        fixture = Path(directory)
        for relative in (CANON, *POLICIES):
            destination = fixture / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(_blob(root, commit, relative))
        return load_preliminary_policy_bundle(fixture)


def _tree(root: Path, commit: str) -> list[tuple[str, int, str, int]]:
    output = _run(root, "ls-tree", "-r", "-z", "--full-tree", "-l", commit)
    records = output.split(b"\0")
    if records[-1:] != [b""]:
        raise ManifestError("invalid_tree", "unexpected Git tree output")
    entries = []
    for record in records[:-1]:
        try:
            info, name = record.split(b"\t", 1)
            mode, kind, oid, size = info.split()
            path = name.decode("utf-8", "strict")
        except (ValueError, UnicodeError) as error:
            raise ManifestError("invalid_tree", "malformed Git tree entry") from error
        if kind != b"blob" or mode not in (b"100644", b"100755"):
            raise ManifestError("unsupported_entry", "release tree contains a link or special entry", path)
        entries.append((path, int(mode, 8), oid.decode("ascii"), int(size)))
    return sorted(entries)


def _private_reason(path: str) -> str | None:
    from transfer_inventory import InventoryError, validate_paths
    try:
        validate_paths([path])
    except InventoryError as error:
        return error.reason
    return None


def _hash_blobs(root: Path, entries: list[tuple[str, int, str, int]]) -> dict[str, dict]:
    oids = [oid for _, _, oid, _ in entries]
    if not oids:
        return {}
    output = _run(root, "cat-file", "--batch", stdin=("\n".join(oids) + "\n").encode("ascii"))
    position = 0
    result: dict[str, dict] = {}
    for path, mode, oid, size in entries:
        newline = output.find(b"\n", position)
        if newline < 0:
            raise ManifestError("invalid_blob_stream", "truncated cat-file header", path)
        header = output[position:newline].split()
        if len(header) != 3 or header[1] != b"blob":
            raise ManifestError("invalid_blob_stream", "unexpected cat-file header", path)
        declared = int(header[2])
        start = newline + 1
        end = start + declared
        if declared != size or end >= len(output) or output[end:end + 1] != b"\n":
            raise ManifestError("invalid_blob_stream", "blob size mismatch", path)
        content = output[start:end]
        result[path] = {"mode": f"{mode:04o}", "size": size,
                        "sha256": hashlib.sha256(content).hexdigest()}
        position = end + 1
    if position != len(output):
        raise ManifestError("invalid_blob_stream", "unexpected trailing blob data")
    return result


def build_manifest(root: Path, commit: str, max_file_bytes: int) -> dict:
    root = _root(root)
    commit = _commit(root, commit)
    if type(max_file_bytes) is not int or max_file_bytes <= 0:
        raise ManifestError("invalid_size_limit", "invalid size limit")
    bundle = _policy_bundle(root, commit)
    entries = _tree(root, commit)
    included, excluded = [], []
    for path, mode, oid, size in entries:
        reason = _private_reason(path)
        if reason == PRIVATE_EXCEPTION:
            excluded.append({"path": path, "reason": "private_path"})
            continue
        if reason is not None:
            raise ManifestError("unsafe_path", reason, path)
        if size > max_file_bytes:
            excluded.append({"path": path, "reason": "size_limit", "size": size})
            continue
        included.append((path, mode, oid, size))
    files = _hash_blobs(root, included)
    missing = [path for path in (CANON, *POLICIES) if path not in files]
    if missing:
        raise ManifestError("release_policy_missing", "policy file is not tracked in the release tree", missing[0])
    return {
        "schema_version": 1,
        "kind": "harness-release-manifest",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": {"commit": commit},
        "policy": {"path": CANON, "distribution_entries": len(bundle["distribution"])},
        "files": [{"path": path, **files[path]} for path in sorted(files)],
        "excluded": sorted(excluded, key=lambda item: item["path"]),
        "counts": {"files": len(files), "excluded": len(excluded),
                   "bytes": sum(item["size"] for item in files.values())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path, help="Git working tree root")
    parser.add_argument("--commit", default="HEAD", help="revision that resolves to a commit")
    parser.add_argument("--out", type=Path, help="write the manifest to this file instead of stdout")
    parser.add_argument("--json", action="store_true", help="accepted; output is always JSON")
    parser.add_argument("--max-file-bytes", type=int, default=8 * 1024 * 1024)
    args = parser.parse_args(argv)
    try:
        manifest = build_manifest(args.root, args.commit, args.max_file_bytes)
    except PolicyError as error:
        print(json.dumps({"status": "failed", "code": error.code, "policy_id": error.policy_id,
                          "relative_path": error.relative_path, "field": error.field}, ensure_ascii=False))
        return 2
    except (ManifestError, OSError, ValueError) as error:
        payload = {"status": "failed", "code": getattr(error, "code", "failed"), "reason": str(error)}
        if getattr(error, "path", None):
            payload["relative_path"] = error.path
        print(json.dumps(payload, ensure_ascii=False))
        return 2
    data = json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.out is None:
        sys.stdout.write(data)
        return 0
    temporary = args.out.with_name("." + args.out.name + ".tmp")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(temporary, "w", encoding="utf-8") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
