#!/usr/bin/env python3
"""Doc Script - документация скриптов внутри скила-владельца."""

from __future__ import annotations

import argparse
import ast
import importlib.util
import os
import re
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
SKILLS_ROOT = ROOT / ".agents" / "skills"
HARNESS_CORE = SKILLS_ROOT / "harness-router" / "children" / "harness-core"
CANON_SCRIPTS = ROOT / ".cursor" / "scripts"
CANON_MCP_STACK = ROOT / ".cursor" / "mcp-stack"
TOOLS_SCRIPTS = ROOT / ".tools" / "scripts"
DSH_SCRIPTS = ROOT / ".dsh" / "scripts"
EXTS = {".sh", ".ps1", ".py", ".js", ".mjs", ".php", ".cmd"}
SKIP = {"__pycache__", "node_modules", "vendor", ".git", ".venv", "venv"}
SECTIONS = [
    "## Суть",
    "## Когда запускать",
    "## Аргументы",
    "## Коды выхода",
    "## Что читает и что пишет",
    "## Побочные эффекты",
    "## Окружение и зависимости",
    "## Примеры",
    "## Ограничения",
    "## Связи",
    "## История изменений",
]
DRAFT_PATTERNS = [
    "Определить при ревью",
    "Определить по коду",
    "Проверить по исходнику",
    "Аргументов не обнаружено",
    "Добавить минимум один рабочий вызов",
]

CREDENTIAL_IN_URL_RE = re.compile(r"://([^:@\s\"']+):([^@\r\n\"']+)@", re.IGNORECASE)
URL_QUERY_SECRET_RE = re.compile(
    r"([?&](?:token|key|secret|password|passwd|api_?key|access_token|auth|client_?secret)=)[^&\s\"'#]+",
    re.IGNORECASE,
)
SECRET_HELP_ASSIGN_RE = re.compile(
    r"((?:password|passwd|token|secret|bearer|api_?key|credential|private_?key)\s*[:=]\s*)['\"]?([^\s,;&\"'\]\)\>]+|(?:\<[^\>\r\n]+\>))['\"]?",
    re.IGNORECASE,
)
BEARER_TOKEN_RE = re.compile(r"(Bearer\s+)[A-Za-z0-9_\-\.]{10,}", re.IGNORECASE)
SECRET_ASSIGN_RE = re.compile(
    r"((?:secret|token|password|api_?key|passwd|credential|auth)\s*[=:]\s*)['\"]?([A-Za-z0-9_\-\.]{6,})['\"]?",
    re.IGNORECASE,
)
SENSITIVE_PARAM_PATTERN = re.compile(
    r"(secret|password|passwd|token|api_?key|auth|cred|credential|private_?key)",
    re.IGNORECASE,
)
SYNTHETIC_SECRET_RE = re.compile(
    r"(FAKE_SECRET[A-Za-z0-9_-]*|SECRET_[A-Za-z0-9_-]+|DUMMY_TOKEN[A-Za-z0-9_-]*)",
    re.IGNORECASE,
)


def is_subpath(path: Path, base: Path) -> bool:
    """Python 3.8 compatible replacement for Path.is_relative_to."""
    try:
        path.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


def safe_relpath(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def sanitize_text(text: str) -> str:
    if not text:
        return text
    cleaned = CREDENTIAL_IN_URL_RE.sub(r"://\1:***@", text)
    cleaned = URL_QUERY_SECRET_RE.sub(r"\1***", cleaned)
    cleaned = SECRET_HELP_ASSIGN_RE.sub(r"\1***", cleaned)
    cleaned = BEARER_TOKEN_RE.sub(r"\1***", cleaned)
    cleaned = SECRET_ASSIGN_RE.sub(r"\1***", cleaned)
    cleaned = SYNTHETIC_SECRET_RE.sub("[MASKED]", cleaned)
    return cleaned


def is_sensitive_parameter(name: str, aliases: str | list[str] = "", help_text: str = "") -> bool:
    alias_str = aliases if isinstance(aliases, str) else " ".join(aliases)
    target = f"{name} {alias_str} {help_text}"
    return bool(SENSITIVE_PARAM_PATTERN.search(target))


def mask_sensitive_default(name: str, aliases: str | list[str], default_val: str, help_text: str = "") -> str:
    if not default_val or str(default_val).strip() in ("", "''", '""', "None"):
        return default_val
    val_str = str(default_val).strip()
    if is_sensitive_parameter(name, aliases, help_text):
        return "[MASKED]"
    return sanitize_text(val_str)


def skill_root_for(script: Path) -> Path | None:
    if CANON_SCRIPTS in script.parents or CANON_MCP_STACK in script.parents:
        return HARNESS_CORE
    if TOOLS_SCRIPTS in script.parents:
        return HARNESS_CORE
    if DSH_SCRIPTS in script.parents:
        dsh_router = ROOT / ".dsh" / "skills" / "dsh-router"
        if (dsh_router / "SKILL.md").is_file():
            return dsh_router
        return SKILLS_ROOT / "harness-router" / "children" / "environment-sync"
    for parent in script.parents:
        if "scripts" not in parent.parts:
            continue
        candidate = parent.parent if parent.name == "scripts" else parent
        while is_subpath(candidate, SKILLS_ROOT) or candidate == SKILLS_ROOT:
            if (candidate / "SKILL.md").is_file():
                return candidate
            if candidate == SKILLS_ROOT:
                break
            candidate = candidate.parent
    return None


def doc_path_for(script: Path) -> Path | None:
    owner = skill_root_for(script)
    if not owner:
        return None
    if CANON_SCRIPTS in script.parents:
        rel = script.relative_to(CANON_SCRIPTS)
        has_collision = (HARNESS_CORE / "scripts" / rel).exists() or (CANON_MCP_STACK / rel).exists()
        if has_collision:
            return owner / "docs" / "scripts" / "cursor-canon" / f"{rel}.md"
        return owner / "docs" / "scripts" / f"{rel}.md"
    elif TOOLS_SCRIPTS in script.parents:
        rel = script.relative_to(TOOLS_SCRIPTS)
        return owner / "docs" / "scripts" / "tools" / f"{rel}.md"
    elif CANON_MCP_STACK in script.parents:
        rel = script.relative_to(CANON_MCP_STACK)
        has_collision = (HARNESS_CORE / "scripts" / rel).exists() or (CANON_SCRIPTS / rel).exists()
        if has_collision:
            return owner / "docs" / "scripts" / "mcp-stack" / f"{rel}.md"
        return owner / "docs" / "scripts" / f"{rel}.md"
    elif DSH_SCRIPTS in script.parents:
        rel = script.relative_to(DSH_SCRIPTS)
        return owner / "docs" / "scripts" / f"{rel}.md"
    else:
        scripts_dir = None
        for parent in script.parents:
            if parent.name == "scripts":
                scripts_dir = parent
                break
        if not scripts_dir:
            return None
        rel = script.relative_to(scripts_dir)
        if owner == HARNESS_CORE:
            has_collision = (CANON_SCRIPTS / rel).exists() or (CANON_MCP_STACK / rel).exists()
            if has_collision:
                return owner / "docs" / "scripts" / "core-scripts" / f"{rel}.md"
        return owner / "docs" / "scripts" / f"{rel}.md"


def script_path_for_doc(doc: Path) -> Path | None:
    if not doc.name.endswith(".md"):
        return None
    docs_scripts = None
    for p in doc.parents:
        if p.name == "scripts" and p.parent.name == "docs":
            docs_scripts = p
            break
    if not docs_scripts:
        return None
    owner = docs_scripts.parent.parent
    rel = doc.relative_to(docs_scripts)
    rel_str = rel.as_posix()
    if rel_str.endswith(".md"):
        rel_str = rel_str[:-3]

    if owner == HARNESS_CORE:
        if rel_str.startswith("cursor-canon/"):
            return CANON_SCRIPTS / rel_str[13:]
        if rel_str.startswith("core-scripts/"):
            return HARNESS_CORE / "scripts" / rel_str[13:]
        if rel_str.startswith("mcp-stack/"):
            return CANON_MCP_STACK / rel_str[10:]
        if rel_str.startswith("tools/"):
            return TOOLS_SCRIPTS / rel_str[6:]
        candidates = [
            CANON_SCRIPTS / rel_str,
            HARNESS_CORE / "scripts" / rel_str,
            CANON_MCP_STACK / rel_str,
            TOOLS_SCRIPTS / rel_str,
        ]
        for cand in candidates:
            if cand.exists():
                return cand
        return CANON_SCRIPTS / rel_str
    elif DSH_SCRIPTS.exists() and (owner.name == "dsh-router" or owner.name == "environment-sync"):
        dsh_cand = DSH_SCRIPTS / rel_str
        if dsh_cand.exists():
            return dsh_cand
        return owner / "scripts" / rel_str
    else:
        return owner / "scripts" / rel_str


def validate_safe_doc_path(doc: Path, owner: Path) -> tuple[bool, str]:
    """Ensures destination doc does not escape owner skill boundaries via traversal or symlinks."""
    try:
        owner_resolved = owner.resolve()
        curr = doc.parent
        while curr != curr.parent:
            if curr.is_symlink():
                resolved_link = curr.resolve()
                if not is_subpath(resolved_link, owner_resolved):
                    return False, f"SECURITY_ERROR: symlinked directory escapes owner skill: {curr} -> {resolved_link}"
            if curr == owner:
                break
            curr = curr.parent

        if doc.is_symlink():
            return False, f"SECURITY_ERROR: target doc is a symlink: {doc}"

        doc_resolved = doc.resolve() if doc.exists() else doc.parent.resolve() / doc.name
        if not is_subpath(doc_resolved, owner_resolved):
            return False, f"SECURITY_ERROR: doc path escapes owner skill: {doc_resolved} not in {owner_resolved}"
        return True, ""
    except Exception as e:
        return False, f"SECURITY_ERROR: path validation failed for {doc}: {e}"


def atomic_write_text(path: Path, content: str, owner: Path | None = None) -> None:
    """Secure atomic file write using tempfile.mkstemp with symlink and TOCTOU directory swap protection."""
    if path.is_symlink():
        raise PermissionError(f"SECURITY_ERROR: target doc is a symlink: {path}")

    owner_resolved = owner.resolve() if owner else None
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.path.islink(path.parent):
        raise PermissionError(f"SECURITY_ERROR: target parent directory is a symlink: {path.parent}")

    parent_before = path.parent.resolve()
    if owner_resolved and not is_subpath(parent_before, owner_resolved):
        raise PermissionError(f"SECURITY_ERROR: target directory escapes owner skill: {parent_before} not in {owner_resolved}")

    fd, temp_path_str = tempfile.mkstemp(
        prefix=f".tmp_{path.name}_",
        dir=str(path.parent),
        text=True,
    )
    temp_file = Path(temp_path_str)
    try:
        if os.path.islink(path.parent):
            raise PermissionError(f"SECURITY_ERROR: target parent directory became a symlink: {path.parent}")
        if path.parent.resolve() != parent_before:
            raise PermissionError("SECURITY_ERROR: target parent directory was swapped during creation")

        tmp_real = Path(os.path.realpath(temp_file))
        if not is_subpath(tmp_real, parent_before):
            raise PermissionError("SECURITY_ERROR: temporary file created outside target parent directory")
        if owner_resolved and not is_subpath(tmp_real, owner_resolved):
            raise PermissionError(f"SECURITY_ERROR: temporary file escapes owner skill: {tmp_real}")

        with open(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())

        if os.path.islink(temp_file):
            raise PermissionError(f"SECURITY_ERROR: temporary file was replaced by symlink: {temp_file}")
        if os.path.islink(path.parent):
            raise PermissionError(f"SECURITY_ERROR: target parent directory became a symlink before replace: {path.parent}")
        if path.parent.resolve() != parent_before:
            raise PermissionError("SECURITY_ERROR: target parent directory was swapped before replace")
        if path.exists() and os.path.islink(path):
            raise PermissionError(f"SECURITY_ERROR: target path became a symlink: {path}")

        temp_file.replace(path)
    finally:
        if temp_file.exists():
            try:
                temp_file.unlink()
            except OSError:
                pass


def detect_script_doc_collisions(scripts: list[Path] | None = None) -> dict[Path, list[Path]]:
    target_scripts = iter_all_harness_scripts() if scripts is None else scripts
    mapping: dict[Path, list[Path]] = {}
    for s in target_scripts:
        doc = doc_path_for(s)
        if doc:
            mapping.setdefault(doc, []).append(s)
    return {doc: srcs for doc, srcs in mapping.items() if len(srcs) > 1}


def find_all_script_docs() -> list[Path]:
    docs: list[Path] = []
    core_scripts_doc_dir = HARNESS_CORE / "docs" / "scripts"
    if core_scripts_doc_dir.exists():
        for p in core_scripts_doc_dir.rglob("*.md"):
            if p.is_file():
                docs.append(p)
    if SKILLS_ROOT.exists():
        for p in SKILLS_ROOT.rglob("*.md"):
            if not p.is_file():
                continue
            parts = p.parts
            if "docs" in parts and "scripts" in parts:
                docs_idx = parts.index("docs")
                if docs_idx + 1 < len(parts) and parts[docs_idx + 1] == "scripts":
                    if p not in docs:
                        docs.append(p)
    return sorted(docs)


def find_orphan_docs() -> list[Path]:
    orphans = []
    for doc in find_all_script_docs():
        script_path = script_path_for_doc(doc)
        if script_path is None or not script_path.is_file():
            orphans.append(doc)
    return orphans


def classify_script(path: Path) -> tuple[str, str]:
    """Classifies script and returns (category, reason)."""
    name = path.name.lower()
    if name.startswith("__") or name.endswith("_test.py") or name.startswith("test_") or "test" in path.parts or "tests" in path.parts or name == "conftest.py":
        return "test", "test file or in test directory"
    if "examples" in path.parts or "assets/examples" in path.as_posix():
        return "library", "example script in examples directory"
    if "lib" in path.parts or "libs" in path.parts:
        return "library", "library in lib/libs directory"
    if name.startswith("_") or name in ("lib.sh", "lib.ps1", "common.sh", "ba_common.py"):
        return "library", "library or internal helper naming convention"

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        return "ignored", f"read error: {e}"

    suffix = path.suffix.lower()
    if suffix in {".sh", ".bash"}:
        if not text.startswith("#!") and not re.search(r"^(?!function\b)[a-zA-Z0-9_-]+\s+", text, re.MULTILINE):
            return "library", "no shebang or top-level command in shell script"
    elif suffix == ".ps1":
        if not extract_ps_param_block(text) and not re.search(r"^(?!function\b)\$[a-zA-Z0-9_]+", text, re.MULTILINE):
            if "function " in text.lower():
                return "library", "contains only functions without entrypoint param block"
    elif suffix == ".py":
        if not text.startswith("#!"):
            has_entrypoint = False
            for pattern in (
                r"^\s*if\s+__name__\s*==\s*[\"']__main__[\"']",
                r"^\s*import\s+(argparse|click|typer|fire)\b",
                r"^\s*from\s+(argparse|click|typer|fire)\b",
                r"^\s*def\s+main\s*\(",
                r"\b(app|cli|parser)\s*=",
            ):
                if re.search(pattern, text, re.MULTILINE):
                    has_entrypoint = True
                    break
            if not has_entrypoint:
                return "library", "imported python module without entrypoint"
    elif suffix in {".js", ".mjs"}:
        if not text.startswith("#!") and not any(k in text for k in ("process.argv", "commander", ".option(")):
            return "library", "imported javascript module without entrypoint"
    elif suffix == ".php":
        if not any(k in text for k in ("$argv", "Symfony\\Component\\Console")):
            return "library", "imported php class/module without entrypoint"

    owner = skill_root_for(path)
    if not owner:
        return "unknown_owner", f"no parent skill found in {path.parent.name}"

    return "entrypoint", "runnable script with owner skill"


def is_runnable(path: Path) -> bool:
    if path.name == "__init__.py":
        return False
    cat, _ = classify_script(path)
    if cat in ("test", "library", "unknown_owner", "ignored"):
        return False
    suffix = path.suffix.lower()
    if suffix in {".sh", ".ps1", ".cmd"}:
        return True
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    if text.startswith("#!"):
        return True
    if suffix == ".py":
        return "__main__" in text or "argparse" in text or "click" in text or "app(" in text
    if suffix in {".js", ".mjs"}:
        return "process.argv" in text or "commander" in text or ".option(" in text
    if suffix == ".php":
        return "$argv" in text or "Symfony\\Component\\Console" in text
    return False


HARNESS_SCAN_BASES = (CANON_SCRIPTS, CANON_MCP_STACK, TOOLS_SCRIPTS, SKILLS_ROOT, DSH_SCRIPTS)


def iter_all_harness_scripts() -> list[Path]:
    found = []
    for base in HARNESS_SCAN_BASES:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in EXTS:
                continue
            if any(part in SKIP for part in path.parts):
                continue
            found.append(path)
    return sorted(list(set(found)))


def iter_scripts() -> list[Path]:
    found = []
    for path in iter_all_harness_scripts():
        cat, _ = classify_script(path)
        if cat == "entrypoint" and is_runnable(path) and doc_path_for(path):
            found.append(path)
    return sorted(found)


# --- PowerShell Parameter Extraction ---


def find_ps_param_keyword(text: str) -> int | None:
    """Finds 'param(' keyword outside of comments and string literals."""
    i = 0
    n = len(text)
    in_s_quote = False
    in_d_quote = False
    in_block_c = False
    in_line_c = False

    while i < n:
        c = text[i]
        c2 = text[i : i + 2]
        if in_block_c:
            if c2 == "#>":
                in_block_c = False
                i += 2
                continue
            i += 1
            continue
        if in_line_c:
            if c == "\n":
                in_line_c = False
            i += 1
            continue
        if in_s_quote:
            if c == "'":
                if i + 1 < n and text[i + 1] == "'":
                    i += 2
                    continue
                in_s_quote = False
            i += 1
            continue
        if in_d_quote:
            if c == "`" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    i += 2
                    continue
                in_d_quote = False
            i += 1
            continue
        if c2 == "<#":
            in_block_c = True
            i += 2
            continue
        if c == "#":
            in_line_c = True
            i += 1
            continue
        if c == "'":
            in_s_quote = True
            i += 1
            continue
        if c == '"':
            in_d_quote = True
            i += 1
            continue

        if text[i : i + 5].lower() == "param":
            j = i + 5
            while j < n and text[j].isspace():
                j += 1
            if j < n and text[j] == "(":
                if i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "_$"):
                    return j + 1
        i += 1
    return None


def extract_ps_param_block(text: str) -> str | None:
    start = find_ps_param_keyword(text)
    if start is None:
        return None
    depth = 1
    i = start
    n = len(text)
    in_s_quote = False
    in_d_quote = False
    in_block_c = False
    in_line_c = False

    while i < n and depth > 0:
        c = text[i]
        c2 = text[i : i + 2]
        if in_block_c:
            if c2 == "#>":
                in_block_c = False
                i += 2
                continue
            i += 1
            continue
        if in_line_c:
            if c == "\n":
                in_line_c = False
            i += 1
            continue
        if in_s_quote:
            if c == "'":
                if i + 1 < n and text[i + 1] == "'":
                    i += 2
                    continue
                in_s_quote = False
            i += 1
            continue
        if in_d_quote:
            if c == "`" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                if i + 1 < n and text[i + 1] == '"':
                    i += 2
                    continue
                in_d_quote = False
            i += 1
            continue
        if c2 == "<#":
            in_block_c = True
            i += 2
            continue
        if c == "#":
            in_line_c = True
            i += 1
            continue
        if c == "'":
            in_s_quote = True
            i += 1
            continue
        if c == '"':
            in_d_quote = True
            i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return None


def split_ps_params(block: str) -> list[str]:
    chunks = []
    start = 0
    i = 0
    n = len(block)
    paren_depth = 0
    bracket_depth = 0
    in_s_quote = False
    in_d_quote = False
    in_block_c = False
    in_line_c = False

    while i < n:
        c = block[i]
        c2 = block[i : i + 2]
        if in_block_c:
            if c2 == "#>":
                in_block_c = False
                i += 2
                continue
            i += 1
            continue
        if in_line_c:
            if c == "\n":
                in_line_c = False
            i += 1
            continue
        if in_s_quote:
            if c == "'":
                if i + 1 < n and block[i + 1] == "'":
                    i += 2
                    continue
                in_s_quote = False
            i += 1
            continue
        if in_d_quote:
            if c == "`" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                if i + 1 < n and block[i + 1] == '"':
                    i += 2
                    continue
                in_d_quote = False
            i += 1
            continue
        if c2 == "<#":
            in_block_c = True
            i += 2
            continue
        if c == "#":
            in_line_c = True
            i += 1
            continue
        if c == "'":
            in_s_quote = True
            i += 1
            continue
        if c == '"':
            in_d_quote = True
            i += 1
            continue
        if c == "(":
            paren_depth += 1
        elif c == ")":
            paren_depth -= 1
        elif c == "[":
            bracket_depth += 1
        elif c == "]":
            bracket_depth -= 1
        elif c == "," and paren_depth == 0 and bracket_depth == 0:
            chunks.append(block[start:i])
            start = i + 1
        i += 1
    if start < n:
        chunks.append(block[start:])
    return [c.strip() for c in chunks if c.strip()]


def extract_ps_brackets(chunk: str) -> tuple[list[str], str]:
    brackets = []
    outside = []
    i = 0
    n = len(chunk)
    depth = 0
    start = 0
    outside_start = 0
    in_s_quote = False
    in_d_quote = False

    while i < n:
        c = chunk[i]
        if in_s_quote:
            if c == "'":
                if i + 1 < n and chunk[i + 1] == "'":
                    i += 2
                    continue
                in_s_quote = False
            i += 1
            continue
        if in_d_quote:
            if c == "`" and i + 1 < n:
                i += 2
                continue
            if c == '"':
                if i + 1 < n and chunk[i + 1] == '"':
                    i += 2
                    continue
                in_d_quote = False
            i += 1
            continue
        if c == "'":
            in_s_quote = True
            i += 1
            continue
        if c == '"':
            in_d_quote = True
            i += 1
            continue
        if c == "[":
            if depth == 0:
                outside.append(chunk[outside_start:i])
                start = i + 1
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                brackets.append(chunk[start:i])
                outside_start = i + 1
        i += 1
    if depth == 0 and outside_start < n:
        outside.append(chunk[outside_start:])
    return brackets, "".join(outside)


def strip_ps_comment(val: str) -> str:
    in_s = False
    in_d = False
    for i, ch in enumerate(val):
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == "#" and not in_s and not in_d:
            return val[:i].strip()
    return val.strip()


def parse_ps_param_chunk(chunk: str) -> dict | None:
    brackets, outside = extract_ps_brackets(chunk)
    m = re.search(r"\$([A-Za-z0-9_]+)(?:\s*=\s*(.*))?", outside, re.DOTALL)
    if not m:
        return None
    var_name = m.group(1)
    raw_default = m.group(2)
    default_val = strip_ps_comment(raw_default) if raw_default is not None else ""

    required = False
    param_type = "string"
    aliases: list[str] = []

    NON_TYPE_ATTRS = (
        "parameter", "alias", "validateset", "validatenotnull", "validatenotnullorempty",
        "validaterange", "validatelength", "validatepattern", "validatescript", "validatecount",
        "allowemptycollection", "allowemptystring", "allownull", "cmdletbinding", "outputtype",
    )

    for attr in brackets:
        attr_clean = attr.strip()
        attr_lower = attr_clean.lower()
        if attr_lower.startswith("parameter"):
            mand_match = re.search(r"\bmandatory\b(?:\s*=\s*(\$true|\$false|1|0))?", attr_clean, re.IGNORECASE)
            if mand_match:
                val = mand_match.group(1)
                if val and val.lower() in ("$false", "0"):
                    required = False
                else:
                    required = True
            elif "mandatory" in attr_lower:
                required = True
        elif attr_lower.startswith("alias"):
            inner = re.search(r"alias\s*\((.*?)\)", attr_clean, re.IGNORECASE)
            if inner:
                for token in inner.group(1).split(","):
                    token = token.strip().strip("'\"")
                    if token:
                        aliases.append(f"-{token}")
            else:
                for a_match in re.finditer(r"['\"]([A-Za-z0-9_-]+)['\"]", attr_clean):
                    aliases.append(f"-{a_match.group(1)}")
        else:
            first_word = re.split(r"[\s(\[]", attr_lower)[0]
            if not any(first_word.startswith(prefix) for prefix in NON_TYPE_ATTRS):
                t = attr_clean.replace("System.", "").replace("system.", "").strip()
                t_lower = t.lower()
                if t_lower == "switch":
                    param_type = "switch"
                elif t_lower in ("string", "string[]"):
                    param_type = "array" if t_lower.endswith("[]") else "string"
                elif t_lower in ("int", "int32", "int64", "int[]"):
                    param_type = "array" if t_lower.endswith("[]") else "int"
                elif t_lower in ("bool", "boolean"):
                    param_type = "bool"
                elif t_lower.endswith("[]") or t_lower == "array":
                    param_type = "array"
                else:
                    param_type = t_lower

    if param_type == "switch" and not required:
        required = False

    masked_default = mask_sensitive_default(f"-{var_name}", aliases, default_val)

    return {
        "name": f"-{var_name}",
        "alias": ", ".join(aliases),
        "type": param_type,
        "required": required,
        "default": masked_default,
        "help": "",
    }


def parse_powershell_args(text: str) -> tuple[list[dict], bool]:
    block = extract_ps_param_block(text)
    if block is None:
        if re.search(r"(\$args\b|\$MyInvocation\b)", text):
            return [], False
        return [], True

    chunks = split_ps_params(block)
    args: list[dict] = []
    for chunk in chunks:
        param = parse_ps_param_chunk(chunk)
        if param:
            args.append(param)
    return args, True


# --- Python argparse / click Extraction ---


def safe_ast_unparse(node: ast.AST) -> str | None:
    """Python 3.8 compatible AST unparser for common literal and compound expressions."""
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)
        except Exception:
            pass
    try:
        if isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = safe_ast_unparse(node.value)
            return f"{val}.{node.attr}" if val is not None else None
        elif isinstance(node, ast.List):
            elts = [safe_ast_unparse(e) for e in node.elts]
            if any(e is None for e in elts):
                return None
            return "[" + ", ".join(elts) + "]"
        elif isinstance(node, ast.Tuple):
            elts = [safe_ast_unparse(e) for e in node.elts]
            if any(e is None for e in elts):
                return None
            return "(" + ", ".join(elts) + ("," if len(elts) == 1 else "") + ")"
        elif isinstance(node, ast.Dict):
            items = []
            for k, v in zip(node.keys, node.values):
                ks = safe_ast_unparse(k) if k else None
                vs = safe_ast_unparse(v)
                if vs is None or (k is not None and ks is None):
                    return None
                items.append(f"{ks}: {vs}" if ks is not None else f"**{vs}")
            return "{" + ", ".join(items) + "}"
        elif isinstance(node, ast.Set):
            elts = [safe_ast_unparse(e) for e in node.elts]
            if any(e is None for e in elts):
                return None
            return "{" + ", ".join(elts) + "}"
        elif isinstance(node, ast.UnaryOp):
            operand = safe_ast_unparse(node.operand)
            if operand is None:
                return None
            if isinstance(node.op, ast.USub):
                return f"-{operand}"
            elif isinstance(node.op, ast.UAdd):
                return f"+{operand}"
            elif isinstance(node.op, ast.Not):
                return f"not {operand}"
        elif isinstance(node, ast.Call):
            func = safe_ast_unparse(node.func)
            if func is None:
                return None
            args = [safe_ast_unparse(a) for a in node.args]
            if any(a is None for a in args):
                return None
            return f"{func}({', '.join(args)})"
    except Exception:
        return None
    return None


def parse_python_args(text: str) -> tuple[list[dict], bool]:
    try:
        tree = ast.parse(text)
    except Exception:
        args = []
        for m in re.finditer(r'add_argument\s*\(\s*["\']([-\w]+)["\']', text):
            args.append({"name": m.group(1), "alias": "", "type": "string", "required": False, "default": "", "help": ""})
        return args, False

    is_reliable = True
    calls = []
    click_calls = []

    # Map subparsers to subcommand names
    subcommand_map: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            if isinstance(node.value, ast.Call):
                func = node.value.func
                if isinstance(func, ast.Attribute) and func.attr == "add_parser":
                    if node.value.args and isinstance(node.value.args[0], ast.Constant):
                        subcmd_name = str(node.value.args[0].value)
                        for target in node.targets:
                            if isinstance(target, ast.Name):
                                subcommand_map[target.id] = subcmd_name

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "add_argument":
                calls.append(node)
            elif (isinstance(func, ast.Attribute) and func.attr == "option") or (isinstance(func, ast.Name) and func.id == "option"):
                if "click" in text or "@click" in text:
                    click_calls.append(node)

    if click_calls:
        args: list[dict] = []
        for node in click_calls:
            opt_strings = []
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    opt_strings.append(arg.value)
                else:
                    is_reliable = False
            if not opt_strings:
                continue
            flags = [s for s in opt_strings if s.startswith("-")]
            long_flags = [s for s in flags if s.startswith("--")]
            short_flags = [s for s in flags if not s.startswith("--")]
            name = long_flags[0] if long_flags else (short_flags[0] if short_flags else opt_strings[0])
            aliases = [s for s in flags if s != name]

            is_flag = False
            required = False
            default_val = ""
            help_text = ""
            for kw in node.keywords:
                if kw.arg == "is_flag" and isinstance(kw.value, ast.Constant):
                    is_flag = bool(kw.value.value)
                elif kw.arg == "required" and isinstance(kw.value, ast.Constant):
                    required = bool(kw.value.value)
                elif kw.arg == "default" and isinstance(kw.value, ast.Constant):
                    default_val = str(kw.value.value)
                elif kw.arg == "help" and isinstance(kw.value, ast.Constant):
                    help_text = str(kw.value.value)

            args.append({
                "name": name,
                "alias": ", ".join(aliases),
                "type": "flag" if is_flag else "string",
                "required": required,
                "default": mask_sensitive_default(name, aliases, default_val, help_text),
                "help": sanitize_text(help_text),
            })
        return args, is_reliable

    if not calls:
        if "argparse" in text and "ArgumentParser" in text:
            if "add_argument" in text:
                return [], False
            return [], True
        if "click" in text or "typer" in text or "docopt" in text or "sys.argv" in text:
            return [], False
        return [], True

    calls.sort(key=lambda n: (getattr(n, "lineno", 0), getattr(n, "col_offset", 0)))

    args = []
    for node in calls:
        subcmd = ""
        if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
            subcmd = subcommand_map.get(node.func.value.id, "")

        opt_strings = []
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                opt_strings.append(arg.value)
            else:
                is_reliable = False

        if not opt_strings:
            is_reliable = False
            continue

        flags = [s for s in opt_strings if s.startswith("-")]
        is_positional = len(flags) == 0

        if is_positional:
            name = opt_strings[0]
            aliases = opt_strings[1:]
            default_required = True
        else:
            long_flags = [s for s in flags if s.startswith("--")]
            short_flags = [s for s in flags if not s.startswith("--")]
            if long_flags:
                name = long_flags[0]
                aliases = short_flags + long_flags[1:]
            else:
                name = short_flags[0]
                aliases = short_flags[1:]
            default_required = False

        arg_type = "string"
        required = default_required
        default_val = ""
        help_text = ""

        for kw in node.keywords:
            k = kw.arg
            v = kw.value
            if k is None:
                is_reliable = False
                continue
            if k == "action":
                if isinstance(v, ast.Constant):
                    act = str(v.value)
                    if act in ("store_true", "store_false"):
                        arg_type = "flag"
                        required = False
                    elif act in ("count",):
                        arg_type = "int"
                        required = False
                    elif act in ("append", "extend"):
                        arg_type = "array"
            elif k == "type":
                if isinstance(v, ast.Name):
                    type_id = v.id
                    arg_type = "string" if type_id == "str" else type_id
                elif isinstance(v, ast.Attribute):
                    arg_type = v.attr.lower()
            elif k == "required":
                if isinstance(v, ast.Constant):
                    required = bool(v.value)
            elif k == "default":
                if isinstance(v, ast.Constant):
                    if v.value is not None:
                        default_val = str(v.value)
                else:
                    unparsed = safe_ast_unparse(v)
                    if unparsed is not None:
                        default_val = unparsed
            elif k == "nargs":
                if isinstance(v, ast.Constant):
                    if v.value in ("?", "*"):
                        required = False
            elif k == "help":
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    help_text = v.value

        args.append({
            "name": name,
            "subcommand": subcmd,
            "alias": ", ".join(aliases),
            "type": arg_type,
            "required": required,
            "default": mask_sensitive_default(name, aliases, default_val, help_text),
            "help": sanitize_text(help_text),
        })

    return args, is_reliable


# --- Shell Argument Extraction ---


def parse_shell_args(text: str) -> tuple[list[dict], bool]:
    args: list[dict] = []
    has_parser = False

    for m in re.finditer(r'getopts\s+"([^"]+)"', text):
        has_parser = True
        opt_string = m.group(1)
        idx = 0
        while idx < len(opt_string):
            ch = opt_string[idx]
            if ch == ":":
                idx += 1
                continue
            takes_val = (idx + 1 < len(opt_string) and opt_string[idx + 1] == ":")
            args.append({
                "name": f"-{ch}",
                "alias": "",
                "type": "string" if takes_val else "flag",
                "required": False,
                "default": "",
                "help": "",
            })
            idx += 2 if takes_val else 1

    case_match = re.search(
        r'case\s+"?\$(?:\{[A-Za-z0-9_@*]+(?::-[^}]*)?\}|[A-Za-z0-9_@*]+)"?\s+in(.*?)\besac\b',
        text, re.DOTALL)
    if case_match:
        has_parser = True
        case_body = case_match.group(1)
        arms = case_body.split(";;")
        for arm in arms:
            arm = arm.strip()
            if not arm:
                continue
            m = re.match(r'^\s*([^)\n]+)\)(.*)', arm, re.DOTALL)
            if not m:
                continue
            pattern_str = m.group(1).strip()
            arm_body = m.group(2)
            takes_value = bool(
                re.search(r"\bshift\s+2\b", arm_body)
                or re.search(r'\$\{?2\b', arm_body)
                or re.search(r'[A-Za-z0-9_]+=["\']?\$2\b', arm_body)
            )
            for token in pattern_str.split("|"):
                token = token.strip().strip("()").strip()
                flag_match = re.fullmatch(r'(--?[A-Za-z][\w-]*)(?:=.*)?', token)
                if flag_match:
                    takes_alias_value = "=" in token
                    args.append({
                        "name": flag_match.group(1),
                        "alias": "",
                        "type": "string" if (takes_value or takes_alias_value) else "flag",
                        "required": False,
                        "default": "",
                        "help": "",
                    })

    if not has_parser:
        if re.search(r"(\$1|\$@|\$\*|\bshift\b)", text):
            return [], False
        return [], True

    seen = set()
    unique = []
    for a in args:
        if a["name"] not in seen:
            seen.add(a["name"])
            unique.append(a)
    return unique, True


def parse_script_arguments(script: Path) -> tuple[list[dict], bool]:
    text = script.read_text(encoding="utf-8", errors="ignore")
    ext = script.suffix.lower()

    if ext == ".ps1":
        return parse_powershell_args(text)
    elif ext == ".py":
        return parse_python_args(text)
    elif ext == ".sh":
        return parse_shell_args(text)
    elif ext in (".js", ".mjs"):
        args = []
        has_parser = False
        is_reliable = True
        if re.search(r'\.(option|requiredOption|argument)\s*\(\s*(?!["\'])', text):
            is_reliable = False

        for m in re.finditer(r'\.(option|requiredOption)\s*\(\s*["\']([^"\']+)["\'](?:\s*,\s*["\']([^"\']*)["\'])?', text):
            has_parser = True
            is_required_call = (m.group(1) == "requiredOption")
            opt_spec = m.group(2).strip()
            help_desc = m.group(3) or ""
            parts = [p.strip() for p in re.split(r"[,|\s]+", opt_spec) if p.strip()]
            flags = [p for p in parts if p.startswith("-")]
            takes_val = any(("<" in p or "[" in p) for p in parts)
            long_flags = [f for f in flags if f.startswith("--")]
            short_flags = [f for f in flags if not f.startswith("--")]
            if long_flags:
                name = long_flags[0]
                aliases = short_flags + long_flags[1:]
            elif short_flags:
                name = short_flags[0]
                aliases = short_flags[1:]
            else:
                continue
            args.append({
                "name": name,
                "alias": ", ".join(aliases),
                "type": "string" if takes_val else "flag",
                "required": is_required_call,
                "default": "",
                "help": sanitize_text(help_desc),
            })
        for m in re.finditer(r'\.argument\s*\(\s*["\']([^"\']+)["\'](?:\s*,\s*["\']([^"\']*)["\'])?', text):
            has_parser = True
            arg_spec = m.group(1).strip()
            help_desc = m.group(2) or ""
            args.append({
                "name": arg_spec,
                "alias": "",
                "type": "string",
                "required": "<" in arg_spec,
                "default": "",
                "help": sanitize_text(help_desc),
            })
        if not has_parser:
            if "process.argv" in text:
                return [], False
            return [], True
        return args, is_reliable
    elif ext == ".php":
        if "Symfony\\Component\\Console" in text:
            args = []
            for m in re.finditer(r'addArgument\s*\(\s*["\']([-\w]+)["\']', text):
                args.append({"name": m.group(1), "alias": "", "type": "string", "required": False, "default": "", "help": ""})
            return args, True
        if "$argv" in text:
            return [], False
        return [], True

    # For scripts without traditional CLI parsers (shell, cmd, etc.),
    # if they have shebang or positional argument handling, consider them reliable
    # if the documentation will be manually written
    if ext in {".sh", ".bash", ".cmd", ".bat"}:
        if text.startswith("#!") or re.search(r"\$[1-9]\b", text):
            return [], True  # Has positional args, reliable for manual docs
        return [], False
    return [], False


def parse_arguments(script: Path) -> list[dict]:
    args, _ = parse_script_arguments(script)
    seen = set()
    unique = []
    for a in args:
        key = (a.get("subcommand", ""), a["name"])
        if key not in seen:
            seen.add(key)
            unique.append(a)
    return unique


# --- Exit Codes, Environment, Side Effects ---


def extract_exit_codes(script: Path) -> list[dict]:
    text = script.read_text(encoding="utf-8", errors="ignore")
    ext = script.suffix.lower()
    codes: list[dict] = []
    has_dynamic = False

    for m in re.finditer(r"(?:sys\.exit|exit|SystemExit)\s*\(?\s*(\d+)\s*\)?", text):
        code = int(m.group(1))
        if all(c.get("code") != code for c in codes):
            codes.append({"code": code})

    usage = re.search(r"Exit(?:\s*codes)?:\s*(.+)", text, re.IGNORECASE)
    if usage:
        for code in re.findall(r"\b(\d+)\b", usage.group(1)):
            value = int(code)
            if all(c.get("code") != value for c in codes):
                codes.append({"code": value})

    if ext == ".py":
        if re.search(r"(?:sys\.exit|raise\s+SystemExit)\s*\(\s*(?!\d+\s*\))([A-Za-z0-9_().]+)\s*\)", text):
            has_dynamic = True
    elif ext in (".sh", ".ps1"):
        if re.search(r"\bexit\s+\$(?!\d\b)[A-Za-z0-9_?]+", text):
            has_dynamic = True

    if has_dynamic:
        codes.append({
            "code": "Динамический",
            "dynamic": True,
            "description": "Определить по коду (динамический код выхода)",
        })

    def sort_key(c: dict):
        cd = c.get("code")
        if isinstance(cd, int):
            return (0, cd)
        return (1, str(cd))

    return sorted(codes, key=sort_key)


def extract_env_vars(script: Path) -> list[str]:
    text = script.read_text(encoding="utf-8", errors="ignore")
    ext = script.suffix.lower()
    if ext == ".py":
        return sorted(set(re.findall(r"os\.environ(?:\.get)?\s*[\[(]\s*[\"']([A-Z_][A-Z0-9_]*)", text)))
    if ext == ".sh":
        assigned = set(re.findall(r"^\s*(?:export\s+)?([A-Z_][A-Z0-9_]*)=", text, re.MULTILINE))
        assigned.update(re.findall(r"for\s+([A-Z_][A-Z0-9_]*)\s+in", text))
        used = set(re.findall(r"\$\{?([A-Z_][A-Z0-9_]*)\}?", text))
        exported = set()
        for line in text.splitlines():
            if re.match(r"\s*export\s+", line):
                exported.update(re.findall(r"\b([A-Z_][A-Z0-9_]*)\b", line))
        internal = {"BASH_SOURCE", "FUNCNAME", "LINENO", "PWD", "OLDPWD", "HOME"}
        return sorted(used - assigned - exported - internal)
    if ext == ".ps1":
        ps_env = set(re.findall(r"\$env:([A-Za-z0-9_]+)", text, re.IGNORECASE))
        return sorted(ps_env)
    return sorted(set(re.findall(r"\$\{?([A-Z_][A-Z0-9_]*)\}?", text)))


def extract_side_effects(script: Path) -> list[str]:
    text = script.read_text(encoding="utf-8", errors="ignore")
    effects = []
    patterns = [
        (r"git\s+(commit|push|merge|checkout|reset)", "git operations"),
        (r"(docker|kubectl|systemctl|service\s+)", "container or service management"),
        (r"(curl|wget|nc\s+|socat\s+|Invoke-WebRequest|Invoke-RestMethod)", "network requests"),
        (r">>?\s*(?=[\"'$~.]|/(?!dev/))|\btee\b|write_text|Set-Content|Out-File", "file writes"),
        (r"(mysql|psql|sqlite)", "database access"),
    ]
    for pattern, label in patterns:
        if re.search(pattern, text):
            effects.append(label)
    return effects


def generate_doc(script: Path) -> str:
    today = date.today().isoformat()
    rel = safe_relpath(script, ROOT)
    args, is_reliable = parse_script_arguments(script)
    codes = extract_exit_codes(script)
    env_vars = extract_env_vars(script)
    effects = extract_side_effects(script)

    if args:
        rows = [
            "| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |",
            "|---|---|---|---|---|---|",
        ]
        for arg in args:
            name = arg.get("name", "")
            subcmd = arg.get("subcommand", "")
            disp_name = f"{subcmd}: {name}" if subcmd else name
            alias = arg.get("alias", "")
            arg_type = arg.get("type", "string")
            req = "да" if arg.get("required") else "нет"
            default = mask_sensitive_default(name, alias, str(arg.get("default", "")), arg.get("help", ""))
            help_text = sanitize_text(arg.get("help", ""))
            rows.append(f"| {disp_name} | {alias} | {arg_type} | {req} | {default} | {help_text} |")
        arg_table = "\n".join(rows)
        if not is_reliable:
            arg_table += "\n\n> Внимание: синтаксис аргументов распознан не полностью (обнаружены динамические или нераспознанные параметры). Требуется ручная сверка по исходному коду."
    elif not is_reliable:
        arg_table = "Определить по коду: синтаксис аргументов не распознан автоматически."
    else:
        arg_table = "Аргументов нет"

    if codes:
        code_rows = ["| Код | Значение | Действие вызывающего |", "|---|---|---|"]
        for code in codes:
            desc = code.get("description", "")
            code_rows.append(f"| {code['code']} | {desc} |  |")
        code_table = "\n".join(code_rows)
    else:
        code_table = "Определить по коду: явных кодов выхода не обнаружено"

    if env_vars:
        env_rows = ["| Переменная | Описание |", "|---|---|"]
        env_rows.extend(f"| {v} |  |" for v in env_vars)
        env_table = "\n".join(env_rows)
    else:
        env_table = "Переменных окружения не обнаружено"

    if effects:
        effects_text = "\n".join(f"- {e}" for e in effects)
    else:
        effects_text = "Определить по коду: автоматический анализ не гарантирует отсутствие побочных эффектов"

    return f"""# Скрипт: `{rel}`

<!-- meta
type: script
status: draft
updated: {today}
related: [../../SKILL.md]
tags: [harness, script, {script.stem}]
-->

## Суть
Заполнить: что делает скрипт и зачем он нужен, 2-4 предложения.

## Когда запускать
Заполнить: кто и в какой ситуации вызывает. Что будет, если запустить не вовремя.

## Аргументы
{arg_table}

## Коды выхода
{code_table}

## Что читает и что пишет
Заполнить: входные файлы, каталоги, база, сеть. Выходные файлы и формат.

## Побочные эффекты
{effects_text}

## Окружение и зависимости
{env_table}

## Примеры
Заполнить: минимум один рабочий вызов и один вызов с необязательными аргументами.

## Ограничения
Заполнить: чего скрипт не делает, где ломается, что не проверяет.

## Связи
Заполнить: кто вызывает, кто зависит, какие документы описывают результат.

## История изменений
- {today}: создан скелет из кода, требуется заполнение агентом
"""


def find_arg_table_row(arg: dict | str, table_text: str) -> tuple[list[str] | None, str]:
    if isinstance(arg, dict):
        name = arg.get("name", "")
        alias_str = arg.get("alias", "")
        subcmd = arg.get("subcommand", "")
    else:
        name = arg
        alias_str = ""
        subcmd = ""

    target_names = {name}
    if alias_str:
        for al in alias_str.split(","):
            al_s = al.strip()
            if al_s:
                target_names.add(al_s)

    for line in table_text.strip().splitlines():
        line = line.strip()
        if not line.startswith("|") or not line.endswith("|"):
            continue
        cols = [c.strip() for c in line.split("|")[1:-1]]
        if not cols or all(set(c) <= {"-", ":", " "} for c in cols):
            continue
        if cols[0].lower() in ("аргумент", "параметр", "имя", "name", "argument"):
            continue

        raw_col0 = cols[0]
        row_subcmd = ""
        # Subcommand prefix detection: "subcmd: --arg" format
        # Only match if colon is followed by space and dash (argument), not inside backticks/quotes
        if ":" in raw_col0 and not ("`" in raw_col0 or '"' in raw_col0 or "'" in raw_col0):
            # Check if format is "subcmd: --arg" or "subcmd: arg"
            parts = raw_col0.split(":", 1)
            if len(parts) == 2 and parts[1].strip().startswith(("-", "--")):
                row_subcmd = parts[0].strip().strip("`").lower()
        elif raw_col0.startswith("[") and "]" in raw_col0:
            row_subcmd = raw_col0[1:raw_col0.index("]")].strip().lower()

        if subcmd:
            if row_subcmd and row_subcmd != subcmd.lower():
                continue
            # Allow rows without subcommand prefix if argument name matches
            # (for flat audit tables that don't repeat subcommand prefix)
            if not row_subcmd and f"{subcmd.lower()}:" not in raw_col0.lower():
                # Check if the argument name itself is in the row
                cell_text_check = cols[0]
                if len(cols) > 1:
                    cell_text_check += " " + cols[1]
                tokens_check = set(re.findall(r"(--?[a-zA-Z0-9_\-\$]+|\b[a-zA-Z0-9_\$]+\b)", cell_text_check))
                stripped_check = {t.lstrip("-") for t in tokens_check if t.startswith("-")}
                tokens_check.update(stripped_check)
                if not (tokens_check & target_names):
                    continue
        else:
            if row_subcmd:
                continue

        cell_text = cols[0]
        if len(cols) > 1:
            cell_text += " " + cols[1]

        # Improved token extraction: include double-dash prefixes and handle subcommand prefixes
        tokens = set(re.findall(r"(--?[a-zA-Z0-9_\-\$]+|\b[a-zA-Z0-9_\$]+\b)", cell_text))
        # Also add stripped versions without leading dashes for matching
        stripped = {t.lstrip("-") for t in tokens if t.startswith("-")}
        tokens.update(stripped)
        if tokens & target_names:
            # Description is in column 5 (6-col table), column 4 (5-col table),
            # or column 1 (2-col audit table).
            desc = cols[5] if len(cols) > 5 else (cols[4] if len(cols) > 4 else (cols[1] if len(cols) > 1 else ""))
            return cols, desc
    return None, ""


def doc_declares_argv_contract(text: str) -> bool:
    """A script reads argv by hand or forwards it verbatim; the doc declares it in meta."""
    meta_match = re.search(r"(?ms)^<!--\s*meta\b(.*?)-->", text)
    if not meta_match:
        return False
    return bool(re.search(r"(?mi)^\s*argv:\s*(?:passthrough|manual)\s*$", meta_match.group(1)))


def audit(script: Path, extra_sections: tuple[str, ...] = ()) -> list[str]:
    doc = doc_path_for(script)
    if not doc:
        return [f"NO_OWNER: {script}"]
    if not doc.is_file():
        return [f"DOC_MISSING: {doc}"]
    text = doc.read_text(encoding="utf-8", errors="ignore")
    errors = []

    m = re.search(r"status:\s*(\S+)", text)
    status = m.group(1) if m else "none"
    if status != "actual":
        errors.append(f"DRAFT_STATUS: {doc} status={status}")

    for section in dict.fromkeys((*SECTIONS, *extra_sections)):
        sec_header_pattern = r"(?m)^" + re.escape(section) + r"\s*$"
        sec_match = re.search(r"(?m)^" + re.escape(section) + r"[ \t]*\r?\n(.*?)(?=^## |\Z)", text, re.DOTALL)
        if not re.search(sec_header_pattern, text):
            errors.append(f"MISSING_SECTION: {doc} {section}")
        elif sec_match:
            sec_content = sec_match.group(1).strip()
            cleaned_sec = re.sub(r"<!--.*?-->", "", sec_content, flags=re.DOTALL).strip()
            if not cleaned_sec:
                errors.append(f"EMPTY_SECTION: {doc} {section}")

    for pattern in DRAFT_PATTERNS:
        if pattern in text:
            errors.append(f"DRAFT_PATTERN: {doc} '{pattern}'")
    if "Заполнить:" in text:
        errors.append(f"PLACEHOLDER: {doc} содержит 'Заполнить:'")

    # Extract ## Аргументы section only
    arg_section_match = re.search(r"(?m)^## Аргументы\s*\(аудит[^\n]*\)[^\n]*\r?\n(.*?)(?=^## |\Z)", text, re.DOTALL)
    if not arg_section_match:
        # Fallback: find last "## Аргументы" section
        matches = list(re.finditer(r"(?m)^## Аргументы[^\n]*\r?\n(.*?)(?=^## |\Z)", text, re.DOTALL))
        if matches:
            arg_section_text = matches[-1].group(1)
        else:
            arg_section_text = ""
    else:
        arg_section_text = arg_section_match.group(1)

    parsed_args, is_reliable = parse_script_arguments(script)
    if not is_reliable and not doc_declares_argv_contract(text):
        errors.append(f"UNRELIABLE_PARSE: {doc} исходный код содержит нераспознанные или динамические аргументы; статус actual недопустим")

    if parsed_args:
        if "Аргументов нет" in arg_section_text:
            errors.append(f"ARG_MISMATCH: {doc} содержит 'Аргументов нет', но скрипт имеет аргументы")
        for arg in parsed_args:
            name = arg["name"]
            cols, desc = find_arg_table_row(arg, arg_section_text)
            if not cols:
                errors.append(f"ARG_MISSING: {doc} {name} (отсутствует строка таблицы)")
            else:
                if not desc or "Заполнить:" in desc:
                    errors.append(f"ARG_DESCRIPTION_MISSING: {doc} отсутствует описание для {name}")
    return errors


def audit_all(scripts: list[Path] | None = None, extra_sections: tuple[str, ...] = ()) -> list[str]:
    if scripts is None:
        scripts = iter_scripts()
    errors = []
    # Check for collisions first
    collisions = detect_script_doc_collisions(scripts)
    for doc, srcs in collisions.items():
        src_names = ", ".join(safe_relpath(s, ROOT) for s in srcs)
        errors.append(f"COLLISION_DETECTED: {safe_relpath(doc, ROOT)} claimed by multiple scripts: {src_names}")

    for script in scripts:
        errors.extend(audit(script, extra_sections))
    for orphan in find_orphan_docs():
        errors.append(f"ORPHAN_DOC: {orphan}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Doc Script")
    parser.add_argument("--script", help="путь к скрипту от корня проекта")
    parser.add_argument(
        "-f", "--force", "--overwrite",
        dest="force",
        action="store_true",
        help="принудительно перезаписать существующий документ",
    )
    parser.add_argument("--all", action="store_true", help="создать скелеты для всех скриптов")
    parser.add_argument("--audit", action="store_true", help="проверить все документы")
    parser.add_argument("--list", action="store_true", help="показать скрипты и пути документов")
    parser.add_argument("--inventory", action="store_true", help="показать классификацию скриптов (entrypoint/library/test)")
    parser.add_argument("--policy-root", help="применить дополнительные обязательные разделы из политики проекта при аудите")
    args = parser.parse_args()

    extra_sections = ()
    if args.policy_root:
        if not args.audit:
            print('ERROR POLICY: --policy-root requires --audit', file=sys.stderr)
            return 2
        loader = Path(__file__).resolve().parents[2] / 'harness-core/scripts/canon_paths.py'
        spec = importlib.util.spec_from_file_location('trusted_doc_policy', loader)
        try:
            if spec is None or spec.loader is None:
                raise ValueError('policy reader unavailable')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            rules = module.load_preliminary_policies(Path(args.policy_root))['component_docs']['rules']
            extra_sections = rules['CD02']['required_sections']
            if any(not section.startswith('## ') for section in extra_sections):
                raise ValueError('invalid required section header')
        except (OSError, ValueError, KeyError, TypeError) as error:
            print(f'ERROR POLICY: {error}', file=sys.stderr)
            return 1

    scripts = iter_scripts()

    if args.inventory:
        all_scripts = iter_all_harness_scripts()
        categories = {"entrypoint": 0, "library": 0, "test": 0, "unknown_owner": 0}
        documented = 0
        missing = 0
        library_reasons = {}
        unknown_owners = []
        for script in all_scripts:
            cat, reason = classify_script(script)
            categories[cat] = categories.get(cat, 0) + 1
            if cat == "library":
                library_reasons.setdefault(reason, []).append(safe_relpath(script, ROOT))
            elif cat == "unknown_owner":
                unknown_owners.append(f"{safe_relpath(script, ROOT)}: {reason}")
            elif cat == "entrypoint":
                doc = doc_path_for(script)
                if doc and doc.is_file():
                    documented += 1
                else:
                    missing += 1
        print(f"Total harness scripts scanned: {len(all_scripts)}")
        print(f"Categories: {categories}")
        print(f"Entrypoints: {categories.get('entrypoint', 0)} (Documented: {documented}, Missing: {missing})")
        if library_reasons:
            print(f"Libraries breakdown: {dict((k, len(v)) for k, v in library_reasons.items())}")
        if unknown_owners:
            print(f"Unknown owners ({len(unknown_owners)}):")
            for u in unknown_owners:
                print(f"  - {u}")
        return 0

    if args.list:
        collisions = detect_script_doc_collisions(scripts)
        if collisions:
            for doc, srcs in collisions.items():
                print(f"COLLISION: {safe_relpath(doc, ROOT)} -> {[safe_relpath(s, ROOT) for s in srcs]}", file=sys.stderr)
        for script in scripts:
            doc = doc_path_for(script)
            print(f"{safe_relpath(script, ROOT)} -> {safe_relpath(doc, ROOT) if doc else 'NO_OWNER'}")
        return 0

    if args.script:
        script = (ROOT / args.script).resolve()
        if not script.is_file():
            print(f"script not found: {args.script}", file=sys.stderr)
            return 1
        if args.audit:
            errors = audit(script, extra_sections)
            for error in errors:
                print(error, file=sys.stderr)
            return 1 if errors else 0
        owner = skill_root_for(script)
        if not owner:
            print(f"no owner skill for {script}", file=sys.stderr)
            return 1
        doc = doc_path_for(script)
        if not doc:
            print(f"cannot compute doc path for {script}", file=sys.stderr)
            return 1

        is_safe, sec_err = validate_safe_doc_path(doc, owner)
        if not is_safe:
            print(sec_err, file=sys.stderr)
            return 1

        # Check collisions even for single script write across all harness scripts
        collisions = detect_script_doc_collisions(iter_all_harness_scripts())
        if doc in collisions:
            other_srcs = [safe_relpath(s, ROOT) for s in collisions[doc] if s.resolve() != script.resolve()]
            if other_srcs:
                print(f"COLLISION_DETECTED: {safe_relpath(doc, ROOT)} claimed by multiple scripts: {[safe_relpath(script, ROOT)] + other_srcs}", file=sys.stderr)
                return 1

        if doc.exists():
            existing_script = script_path_for_doc(doc)
            if existing_script and existing_script.resolve() != script.resolve():
                print(f"COLLISION_OVERWRITE_PREVENTED: {safe_relpath(doc, ROOT)} belongs to {safe_relpath(existing_script, ROOT)}, cannot overwrite from {safe_relpath(script, ROOT)} even with --force", file=sys.stderr)
                return 1
            if not args.force:
                print(f"DOCUMENT_EXISTS: {safe_relpath(doc, ROOT)}. Use --force or --overwrite to overwrite.", file=sys.stderr)
                return 1

        atomic_write_text(doc, generate_doc(script), owner=owner)
        print(safe_relpath(doc, ROOT))
        return 0

    if args.all:
        created = 0
        collisions = detect_script_doc_collisions(scripts)
        if collisions:
            for doc, srcs in collisions.items():
                print(f"COLLISION: {safe_relpath(doc, ROOT)} claimed by {srcs}", file=sys.stderr)
            return 1

        for script in scripts:
            owner = skill_root_for(script)
            if not owner:
                continue
            doc = doc_path_for(script)
            if not doc:
                continue
            is_safe, _ = validate_safe_doc_path(doc, owner)
            if not is_safe:
                continue
            if doc.exists() and not args.force:
                continue
            atomic_write_text(doc, generate_doc(script), owner=owner)
            created += 1
        print(f"created {created} docs")
        return 0

    if args.audit:
        errors = audit_all(scripts, extra_sections)
        if errors:
            for error in errors:
                print(error, file=sys.stderr)
            print(f"errors: {len(errors)}", file=sys.stderr)
            return 1
        print(f"OK: {len(scripts)} scripts")
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
