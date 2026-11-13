#!/usr/bin/env python3
"""CodePrism MCP entrypoint with in-process save-time index updates.

The upstream `codeprism serve` builds the index once at startup and never
watches files. This wrapper starts the same MCP server and, after the initial
index is ready, runs its file watcher inside the server process. The watcher
uses the same in-memory graph and storage, so tool results see a saved file
without a restart.

Version 0.1.11 is pinned. The wrapper uses module internals that are checked by
the version guard below; after a package upgrade, re-run the live test.
"""

from __future__ import annotations

import argparse
import fcntl
import importlib.metadata
import os
import sys
from pathlib import Path

PINNED_VERSION = "0.1.11"

SKIP_DIRS = {
    "vendor",
    "node_modules",
    "templates_c",
    "dist",
    "plugins",
    "jscalendar-1.0",
    "minified",
    "i18n",
    "lang",
    "migrations",
    "fixtures",
}


def project_path(root: Path, path: str) -> Path:
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root):
        raise ValueError(f"Path traversal denied: '{path}' is outside project root '{root}'")
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve a CodePrism project")
    parser.add_argument("project", nargs="?", default=".")
    parser.add_argument("--transport", choices=("stdio", "http"), default="stdio")
    parser.add_argument("--port", type=int, help="Loopback port for HTTP")
    args = parser.parse_args()
    if args.transport == "http" and (args.port is None or not 1 <= args.port <= 65535):
        parser.error("HTTP requires --port in the range 1..65535")
    if args.transport == "stdio" and args.port is not None:
        parser.error("--port requires --transport http")
    root = Path(args.project).resolve()
    if not root.is_dir():
        parser.error(f"project directory does not exist: {root}")

    try:
        from codeprism.indexer import watcher as watcher_module
        from codeprism.indexer.incremental_updater import IncrementalUpdater
        from codeprism.indexer.watcher import ProjectWatcher
        from codeprism.mcp import server as srv
    except ImportError as exc:
        print(f"codeprism import failed: {exc}", file=sys.stderr)
        return 127

    version = importlib.metadata.version("codeprism-ai")
    if version != PINNED_VERSION:
        print(
            f"warning: codeprism-ai {version} differs from pinned {PINNED_VERSION}; "
            "verify the live index test",
            file=sys.stderr,
        )

    watcher_module._SKIP_DIRS = frozenset(set(watcher_module._SKIP_DIRS) | SKIP_DIRS)
    original_accepts = watcher_module._FileEventHandler._accepts

    def accepts(self, path: str) -> bool:
        if str(path).lower().endswith(".min.js"):
            return False
        return original_accepts(self, path)

    watcher_module._FileEventHandler._accepts = accepts

    original_background_index = srv._background_index

    async def background_index_with_watch(graph, storage, cfg) -> None:
        await original_background_index(graph, storage, cfg)
        updater = IncrementalUpdater(graph, storage)
        watcher = ProjectWatcher(updater, debounce_ms=cfg.watch_debounce_ms)
        await watcher.run(srv._project_path)

    srv._background_index = background_index_with_watch
    auto_index = os.environ.get("CODEPRISM_NO_AUTO_INDEX", "0") != "1"
    if args.transport == "stdio":
        srv.configure(str(root), auto_index=auto_index)
        srv.mcp.run()
        return 0

    try:
        lock = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            os.close(lock)
            raise
    except BlockingIOError:
        print(f"CodePrism HTTP server already running for project: {root}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Cannot lock CodePrism project {root}: {exc}", file=sys.stderr)
        return 1

    try:
        from codeprism.mcp.session import SessionManager

        def safe_abs(path: str) -> str:
            return str(project_path(root, path)) if path else path

        def validate_path(self, path: str) -> Path:
            return project_path(root, path)

        srv._abs = safe_abs
        SessionManager._validate_path = validate_path
        srv.mcp.disable(names={"index_project"}, components={"tool"})
        srv.configure(str(root), auto_index=auto_index)
        srv.mcp.run(
            transport="streamable-http", host="127.0.0.1", port=args.port,
            host_origin_protection=True, allowed_hosts=["127.0.0.1", "localhost", "::1"],
            allowed_origins=[],
        )
    finally:
        os.close(lock)
    return 0


if __name__ == "__main__":
    sys.exit(main())
