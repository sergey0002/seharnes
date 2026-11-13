"""Read selected blobs from an already trusted local bare Git object store.

This is not a fetcher, release verifier, comprehensive secret scanner or apply engine. The
caller must authenticate the commit and select the permitted paths. No
checkout, hooks, filters, submodules or candidate code are executed.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import threading
import urllib.parse
from pathlib import Path

from transfer_diff import FileState
from transfer_inventory import contains_known_secret, snapshot_files, validate_paths
from transfer_plan import _assemble, _root_path, _validate_selection


def _git_environment() -> dict[str, str]:
    env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0", "GIT_NO_LAZY_FETCH": "1", "GIT_OPTIONAL_LOCKS": "0",
                "GIT_NO_REPLACE_OBJECTS": "1", "GIT_LITERAL_PATHSPECS": "1", "LC_ALL": "C"})
    return env


def validate_remote(url: str, allow_local: bool) -> None:
    if not isinstance(url, str) or not url or len(url) > 2048 or url.startswith("-"):
        raise ValueError("invalid Git remote")
    if any(ord(char) < 32 for char in url):
        raise ValueError("invalid Git remote")
    if re.fullmatch(r"[A-Za-z0-9._-]+@[A-Za-z0-9._-]+:[^\s]+", url):
        return
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme in ("https", "ssh"):
        if not parsed.hostname or parsed.password is not None:
            raise ValueError("invalid Git remote or embedded credentials")
        return
    if parsed.scheme == "file":
        if not allow_local or parsed.username or parsed.password or parsed.hostname:
            raise ValueError("local Git remotes require --allow-local and an absolute path")
        return
    if "://" in url:
        raise ValueError("unsupported Git remote protocol")
    if allow_local and Path(url).is_absolute():
        return
    raise ValueError("unsupported Git remote protocol")


def init_bare_store(path: Path) -> Path:
    """Create a local bare object store when absent; never reuse a non-bare path."""
    root = Path(path).absolute()
    if root.exists():
        if root.is_symlink() or not root.is_dir():
            raise ValueError("cache path must be a directory")
        return _root_path(root, must_exist=True)
    if not root.parent.is_dir():
        raise ValueError("cache parent directory is missing")
    git = shutil.which("git")
    if git is None:
        raise ValueError("git is unavailable")
    try:
        result = subprocess.run([git, "init", "--bare", "--quiet", str(root)], env=_git_environment(),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("Git cache initialization failed") from error
    if result.returncode:
        raise ValueError("Git cache initialization failed")
    return _root_path(root, must_exist=True)


def validate_ref(ref: str) -> None:
    if (not isinstance(ref, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,200}", ref)
            or ".." in ref or ref.endswith((".lock", "/", "."))):
        raise ValueError("invalid Git ref")


def fetch_ref(repo: Path, url: str, ref: str, *, allow_local: bool = False, timeout: int = 120) -> dict:
    """Fetch one named ref into refs/harness/source without checkout or hooks.

    The object store must already be a local bare repository. The caller
    authenticates the remote and treats the fetched commit as untrusted data.
    """
    validate_remote(url, allow_local)
    validate_ref(ref)
    root = _root_path(Path(repo), must_exist=True)
    if (root / "objects/info/alternates").exists() or (root / "objects/info/alternates").is_symlink():
        raise ValueError("Git alternates are not supported")
    git = shutil.which("git")
    if git is None:
        raise ValueError("git is unavailable")
    env = _git_environment()

    def run(*args: str, max_time: int = 30) -> bytes:
        try:
            result = subprocess.run([git, "--git-dir", str(root), *args], env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=max_time, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("Git operation failed") from error
        if result.returncode:
            raise ValueError("Git operation failed")
        return result.stdout

    if run("rev-parse", "--is-bare-repository").strip() != b"true":
        raise ValueError("a bare object store is required")
    try:
        result = subprocess.run([git, "--git-dir", str(root), "fetch", "--no-tags", url,
                                 f"+{ref}:refs/harness/source"], env=env, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError("Git fetch failed") from error
    if result.returncode:
        raise ValueError("Git fetch failed")
    commit = run("rev-parse", "refs/harness/source").strip().decode("ascii", "strict")
    object_format = run("rev-parse", "--show-object-format").strip()
    if (object_format, len(commit)) not in ((b"sha1", 40), (b"sha256", 64)):
        raise ValueError("fetched object id does not match object format")
    if not re.fullmatch(r"[0-9a-f]+", commit) or run("cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("fetched ref is not a commit")
    return {"ref": ref, "commit": commit, "object_format": object_format.decode("ascii")}


def snapshot_git_blobs(repo: Path, commit: str, paths: list[str], *, max_file_bytes: int) -> dict[str, FileState]:
    """Return SHA-256 and Git executable modes for selected paths at a pinned commit.

    The repository is a locally controlled bare store, not an arbitrary
    candidate repository. Only regular blobs are accepted. Size, ownership,
    provenance and content policy still need independent release-level gates.
    """
    selected = validate_paths(paths)
    if type(max_file_bytes) is not int or max_file_bytes <= 0:
        raise ValueError("invalid file size limit")
    if not isinstance(commit, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", commit):
        raise ValueError("commit must be a full lowercase object id")
    root = _root_path(Path(repo), must_exist=True)
    if (root / "objects/info/alternates").exists() or (root / "objects/info/alternates").is_symlink():
        raise ValueError("Git alternates are not supported")
    git = shutil.which("git")
    if git is None:
        raise ValueError("git is unavailable")
    env = _git_environment()

    def run(*args: str) -> bytes:
        try:
            result = subprocess.run([git, "--git-dir", str(root), *args], env=env,
                                    stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ValueError("Git object read failed") from error
        if result.returncode:
            raise ValueError("Git object read failed")
        return result.stdout

    if run("rev-parse", "--is-bare-repository").strip() != b"true":
        raise ValueError("a bare object store is required")
    object_format = run("rev-parse", "--show-object-format").strip()
    if (object_format, len(commit)) not in ((b"sha1", 40), (b"sha256", 64)):
        raise ValueError("commit id does not match object format")
    if run("cat-file", "-t", commit).strip() != b"commit":
        raise ValueError("object is not a commit")
    result: dict[str, FileState] = {}
    for path in selected:
        listing = run("ls-tree", "-z", "--full-tree", commit, "--", path)
        if not listing:
            continue
        records = listing.split(b"\0")
        if len(records) != 2 or records[-1] != b"":
            raise ValueError("unexpected Git tree result")
        try:
            info, name = records[0].split(b"\t", 1)
            mode, kind, oid = info.split(b" ")
            if name.decode("utf-8", "strict") != path or kind != b"blob" or mode not in (b"100644", b"100755"):
                raise ValueError("non-regular or mismatched Git tree entry")
            object_id = oid.decode("ascii")
            if not re.fullmatch(r"[0-9a-f]{%d}" % len(commit), object_id):
                raise ValueError("invalid blob object id")
            size = int(run("cat-file", "-s", object_id).strip())
        except (UnicodeError, ValueError) as error:
            raise ValueError("invalid Git tree entry") from error
        if size < 0 or size > max_file_bytes:
            raise ValueError("Git blob exceeds size limit")
        content = run("cat-file", "blob", object_id)
        if len(content) != size:
            raise ValueError("Git blob size changed")
        if contains_known_secret(content):
            raise ValueError("Git blob contains a known secret signature")
        result[path] = FileState(hashlib.sha256(content).hexdigest(), 0o755 if mode == b"100755" else 0o644)
    return result


def capture_git_blob(repo: Path, commit: str, path: str, *, max_file_bytes: int) -> tuple[FileState, bytes] | None:
    """Return verified bytes and state for one regular blob, without checkout."""
    state = snapshot_git_blobs(repo, commit, [path], max_file_bytes=max_file_bytes).get(path)
    if state is None:
        return None
    root = _root_path(Path(repo), must_exist=True)
    git = shutil.which("git")
    if git is None:
        raise ValueError("git is unavailable")
    env = _git_environment()
    listing = subprocess.run([git, "--git-dir", str(root), "ls-tree", "-z", "--full-tree", commit, "--", path],
                             env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=30, check=False)
    if listing.returncode:
        raise ValueError("Git object read failed")
    records = listing.stdout.split(b"\0")
    if len(records) != 2 or records[-1] != b"":
        raise ValueError("unexpected Git tree result")
    info, name = records[0].split(b"\t", 1)
    mode, kind, oid = info.split(b" ")
    if name.decode("utf-8", "strict") != path or kind != b"blob" or mode not in (b"100644", b"100755"):
        raise ValueError("non-regular or mismatched Git tree entry")
    content = subprocess.run([git, "--git-dir", str(root), "cat-file", "blob", oid.decode("ascii")],
                             env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=30, check=False)
    if content.returncode or hashlib.sha256(content.stdout).hexdigest() != state.sha256:
        raise ValueError("Git blob read failed")
    return state, content.stdout


def discover_git_paths(repo: Path, commit: str, roots: list[str], *, max_entries: int = 2000) -> list[str]:
    """Discover regular Git blobs below explicitly selected roots, without checkout.

    This is not a release policy: the caller selects and authenticates roots.
    Unsafe paths and links reject the entire result rather than being omitted.
    """
    selected = validate_paths(roots)
    if not selected or type(max_entries) is not int or not 1 <= max_entries <= 2000:
        raise ValueError("invalid roots or entry limit")
    root = _root_path(Path(repo), must_exist=True)
    snapshot_git_blobs(root, commit, [], max_file_bytes=1)  # validate store and pinned commit
    git = shutil.which("git")
    process = None
    timed_out = threading.Event()
    try:
        process = subprocess.Popen([git, "--git-dir", str(root), "ls-tree", "-r", "-z", "--full-tree",
                                    commit, "--", *selected], env=_git_environment(), stdin=subprocess.DEVNULL,
                                   stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        def stop() -> None:
            timed_out.set()
            try:
                if process.poll() is None:
                    process.kill()
            except ProcessLookupError:
                pass
        timer = threading.Timer(30, stop)
        timer.daemon = True
        timer.start()
        chunks = []
        length = 0
        try:
            while True:
                chunk = process.stdout.read(65536)
                if not chunk:
                    break
                length += len(chunk)
                if length > 16 * 1024 * 1024:
                    process.kill()
                    raise ValueError("Git tree output exceeds limit")
                chunks.append(chunk)
            code = process.wait()
        finally:
            timer.cancel()
            process.stdout.close()
            if process.poll() is None:
                process.kill()
                process.wait()
        if timed_out.is_set() or code != 0:
            raise ValueError("Git tree read failed")
    except OSError as error:
        raise ValueError("Git tree read failed") from error
    output = b"".join(chunks)
    records = output.split(b"\0")
    if records[-1] != b"" or len(records) - 1 > max_entries:
        raise ValueError("invalid or oversized Git tree")
    paths = []
    for record in records[:-1]:
        try:
            info, name = record.split(b"\t", 1)
            mode, kind, oid = info.split(b" ")
            path = name.decode("utf-8", "strict")
            if mode not in (b"100644", b"100755") or kind != b"blob":
                raise ValueError("non-regular Git tree entry")
            if not re.fullmatch(rb"[0-9a-f]{%d}" % len(commit), oid):
                raise ValueError("invalid Git object id")
            if not any(path == prefix or path.startswith(prefix + "/") for prefix in selected):
                raise ValueError("Git entry outside selected roots")
            paths.append(path)
        except (UnicodeError, ValueError) as error:
            raise ValueError("unsafe Git tree entry") from error
    validate_paths(paths)
    return sorted(paths)


def plan_selected_git_update(*, repo: Path, commit: str, target: Path, paths: list[str],
                             receipt: dict[str, FileState] | None, local_paths: list[str],
                             max_file_bytes: int) -> dict:
    """Preview selected paths only; this output is neither approved nor applyable.

    Git mode bits and local OS mode bits have different semantics, particularly
    on Windows. They are deliberately reported unchanged; mode-only differences
    are not evidence of a real local edit until a portable mode policy exists.
    """
    selected, local = _validate_selection(paths, receipt, local_paths)
    src = _root_path(Path(repo), must_exist=True)
    dst = _root_path(Path(target), must_exist=False)
    try:
        common = Path(os.path.commonpath((str(src), str(dst))))
    except ValueError:
        common = None
    if common == src or common == dst:
        raise ValueError("object store and target roots must not overlap")
    incoming = snapshot_git_blobs(src, commit, list(selected), max_file_bytes=max_file_bytes)
    current = snapshot_files(dst, list(selected), max_file_bytes=max_file_bytes) if dst.is_dir() else {}
    result = _assemble(selected, local, receipt, current, incoming)
    result.update({"source_kind": "local_bare_git", "commit": commit,
                   "mode_comparison": "raw_os_vs_git_unverified", "applyable": False})
    return result
