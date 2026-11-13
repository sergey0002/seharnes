"""Port selection and owner detection."""
from __future__ import annotations

import socket
from pathlib import Path


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port)) != 0


def first_free(start: int, end: int = 9199, avoid: set[int] | None = None) -> int:
    avoid = avoid or set()
    for port in range(start, end + 1):
        if port not in avoid and port_free(port):
            return port
    raise RuntimeError(f"no free port in {start}-{end}")


def owner(port: int) -> Path | None:
    """Return the Serena project listening on a port, when /proc is available."""
    proc = Path("/proc")
    if not proc.is_dir():
        return None
    needle = f"--port {port}"
    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            parts = [part for part in (entry / "cmdline").read_bytes().split(b"\0") if part]
        except OSError:
            continue
        command = [part.decode("utf-8", "replace") for part in parts]
        if "start-mcp-server" not in command or needle not in " ".join(command):
            continue
        if "--project" in command:
            index = command.index("--project") + 1
            if index < len(command):
                return Path(command[index]).resolve()
    return None


def sibling_ports(root: Path, mcp_file: str = ".cursor/mcp.json") -> set[int]:
    import json
    import re

    ports: set[int] = set()
    parent = root.parent
    if not parent.is_dir():
        return ports
    for project in parent.iterdir():
        if project == root or not project.is_dir():
            continue
        path = project / mcp_file
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        text = json.dumps(data)
        ports.update(int(value) for value in re.findall(r"127\\.0\\.0\\.1:(9\\d{3})", text))
    return ports
