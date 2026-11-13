#!/usr/bin/env python3
"""Small cross-platform process and path primitives for a future supervisor.

This module contains OS primitives only. It has no transfer policy, trust,
approval or conflict logic and must not be used to authorize file writes.
"""
from __future__ import annotations

import os
import signal
import stat
import subprocess
import time
from pathlib import Path

_running: dict[int, subprocess.Popen] = {}


def _regular_directory(path: Path) -> Path:
    absolute = Path(path).absolute()
    current = absolute
    while True:
        try:
            info = current.lstat()
        except FileNotFoundError:
            if current == current.parent:
                raise ValueError("path has no existing ancestor")
            current = current.parent
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(
                stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
            raise ValueError("path must not contain links")
        if not stat.S_ISDIR(info.st_mode):
            raise ValueError("path ancestor is not a directory")
        if current == current.parent:
            break
        current = current.parent
    if not absolute.is_dir():
        raise ValueError("directory is missing")
    return absolute


def _open_output(path: Path):
    path = Path(path).absolute()
    _regular_directory(path.parent)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags, 0o600)


def path_is_local(path: Path) -> bool:
    """Reject UNC shares and mapped network drives on Windows; POSIX is local."""
    if os.name != "nt":
        return True
    text = str(Path(path).absolute())
    if text.startswith("\\\\"):
        return False
    import ctypes
    drive = os.path.splitdrive(text)[0] + "\\"
    return ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(drive)) != 4


def spawn_detached(command: list[str], cwd: Path, stdout_path: Path, stderr_path: Path,
                   env: dict[str, str] | None = None) -> int:
    """Start one process outside the caller's session and return its pid."""
    if not isinstance(command, list) or not command:
        raise ValueError("command must be a non-empty list")
    if any(not isinstance(item, str) or not item or "\0" in item for item in command):
        raise ValueError("invalid command argument")
    if env is not None and (not isinstance(env, dict) or any(
            not isinstance(key, str) or not isinstance(value, str) for key, value in env.items())):
        raise ValueError("invalid environment")
    directory = _regular_directory(cwd)
    stdout_fd = _open_output(stdout_path)
    stderr_fd = _open_output(stderr_path)
    kwargs = {"stdin": subprocess.DEVNULL, "stdout": stdout_fd, "stderr": stderr_fd,
              "cwd": str(directory), "close_fds": True}
    if env is not None:
        kwargs["env"] = env
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(command, **kwargs)
    finally:
        os.close(stdout_fd)
        os.close(stderr_fd)
    _running[process.pid] = process
    for key, running in list(_running.items()):
        if running.poll() is not None:
            _running.pop(key, None)
    return process.pid


def _wait_popen(process: subprocess.Popen, timeout: float) -> bool:
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            return False
    return True


def terminate(pid: int, timeout: float = 5.0) -> bool:
    """Ask one process tree to stop, then force it after a bounded wait."""
    if type(pid) is not int or pid <= 1:
        raise ValueError("invalid process id")
    if type(timeout) not in (int, float) or timeout <= 0 or timeout > 60:
        raise ValueError("invalid timeout")
    process = _running.pop(pid, None)
    if process is not None:
        if os.name == "nt":
            try:
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, timeout=timeout, check=False)
            except (OSError, subprocess.TimeoutExpired):
                pass
            return _wait_popen(process, timeout)
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            _wait_popen(process, timeout)
            return True
        if _wait_popen(process, timeout):
            return True
        try:
            os.killpg(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return _wait_popen(process, timeout)
    if os.name == "nt":
        try:
            result = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=timeout, check=False)
        except (OSError, subprocess.TimeoutExpired):
            return False
        return result.returncode == 0
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return True
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        return True
    return True
