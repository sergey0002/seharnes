#!/usr/bin/env python3
"""Harness Mirror: one JSON node per harness file, plus a read-only graph viewer.

Deterministic part (this script): split a file into blocks that concatenate
back to the exact original bytes, hash it, detect literal links.
Semantic part (agent): description, lifecycle, sources of truth, curated
relations. The agent fills them through `apply`; the script never invents them.

Commands
    serve   static viewer with a write API on 127.0.0.1
    scan    build or refresh node JSON for harness files
    prompt  print the analysis task for one node
    apply   merge an agent analysis JSON into a node
    get     print one node with incoming and outgoing edges
    set     replace one block of a canonical file and recompile it
    build   write graph.json and copy the viewer
    check   verify node invariants and lossless round trip

Exit codes: 0 success, 1 checked negative result, 2 usage or validation error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import posixpath
import re
import shutil
import sys
import tempfile
from pathlib import Path

PARSER_VERSION = "3.6"
DEFAULT_DATA = ".doc/skil_data/mirror"
SCHEMA_VERSION = "2.2"

DECLARATIVE_EXT = {".md", ".markdown", ".txt", ".yml", ".yaml", ".mdc"}
EXECUTABLE_EXT = {".sh", ".bash", ".zsh", ".py", ".mjs", ".js", ".ts", ".ps1", ".cmd", ".bat", ".php"}
SKIP_DIRS = {
    ".git", "node_modules", "vendor", "__pycache__", ".venv", "venv",
    "pageImages", "images", "dompdf", "frontend", "admin", "templates",
    "templates_c", "cache", "storage", "var", "logs", "mailing",
    "worktrees", ".history", ".playwright-mcp", "graphify-out", ".codegraph", "tools", ".tools", ".data", ".state",
}
SKIP_NAMES = {"mcp.env", ".env", "id_rsa", "id_ed25519"}
SECRET_NAME = re.compile(r"(^|/)([^/]*(secret|credential|token|password)[^/]*)$", re.IGNORECASE)
SECRET_VALUE = re.compile(
    r"(sgp_[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9]{8,}|sk-[A-Za-z0-9]{12,}|AKIA[0-9A-Z]{12,}"
    r"|-----BEGIN [A-Z ]*PRIVATE KEY-----|Bearer\s+[A-Za-z0-9._-]{16,})"
)
INDEX_PREFIXES = (
    ".cursor/", ".codex/", ".kilo/", ".antigravity/", ".gemini/",
    ".agents/", ".dsh/",
)
INDEX_SKIP_PARTS = {"sandbox", "runs", "__pycache__", "node_modules", ".git"}
NODE_EXTRA_EXT = {".json", ".jsonc", ".toml"}
SKIP_FILE_NAMES = {"package-lock.json"}
DEFAULT_PATHS = [
    ".cursor/rules",
    ".cursor/skills",
    ".agents/skills",
    ".cursor/scripts",
    ".cursor/mcp-stack",
]
MIRROR_ROOTS = [".codex", ".kilo", ".agents", ".antigravity", ".gemini"]
DSH_ROOT = ".dsh"
ENV_PREFIXES = (
    (".cursor/", "cursor"),
    (".codex/", "codex"),
    (".kilo/", "kilo"),
    (".antigravity/", "antigravity"),
    (".gemini/", "gemini"),
    (".agents/", "agents"),
    (".dsh/", "dsh"),
)
EXTERNAL_TOOLS = {
    "git", "npm", "npx", "node", "docker", "php", "python", "python3",
    "bash", "sh", "zsh", "curl", "wget", "powershell", "pwsh", "composer",
    "rg", "grep", "sed", "awk", "jq", "uvx", "uv",
}
RELATION_TYPES = {
    "invokes_tool", "delegates_to", "constrained_by", "governed_by",
    "enforces_gate", "reads_context", "next_stage_pipeline",
    "patches_target", "mirrors", "synced_by",
}
AGENT_RELATION_REQUIRED = {"block_id", "target_name", "target_type", "relation_type", "origin", "resolution", "anchor_text"}
TARGET_TYPES = {"rule", "skill", "script", "config", "external_tool", "doc", "mcp"}
RESOLUTIONS = {"resolved", "ambiguous", "unresolved", "external", "missing"}
EDITABLE_TYPES = {"skill", "rule"}
PRIMARY_STEMS = {"skill", "skills", "rule", "rules", "agents", "claude", "cordis.patch", "index", "main"}
AUX_STEMS = {"readme", "guide", "docs", "notes", "changelog", "plan"}

MD_HEADING = re.compile(r"(?m)^(#{1,6})[ \t]+(.+?)[ \t]*$")
MD_LINK = re.compile(r"\[[^\]\n]*\]\(([^)\s]+)")
CODE_TARGET = re.compile(
    r"`((?:\.{0,2}/)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:md|mdc|json|jsonc|sh|bash|zsh|py|mjs|js|ts|ps1|cmd|bat|yml|yaml|php|tpl))`"
)
SKILL_MENTION = re.compile(r"(?:скил[аеуы]?|skill)\s+[`'\"]?([a-z][a-z0-9-]{2,})", re.IGNORECASE)
CODE_MARKERS = (
    re.compile(r"^(?:async\s+def|def|class)\s+\w+"),
    re.compile(r"^(?:export\s+)?(?:async\s+)?function\s+\w+"),
    re.compile(r"^(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?(?:function|\()"),
    re.compile(r"^(?:function\s+)?[\w.-]+\s*\(\)\s*\{"),
    re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\s*\(\)\s*\{"),
)
ENV_VAR = re.compile(r"\$\{?([A-Z][A-Z0-9_]{2,})\}?")
ARG_DEF = re.compile(r"add_argument\(\s*[\"']([^\"']+)[\"']")
DESTRUCTIVE = re.compile(r"\b(rm\s+-rf|git\s+push|DROP\s+TABLE|DELETE\s+FROM|truncate)\b", re.IGNORECASE)
WRITE_OP = re.compile(r"(>\s*[\w./-]+|\btee\b|\bmv\b|\bcp\b|\bmkdir\b|open\([^)]*[\"']w)", re.IGNORECASE)
NETWORK = re.compile(r"\b(curl|wget|npm\s+install|pip\s+install|fetch\(|requests\.)", re.IGNORECASE)


class MirrorError(Exception):
    """Error with a documented exit code."""

    def __init__(self, message: str, code: int = 2):
        super().__init__(message)
        self.code = code


def warn(message: str) -> None:
    sys.stderr.write(message + "\n")


def find_root(explicit: str | None, script: Path) -> Path:
    if explicit:
        candidate = Path(explicit).resolve()
        if not ((candidate / ".git").exists() or (candidate / ".cursor").is_dir()):
            raise MirrorError("root has no .git and no .cursor: %s" % candidate)
        return candidate
    for start in (script.resolve().parent, Path.cwd().resolve()):
        for candidate in [start, *start.parents]:
            if (candidate / ".git").exists() or (candidate / ".cursor").is_dir():
                return candidate
    raise MirrorError("root not found: pass --root")


def rel_of(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


def environment_of(rel: str) -> str:
    for prefix, env in ENV_PREFIXES:
        if rel.startswith(prefix):
            return env
    return "project"


def type_of(rel: str) -> str:
    if "/skills/" in rel and rel.endswith("SKILL.md"):
        return "skill"
    if "/rules/" in rel:
        return "rule"
    ext = Path(rel).suffix.lower()
    if ext in EXECUTABLE_EXT:
        return "script"
    if ext in {".json", ".jsonc", ".yml", ".yaml", ".toml"}:
        return "config"
    if Path(rel).name in {"mcp.json", "config.toml", "kilo.jsonc"}:
        return "config"
    return "doc"


def slug_of(rel: str) -> str:
    path = Path(rel)
    stem = path.stem.lower()
    parent = path.parent.name.lower()
    # The skill name goes first, otherwise `references/index.md` in two skills
    # both collapse to `references` and `scan` fails with a node_id collision.
    if "/skills/" in rel and not rel.endswith("/SKILL.md"):
        parts = rel.split("/skills/", 1)[1].split("/")
        skill = parts[0].lower()
        if "children" in parts[:-1] or len(parts) > 3:
            stem = "-".join(part.lower() for part in parts[:-1] + [stem])
        else:
            stem = "%s-%s" % (skill, parent if stem in PRIMARY_STEMS else stem)
    elif stem in PRIMARY_STEMS:
        stem = parent
    elif stem in AUX_STEMS and parent not in {".cursor", "rules", "skills", "scripts", "docs", ""}:
        stem = "%s-%s" % (parent, stem)
    stem = re.sub(r"[^a-z0-9._-]+", "-", stem).strip("-.")
    return stem or "node"


def is_canonical_rel(rel: str) -> bool:
    """Canonical is `.cursor/`, project root and the real skills tree.

    `.agents/skills` is the real directory; `.cursor/skills` is a symlink to
    it. Both paths address the same file, so both are canonical and produce
    the same node_id. Mirrors of rules and scripts stay under `.cursor/`.
    """
    return environment_of(rel) in ("cursor", "project") or rel.startswith(".agents/skills/")


def node_id_of(rel: str) -> str:
    kind = type_of(rel)
    env = environment_of(rel)
    slug = slug_of(rel)
    if kind == "script":
        slug = "%s-%s" % (slug, Path(rel).suffix.lstrip(".").lower())
    base = f"{kind}:{slug}"
    return base if is_canonical_rel(rel) else f"{base}@{env}"


def canon_candidates_of(rel: str) -> list[str]:
    """Canonical paths for a mirror file, most specific first."""
    if is_canonical_rel(rel):
        return [rel]
    for prefix, _env in ENV_PREFIXES:
        if rel.startswith(prefix):
            rest = rel[len(prefix):]
            if rest.startswith("skills/"):
                tail = rest[len("skills/"):]
                return [".agents/skills/" + tail, ".cursor/skills/" + tail]
            return [".cursor/" + rest]
    return []


def canon_rel_of(rel: str) -> str | None:
    candidates = canon_candidates_of(rel)
    return candidates[0] if candidates else None


def safe_name(node_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "__", node_id)


def sha256_of(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def lf_sha256_of(path: Path) -> str | None:
    """Hash that ignores line endings, matching the parity rule of the project."""
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    return hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest()


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise


def write_text(path: Path, text: str) -> None:
    atomic_write(path, text.encode("utf-8"))


def write_json(path: Path, data: dict) -> None:
    write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


class Lock:
    """Best effort single-writer lock for mutating commands."""

    def __init__(self, data_dir: Path):
        self.path = data_dir / ".lock"
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = open(self.path, "a+")
        try:
            import fcntl
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        except (ImportError, OSError):
            pass
        return self

    def __exit__(self, *_exc):
        if self.handle is not None:
            try:
                import fcntl
                fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            except (ImportError, OSError):
                pass
            self.handle.close()


def read_source(path: Path) -> tuple[bytes, str, bool]:
    raw = path.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise MirrorError("not utf-8: %s (%s)" % (path, exc)) from exc
    return raw, text, bom


def line_ending_of(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    if crlf and lf:
        return "mixed"
    return "\r\n" if crlf else "\n"


def split_markdown(text: str) -> list[dict]:
    blocks: list[dict] = []
    pos = 0
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            newline = text.find("\n", end + 1)
            end = len(text) if newline == -1 else newline + 1
            blocks.append({
                "block_type": "frontmatter",
                "header_text": None,
                "header_level": None,
                "raw_content": text[:end],
            })
            pos = end
    heads = [m for m in MD_HEADING.finditer(text) if m.start() >= pos]
    if not heads:
        if pos < len(text):
            blocks.append({
                "block_type": "preamble" if not blocks else "section",
                "header_text": None,
                "header_level": None,
                "raw_content": text[pos:],
            })
        return blocks
    if heads[0].start() > pos:
        blocks.append({
            "block_type": "preamble",
            "header_text": None,
            "header_level": None,
            "raw_content": text[pos:heads[0].start()],
        })
    for index, match in enumerate(heads):
        stop = heads[index + 1].start() if index + 1 < len(heads) else len(text)
        blocks.append({
            "block_type": "section",
            "header_text": match.group(2).strip(),
            "header_level": len(match.group(1)),
            "raw_content": text[match.start():stop],
        })
    return blocks


def split_code(text: str) -> list[dict]:
    lines = text.splitlines(keepends=True)
    starts = [0]
    for index, line in enumerate(lines):
        if index == 0:
            continue
        if any(marker.match(line) for marker in CODE_MARKERS):
            starts.append(index)
    starts = sorted(set(starts))
    blocks = []
    for index, start in enumerate(starts):
        stop = starts[index + 1] if index + 1 < len(starts) else len(lines)
        raw = "".join(lines[start:stop])
        if not raw:
            continue
        head = lines[start].strip()
        name = "block %d" % index
        for pattern in (
            r"^(?:async\s+def|def|class|function)\s+([\w.-]+)",
            r"^(?:export\s+)?(?:async\s+)?function\s+([\w.-]+)",
            r"^([\w.-]+)\s*\(\)\s*\{",
        ):
            match = re.match(pattern, head)
            if match:
                name = match.group(1)
                break
        else:
            if head.startswith("#!"):
                name = "shebang"
        blocks.append({
            "block_id": "b%03d" % index,
            "order": index,
            "line_range": "%d-%d" % (start + 1, stop),
            "name_or_purpose": name,
            "raw_code": raw,
        })
    return blocks


MCP_CONFIG_CANDIDATES = [".cursor/mcp.json", ".cursor/mcp_config.json"]
MCP_NAME_KEYS = ("mcpServers", "servers")
MCP_CUE = re.compile(r"(?i)(?<![a-z0-9_])mcp(?![a-z0-9_])")
# `mcp.json`, `mcp.env`, `mcp-stack` are file and directory names, not a claim
# that the line talks about an MCP server.
# Standalone token: not the tail of another server name such as
# `codebase-memory-mcp`, but `MCP-серверы` and `mcp-server-git` still count.
STANDALONE_MCP = re.compile(r"(?i)(?<![A-Za-z0-9_.-])mcp(?![a-z0-9_.])")
MCP_FILE_TAIL = re.compile(r"(?i)^[._-](json|env|stack|servers|config|shared|proxy|client|mjs)")


# Names that are also ordinary CLI tools or product names. A line that says
# `git push` is not about the git MCP server, so these need a tight cue.
AMBIGUOUS_MCP = {
    "git", "mysql", "playwright", "serena", "codegraph", "sourcegraph",
    "xdebug", "semgrep", "context7", "deepwiki", "jira-task", "bitbucket-task",
}
CLI_VERB = re.compile(
    r"^(status|add|log|diff|show|blame|push|pull|commit|clone|fetch|merge|rebase|"
    r"checkout|switch|branch|remote|check-ignore|run|exec|-e|-u|--?\w+)",
    re.IGNORECASE,
)


def has_mcp_cue(line: str) -> bool:
    for match in MCP_CUE.finditer(line):
        if MCP_FILE_TAIL.match(line[match.end():match.end() + 12]):
            continue
        return True
    return False


def ambiguous_ok(line: str, match) -> bool:
    """Position check for names shared with CLI tools."""
    before = line[max(0, match.start() - 1):match.start()]
    after = line[match.end():]
    if before == ".":
        return False
    if re.match(r"^(__|_|-)", after):
        return True
    if CLI_VERB.match(after.strip()):
        return False
    for cue in STANDALONE_MCP.finditer(line):
        if MCP_FILE_TAIL.match(line[cue.end():cue.end() + 12]):
            continue
        gap = cue.start() - match.end() if cue.start() >= match.end() else match.start() - cue.end()
        if 0 <= gap <= 25:
            return True
    return False


def mcp_anchor(raw: str, name: str) -> str:
    """Line that really refers to the MCP server, or empty string.

    A bare word is not enough: `git` in `git status` is a command, `mysql` in a
    SQL note is a database. The line must carry an MCP cue, or the server name
    itself must contain `mcp`.
    """
    word = r"(?<![A-Za-z0-9_-])" + re.escape(name) + r"(?![A-Za-z0-9_-])"
    if "mcp" in name.lower():
        match = re.search(word, raw)
        if not match:
            return ""
        return anchor_of(raw, name) or match.group(0)
    tool_prefix = re.compile(r"mcp[_-]{1,2}" + re.escape(name), re.IGNORECASE)
    ambiguous = name.lower() in AMBIGUOUS_MCP
    for line in raw.splitlines():
        if tool_prefix.search(line):
            return line.strip()[:200]
        matches = list(re.finditer(word, line))
        if not matches or not has_mcp_cue(line):
            continue
        if ambiguous and not any(ambiguous_ok(line, m) for m in matches):
            continue
        return line.strip()[:200]
    return ""


def load_mcp_servers(root: Path) -> tuple[str | None, dict]:
    """Read MCP server names and shape only. Values and secrets never leave this function."""
    for rel in MCP_CONFIG_CANDIDATES:
        path = root / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        servers = None
        for key in MCP_NAME_KEYS:
            if isinstance(data.get(key), dict):
                servers = data[key]
                break
        if servers is None:
            continue
        out = {}
        for name, cfg in servers.items():
            if not isinstance(name, str) or not isinstance(cfg, dict):
                continue
            transport = cfg.get("type") or ("http" if cfg.get("url") else "stdio")
            out[name] = {
                "transport": str(transport),
                "command": str(cfg.get("command") or "")[:80],
                "args": len(cfg.get("args") or []),
                "env_keys": sorted((cfg.get("env") or {}).keys())[:20],
            }
        return rel, out
    return None, {}


def is_secret_name(rel: str) -> bool:
    name = Path(rel).name
    if name.endswith((".example", ".dist", ".template", ".sample")):
        return False
    if name in SKIP_NAMES or name.endswith((".env", ".key", ".pem", ".p12", ".pfx")):
        return True
    return bool(SECRET_NAME.search(rel))


def looks_secret(text: str) -> bool:
    return bool(SECRET_VALUE.search(text))


def build_index(root: Path) -> dict:
    files: dict[str, dict] = {}
    stems: dict[str, list[str]] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        # Harness scope is the agent configuration tree only. Documentation,
        # product code and tasks are outside and never enter the index.
        if rel_dir != "." and not (rel_dir + "/").startswith(INDEX_PREFIXES):
            dirnames[:] = []
            continue
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in SKIP_DIRS and d not in INDEX_SKIP_PARTS and not d.startswith(".playwright")
        )
        for filename in sorted(filenames):
            rel = (Path(rel_dir) / filename).as_posix() if rel_dir != "." else filename
            if len(Path(rel).parts) > 16 or is_secret_name(rel) or filename.startswith("."):
                continue
            if rel_dir != "." and not rel.startswith(INDEX_PREFIXES):
                continue
            if Path(rel).suffix.lower() not in DECLARATIVE_EXT | EXECUTABLE_EXT | NODE_EXTRA_EXT:
                continue
            files[rel] = {
                "type": type_of(rel),
                "environment": environment_of(rel),
                "node_id": node_id_of(rel),
            }
            stems.setdefault(Path(rel).stem.lower(), []).append(rel)
    return {"files": files, "stems": stems}


def anchor_of(raw: str, needle: str) -> str:
    for line in raw.splitlines():
        if needle in line:
            return line.strip()[:200] or needle[:200]
    return ""


def clean_rel(path: str) -> str:
    """Drop a leading ./ and / only. Never strip the dot of `.cursor` or `.doc`."""
    while path.startswith("./"):
        path = path[2:]
    return path.lstrip("/")


def resolve(target: str, index: dict, hint: str | None, base_dir: str = "") -> tuple[str | None, str | None, str, list[str]]:
    files = index["files"]
    raw = target.strip().strip("`'\"")
    if raw in EXTERNAL_TOOLS:
        return None, None, "external", []
    candidate = raw.replace("\\", "/")
    variants: list[str] = []
    if candidate.startswith(("/", "./", "../")):
        joined = posixpath.normpath(posixpath.join(base_dir, candidate))
        variants.append(clean_rel(joined))
    stripped = candidate
    while stripped.startswith("../"):
        stripped = stripped[3:]
    variants.append(clean_rel(stripped))
    # `.cursor/skills` is a symlink view; the indexed file lives under
    # `.agents/skills`. Try the real path before falling back to stem search.
    for variant in list(variants):
        if variant.startswith(".cursor/skills/"):
            variants.append(".agents/skills/" + variant[len(".cursor/skills/"):])
    for variant in variants:
        if variant in files:
            entry = files[variant]
            return variant, entry["node_id"], "resolved", []
    candidate = variants[0] if variants else stripped
    if "/" not in candidate:
        # Bare `SKILL.md`, `README.md`, `plan.md` inside a skill refer to the
        # nearest matching file in the same subtree, not to any file with that
        # stem in the project.
        cur = Path(base_dir) if base_dir else None
        for _ in range(4):
            if cur is None or cur.as_posix() in (".", ""):
                break
            trial = clean_rel((cur / candidate).as_posix())
            if trial in files:
                entry = files[trial]
                return trial, entry["node_id"], "resolved", []
            cur = cur.parent
    by_stem = list(index["stems"].get(Path(candidate).stem.lower(), []))
    if not by_stem and candidate:
        wanted = candidate.lower()
        by_stem = [p for p in files if slug_of(p) == wanted]
    if hint == "skill":
        by_stem = [p for p in by_stem if "/skills/" in p] or by_stem
    if len(by_stem) > 1:
        canonical = [p for p in by_stem if p.startswith(".cursor/")]
        if len(canonical) == 1:
            by_stem = canonical
    if len(by_stem) == 1:
        entry = files[by_stem[0]]
        return by_stem[0], entry["node_id"], "resolved", []
    if len(by_stem) > 1:
        return None, None, "ambiguous", by_stem[:8]
    return None, None, "unresolved", []


def relation_type_for(path: str | None, kind: str, anchor: str) -> str:
    low = anchor.lower()
    if kind == "external_tool" or (kind == "script" and re.search(r"(run|запуст|invoke|вызов)", low)):
        return "invokes_tool"
    if kind == "skill":
        return "delegates_to"
    if kind == "rule":
        return "governed_by"
    return "reads_context"


def detect_relations(raw: str, index: dict, base_dir: str = "", mcp_names: list[str] | None = None) -> list[dict]:
    found: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(target: str, hint: str | None) -> None:
        path, node_id, resolution, candidates = resolve(target, index, hint, base_dir)
        if resolution == "external":
            kind = "external_tool"
        elif path:
            kind = index["files"][path]["type"]
        else:
            # Documentation, product code and other non-harness paths stay out
            # of the graph: skills must not depend on docs that change daily.
            probe = target.replace("\\", "/")
            while probe.startswith(("./", "../")):
                probe = probe[2:] if probe.startswith("./") else probe[3:]
            if not probe.startswith(INDEX_PREFIXES):
                return
            kind = hint or "doc"
        anchor = anchor_of(raw, target)
        rel_type = relation_type_for(path, kind, anchor)
        key = (node_id or target, rel_type)
        if key in seen:
            return
        seen.add(key)
        item = {
            "target_name": Path(target).stem if path is None else Path(path).name,
            "target_type": kind,
            "target_path": path,
            "target_node_id": node_id,
            "relation_type": rel_type,
            "origin": "auto",
            "resolution": resolution,
            "anchor_text": anchor,
            "execution_moment": "",
        }
        if candidates:
            item["candidates"] = candidates
        found.append(item)

    for match in MD_LINK.finditer(raw):
        url = match.group(1)
        if url.startswith(("http://", "https://", "mailto:", "#")):
            continue
        add(url.split("#", 1)[0], None)
    for match in CODE_TARGET.finditer(raw):
        add(match.group(1), None)
    for match in SKILL_MENTION.finditer(raw):
        add(match.group(1), "skill")
    for name in mcp_names or []:
        anchor = mcp_anchor(raw, name)
        if not anchor:
            continue
        key = ("mcp:" + name, "invokes_tool")
        if key in seen:
            continue
        seen.add(key)
        found.append({
            "target_name": name,
            "target_type": "mcp",
            "target_path": None,
            "target_node_id": "mcp:" + name,
            "relation_type": "invokes_tool",
            "origin": "auto",
            "resolution": "resolved",
            "anchor_text": anchor,
            "execution_moment": "",
        })
    return found


def merge_relations(previous: list[dict], detected: list[dict]) -> list[dict]:
    merged = list(detected)
    keys = {(item.get("target_node_id") or item.get("target_name"), item.get("relation_type")) for item in merged}
    for item in previous:
        # Auto relations are recomputed on every parse; keeping them would make
        # an outdated detection survive forever.
        if item.get("origin") != "agent":
            continue
        key = (item.get("target_node_id") or item.get("target_name"), item.get("relation_type"))
        if key not in keys:
            merged.append(item)
            keys.add(key)
    return merged


def default_lifecycle() -> dict:
    return {"trigger_condition": "", "phase": "execution", "priority": None}


def frontmatter_fields(text: str) -> dict:
    """Small frontmatter reader: plain keys plus folded and literal blocks.

    No YAML dependency: harness frontmatter uses simple keys, and the panel only
    needs description and name.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end < 0:
        return {}
    lines = text[3:end].split("\n")
    fields: dict[str, str] = {}
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        if not line.strip() or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value in (">", "|", ">-", "|-"):
            collected: list[str] = []
            while index < len(lines):
                nxt = lines[index]
                if nxt.strip() and not nxt.startswith((" ", "\t")):
                    break
                collected.append(nxt.strip())
                index += 1
            joiner = " " if value.startswith(">") else "\n"
            value = joiner.join(part for part in collected if part)
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        fields[key] = value
    return fields


def first_sentence(text: str, limit: int = 110) -> str:
    flat = " ".join(str(text or "").split())
    if not flat:
        return ""
    cut = flat
    for mark in (". ", "! ", "? "):
        pos = flat.find(mark)
        if pos > 0:
            cut = flat[:pos + 1]
            break
    if len(cut) > limit:
        cut = cut[:limit - 1].rstrip() + "…"
    return cut


def meta_block(rel: str, root: Path, raw: bytes, kind: str, description: str, symlink: str | None) -> dict:
    env = environment_of(rel)
    canonical = is_canonical_rel(rel)
    projection = None
    # mcp-servers files may exist as adapted per-environment copies (for
    # example a Codex copy pointing to `.codex/tools`). Those are not byte
    # mirrors of any canon file, so comparing hashes would report permanent
    # false drift; keep them standalone.
    adapted = "/mcp-servers/" in rel
    if not canonical and not adapted:
        for candidate in canon_candidates_of(rel):
            if (root / candidate).is_file():
                projection = node_id_of(candidate)
                break
    meta = {
        "node_id": node_id_of(rel),
        "name": slug_of(rel),
        "type": kind,
        "environment": env,
        "source_file_path": rel,
        "canonical": canonical,
        "projection_of": projection,
        "transferable": Path(rel).name != "ADAPTERS.local.md",
        "content_sha256": sha256_of(raw),
        "parser_version": PARSER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "description": description,
    }
    if symlink:
        meta["symlink_target"] = symlink
    return meta


def build_node(rel: str, root: Path, index: dict, previous: dict | None, mcp_names: list[str] | None = None) -> dict:
    path = root / rel
    raw_bytes, text, bom = read_source(path)
    symlink = os.readlink(path) if path.is_symlink() else None
    descriptive = Path(rel).suffix.lower() not in EXECUTABLE_EXT
    prev_meta = (previous or {}).get("meta", {})
    description = prev_meta.get("description", "")
    if not description and Path(rel).suffix.lower() in {".md", ".mdc"}:
        description = frontmatter_fields(text).get("description", "")
    common_meta = meta_block(rel, root, raw_bytes, type_of(rel), description, symlink)
    recon = {
        "total_blocks": 0,
        "line_ending": line_ending_of(text),
        "bom": bom,
        "final_newline": text.endswith("\n") or text == "",
    }
    if descriptive:
        recon["has_frontmatter"] = text.startswith("---")
        blocks = []
        for order, block in enumerate(split_markdown(text)):
            detected = detect_relations(block["raw_content"], index, posixpath.dirname(rel), mcp_names)
            old = []
            old_blocks = (previous or {}).get("content_blocks", [])
            if previous and order < len(old_blocks) and old_blocks[order].get("raw_content") == block["raw_content"]:
                old = old_blocks[order].get("relations", [])
            blocks.append({
                "block_id": "b%03d" % order,
                "order": order,
                "block_type": block["block_type"],
                "header_text": block["header_text"],
                "header_level": block["header_level"],
                "raw_content": block["raw_content"],
                "relations": merge_relations(old, detected),
            })
        recon["total_blocks"] = len(blocks)
        return {
            "meta": common_meta,
            "lifecycle": (previous or {}).get("lifecycle") or default_lifecycle(),
            "sources_of_truth": (previous or {}).get("sources_of_truth", []),
            "reconstruction_meta": recon,
            "content_blocks": blocks,
            "global_relations": (previous or {}).get("global_relations", []),
            "analysis": (previous or {}).get("analysis") or {"status": "pending", "model": None},
        }
    blocks = []
    for order, block in enumerate(split_code(text)):
        detected = detect_relations(block["raw_code"], index, posixpath.dirname(rel), mcp_names)
        old = []
        old_blocks = (previous or {}).get("code_blocks", [])
        if previous and order < len(old_blocks) and old_blocks[order].get("raw_code") == block["raw_code"]:
            old = old_blocks[order].get("relations", [])
        blocks.append(dict(block, relations=merge_relations(old, detected)))
    recon["total_blocks"] = len(blocks)
    shebang = text.splitlines()[0] if text.startswith("#!") else None
    env_vars = sorted({m.group(1) for m in ENV_VAR.finditer(text)} - {"PATH", "HOME", "PWD", "IFS", "SHELL", "USER"})
    args = [
        {"name": m.group(1).lstrip("-"), "type": "string", "required": False, "default": None, "description": ""}
        for m in ARG_DEF.finditer(text)
    ]
    destructive = bool(DESTRUCTIVE.search(text))
    return {
        "meta": dict(common_meta, type="script"),
        "execution_profile": {
            "runtime": {".sh": "bash", ".bash": "bash", ".zsh": "zsh", ".py": "python", ".js": "node", ".mjs": "node", ".ts": "node"}.get(
                Path(rel).suffix.lower(), "sh"
            ),
            "interpreter_shebang": shebang,
            "command_template": "%s %s" % (Path(rel).suffix.lstrip("."), rel),
            "env_vars_required": env_vars,
            "arguments": args,
        },
        "lifecycle": (previous or {}).get("lifecycle") or {
            "trigger_condition": "",
            "phase": "execution",
            "security_level": "destructive_write" if destructive else ("idempotent_write" if WRITE_OP.search(text) else "read_only"),
        },
        "sandbox_policy": (previous or {}).get("sandbox_policy") or {
            "requires_approval": destructive,
            "filesystem_access": "workspace_only",
            "network_access": bool(NETWORK.search(text)),
        },
        "reconstruction_meta": recon,
        "code_blocks": blocks,
        "global_relations": (previous or {}).get("global_relations", []),
        "analysis": (previous or {}).get("analysis") or {"status": "pending", "model": None},
    }


def node_path(data: Path, node_id: str) -> Path:
    return data / "nodes" / (safe_name(node_id) + ".json")


def load_node(data: Path, node_id: str) -> dict:
    path = node_path(data, node_id)
    if not path.is_file():
        raise MirrorError("node not found: " + node_id, 1)
    return json.loads(path.read_text(encoding="utf-8"))


def save_node(data: Path, node: dict) -> Path:
    own_id = node["meta"]["node_id"]
    for block in node.get("content_blocks", node.get("code_blocks", [])):
        relations = block.get("relations")
        if not relations:
            continue
        block["relations"] = [
            rel for rel in relations
            if not (rel.get("origin") == "auto" and rel.get("target_node_id") == own_id)
        ]
    path = node_path(data, own_id)
    write_json(path, node)
    return path


def block_key(node: dict) -> str:
    return "content_blocks" if "content_blocks" in node else "code_blocks"


def compile_node(node: dict) -> str:
    key = block_key(node)
    field = "raw_content" if key == "content_blocks" else "raw_code"
    return "".join(block[field] for block in sorted(node[key], key=lambda b: b["order"]))


def targets_for(root: Path, includes: list[str], mirrors: bool, dsh: bool) -> list[str]:
    roots = list(includes) if includes else list(DEFAULT_PATHS)
    if mirrors:
        roots += list(MIRROR_ROOTS)
    if dsh:
        roots.append(DSH_ROOT)
    out: list[str] = []
    for entry in roots:
        path = root / entry
        if path.is_file():
            out.append(entry)
            continue
        if not path.is_dir():
            continue
        for dirpath, dirnames, filenames in os.walk(path):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for filename in sorted(filenames):
                if filename.startswith(".") or filename in SKIP_FILE_NAMES:
                    continue
                rel = rel_of(Path(dirpath) / filename, root)
                if Path(rel).suffix.lower() in DECLARATIVE_EXT | EXECUTABLE_EXT | NODE_EXTRA_EXT:
                    if Path(rel).name.endswith(".lock"):
                        continue
                    out.append(rel)
    # A symlinked tree (`.cursor/skills` -> `.agents/skills`) yields the same
    # file under two paths. Keep one target so node_id stays unique.
    unique: list[str] = []
    real_seen: set[str] = set()
    for rel in sorted(set(out)):
        real = str((root / rel).resolve())
        if real in real_seen:
            continue
        real_seen.add(real)
        unique.append(rel)
    return unique


def cmd_scan(args, root: Path, data: Path) -> int:
    index = build_index(root)
    _mcp_rel, mcp_servers = load_mcp_servers(root)
    mcp_names = sorted(mcp_servers)
    cache_path = data / "cache.map"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    written = skipped = 0
    seen: dict[str, str] = {}
    targets = targets_for(root, args.paths, args.include_mirrors, args.include_dsh)
    target_set = set(targets)
    # A symlinked tree can keep an old cache entry for the alias path. Drop it
    # before the loops so a forced scan cannot rewrite the node from the alias.
    target_real = {str((root / rel).resolve()): rel for rel in targets}
    for rel in list(cache):
        real = str((root / rel).resolve())
        if real in target_real and target_real[real] != rel:
            del cache[rel]
    for rel in targets:
        path = root / rel
        if Path(rel).name.startswith(".") or is_secret_name(rel):
            warn("skip secret or hidden name: " + rel)
            continue
        raw_bytes, text, _bom = read_source(path)
        if looks_secret(text):
            warn("skip secret value: " + rel)
            continue
        node_id = node_id_of(rel)
        if node_id in seen and seen[node_id] != rel:
            raise MirrorError("node_id collision: %s used by %s and %s" % (node_id, seen[node_id], rel), 1)
        seen[node_id] = rel
        digest = sha256_of(raw_bytes)
        old = cache.get(rel, {})
        exists = node_path(data, node_id).is_file()
        if (
            not args.force
            and exists
            and old.get("node_id") == node_id
            and old.get("sha256") == digest
            and old.get("parser_version") == PARSER_VERSION
            and old.get("schema_version") == SCHEMA_VERSION
        ):
            skipped += 1
            continue
        previous = load_node(data, node_id) if exists else None
        node = build_node(rel, root, index, previous, mcp_names)
        save_node(data, node)
        cache[rel] = {
            "sha256": digest,
            "node_id": node_id,
            "parser_version": PARSER_VERSION,
            "schema_version": SCHEMA_VERSION,
            "node_file": str(node_path(data, node_id).relative_to(data)),
        }
        written += 1

    for rel, entry in sorted(cache.items()):
        # Harness files outside the current target set (a canon-only scan with
        # mirrors and .dsh present) still refresh when their bytes changed, so
        # the index never points at an older version of a harness file.
        if rel in target_set:
            continue
        path = root / rel
        if not path.is_file():
            continue
        raw_bytes, text, _bom = read_source(path)
        if looks_secret(text):
            continue
        node_id = node_id_of(rel)
        exists = node_path(data, node_id).is_file()
        if (
            not args.force
            and exists
            and entry.get("node_id") == node_id
            and entry.get("sha256") == sha256_of(raw_bytes)
            and entry.get("parser_version") == PARSER_VERSION
            and entry.get("schema_version") == SCHEMA_VERSION
        ):
            continue
        previous = load_node(data, node_id) if exists else None
        save_node(data, build_node(rel, root, index, previous, mcp_names))
        cache[rel] = {
            "sha256": sha256_of(raw_bytes),
            "node_id": node_id,
            "parser_version": PARSER_VERSION,
            "schema_version": SCHEMA_VERSION,
            "node_file": str(node_path(data, node_id).relative_to(data)),
        }
        written += 1

    if not args.paths:
        # Scope is fixed by INDEX_PREFIXES. Entries outside it (previously
        # indexed documentation, tasks, product code) are dropped on a full scan.
        for rel in [key for key in cache if not key.startswith(INDEX_PREFIXES)]:
            del cache[rel]
    for rel in [key for key in cache if not (root / key).is_file()]:
        del cache[rel]

    # Symlinked trees produce two paths for one file. Keep the real skills
    # path and drop the alias, otherwise the cache counts one node twice.
    def cache_rank(rel: str) -> int:
        if rel.startswith(".agents/skills/"):
            return 0
        if rel.startswith(".cursor/"):
            return 1
        return 2

    by_real: dict[str, str] = {}
    for rel in sorted(cache, key=lambda item: (cache_rank(item), item)):
        real = str((root / rel).resolve())
        if real in by_real:
            del cache[rel]
            continue
        by_real[real] = rel

    inherited = 0
    for rel, entry in list(cache.items()):
        mirror_file = node_path(data, entry["node_id"])
        if not mirror_file.is_file():
            continue
        mirror = json.loads(mirror_file.read_text(encoding="utf-8"))
        target = mirror["meta"].get("projection_of")
        if target and not node_path(data, target).is_file():
            mirror["meta"]["projection_of"] = None
            write_json(mirror_file, mirror)
            continue
        if not target:
            continue
        canon = load_node(data, target)
        if lf_sha256_of(root / canon["meta"]["source_file_path"]) != lf_sha256_of(root / mirror["meta"]["source_file_path"]):
            continue
        if mirror.get("analysis", {}).get("status") == "filled":
            continue
        for field in ("description",):
            mirror["meta"][field] = canon["meta"].get(field, "")
        for field in ("lifecycle", "sources_of_truth", "global_relations", "analysis"):
            if field in canon:
                mirror[field] = canon[field]
        if block_key(canon) == block_key(mirror):
            for left, right in zip(mirror[block_key(mirror)], canon[block_key(canon)]):
                left["relations"] = right.get("relations", [])
        write_json(mirror_file, mirror)
        inherited += 1

    loaded: dict[str, tuple[Path, dict]] = {}
    for entry in cache.values():
        node_file = node_path(data, entry["node_id"])
        if node_file.is_file():
            loaded[entry["node_id"]] = (node_file, json.loads(node_file.read_text(encoding="utf-8")))
    known = set(loaded)
    source_of = {nid: pair[1]["meta"]["source_file_path"] for nid, pair in loaded.items()}
    downgraded = 0
    for node_id, (node_file, node) in loaded.items():
        changed = False
        target = node["meta"].get("projection_of")
        if target:
            expected = canon_candidates_of(node["meta"]["source_file_path"])
            if source_of.get(target) not in expected:
                node["meta"]["projection_of"] = None
                changed = True
        for block in node[block_key(node)]:
            kept = []
            for rel in block.get("relations", []):
                if rel.get("origin") == "auto" and rel.get("target_node_id") == node_id:
                    changed = True
                    continue
                target_path = rel.get("target_path")
                if rel.get("target_type") != "mcp" and target_path and not target_path.startswith(INDEX_PREFIXES):
                    # Old scan scope could index documentation. Such links are
                    # removed so the harness graph stays independent of docs.
                    changed = True
                    continue
                if rel.get("target_type") == "mcp":
                    kept.append(rel)
                    continue
                resolution = rel.get("resolution")
                # The file decides, not the scanned subset: a canon-only scan
                # must not turn a link to an unscanned mirror into `missing`.
                file_exists = bool(target_path) and (root / target_path).is_file()
                if resolution == "unresolved" and (rel.get("target_node_id") or target_path):
                    # Legacy nodes kept a target on an unresolved relation.
                    if file_exists:
                        rel["resolution"] = "resolved"
                    elif target_path:
                        rel["resolution"] = "missing"
                        downgraded += 1
                    else:
                        rel["target_node_id"] = None
                    changed = True
                elif resolution == "resolved" and target_path and not file_exists:
                    # The target used to be indexed and its file is gone. Keeping
                    # path and id makes the loss visible instead of hiding it.
                    rel["resolution"] = "missing"
                    changed = True
                    downgraded += 1
                elif resolution == "missing" and file_exists:
                    rel["resolution"] = "resolved"
                    changed = True
                elif resolution == "missing" and not target_path:
                    rel["resolution"] = "unresolved"
                    changed = True
                kept.append(rel)
            if kept != block.get("relations", []):
                block["relations"] = kept
        if node.get("global_relations"):
            kept_global = [
                rel for rel in node["global_relations"]
                if rel.get("target_type") == "mcp"
                or not rel.get("target_path")
                or rel["target_path"].startswith(INDEX_PREFIXES)
            ]
            if kept_global != node["global_relations"]:
                node["global_relations"] = kept_global
                changed = True
        if changed:
            write_json(node_file, node)

    expected = {safe_name(entry["node_id"]) + ".json" for entry in cache.values()}
    removed = 0
    for path in (data / "nodes").glob("*.json"):
        if path.name not in expected:
            path.unlink()
            removed += 1
    write_json(cache_path, cache)
    print(json.dumps({
        "status": "ok", "written": written, "skipped": skipped,
        "inherited": inherited, "removed": removed, "downgraded": downgraded, "nodes": len(cache),
    }, ensure_ascii=False))
    return 0


def prompt_text(node: dict) -> str:
    meta = node["meta"]
    key = block_key(node)
    blocks = "\n".join(
        "- %s: %s" % (b["block_id"], b.get("header_text") or b.get("name_or_purpose") or b["block_id"])
        for b in node[key]
    )
    pending = sorted({
        r.get("target_name", "?")
        for block in node[key] for r in block.get("relations", [])
        if r.get("resolution") != "resolved"
    })
    return (
        "Analyze one harness file and return analysis JSON only.\n\n"
        "file: %s\nnode: %s\ntype: %s\n\nblocks:\n%s\n\n"
        "Rules:\n"
        "1. summary: one short Russian line up to 90 characters, what the file does. Facts only.\n"
        "2. details: two to four short Russian sentences up to 400 characters, what the file does, when it runs, what it regulates. Facts only, no product names.\n"
        "3. description: one or two sentences, no product names.\n"
        "4. lifecycle.trigger_condition: exact phrases or condition from the text.\n"
        "5. sources_of_truth: authoritative standards the file obeys, with path if present.\n"
        "6. relations: origin must be agent; anchor_text must be an exact substring of that block.\n"
        "7. relation_type from: %s\n"
        "8. Do not invent target_path. Unknown target means resolution unresolved and null path.\n"
        "9. Return only: {\"summary\":\"\",\"details\":\"\",\"description\":\"\",\"lifecycle\":{},\"sources_of_truth\":[],\"relations\":[],\"global_relations\":[]}\n"
        "10. Unresolved targets from the literal pass: %s\n"
        % (
            meta["source_file_path"], meta["node_id"], meta["type"], blocks,
            ", ".join(sorted(RELATION_TYPES)), ", ".join(pending) or "none",
        )
    )


def validate_analysis(node: dict, analysis: dict, known: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    key = block_key(node)
    by_id = {b["block_id"]: b for b in node[key]}
    allowed = {"description", "summary", "details", "lifecycle", "sources_of_truth", "relations", "global_relations"}
    extra = set(analysis) - allowed
    if extra:
        errors.append("unknown analysis keys: " + ", ".join(sorted(extra)))
    summary = analysis.get("summary", "")
    if summary and (not isinstance(summary, str) or len(summary) > 140):
        errors.append("summary must be a string up to 140 characters")
    details = analysis.get("details", "")
    if details and (not isinstance(details, str) or len(details) > 600):
        errors.append("details must be a string up to 600 characters")
    for item in analysis.get("relations", []):
        missing = AGENT_RELATION_REQUIRED - set(item)
        if missing:
            errors.append("relation missing fields: " + ", ".join(sorted(missing)))
            continue
        if item["relation_type"] not in RELATION_TYPES:
            errors.append("unknown relation_type: " + str(item["relation_type"]))
        if item["target_type"] not in TARGET_TYPES:
            errors.append("unknown target_type: " + str(item["target_type"]))
        if item["origin"] != "agent":
            errors.append("analysis relation origin must be agent: " + str(item["target_name"]))
        resolution = item.get("resolution")
        if resolution not in RESOLUTIONS:
            errors.append("unknown resolution: " + str(resolution))
        block = by_id.get(item["block_id"])
        if block is None:
            errors.append("unknown block_id: " + str(item["block_id"]))
            continue
        raw = block.get("raw_content") or block.get("raw_code") or ""
        if not item["anchor_text"] or item["anchor_text"] not in raw:
            errors.append("anchor not found in %s: %s" % (item["block_id"], str(item["anchor_text"])[:60]))
        if resolution != "resolved" or item["target_type"] == "mcp":
            continue
        target_id = item.get("target_node_id")
        if not target_id:
            errors.append("resolved relation without target_node_id: " + str(item["target_name"]))
        elif known is not None and target_id not in known:
            errors.append("resolved target is not an indexed node: " + str(target_id))
    return errors


def anchor_warnings(node: dict, analysis: dict) -> list[str]:
    """Same anchor used for several agent relations in one block is ambiguous."""
    warnings: list[str] = []
    key = block_key(node)
    by_id = {b["block_id"]: b for b in node[key]}
    for item in analysis.get("relations", []):
        block = by_id.get(item.get("block_id"))
        if block is None:
            continue
        same = [
            r for r in block.get("relations", [])
            if r.get("origin") == "agent" and r.get("anchor_text") == item.get("anchor_text")
        ]
        anchor = str(item.get("anchor_text") or "")[:60]
        if same and not any(w.endswith(anchor) for w in warnings):
            warnings.append("anchor used by several relations in %s: %s" % (block["block_id"], anchor))
    return warnings


def cmd_apply(args, root: Path, data: Path) -> int:
    node = load_node(data, args.node)
    payload = json.loads(Path(args.json).read_text(encoding="utf-8")) if args.json else json.load(sys.stdin)
    known = {entry["node_id"] for entry in json.loads((data / "cache.map").read_text(encoding="utf-8")).values()} \
        if (data / "cache.map").is_file() else None
    errors = validate_analysis(node, payload, known)
    if errors:
        print(json.dumps({"status": "failed", "errors": errors}, ensure_ascii=False, indent=2))
        return 1
    for message in anchor_warnings(node, payload):
        warn(message)
    key = block_key(node)
    by_id = {b["block_id"]: b for b in node[key]}
    if payload.get("description"):
        node["meta"]["description"] = payload["description"]
    for field in ("summary", "details"):
        if payload.get(field):
            node["analysis"][field] = payload[field]
    if payload.get("lifecycle"):
        node["lifecycle"].update(payload["lifecycle"])
    if payload.get("sources_of_truth"):
        node["sources_of_truth"] = payload["sources_of_truth"]
    for item in payload.get("relations", []):
        item.setdefault("target_path", None)
        item.setdefault("target_node_id", None)
        item.setdefault("execution_moment", "")
        block = by_id[item["block_id"]]
        pair = (item.get("target_node_id") or item["target_name"], item["relation_type"])
        existing = {(r.get("target_node_id") or r.get("target_name"), r.get("relation_type")) for r in block["relations"]}
        if pair in existing:
            block["relations"] = [r for r in block["relations"] if (r.get("target_node_id") or r.get("target_name"), r.get("relation_type")) != pair]
        block["relations"].append(item)
    for item in payload.get("global_relations", []):
        item.setdefault("target_path", None)
        item.setdefault("target_node_id", None)
        item.setdefault("origin", "agent")
        item.setdefault("resolution", "unresolved")
        node["global_relations"] = [
            r for r in node["global_relations"]
            if (r.get("target_node_id") or r.get("target_name"), r.get("relation_type"))
            != (item.get("target_node_id") or item.get("target_name"), item.get("relation_type"))
        ]
        node["global_relations"].append(item)
    node["analysis"] = {
        "status": "filled",
        "model": args.model or "agent",
        "summary": node["analysis"].get("summary", ""),
        "details": node["analysis"].get("details", ""),
    }
    save_node(data, node)
    print(json.dumps({"status": "ok", "node": node["meta"]["node_id"]}, ensure_ascii=False))
    return 0


def cmd_prompt(args, root: Path, data: Path) -> int:
    node = load_node(data, args.node)
    sys.stdout.write(prompt_text(node))
    return 0


def cmd_get(args, root: Path, data: Path) -> int:
    node = load_node(data, args.node)
    edges = {"incoming": [], "outgoing": []}
    for edge in load_graph_edges(data):
        if edge.get("target") == args.node:
            edges["incoming"].append(edge)
        if edge.get("source") == args.node:
            edges["outgoing"].append(edge)
    payload = {"node": node_summary(node) if getattr(args, "slim", False) else node, "edges": edges}
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def node_rank(node: dict) -> tuple:
    path = node["meta"]["source_file_path"]
    if path.endswith("/SKILL.md"):
        return (0, path)
    if path.endswith("/README.md"):
        return (1, path)
    return (2, path)


def canonical_nodes(data: Path) -> list[dict]:
    nodes = []
    for path in sorted((data / "nodes").glob("*.json")):
        node = json.loads(path.read_text(encoding="utf-8"))
        if node["meta"]["canonical"]:
            nodes.append(node)
    return nodes


def skill_nodes(data: Path, name: str) -> list[dict]:
    markers = ("/skills/%s/" % name, "/children/%s/" % name)
    seen: set[str] = set()
    nodes: list[dict] = []
    for node in canonical_nodes(data):
        path = "/" + node["meta"]["source_file_path"]
        if not any(marker in path for marker in markers):
            continue
        node_id = node["meta"]["node_id"]
        if node_id in seen:
            continue
        seen.add(node_id)
        nodes.append(node)
    return nodes


def relations_report(nodes: list[dict]) -> dict:
    rows = []
    for node in nodes:
        key = block_key(node)
        for block in node[key]:
            for rel in block.get("relations", []):
                if rel.get("resolution") in ("ambiguous", "unresolved", "missing"):
                    rows.append({
                        "node": node["meta"]["node_id"],
                        "block_id": block["block_id"],
                        "target": rel.get("target_name"),
                        "type": rel.get("relation_type"),
                        "resolution": rel.get("resolution"),
                        "anchor": (rel.get("anchor_text") or "")[:120],
                    })
    return {"count": len(rows), "items": rows}


def cmd_bundle(args, root: Path, data: Path) -> int:
    nodes = skill_nodes(data, args.skill)
    if not nodes:
        print(json.dumps({"status": "failed", "error": "skill not found: " + args.skill}, ensure_ascii=False))
        return 1
    ids = {n["meta"]["node_id"] for n in nodes}
    labels, summaries = edge_labels(data)
    edges = load_graph_edges(data)
    outgoing, incoming = {}, {}
    for edge in edges:
        if edge["type"] == "mirrors":
            continue
        if edge["source"] in ids and edge["target"] not in ids:
            key = (edge["target"], edge["type"])
            outgoing[key] = compact_edge(edge, "target", labels, summaries, 3)
        if edge["target"] in ids and edge["source"] not in ids:
            key = (edge["source"], edge["type"])
            incoming[key] = compact_edge(edge, "source", labels, summaries, 3)
    def is_skill_main(node: dict) -> bool:
        path = node["meta"]["source_file_path"]
        return path.endswith("/skills/%s/SKILL.md" % args.skill) or path.endswith("/children/%s/SKILL.md" % args.skill)

    main = next((n for n in nodes if is_skill_main(n)),
                next((n for n in nodes if n["meta"]["source_file_path"].endswith("/SKILL.md")), nodes[0]))
    files = [node_summary(n) for n in sorted(nodes, key=node_rank)]
    sources = []
    for node in nodes:
        sources.extend(node.get("sources_of_truth") or [])
    payload = {
        "skill": args.skill,
        "dir": ".agents/skills/" + args.skill,
        "main": main["meta"]["node_id"],
        "files": files,
        "triggers": [{"node": n["meta"]["node_id"], "text": (n.get("lifecycle") or {}).get("trigger_condition", "")}
                     for n in nodes if (n.get("lifecycle") or {}).get("trigger_condition")],
        "sources_of_truth": sources,
        "edges": {
            "outgoing": [outgoing[k] for k in sorted(outgoing)],
            "incoming": [incoming[k] for k in sorted(incoming)],
        },
        "unresolved": relations_report(nodes),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0




AUDIT_EDGE_TYPES = ("delegates_to",)


def derived_edges(nodes: list[dict], data: Path) -> list[dict]:
    edges = load_graph_edges(data)
    if edges:
        return [e for e in edges if e.get("type") != "mirrors"]
    rows: dict[tuple, dict] = {}
    for node in nodes:
        source = node["meta"]["node_id"]
        for block in node[block_key(node)]:
            for rel in block.get("relations", []):
                target = rel.get("target_node_id")
                if rel.get("resolution") != "resolved" or not target:
                    continue
                key = (source, target, rel.get("relation_type"))
                cur = rows.get(key)
                if cur is None:
                    rows[key] = {"source": source, "target": target, "type": rel.get("relation_type"),
                                 "blocks": 1, "anchors": [rel.get("anchor_text") or ""]}
                else:
                    cur["blocks"] += 1
    return list(rows.values())


def node_degrees(edges: list[dict]) -> dict[str, int]:
    degree: dict[str, int] = {}
    for edge in edges:
        degree[edge["source"]] = degree.get(edge["source"], 0) + 1
        degree[edge["target"]] = degree.get(edge["target"], 0) + 1
    return degree


def find_cycles(edges: list[dict]) -> list[list[str]]:
    adjacency: dict[str, set] = {}
    for edge in edges:
        if edge.get("type") in AUDIT_EDGE_TYPES:
            adjacency.setdefault(edge["source"], set()).add(edge["target"])
    color: dict[str, int] = {}
    stack: list[str] = []
    found: list[list[str]] = []

    def walk(node: str) -> None:
        color[node] = 1
        stack.append(node)
        for nxt in sorted(adjacency.get(node, ())):
            state = color.get(nxt, 0)
            if state == 1:
                start = stack.index(nxt)
                cycle = stack[start:] + [nxt]
                if len(cycle) == 2 and cycle[0] == cycle[1]:
                    continue
                if cycle not in found and cycle[::-1] not in found:
                    found.append(cycle)
            elif state == 0:
                walk(nxt)
        stack.pop()
        color[node] = 2

    for node in sorted(adjacency):
        if color.get(node, 0) == 0:
            walk(node)
    return found


LINT_SEVERITY = {
    "bad_relation": "error",
    "cycle": "info",
    "self_relation": "warn",
    "missing_main": "error",
    "no_summary": "warn",
    "empty_details": "warn",
    "duplicate_summary": "warn",
    "no_trigger": "info",
    "no_sources": "info",
    "isolated": "info",
    "unreferenced_script": "info",
}


def lint_canon(data: Path) -> dict:
    nodes = canonical_nodes(data)
    ids = {n["meta"]["node_id"] for n in nodes}
    edges = [e for e in derived_edges(nodes, data) if e["source"] in ids and e["target"] in ids]
    degree = node_degrees(edges)
    issues: list[dict] = []

    def add(kind: str, node: str, detail: str) -> None:
        issues.append({"kind": kind, "node": node, "detail": detail,
                       "severity": LINT_SEVERITY.get(kind, "info")})

    for edge in edges:
        if edge["source"] == edge["target"] and edge["type"] in AUDIT_EDGE_TYPES:
            add("self_relation", edge["source"], "связь указывает на себя: %s" % edge["type"])
    for cycle in find_cycles(edges):
        add("cycle", cycle[0], "цикл: " + " -> ".join(cycle))

    summaries: dict[str, list[str]] = {}
    skill_groups: dict[str, list[str]] = {}
    for node in nodes:
        meta = node["meta"]
        node_id = meta["node_id"]
        info = node_summary(node)
        kind = meta["type"]
        if kind in ("skill", "rule"):
            if not info["summary"]:
                add("no_summary", node_id, "нет summary и описания")
            if not (info["details"] or "").strip() or len(info["details"]) < 20:
                add("empty_details", node_id, "details пустой или короче 20 символов")
            if not (info["lifecycle"] or {}).get("trigger_condition"):
                add("no_trigger", node_id, "не задан trigger_condition")
            if not info["sources_of_truth"]:
                add("no_sources", node_id, "нет sources_of_truth")
        if info["summary"]:
            key = " ".join(info["summary"].lower().split())
            summaries.setdefault(key, []).append(node_id)
        if not degree.get(node_id):
            add("isolated", node_id, "нет входящих и исходящих связей")
        if kind == "script" and not any(e["target"] == node_id for e in edges):
            add("unreferenced_script", node_id, "скрипт нигде не упомянут")
        if meta["source_file_path"].startswith(".agents/skills/"):
            parts = meta["source_file_path"].split("/")
            skill_groups.setdefault(parts[2], []).append(meta["source_file_path"])
        if kind not in ("skill", "rule"):
            continue
        key = block_key(node)
        for block in node[key]:
            for rel in block.get("relations", []):
                resolution = rel.get("resolution")
                if resolution in ("ambiguous", "unresolved", "missing"):
                    add("bad_relation", node_id,
                        "%s %s: %s" % (resolution, rel.get("target_name"), (rel.get("anchor_text") or "")[:80]))

    for key, ids in summaries.items():
        if len(ids) > 1:
            for node_id in ids:
                add("duplicate_summary", node_id, "такая же подпись у: " + ", ".join(x for x in ids if x != node_id))

    for skill, files in sorted(skill_groups.items()):
        if not any(path.endswith("/SKILL.md") for path in files):
            add("missing_main", "skill:" + skill, "у скила нет SKILL.md")

    by_kind: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for issue in issues:
        by_kind[issue["kind"]] = by_kind.get(issue["kind"], 0) + 1
        by_severity[issue["severity"]] = by_severity.get(issue["severity"], 0) + 1
    return {"issues": issues, "by_kind": dict(sorted(by_kind.items())),
            "by_severity": dict(sorted(by_severity.items())), "nodes": len(nodes), "edges": len(edges)}


def section_digest(node: dict, limit: int = 150) -> list[dict]:
    rows = []
    for block in sorted(node[block_key(node)], key=lambda b: b.get("order", 0)):
        header = (block.get("header_text") or "").strip()
        if not header:
            continue
        raw = block.get("raw_content") or block.get("raw_code") or ""
        body = []
        for line in raw.splitlines()[1:]:
            text = line.strip().lstrip("-*|").strip()
            if text and not text.startswith("|") and not text.startswith("#"):
                body.append(text)
        rows.append({"header": header.lstrip("#").strip(), "first_line": (body[0][:limit] if body else "")})
    return rows


def cmd_lint(args, root: Path, data: Path) -> int:
    report = lint_canon(data)
    actionable = [i for i in report["issues"] if i.get("severity") in ("warn", "error")]
    report["status"] = "review" if actionable else "ok"
    report["pending_analysis"] = sum(1 for i in report["issues"] if i.get("severity") == "info")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


REVIEW_HINTS = {
    "skill": [
        "Сверь триггеры в описании с телом скила: скил не должен срабатывать на чужие запросы.",
        "Проверь, что каждый скрипт и файл references упомянут в тексте и делает то, что обещано.",
        "Проверь, что ссылки на правила и другие скилы обоснованы, а не скопированы.",
    ],
    "rule": [
        "Проверь, что правило не дублирует по смыслу другое правило и не противоречит ему.",
        "Сверь охват правила с его триггером: always для постоянных требований, иначе явные условия.",
        "Проверь, что источники правды и связи ведут на существующие и уместные файлы.",
    ],
}


def review_payload(nodes: list[dict], data: Path, lint: dict | None = None) -> dict:
    ids = {n["meta"]["node_id"] for n in nodes}
    labels, summaries = edge_labels(data)
    edges = derived_edges(nodes, data)
    outgoing, incoming = {}, {}
    for edge in edges:
        if edge["source"] in ids and edge["target"] not in ids:
            outgoing[(edge["target"], edge["type"])] = compact_edge(edge, "target", labels, summaries, 3)
        if edge["target"] in ids and edge["source"] not in ids:
            incoming[(edge["source"], edge["type"])] = compact_edge(edge, "source", labels, summaries, 3)
    files = []
    for node in sorted(nodes, key=node_rank):
        info = node_summary(node)
        info["outline"] = section_digest(node)
        files.append(info)
    types = {n["meta"]["type"] for n in nodes}
    hints = []
    for kind in sorted(types):
        hints.extend(REVIEW_HINTS.get(kind, []))
    issues = []
    if lint:
        issues = [i for i in lint["issues"] if i["node"] in ids]
    return {
        "target": {"skills": sorted({n["meta"]["source_file_path"].split("/")[2] for n in nodes
                                     if n["meta"]["source_file_path"].startswith(".agents/skills/")}),
                   "nodes": sorted(ids)},
        "files": files,
        "edges": {"outgoing": [outgoing[k] for k in sorted(outgoing)],
                  "incoming": [incoming[k] for k in sorted(incoming)]},
        "issues": issues,
        "questions": hints,
    }


def cmd_review(args, root: Path, data: Path) -> int:
    lint = lint_canon(data)
    if getattr(args, "all", False):
        rows = []
        for node in canonical_nodes(data):
            if node["meta"]["type"] not in ("skill", "rule"):
                continue
            info = node_summary(node)
            rows.append({
                "node": info["id"], "type": info["type"], "path": info["path"],
                "summary": info["summary"], "analysis": info["analysis"],
                "trigger": bool((info["lifecycle"] or {}).get("trigger_condition")),
                "sources": len(info["sources_of_truth"]),
                "issues": [i["kind"] for i in lint["issues"] if i["node"] == info["id"]],
            })
        print(json.dumps({"status": "ok", "items": rows, "by_kind": lint["by_kind"]},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if bool(getattr(args, "node", None)) == bool(getattr(args, "skill", None)):
        print(json.dumps({"status": "failed", "error": "pass exactly one of --node, --skill or --all"}, ensure_ascii=False))
        return 2
    if getattr(args, "skill", None):
        nodes = skill_nodes(data, args.skill)
    else:
        try:
            nodes = [load_node(data, args.node)]
        except MirrorError as exc:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
            return 1
    if not nodes:
        print(json.dumps({"status": "failed", "error": "nothing found"}, ensure_ascii=False))
        return 1
    payload = review_payload(nodes, data, lint)
    payload["status"] = "ok"
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0

def cmd_audit(args, root: Path, data: Path) -> int:
    node_arg = getattr(args, "node", None)
    skill_arg = getattr(args, "skill", None)
    if bool(node_arg) == bool(skill_arg):
        print(json.dumps({"status": "failed", "error": "pass exactly one of --node or --skill"}, ensure_ascii=False))
        return 2
    if skill_arg:
        nodes = skill_nodes(data, skill_arg)
    else:
        try:
            nodes = [load_node(data, node_arg)]
        except MirrorError as exc:
            print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
            return 1
    if not nodes:
        print(json.dumps({"status": "failed", "error": "nothing found"}, ensure_ascii=False))
        return 1
    ids = {n["meta"]["node_id"] for n in nodes}
    labels, summaries = edge_labels(data)
    edges = load_graph_edges(data)
    outgoing, incoming = {}, {}
    for edge in edges:
        if edge["type"] == "mirrors":
            continue
        if edge.get("source") in ids and edge.get("target") not in ids:
            outgoing[(edge["target"], edge["type"])] = compact_edge(edge, "target", labels, summaries, 1)
        if edge.get("target") in ids and edge.get("source") not in ids:
            incoming[(edge["source"], edge["type"])] = compact_edge(edge, "source", labels, summaries, 1)
    files = [node_summary(n) for n in sorted(nodes, key=node_rank)]
    warnings, notes = [], []
    for item in files:
        if not item["summary"]:
            warnings.append(item["id"] + ": нет summary")
        if item["analysis"] == "pending":
            warnings.append(item["id"] + ": смысловой анализ не заполнен")
        if not item["lifecycle"].get("trigger_condition"):
            notes.append(item["id"] + ": не задан триггер")
        if not item["sources_of_truth"]:
            notes.append(item["id"] + ": нет источников правды")
    if not outgoing:
        notes.append("нет исходящих связей")
    if not incoming:
        notes.append("нет входящих связей")
    unresolved = relations_report(nodes)
    if unresolved["count"]:
        warnings.append("неразрешённых связей: %d" % unresolved["count"])
    payload = {
        "target": {"node": node_arg, "skill": skill_arg},
        "files": files,
        "triggers": [{"node": n["meta"]["node_id"], "text": (n.get("lifecycle") or {}).get("trigger_condition", "")}
                     for n in nodes if (n.get("lifecycle") or {}).get("trigger_condition")],
        "sources_of_truth": [s for n in nodes for s in (n.get("sources_of_truth") or [])],
        "edges": {
            "outgoing": [outgoing[k] for k in sorted(outgoing)],
            "incoming": [incoming[k] for k in sorted(incoming)],
        },
        "unresolved": unresolved,
        "coverage": {
            "files": len(files),
            "filled": sum(1 for f in files if f["analysis"] == "filled"),
            "pending": sum(1 for f in files if f["analysis"] == "pending"),
            "with_summary": sum(1 for f in files if f["summary"]),
            "with_details": sum(1 for f in files if f["details"]),
        },
        "warnings": warnings,
        "notes": notes,
        "verdict": "ok" if not warnings else "review",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def cmd_set(args, root: Path, data: Path) -> int:
    text = Path(args.content).read_text(encoding="utf-8") if args.content else sys.stdin.read()
    whole_file = bool(getattr(args, "file", False))
    if not whole_file and not getattr(args, "block", None):
        print(json.dumps({"status": "failed", "error": "pass --block or --file"}, ensure_ascii=False))
        return 2
    try:
        if whole_file:
            result = set_file(root, data, args.node, text)
        else:
            result = set_block(root, data, args.node, args.block, text)
    except MirrorError as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    try:
        result["stats"] = build_graph(root, data)["stats"]
    except MirrorError as exc:
        warn("graph not rebuilt: %s" % exc)
        result["stats"] = None
    print(json.dumps(result, ensure_ascii=False))
    return 0


def collapse_edges(edges: list[dict]) -> list[dict]:
    """One edge per source, target and type.

    The same pair can be mentioned in several blocks of one file. For the graph,
    the panel and the audit one line is enough, with a block counter and a few
    anchors as evidence.
    """
    out: dict[tuple, dict] = {}
    for edge in edges:
        key = (edge["source"], edge["target"], edge["type"])
        anchor = edge.get("anchor") or ""
        current = out.get(key)
        if current is None:
            out[key] = {
                "source": edge["source"],
                "target": edge["target"],
                "type": edge["type"],
                "origin": edge.get("origin", "auto"),
                "block_id": edge.get("block_id"),
                "anchor": anchor,
                "blocks": 1,
                "anchors": [anchor] if anchor else [],
            }
            continue
        current["blocks"] += 1
        if edge.get("origin") == "agent":
            current["origin"] = "agent"
        if anchor and anchor not in current["anchors"] and len(current["anchors"]) < 5:
            current["anchors"].append(anchor)
    return [out[key] for key in sorted(out)]


def node_summary(node: dict) -> dict:
    meta = node["meta"]
    analysis = node.get("analysis") or {}
    description = meta.get("description", "")
    return {
        "id": meta["node_id"],
        "type": meta["type"],
        "path": meta["source_file_path"],
        "environment": meta["environment"],
        "canonical": meta["canonical"],
        "analysis": analysis.get("status", "pending"),
        "summary": analysis.get("summary") or first_sentence(description) or heading_of(node),
        "details": analysis.get("details") or description,
        "description": description,
        "blocks": node["reconstruction_meta"]["total_blocks"],
        "bytes": len(compile_node(node).encode("utf-8")),
        "lifecycle": node.get("lifecycle") or {},
        "sources_of_truth": node.get("sources_of_truth") or [],
    }


def load_graph_edges(data: Path) -> list[dict]:
    path = data / "graph.json"
    if not path.is_file():
        return []
    return json.loads(path.read_text(encoding="utf-8")).get("edges", [])


def compact_edge(edge: dict, side: str, labels: dict, summaries: dict, anchor_limit: int = 3) -> dict:
    other = edge[side]
    return {
        "id": other,
        "type": edge["type"],
        "label": labels.get(other, other),
        "summary": summaries.get(other, ""),
        "blocks": edge.get("blocks", 1),
        "anchors": [a[:100] for a in edge.get("anchors", [])[:anchor_limit]],
    }


def edge_labels(data: Path) -> tuple[dict, dict]:
    labels, summaries = {}, {}
    path = data / "graph.json"
    if not path.is_file():
        return labels, summaries
    for node in json.loads(path.read_text(encoding="utf-8")).get("nodes", []):
        labels[node["id"]] = node.get("label") or node["id"]
        summaries[node["id"]] = node.get("summary") or ""
    return labels, summaries


def heading_of(node: dict) -> str:
    """First section heading, used as a human readable title in the panel."""
    for block in node[block_key(node)]:
        header = (block.get("header_text") or "").strip().lstrip("#").strip()
        if header:
            return header[:90]
    return ""


def build_graph(root: Path, data: Path) -> dict:
    nodes_dir = data / "nodes"
    if not nodes_dir.is_dir():
        raise MirrorError("no nodes: run scan first", 1)
    nodes: list[dict] = []
    hashes: dict[str, str | None] = {}
    for path in sorted(nodes_dir.glob("*.json")):
        node = json.loads(path.read_text(encoding="utf-8"))
        meta = node["meta"]
        hashes[meta["node_id"]] = lf_sha256_of(root / meta["source_file_path"])
        nodes.append({
            "id": meta["node_id"],
            "logical_id": meta.get("projection_of") or meta["node_id"],
            "label": Path(meta["source_file_path"]).name if meta["type"] == "script" else meta["name"],
            "type": meta["type"],
            "environment": meta["environment"],
            "canonical": meta["canonical"],
            "projection_of": meta.get("projection_of"),
            "transferable": meta.get("transferable", True),
            "path": meta["source_file_path"],
            "dir": str(Path(meta["source_file_path"]).parent),
            "file": Path(meta["source_file_path"]).name,
            "json": "nodes/" + path.name,
            "description": meta.get("description", ""),
            "heading": heading_of(node),
            "summary": (node.get("analysis") or {}).get("summary") or first_sentence(meta.get("description", "")) or heading_of(node),
            "details": (node.get("analysis") or {}).get("details") or meta.get("description", ""),
            "analysis": node.get("analysis", {}).get("status", "pending"),
        })
    edges: list[dict] = []
    relations: dict[str, int] = {}
    for path in sorted(nodes_dir.glob("*.json")):
        node = json.loads(path.read_text(encoding="utf-8"))
        meta = node["meta"]
        for block in node[block_key(node)]:
            for rel in block.get("relations", []):
                relations[rel.get("relation_type", "?")] = relations.get(rel.get("relation_type", "?"), 0) + 1
                if rel.get("resolution") != "resolved" or not rel.get("target_node_id"):
                    continue
                edges.append({
                    "source": meta["node_id"], "target": rel["target_node_id"],
                    "type": rel["relation_type"], "origin": rel.get("origin", "auto"),
                    "block_id": block["block_id"], "anchor": rel.get("anchor_text", ""),
                })
        for rel in node.get("global_relations", []):
            if rel.get("resolution") == "resolved" and rel.get("target_node_id"):
                edges.append({
                    "source": meta["node_id"], "target": rel["target_node_id"],
                    "type": rel["relation_type"], "origin": rel.get("origin", "auto"),
                    "block_id": None, "anchor": rel.get("anchor_text", ""),
                })
        target = meta.get("projection_of")
        if target:
            state = "equal" if hashes.get(target) is not None and hashes.get(target) == hashes.get(meta["node_id"]) else "drift"
            edges.append({
                "source": meta["node_id"], "target": target, "type": "mirrors",
                "origin": "auto", "block_id": None, "anchor": "", "state": state,
            })
    for entry in nodes:
        if entry["projection_of"]:
            entry["state"] = "equal" if hashes.get(entry["projection_of"]) == hashes.get(entry["id"]) and hashes.get(entry["id"]) else "drift"
    mcp_rel, mcp_servers = load_mcp_servers(root)
    known = {n["id"] for n in nodes}
    unlinked = 0
    for name, info in sorted(mcp_servers.items()):
        node_id = "mcp:" + name
        if node_id in known:
            continue
        nodes.append({
            "id": node_id,
            "logical_id": node_id,
            "label": name,
            "type": "mcp",
            "environment": "cursor",
            "canonical": True,
            "projection_of": None,
            "transferable": True,
            "path": mcp_rel or ".cursor/mcp.json",
            "dir": ".cursor",
            "file": "mcp.json",
            "json": None,
            "description": (info["transport"] + " " + info["command"]).strip(),
            "heading": "",
            "summary": "",
            "details": "",
            "analysis": "n/a",
            "synthetic": True,
            "mcp": info,
        })
        known.add(node_id)
    visibility = compute_visibility(root)["matrix"]
    for entry in nodes:
        if entry["type"] != "rule":
            continue
        path = entry["path"]
        prefix = ".cursor/rules/"
        if path.startswith(prefix) and path.endswith(".mdc"):
            entry["injection"] = visibility.get(path[len(prefix):-4], {})
    linked = []
    for edge in edges:
        if edge["source"] in known and edge["target"] in known:
            linked.append(edge)
        else:
            unlinked += 1
    ordered = collapse_edges(linked)
    canon = [n for n in nodes if n["canonical"]]
    graph = {
        "schema": "harness-graph/2.3",
        "stats": {
            "nodes": len(nodes),
            "canonical": len(canon),
            "mirrors": len(nodes) - len(canon),
            "logical": len({n["logical_id"] for n in nodes}),
            "edges": len(ordered),
            "relation_blocks": len(linked),
            "drift": sum(1 for n in nodes if n.get("state") == "drift"),
            "pending_analysis": sum(1 for n in nodes if n["analysis"] == "pending"),
            "mcp": sum(1 for n in nodes if n["type"] == "mcp"),
            "unlinked_relations": unlinked,
        },
        "relation_types": dict(sorted(relations.items())),
        "nodes": nodes,
        "edges": ordered,
    }
    write_json(data / "graph.json", graph)
    viewer = Path(__file__).resolve().parent.parent / "assets" / "viewer.html"
    if viewer.is_file():
        atomic_write(data / "index.html", viewer.read_bytes())
    return graph


def cmd_build(args, root: Path, data: Path) -> int:
    graph = build_graph(root, data)
    print(json.dumps({
        "status": "ok", "graph": str((data / "graph.json").relative_to(root)),
        "nodes": graph["stats"]["nodes"], "logical": graph["stats"]["logical"],
        "edges": graph["stats"]["edges"], "drift": graph["stats"]["drift"],
    }, ensure_ascii=False))
    return 0


def cmd_rebuild(args, root: Path, data: Path) -> int:
    cache_path = data / "cache.map"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    prefixes = tuple(prefix + "/" for prefix in MIRROR_ROOTS)
    scan_args = argparse.Namespace(
        paths=[],
        include_mirrors=any(rel.startswith(prefixes) for rel in cache),
        include_dsh=any(rel.startswith(DSH_ROOT + "/") for rel in cache),
        force=False,
    )
    code = cmd_scan(scan_args, root, data)
    if code != 0:
        return code
    return cmd_build(args, root, data)


def set_block(root: Path, data: Path, node_id: str, block_id: str, text: str) -> dict:
    node = load_node(data, node_id)
    if not node["meta"]["canonical"]:
        raise MirrorError("mirror is generated: edit %s and run the sync" % (node["meta"].get("projection_of") or "canon"), 1)
    key = block_key(node)
    field = "raw_content" if key == "content_blocks" else "raw_code"
    target = next((b for b in node[key] if b["block_id"] == block_id), None)
    if target is None:
        raise MirrorError("unknown block: " + block_id, 1)
    source = root / node["meta"]["source_file_path"]
    original = source.read_bytes()
    snapshot = json.loads(json.dumps(node))
    target[field] = text
    rebuilt = compile_node(node)
    bom = "\ufeff" if node["reconstruction_meta"].get("bom") else ""
    expected = (bom + rebuilt).encode("utf-8")
    if expected.decode("utf-8-sig") != rebuilt:
        raise MirrorError("recompile failed: block text does not decode back", 1)
    if source.read_bytes() != original:
        raise MirrorError("source changed while editing, retry: " + node["meta"]["source_file_path"], 1)
    try:
        atomic_write(source, expected)
    except OSError as exc:  # noqa: BLE001
        raise MirrorError("cannot write source: %s" % exc, 2) from exc
    if source.read_bytes() != expected:
        atomic_write(source, original)
        raise MirrorError("round trip mismatch after write, source restored", 1)
    history = data / "nodes" / ".history"
    history.mkdir(parents=True, exist_ok=True)
    version = 1
    while (history / ("%s.v%d.json" % (safe_name(node_id), version))).exists():
        version += 1
    write_json(history / ("%s.v%d.json" % (safe_name(node_id), version)), snapshot)
    _mcp_rel, mcp_servers = load_mcp_servers(root)
    fresh = build_node(node["meta"]["source_file_path"], root, build_index(root), node, sorted(mcp_servers))
    save_node(data, fresh)
    cache_path = data / "cache.map"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    cache[node["meta"]["source_file_path"]] = {
        "sha256": sha256_of(source.read_bytes()),
        "node_id": node_id,
        "parser_version": PARSER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "node_file": "nodes/" + node_path(data, node_id).name,
    }
    write_json(cache_path, cache)
    return {"status": "ok", "node": node_id, "block": block_id, "backup": version}


def set_file(root: Path, data: Path, node_id: str, text: str) -> dict:
    """Replace the whole source file of a skill or rule.

    Only skill and rule files are editable from the panel: other harness files
    change through their generators or through the project sync.
    """
    node = load_node(data, node_id)
    meta = node["meta"]
    if not meta["canonical"]:
        raise MirrorError(
            "mirror is generated: edit %s and run the sync" % (meta.get("projection_of") or "canon"), 1
        )
    if meta["type"] not in EDITABLE_TYPES:
        raise MirrorError(
            "editable types are %s, got %s" % (", ".join(sorted(EDITABLE_TYPES)), meta["type"]), 1
        )
    source = root / meta["source_file_path"]
    original = source.read_bytes()
    bom = "\ufeff" if node["reconstruction_meta"].get("bom") else ""
    body = text.replace("\r\n", "\n")
    if node["reconstruction_meta"].get("line_ending") == "\r\n":
        body = body.replace("\n", "\r\n")
    expected = (bom + body).encode("utf-8")
    if source.read_bytes() != original:
        raise MirrorError("source changed while editing, retry: " + meta["source_file_path"], 1)
    snapshot = json.loads(json.dumps(node))
    try:
        atomic_write(source, expected)
    except OSError as exc:  # noqa: BLE001
        raise MirrorError("cannot write source: %s" % exc, 2) from exc
    if source.read_bytes() != expected:
        atomic_write(source, original)
        raise MirrorError("read back mismatch after write, source restored", 1)
    _mcp_rel, mcp_servers = load_mcp_servers(root)
    fresh = build_node(meta["source_file_path"], root, build_index(root), node, sorted(mcp_servers))
    if compile_node(fresh) != body:
        atomic_write(source, original)
        raise MirrorError("new text does not split into blocks losslessly, source restored", 1)
    history = data / "nodes" / ".history"
    history.mkdir(parents=True, exist_ok=True)
    version = 1
    while (history / ("%s.v%d.json" % (safe_name(node_id), version))).exists():
        version += 1
    write_json(history / ("%s.v%d.json" % (safe_name(node_id), version)), snapshot)
    save_node(data, fresh)
    cache_path = data / "cache.map"
    cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.is_file() else {}
    cache[meta["source_file_path"]] = {
        "sha256": sha256_of(source.read_bytes()),
        "node_id": node_id,
        "parser_version": PARSER_VERSION,
        "schema_version": SCHEMA_VERSION,
        "node_file": "nodes/" + node_path(data, node_id).name,
    }
    write_json(cache_path, cache)
    return {"status": "ok", "node": node_id, "file": meta["source_file_path"], "backup": version}


def serve(data: Path, root: Path, host: str, port: int) -> int:
    import http.server
    import socketserver
    import urllib.parse

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *a, **kw):
            super().__init__(*a, directory=str(data), **kw)

        def _loopback(self, value: str) -> bool:
            if not value:
                return True
            return urllib.parse.urlparse("//" + value).hostname in ("127.0.0.1", "localhost", "::1")

        def _origin_allowed(self) -> bool:
            """Only pages served from loopback may call the write API.

            A wildcard CORS header would let any open tab rewrite canonical
            harness files, so the header is echoed back only for loopback.
            """
            origin = self.headers.get("Origin") or ""
            if origin and not self._loopback(origin.split("://", 1)[-1]):
                return False
            return self._loopback(self.headers.get("Host") or "")

        def _cors(self) -> None:
            origin = self.headers.get("Origin")
            if origin and self._origin_allowed():
                self.send_header("Access-Control-Allow-Origin", origin)
                self.send_header("Vary", "Origin")

        def _json(self, payload: dict, code: int = 200) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self._cors()
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def end_headers(self):
            if not self.path.startswith("/api/"):
                self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_OPTIONS(self):
            if not self._origin_allowed():
                self._json({"status": "failed", "error": "origin not allowed"}, 403)
                return
            self.send_response(204)
            self._cors()
            self.send_header("Access-Control-Allow-Methods", "GET, PUT, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def _query(self) -> dict:
            parsed = urllib.parse.urlparse(self.path)
            return {k: v[0] for k, v in urllib.parse.parse_qs(parsed.query).items()}

        def do_GET(self):
            if self.path.startswith("/api/health"):
                graph = data / "graph.json"
                stats = json.loads(graph.read_text(encoding="utf-8"))["stats"] if graph.is_file() else {}
                self._json({"status": "ok", "writable": True, "stats": stats})
                return
            if self.path.startswith("/api/node"):
                node_id = self._query().get("id", "")
                try:
                    node = load_node(data, node_id)
                except MirrorError as exc:
                    self._json({"status": "failed", "error": str(exc)}, 404)
                    return
                self._json({"status": "ok", "node": node})
                return
            super().do_GET()

        def do_PUT(self):
            if not self.path.startswith("/api/node"):
                self._json({"status": "failed", "error": "unknown endpoint"}, 404)
                return
            if not self._origin_allowed():
                self._json({"status": "failed", "error": "origin not allowed"}, 403)
                return
            node_id = self._query().get("id", "")
            length = int(self.headers.get("Content-Length") or 0)
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError as exc:
                self._json({"status": "failed", "error": "bad json: %s" % exc}, 400)
                return
            try:
                with Lock(data):
                    if "raw_file" in payload:
                        result = set_file(root, data, node_id, str(payload.get("raw_file", "")))
                    else:
                        result = set_block(root, data, node_id, str(payload.get("block_id", "")), str(payload.get("raw_content", "")))
                    graph = build_graph(root, data)
            except MirrorError as exc:
                self._json({"status": "failed", "error": str(exc)}, 400 if exc.code == 1 else 500)
                return
            result["stats"] = graph["stats"]
            result["node"] = load_node(data, node_id)
            self._json(result)

        def do_POST(self):
            if not self.path.startswith("/api/rebuild"):
                self._json({"status": "failed", "error": "unknown endpoint"}, 404)
                return
            if not self._origin_allowed():
                self._json({"status": "failed", "error": "origin not allowed"}, 403)
                return
            try:
                with Lock(data):
                    graph = build_graph(root, data)
            except MirrorError as exc:
                self._json({"status": "failed", "error": str(exc)}, 500)
                return
            self._json({"status": "ok", "stats": graph["stats"]})

        def log_message(self, fmt, *a):
            warn("%s %s" % (self.address_string(), fmt % a))

    socketserver.TCPServer.allow_reuse_address = True
    if host not in ("127.0.0.1", "localhost", "::1"):
        warn("warning: %s is not loopback, the write API rejects non-loopback origins" % host)
    with socketserver.TCPServer((host, port), Handler) as httpd:
        print(json.dumps({"status": "serving", "url": "http://%s:%d/" % (host, port),
                          "data": str(data), "writable": True}, ensure_ascii=False))
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            return 0
    return 0


def cmd_serve(args, root: Path, data: Path) -> int:
    return serve(data, root, args.host, args.port)


def cmd_check(args, root: Path, data: Path) -> int:
    errors: list[str] = []
    ids: dict[str, str] = {}
    for path in sorted((data / "nodes").glob("*.json")):
        node = json.loads(path.read_text(encoding="utf-8"))
        meta = node["meta"]
        node_id = meta["node_id"]
        if node_id in ids:
            errors.append("duplicate node_id %s in %s and %s" % (node_id, ids[node_id], path.name))
        ids[node_id] = path.name
        source = root / meta["source_file_path"]
        if not source.is_file():
            errors.append("%s: source missing %s" % (node_id, meta["source_file_path"]))
            continue
        if sha256_of(source.read_bytes()) != meta["content_sha256"]:
            errors.append("%s: content_sha256 mismatch" % node_id)
        rebuilt = compile_node(node)
        bom = "\ufeff" if node["reconstruction_meta"].get("bom") else ""
        if (bom + rebuilt).encode("utf-8") != source.read_bytes():
            errors.append("%s: lossless round trip failed" % node_id)
        if meta["canonical"] and meta["projection_of"] is not None:
            errors.append("%s: canonical node has projection_of" % node_id)
        if not meta["canonical"] and meta["projection_of"] and meta["projection_of"] not in ids:
            errors.append("%s: projection_of target missing" % node_id)
        for block in node[block_key(node)]:
            raw = block.get("raw_content") or block.get("raw_code") or ""
            for rel in block.get("relations", []):
                origin = rel.get("origin")
                if origin not in ("auto", "agent"):
                    errors.append("%s/%s: missing or bad origin" % (node_id, block["block_id"]))
                if rel.get("relation_type") not in RELATION_TYPES:
                    errors.append("%s/%s: bad relation_type %s" % (node_id, block["block_id"], rel.get("relation_type")))
                if origin == "agent" and (not rel.get("anchor_text") or rel["anchor_text"] not in raw):
                    errors.append("%s/%s: agent anchor not in block" % (node_id, block["block_id"]))
                resolution = rel.get("resolution")
                if resolution not in RESOLUTIONS:
                    errors.append("%s/%s: bad resolution %s" % (node_id, block["block_id"], resolution))
                target_path = rel.get("target_path")
                if target_path and not target_path.startswith(INDEX_PREFIXES):
                    errors.append("%s/%s: relation leaves harness scope %s" % (node_id, block["block_id"], target_path))
                elif resolution == "unresolved" and (rel.get("target_path") or rel.get("target_node_id")):
                    errors.append("%s/%s: unresolved relation keeps a target" % (node_id, block["block_id"]))
                elif resolution == "missing" and not rel.get("target_path"):
                    errors.append("%s/%s: missing relation has no target_path" % (node_id, block["block_id"]))
                elif (
                    resolution == "resolved"
                    and rel.get("target_type") != "mcp"
                    and not rel.get("target_path")
                ):
                    errors.append("%s/%s: resolved relation has no target_path" % (node_id, block["block_id"]))
                if rel.get("target_type") == "mcp":
                    if not rel.get("target_node_id"):
                        errors.append("%s/%s: mcp relation without target_node_id" % (node_id, block["block_id"]))
                    continue
                if rel.get("resolution") == "resolved" and rel.get("target_path") and not (root / rel["target_path"]).exists():
                    errors.append("%s/%s: resolved target missing %s" % (node_id, block["block_id"], rel["target_path"]))
    cache_path = data / "cache.map"
    if cache_path.is_file():
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        cached = {entry.get("node_id") for entry in cache.values()}
        for node_id in sorted(cached - set(ids)):
            errors.append("cache entry without node file: %s" % node_id)
        for node_id in sorted(set(ids) - cached):
            errors.append("node file without cache entry: %s" % node_id)
        stale = sorted(rel for rel, entry in cache.items()
                       if entry.get("parser_version") != PARSER_VERSION or entry.get("schema_version") != SCHEMA_VERSION)
        for rel in stale:
            warn("stale cache version, rerun scan: %s" % rel)
    without_projection = sum(
        1 for path in (data / "nodes").glob("*.json")
        if (lambda meta: meta["canonical"] is False and not meta.get("projection_of"))(
            json.loads(path.read_text(encoding="utf-8"))["meta"]
        )
    )
    visibility_report = compute_visibility(root)
    errors.extend(visibility_report["errors"])
    report = {
        "status": "passed" if not errors else "failed",
        "nodes": len(ids),
        "nodes_without_projection": without_projection,
        "visibility": {
            "gates": visibility_report["gates"],
            "attach_globs": visibility_report["attach_globs"],
        },
        "errors": errors,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not errors else 1


VISIBILITY_ENVS = ("cursor", "codex", "kilo", "dsh", "qoder", "qwen", "antigravity")
TRIGGER_MODE = {
    "always_on": "inline",
    "glob": "glob",
    "model_decision": "choice",
    "manual": "manual",
}


def read_rule_fields(path: Path) -> dict:
    """Parse the flat YAML frontmatter of one canonical rule."""
    text = path.read_text(encoding="utf-8", errors="replace")
    match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.S)
    fields: dict = {}
    if not match:
        return fields
    key = ""
    for line in match.group(1).splitlines():
        if not line.strip():
            continue
        if line[:1] in (" ", "\t"):
            item = line.strip()
            if key and item.startswith("- "):
                current = fields.get(key)
                if not isinstance(current, list):
                    current = []
                current.append(item[2:].strip().strip("\"'"))
                fields[key] = current
            continue
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip().strip("\"'")
    return fields


def rule_kind(fields: dict) -> str:
    if str(fields.get("alwaysApply", "")).strip().lower() == "true":
        return "always"
    if fields.get("globs") or fields.get("paths"):
        return "conditional"
    if str(fields.get("description", "")).strip():
        return "agent_requested"
    return "manual"


def rule_globs(fields: dict) -> list[str]:
    value = fields.get("globs") or fields.get("paths") or []
    if isinstance(value, str):
        return [value.strip().strip("\"'")] if value.strip() else []
    return [str(item).strip().strip("\"'") for item in value if str(item).strip()]


def flat_rule_name(relative: Path) -> str:
    parts = relative.with_suffix("").parts
    if len(parts) == 2 and parts[0] == "mcp":
        return "mcp-" + parts[1]
    return "-".join(parts)


def kilo_instructions(root: Path) -> set[str]:
    path = root / ".kilo" / "kilo.jsonc"
    if not path.is_file():
        return set()
    text = "\n".join(
        line for line in path.read_text(encoding="utf-8").splitlines()
        if not line.lstrip().startswith("//")
    )
    try:
        return set(json.loads(text).get("instructions", []))
    except json.JSONDecodeError:
        return set()


def trigger_of(path: Path) -> str:
    if not path.is_file():
        return "none"
    return str(read_rule_fields(path).get("trigger", "")).strip() or "none"


def qwen_mode(root: Path, flat: str) -> str:
    rule_path = root / ".qwen" / "rules" / (flat + ".md")
    if rule_path.is_file():
        fields = read_rule_fields(rule_path)
        return "glob" if (fields.get("paths") or fields.get("globs")) else "inline"
    if (root / ".qwen" / "skills" / ("rule-" + flat) / "SKILL.md").is_file():
        return "skill"
    return "none"


def compute_visibility(root: Path) -> dict:
    """Rule visibility matrix per environment, plus contract violations.

    File parity answers "is the copy equal". This answers "what the agent can
    actually see at start", which is the property the gates depend on.
    """
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "environment-sync/scripts"))
    import rule_model
    canon = root / ".cursor" / "rules"
    startup = root / "AGENTS.md"
    startup_text = startup.read_text(encoding="utf-8") if startup.is_file() else ""
    instructions = kilo_instructions(root)
    kilo_index_path = root / ".kilo" / "rules-index.md"
    kilo_index = kilo_index_path.read_text(encoding="utf-8") if kilo_index_path.is_file() else ""
    dsh_path = root / "DSH-RULES.md"
    dsh_text = dsh_path.read_text(encoding="utf-8") if dsh_path.is_file() else ""
    dsh_head, _, dsh_tail = dsh_text.partition("## On-demand rules")
    codex_index_path = root / ".codex" / "rules-index.md"
    codex_text = codex_index_path.read_text(encoding="utf-8") if codex_index_path.is_file() else ""
    codex_head, _, codex_tail = codex_text.partition("## По требованию")

    matrix: dict[str, dict[str, str]] = {}
    errors: list[str] = []
    gates: list[str] = []
    attach_globs: list[str] = []

    for rule_path in sorted(canon.rglob("*.mdc")):
        relative = rule_path.relative_to(canon)
        key = relative.with_suffix("").as_posix()
        fields = read_rule_fields(rule_path)
        kind = rule_kind(fields)
        flat = flat_rule_name(relative)
        rel_md = relative.with_suffix(".md").as_posix()
        kilo_path = f".kilo/rules/{rel_md}"
        codex_target = f".codex/rules/{rel_md}"
        gate_body = rule_model.rebase_links(rule_model.body_without_frontmatter(
            rule_path.read_text(encoding="utf-8")), rule_path, startup).strip()
        codex_inline = (f"<!-- harness-gate: {key} -->" in startup_text and bool(gate_body)
                        and gate_body in startup_text)

        qoder_trigger = trigger_of(root / ".qoder" / "rules" / (flat + ".md"))
        antigravity_trigger = trigger_of(root / ".agents" / "rules" / (flat + ".md"))
        modes = {
            "cursor": "inline" if kind == "always" else ("glob" if kind == "conditional" else "choice"),
            "codex": "inline" if codex_inline else ("index" if codex_target in codex_text else "none"),
            "kilo": "inline" if kilo_path in instructions else "index",
            "dsh": "inline" if f"<!-- rule: {flat} (always) -->" in dsh_head else "index",
            "qoder": TRIGGER_MODE.get(qoder_trigger, "none"),
            "qwen": qwen_mode(root, flat),
            "antigravity": TRIGGER_MODE.get(antigravity_trigger, "none"),
        }
        matrix[key] = modes

        if str(fields.get("gate", "")).strip().lower() == "true":
            gates.append(key)
            for env in VISIBILITY_ENVS:
                if modes[env] != "inline":
                    errors.append(f"{key}: gate not inline in {env} ({modes[env]})")

        if str(fields.get("attach", "")).strip().lower() == "glob":
            attach_globs.append(key)
            globs = rule_globs(fields)
            if kind != "conditional" or not globs:
                errors.append(f"{key}: attach glob requires globs or paths")
            for env in ("cursor", "qoder", "qwen", "antigravity"):
                if modes[env] != "glob":
                    errors.append(f"{key}: path trigger not attached in {env} ({modes[env]})")
            for env, text in (("kilo", kilo_index), ("codex", codex_tail), ("dsh", dsh_tail)):
                if "<!-- glob-triggers -->" not in text:
                    errors.append(f"{key}: generated glob block missing in {env}")
                for glob in globs:
                    if glob not in text:
                        errors.append(f"{key}: glob {glob} missing from {env} glob block")

    return {
        "status": "passed" if not errors else "failed",
        "rules": len(matrix),
        "gates": gates,
        "attach_globs": attach_globs,
        "matrix": matrix,
        "errors": errors,
    }


def cmd_visibility(args, root: Path, data: Path) -> int:
    report = compute_visibility(root)
    if args.summary:
        report = {
            key: report[key]
            for key in ("status", "rules", "gates", "attach_globs", "errors")
        }
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "passed" else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="harness_mirror.py", description="One JSON node per harness file")
    parser.add_argument("--root", help="project root; default: nearest .git or .cursor from script or cwd")
    parser.add_argument("--data", default=DEFAULT_DATA, help="data directory relative to root")
    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="build or refresh nodes")
    scan.add_argument("--paths", nargs="*", default=[], help="relative paths to scan")
    scan.add_argument("--include-mirrors", action="store_true", help="add .codex .kilo .antigravity .gemini .agents")
    scan.add_argument("--include-dsh", action="store_true", help="add .dsh")
    scan.add_argument("--force", action="store_true", help="ignore cache")
    scan.set_defaults(func=cmd_scan, mutate=True)

    prompt = sub.add_parser("prompt", help="print analysis task for one node")
    prompt.add_argument("--node", required=True)
    prompt.set_defaults(func=cmd_prompt, mutate=False)

    apply_cmd = sub.add_parser("apply", help="merge agent analysis into a node")
    apply_cmd.add_argument("--node", required=True)
    apply_cmd.add_argument("--json", help="analysis file; stdin when omitted")
    apply_cmd.add_argument("--model", default=None)
    apply_cmd.set_defaults(func=cmd_apply, mutate=True)

    get = sub.add_parser("get", help="print node with edges")
    get.add_argument("--node", required=True)
    get.add_argument("--slim", action="store_true", help="labels, summary and edges without blocks")
    get.set_defaults(func=cmd_get, mutate=False)

    bundle = sub.add_parser("bundle", help="compact view of one skill: files, triggers, edges")
    bundle.add_argument("--skill", required=True)
    bundle.set_defaults(func=cmd_bundle, mutate=False)

    lint = sub.add_parser("lint", help="structural and semantic-adjacent checks over the whole canon")
    lint.set_defaults(func=cmd_lint, mutate=False)

    review = sub.add_parser("review", help="semantic review packet: digest, outline, edges, issues")
    review.add_argument("--node")
    review.add_argument("--skill")
    review.add_argument("--all", action="store_true", help="compact overview of all skills and rules")
    review.set_defaults(func=cmd_review, mutate=False)

    audit = sub.add_parser("audit", help="compact audit report for a node or a skill")
    audit.add_argument("--node")
    audit.add_argument("--skill")
    audit.set_defaults(func=cmd_audit, mutate=False)

    set_cmd = sub.add_parser("set", help="replace a block or the whole file of a skill or rule")
    set_cmd.add_argument("--node", required=True)
    set_cmd.add_argument("--block", help="block id; omit with --file")
    set_cmd.add_argument("--file", action="store_true", help="replace the whole file, skills and rules only")
    set_cmd.add_argument("--content", help="new text file; stdin when omitted")
    set_cmd.set_defaults(func=cmd_set, mutate=True)

    build = sub.add_parser("build", help="write graph.json and viewer")
    build.set_defaults(func=cmd_build, mutate=True)

    rebuild = sub.add_parser("rebuild", help="refresh changed sources, then write graph.json and viewer")
    rebuild.set_defaults(func=cmd_rebuild, mutate=True)

    check = sub.add_parser("check", help="verify invariants")
    check.set_defaults(func=cmd_check, mutate=False)

    visibility = sub.add_parser("visibility", help="rule visibility matrix per environment")
    visibility.add_argument("--summary", action="store_true", help="omit the full rule-by-environment matrix")
    visibility.set_defaults(func=cmd_visibility, mutate=False)

    serve_cmd = sub.add_parser("serve", help="static viewer plus write API")
    serve_cmd.add_argument("--host", default="127.0.0.1")
    serve_cmd.add_argument("--port", type=int, default=8090)
    serve_cmd.set_defaults(func=cmd_serve, mutate=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        root = find_root(args.root, Path(__file__))
        data = (root / args.data).resolve()
        if args.mutate:
            data.mkdir(parents=True, exist_ok=True)
            with Lock(data):
                return args.func(args, root, data)
        return args.func(args, root, data)
    except MirrorError as exc:
        warn(str(exc))
        return exc.code
    except FileNotFoundError as exc:
        warn("file not found: %s" % exc)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
