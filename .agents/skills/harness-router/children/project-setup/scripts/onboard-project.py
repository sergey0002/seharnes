#!/usr/bin/env python3
"""Onboard a project after the harness migration.

The export copies the agent environment, but a new project still needs its own
MCP values, indexes and ports. This script is the single entry point an agent
runs **in the target project root** after the export. It is idempotent, never
deletes project files and never commits anything.

What it does:

- detects the PHP container and the project documentation root;
- rewrites the Jira/bitbucket container in `.cursor` and `.codex`;
- sets or disables the mysql MCP and updates `MYSQL_*` in env files;
- picks a free Serena port and a free documentation panel port;
- sets `CODEPRISM_TARGET` to the project root and creates the codeprism venv;
- builds indexes: codegraph, CBM (async), jdocmunch, codeprism venv;
- optionally runs the project's slow doc index (`.dsh/scripts/doc-index.sh`);
- keeps `.git/info/exclude` rules so the harness is not committed by default;
- optionally stages safe harness paths when `--add-harness-to-git` is passed.

Usage:
  python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --check
  python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --yes \
      --php-container my-web-1 --mysql disable --serena-port 9124 --web-port 8079
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

TEXT = ("utf-8", "replace")


def log(message: str) -> None:
    print(message, flush=True)


def run(cmd: list[str], root: Path, env: dict[str, str] | None = None, timeout: int = 900) -> tuple[int, str]:
    merged = {**os.environ, **(env or {})}
    try:
        proc = subprocess.run(
            cmd, cwd=root, env=merged, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        output = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, output
    except FileNotFoundError:
        return 127, f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, f"timeout: {' '.join(cmd)}"


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def first_free(start: int, end: int = 9199, avoid: set[int] | None = None) -> int:
    avoid = avoid or set()
    for port in range(start, end + 1):
        if port in avoid:
            continue
        if port_free(port):
            return port
    raise SystemExit(f"no free port in {start}-{end}")


def sibling_ports(root: Path, kind: str) -> set[int]:
    """Ports already assigned to sibling projects, even when they are stopped."""
    ports: set[int] = set()
    parent = root.parent
    if not parent.is_dir():
        return ports
    for project in parent.iterdir():
        if project == root or not project.is_dir():
            continue
        if kind == "web":
            env_file = project / ".doc" / "web" / ".env"
            if env_file.is_file():
                match = re.search(r"(?m)^WEB_PANEL_PORT=(\d+)", env_file.read_text(encoding="utf-8", errors="replace"))
                if match:
                    ports.add(int(match.group(1)))
        elif kind == "serena":
            config = load_json(project / ".cursor" / "mcp.json")
            server = config.get("mcpServers", {}).get("serena")
            value = serena_url((server or {}).get("url", ""))
            if value:
                ports.add(int(value))
    return ports


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def serena_url(text: str) -> str | None:
    match = re.search(r"http://127\.0\.0\.1:(\d+)/mcp", text or "")
    return match.group(1) if match else None


def detect_container(root: Path) -> str | None:
    candidates = [
        root / ".dsh" / "scripts" / "php-docker.sh",
        root / ".dsh" / "AGENTS.md",
        root / "README.md",
    ]
    patterns = [
        r'CONTAINER="\$\{[A-Z_]+:-([A-Za-z0-9_.-]+)\}"',
        r"docker exec (?:-i )?(?:-w \S+ )?([A-Za-z0-9_.-]+) php",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
    return None


def detect_docroot(root: Path) -> Path | None:
    for candidate in (root / ".doc" / "archiecture", root / ".doc" / "architecture", root / "doc", root / ".doc"):
        if candidate.is_dir() and any(candidate.rglob("*.md")):
            return candidate
    return None


def replace_container(root: Path, old: str | None, new: str) -> int:
    changed = 0
    for path in (root / ".cursor" / "mcp.json", root / ".codex" / "mcp.json"):
        if not path.is_file():
            continue
        config = load_json(path)
        touched = False
        for server in config.get("mcpServers", {}).values():
            args = server.get("args")
            if isinstance(args, list) and "exec" in args and "-i" in args:
                index = args.index("-i") + 1
                if index < len(args) and isinstance(args[index], str):
                    args[index] = new
                    touched = True
        if touched:
            save_json(path, config)
            changed += 1

    codex = root / ".codex" / "config.toml"
    if codex.is_file():
        text = codex.read_text(encoding="utf-8", errors="replace")
        updated = re.sub(r'(args = \["exec", "-i", ")[^"]+(")', rf"\g<1>{new}\g<2>", text)
        if old:
            updated = updated.replace(old, new)
        if updated != text:
            codex.write_text(updated, encoding="utf-8")
            changed += 1
    return changed


def _set_toml_mysql_enabled(text: str, enabled: bool) -> str:
    match = re.search(r"(?ms)^\[mcp_servers\.mysql\]\s*$.*?(?=^\[|\Z)", text)
    if not match:
        return text
    block = match.group(0)
    if re.search(r"(?m)^enabled\s*=", block):
        block = re.sub(r"(?m)^enabled\s*=.*$", f"enabled = {str(enabled).lower()}", block, count=1)
    else:
        block = block.replace("[mcp_servers.mysql]", f"[mcp_servers.mysql]\nenabled = {str(enabled).lower()}", 1)
    return text[:match.start()] + block + text[match.end():]


def set_mysql(root: Path, mode: str, database: str | None, port: str | None) -> dict:
    cursor = root / ".cursor" / "mcp.json"
    config = load_json(cursor)
    server = config.get("mcpServers", {}).get("mysql")
    if server is None:
        return {"state": "missing"}
    if mode == "disable":
        server["disabled"] = True
    elif mode == "set":
        server["disabled"] = False
    if database:
        server.setdefault("env", {})["MYSQL_DATABASE"] = database
    if port:
        server.setdefault("env", {})["MYSQL_PORT"] = port
    save_json(cursor, config)

    for env_path in (root / ".cursor" / "mcp.env", root / ".codex" / "mcp.env", root / ".kilo" / "mcp.env"):
        if not env_path.is_file():
            continue
        text = env_path.read_text(encoding="utf-8", errors="replace")
        if database:
            text = re.sub(r"(?m)^MYSQL_DATABASE=.*$", f"MYSQL_DATABASE={database}", text)
        if port:
            text = re.sub(r"(?m)^MYSQL_PORT=.*$", f"MYSQL_PORT={port}", text)
        env_path.write_text(text, encoding="utf-8")

    codex = root / ".codex" / "config.toml"
    if codex.is_file():
        text = codex.read_text(encoding="utf-8", errors="replace")
        if mode == "disable":
            text = _set_toml_mysql_enabled(text, False)
        elif mode == "set":
            text = _set_toml_mysql_enabled(text, True)
        if database:
            text = re.sub(r'(?m)^MYSQL_DATABASE = ".*"$', f'MYSQL_DATABASE = "{database}"', text)
        if port:
            text = re.sub(r'(?m)^MYSQL_PORT = ".*"$', f'MYSQL_PORT = "{port}"', text)
        codex.write_text(text, encoding="utf-8")
    return {"state": "disabled" if mode == "disable" else ("configured" if mode == "set" else "unchanged")}


def ensure_codeprism(root: Path, check_only: bool) -> dict:
    cursor = root / ".cursor" / "mcp.json"
    config = load_json(cursor)
    server = config.get("mcpServers", {}).get("codeprism")
    if server is None:
        return {"state": "missing"}
    server.setdefault("env", {})["CODEPRISM_TARGET"] = str(root)
    if not check_only:
        save_json(cursor, config)

    codex = root / ".codex" / "config.toml"
    if codex.is_file():
        text = codex.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r'(?m)^CODEPRISM_TARGET = ".*"$', f'CODEPRISM_TARGET = "{root}"', text)
        if not check_only:
            codex.write_text(text, encoding="utf-8")

    config_path = root / ".codeprism.toml"
    if not config_path.is_file() and not check_only:
        config_path.write_text(
            '[codeprism]\nlanguages = ["php", "javascript", "typescript"]\n'
            "respect_gitignore = true\nauto_index = true\nenable_embeddings = false\n"
            "enable_security_gate = true\nwatch_debounce_ms = 800\n\n"
            "[codeprism.security]\nblock_on_secrets = true\nwarn_on_weak_crypto = true\n"
            "check_new_dependencies = true\nignore_paths = [\"*/vendor/*\", \"*/node_modules/*\", "
            "\"*/dist/*\", \"*/.dsh/*\", \"*/tests/*\"]\n",
            encoding="utf-8",
        )

    venv_python = root / ".cursor" / "tools" / "codeprism-ai" / "venv" / "bin" / "python"
    venv = {"present": venv_python.is_file()}
    if not venv["present"] and not check_only and shutil.which("uv"):
        (root / ".cursor" / "tools" / "codeprism-ai").mkdir(parents=True, exist_ok=True)
        code, out = run(["uv", "venv", ".cursor/tools/codeprism-ai/venv"], root, timeout=300)
        if code == 0:
            code, out = run(
                ["uv", "pip", "install", "--python", str(venv_python), "codeprism-ai==0.1.11"],
                root, timeout=900,
            )
        venv = {"present": venv_python.is_file(), "exit": code, "tail": out[-300:]}
    return {"target": str(root), "config": config_path.is_file(), **venv}


def serena_owner(port: int) -> Path | None:
    """Find the Serena project listening on a port (Linux /proc)."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    needle = f"--port {port}"
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        parts = [part.decode("utf-8", "replace") for part in raw.split(b"\0") if part]
        if "start-mcp-server" not in parts or needle not in " ".join(parts):
            continue
        if "--project" in parts:
            index = parts.index("--project") + 1
            if index < len(parts):
                return Path(parts[index]).resolve()
    return None


def set_serena(root: Path, requested: int, check_only: bool = False) -> tuple[int, list[str]]:
    cursor = root / ".cursor" / "mcp.json"
    config = load_json(cursor)
    server = config.get("mcpServers", {}).get("serena")
    if server is None:
        return requested or 9121, ["serena server not found"]
    current = serena_url(server.get("url", ""))
    port = requested or (int(current) if current else 0)
    notes = []
    if port and not requested:
        owner = serena_owner(port)
        if owner is not None and owner != root:
            notes.append(f"port {port} belongs to {owner}")
            port = first_free(9122, 9199, sibling_ports(root, "serena"))
        elif owner is None and (not port_free(port) or port in sibling_ports(root, "serena")):
            notes.append(f"port {port} is busy or reserved by a sibling project")
            port = first_free(9122, 9199, sibling_ports(root, "serena"))
    if not port:
        port = first_free(9122, 9199, sibling_ports(root, "serena"))
    if current and int(current) != port and not check_only:
        server["url"] = f"http://127.0.0.1:{port}/mcp"
        save_json(cursor, config)
    codex = root / ".codex" / "config.toml"
    if codex.is_file() and not check_only:
        text = codex.read_text(encoding="utf-8", errors="replace")
        updated = re.sub(r"http://127\.0\.0\.1:\d+/mcp", f"http://127.0.0.1:{port}/mcp", text)
        if updated != text:
            codex.write_text(updated, encoding="utf-8")
    if port_free(port):
        notes.append(f"serena port {port} is free; register with add-serena.sh")
    return port, notes


HARNESS_LINES = [
    "/.cursor/", "/.codex/", "/.agents/", "/.kilo/", "/.qoder/", "/.qwen/",
    "/.dsh/", "/.serena/",
]
DOC_LINE = "/.doc/"
DOC_HARNESS_LINES = [
    "/.doc/harnes/", "/.doc/skil_data/harness-core/", "/.doc/web/",
    "/.doc/skil_data/jira/",
    "/.doc/skil_data/task-doc/",
    "/.doc/skil_data/yadisk-screenshot/",
    "/.doc/skil_data/test-task/",
]
DOC_TRACKED_PATHS = [".doc/architecture", ".doc/archiecture", ".doc/tasks", ".doc/manifest", ".doc/archviz"]


def manage_git(
    root: Path,
    exclude_harness: bool,
    exclude_docs: bool | None,
    add_harness: bool,
    add_docs: bool,
    check_only: bool,
) -> dict:
    exclude = root / ".git" / "info" / "exclude"
    state = {"exclude_path": str(exclude), "harness_excluded": exclude_harness, "docs_excluded": exclude_docs}
    if not exclude.parent.is_dir():
        state["state"] = "no-git"
        return state

    lines = exclude.read_text(encoding="utf-8", errors="replace").splitlines() if exclude.exists() else []
    changed = False

    def ensure(line: str) -> None:
        nonlocal changed
        if line not in lines:
            lines.append(line)
            changed = True

    def remove(line: str) -> None:
        nonlocal changed
        while line in lines:
            lines.remove(line)
            changed = True

    if exclude_harness:
        for line in HARNESS_LINES:
            ensure(line)
    else:
        for line in HARNESS_LINES:
            remove(line)
    if exclude_docs is True:
        ensure(DOC_LINE)
        for line in DOC_HARNESS_LINES:
            remove(line)
    elif exclude_docs is False:
        remove(DOC_LINE)
        for line in DOC_HARNESS_LINES:
            ensure(line)

    if changed and not check_only:
        exclude.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")

    staged: list[str] = []
    if add_harness and not check_only:
        staged += stage_safe_harness(root)
    if add_docs and not check_only:
        paths = [item for item in DOC_TRACKED_PATHS if (root / item).exists()]
        if paths:
            code, out = run(["git", "add", "--", *paths], root, timeout=120)
            staged += paths if code == 0 else [f"git add docs failed: {out[-200:]}"]
    state.update({"changed": changed, "staged": staged, "harness_committed": False})
    return state


def stage_safe_harness(root: Path) -> list[str]:
    safe = [
        "AGENTS.md", "mcp.index.md", ".codeprism.toml", ".cbmignore",
        ".cursor/rules", ".tools/scripts", ".codex/rules", ".codex/config.toml",
        ".kilo/rules", ".agents/rules", ".agents/skills",
        ".qoder/rules", ".qoder/skills", ".qwen/rules",
    ]
    paths = [item for item in safe if (root / item).exists()]
    if not paths:
        return []
    code, out = run(["git", "add", "-f", "--", *paths], root, timeout=120)
    return paths if code == 0 else [f"git add failed: {out[-200:]}"]


def build_indexes(root: Path, docroot: Path | None, repo: str, check_only: bool, reindex_docs: bool = False) -> dict:
    result: dict = {}

    codegraph = shutil.which("codegraph")
    status = {}
    if codegraph:
        if not check_only:
            run(["codegraph", "init", "--yes", str(root)], root, timeout=1200)
        code, out = run(["codegraph", "status", "--json"], root, timeout=120)
        try:
            status = json.loads(out[out.find("{"):]) if "{" in out else {}
        except json.JSONDecodeError:
            status = {}
        result["codegraph"] = {
            "fileCount": status.get("fileCount"),
            "nodeCount": status.get("nodeCount"),
            "pending": status.get("pendingChanges"),
            "state": (status.get("index") or {}).get("state"),
        }
    else:
        result["codegraph"] = {"state": "cli-missing"}

    jdoc = root / ".cursor" / "scripts" / "jdocmunch-mcp.sh"
    if jdoc.is_file() and docroot:
        if not check_only:
            env = {"JDOCMUNCH_REPO": repo, "JDOCMUNCH_DOCROOT": str(docroot)}
            run(["bash", str(jdoc.relative_to(root)), "--index"], root, env=env, timeout=1800)
        code, out = run(["bash", str(jdoc.relative_to(root)), "--repo"], root, timeout=120)
        result["jdocmunch"] = {"repo": out.strip().splitlines()[0] if out.strip() else "", "docroot": str(docroot)}
    else:
        result["jdocmunch"] = {"state": "script-or-docs-missing"}

    cbm = shutil.which("codebase-memory-mcp")
    if cbm:
        if not check_only:
            code, out = run(["codebase-memory-mcp", "cli", "index_repository", "--repo-path", str(root),
                             "--mode", "fast", "--async", "true"], root, timeout=300)
            result["codebase-memory-mcp"] = {"requested": code == 0, "tail": out[-200:]}
        else:
            code, out = run(["codebase-memory-mcp", "cli", "--json", "list_projects"], root, timeout=120)
            result["codebase-memory-mcp"] = {"projects": out[-400:] if code == 0 else "list_projects failed"}
    else:
        result["codebase-memory-mcp"] = {"state": "cli-missing"}

    if (root / ".dsh" / "scripts" / "doc-index.sh").is_file():
        project_index = {
            "state": "available",
            "command": "bash .dsh/scripts/doc-index.sh rebuild-arch",
            "note": "slow: multilingual mpnet, 15-20 min",
        }
        if reindex_docs and not check_only:
            script = ".dsh/scripts/doc-index.sh"
            runs = {}
            for action in ("rebuild-arch", "rebuild-manifest"):
                code, out = run(["bash", script, action], root, timeout=1800)
                runs[action] = {"exit": code, "tail": out[-200:]}
            project_index = {"state": "rebuilt", "runs": runs}
        result["project-doc-index"] = project_index
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Onboard a migrated project")
    parser.add_argument("--root", default=".", help="project root")
    parser.add_argument("--project-name", default="", help="default: directory name")
    parser.add_argument("--php-container", default="", help="PHP docker container name")
    parser.add_argument("--mysql", choices=("keep", "disable", "set"), default="keep")
    parser.add_argument("--mysql-database", default="")
    parser.add_argument("--mysql-port", default="")
    parser.add_argument("--serena-port", type=int, default=0)
    parser.add_argument("--web-port", type=int, default=0)
    parser.add_argument("--jdoc-repo", default="")
    parser.add_argument("--add-harness-to-git", action="store_true")
    parser.add_argument("--include-harness", action="store_true",
                        help="remove harness dirs from .git/info/exclude")
    docs_group = parser.add_mutually_exclusive_group()
    docs_group.add_argument("--exclude-docs", action="store_true",
                            help="add /.doc/ to .git/info/exclude")
    docs_group.add_argument("--include-docs", action="store_true",
                            help="remove /.doc/ from .git/info/exclude")
    parser.add_argument("--add-docs-to-git", action="store_true",
                        help="stage project docs (architecture, tasks, manifest, archviz)")
    parser.add_argument("--skip-indexes", action="store_true")
    parser.add_argument("--reindex-project-docs", action="store_true",
                        help="run .dsh/scripts/doc-index.sh rebuild-arch/rebuild-manifest (slow, 15-20 min)")
    parser.add_argument("--check", action="store_true", help="report state without changes")
    parser.add_argument("--yes", action="store_true", help="no prompts")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    name = args.project_name or root.name
    repo = args.jdoc_repo or f"local/{name}"
    docroot = detect_docroot(root)
    report: dict = {"root": str(root), "project": name, "check": args.check, "steps": {}}

    container = args.php_container or detect_container(root)
    if container and not args.check:
        report["steps"]["php-container"] = {
            "value": container,
            "files": replace_container(root, None, container),
        }
    else:
        report["steps"]["php-container"] = {"value": container, "state": "unknown" if not container else "detected"}

    report["steps"]["mysql"] = (
        {"state": "checked"} if args.check else set_mysql(root, args.mysql, args.mysql_database or None, args.mysql_port or None)
    )

    serena_port, serena_notes = set_serena(root, args.serena_port, args.check)
    report["steps"]["serena"] = {"port": serena_port, "notes": serena_notes}

    report["steps"]["codeprism"] = ensure_codeprism(root, args.check)

    web_env = root / ".doc" / "web" / ".env"
    web_example = root / ".doc" / "web" / ".env.example"
    web_port = args.web_port
    if not web_port:
        existing = ""
        if web_env.is_file():
            match = re.search(r"(?m)^WEB_PANEL_PORT=(\d+)", web_env.read_text(encoding="utf-8", errors="replace"))
            existing = match.group(1) if match else ""
        web_port = int(existing) if existing and int(existing) not in sibling_ports(root, "web") and port_free(int(existing)) else first_free(8077, 8099, sibling_ports(root, "web"))
    if not web_env.is_file() and (root / ".doc" / "web").is_dir() and not args.check:
        if web_example.is_file():
            web_env.write_text(web_example.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        else:
            web_env.write_text(f"WEB_PANEL_PORT={web_port}\n", encoding="utf-8")
    if web_env.is_file() and not args.check:
        text = web_env.read_text(encoding="utf-8", errors="replace")
        if re.search(r"(?m)^WEB_PANEL_PORT=.*$", text):
            text = re.sub(r"(?m)^WEB_PANEL_PORT=.*$", f"WEB_PANEL_PORT={web_port}", text)
        else:
            text = text.rstrip() + f"\nWEB_PANEL_PORT={web_port}\n"
        web_env.write_text(text, encoding="utf-8")
    report["steps"]["web-panel"] = {
        "port": web_port,
        "env": str(web_env) if web_env.is_file() else "missing",
        "start": f"WEB_PANEL_PORT={web_port} bash .doc/web/start.sh" if web_env.is_file() else "",
    }

    exclude_harness = not args.include_harness and not args.add_harness_to_git
    if args.exclude_docs:
        exclude_docs: bool | None = True
    elif args.include_docs or args.add_docs_to_git:
        exclude_docs = False
    else:
        exclude_docs = None
    report["steps"]["git"] = manage_git(
        root,
        exclude_harness=exclude_harness,
        exclude_docs=exclude_docs,
        add_harness=args.add_harness_to_git,
        add_docs=args.add_docs_to_git,
        check_only=args.check,
    )

    if not args.skip_indexes:
        report["steps"]["indexes"] = build_indexes(root, docroot, repo, args.check, args.reindex_project_docs)
    else:
        report["steps"]["indexes"] = {"state": "skipped"}

    sync = root / ".agents" / "skills" / "harness-router" / "children" / "environment-sync" / "scripts" / "sync-agent-views.sh"
    if sync.is_file() and not args.check:
        code, out = run(["bash", str(sync.relative_to(root))], root, timeout=600)
        report["steps"]["sync"] = {"exit": code, "tail": out[-300:]}
    else:
        report["steps"]["sync"] = {"state": "skipped" if args.check else "missing"}

    questions = []
    if not container:
        questions.append("Имя PHP-контейнера не найдено: передайте --php-container.")
    mysql_cfg = load_json(root / ".cursor" / "mcp.json").get("mcpServers", {}).get("mysql", {})
    if mysql_cfg.get("disabled"):
        questions.append("MySQL MCP уже отключён. Включить: --mysql set --mysql-database <db> --mysql-port <port>.")
    else:
        questions.append("MySQL MCP включён. Отключить: --mysql disable; задать БД: --mysql set --mysql-database <db>.")
    if not docroot:
        questions.append("Документация .doc не найдена: укажите корень и запустите индексацию.")
    if args.serena_port == 0:
        questions.append(f"Serena порт выбран {serena_port}; проверьте, что он свободен и закреплён за проектом.")
    git_state = report["steps"]["git"]
    if git_state.get("harness_excluded"):
        questions.append("Харнес исключён из git. Добавить: --add-harness-to-git (стейджинг без коммита).")
    if git_state.get("docs_excluded") is True:
        questions.append("Документация .doc исключена из git. Включить: --include-docs; добавить: --add-docs-to-git.")
    elif git_state.get("docs_excluded") is False:
        questions.append("Документация .doc не исключена из git. Скрыть: --exclude-docs.")
    report["questions"] = questions

    out_json = root / ".doc" / "onboard-report.json"
    out_md = root / ".doc" / "onboard-report.md"
    if not args.check:
        save_json(out_json, report)
        lines = [f"# Onboard: {name}", "", f"Root: `{root}`", ""]
        for key, value in report["steps"].items():
            lines.append(f"- `{key}`: {json.dumps(value, ensure_ascii=False)}")
        lines += ["", "## Вопросы", ""] + [f"- {item}" for item in questions]
        out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 1 if report["steps"]["sync"].get("exit", 0) else 0


if __name__ == "__main__":
    raise SystemExit(main())
