#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""
Deterministic static & structural pre-auditor for Agent Skills & companion configs (v3.1).
Strictly zero semantic prose heuristics (all meaning/tone/fluff/SCAR/CSO judgments stay with the LLM).
Supports:
- Standard skill packages (SKILL.md + recursive child skills + subagents/scripts/references/evals)
- 17-target cross-agent format compliance & auto-discovery compatibility matrix (Cursor, Antigravity, Claude Code, Kilo Code, OpenCode, Pi Agent, Qoder, Codex, GitHub Copilot, Windsurf, Cline, Roo Code, Gemini CLI, Kiro, Amp, OpenClaw, agentskills.io)
- Packaged .skill / .zip archives (Zip-Slip & Zip-Bomb guarded)
- Standalone AGENTS.md / CLAUDE.md (structure, bloat, volatile prefixes)
- Cursor .cursor/rules/*.mdc (globs, alwaysApply, description)
- Standalone agent profiles (.claude/agents/*.md, .codex/agents/*.toml, .cursor/agents/*.md)
- Plugin bundles (.claude-plugin/plugin.json) & companion configs (openai.yaml, .mcp.json, hooks.json)
- Skill fleets (--target-type fleet: startup index budget, trigger overlap, Cross-Skill Lethal Trifecta)
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import struct
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

# Optional PyYAML; falls back cleanly to stdlib parser if unavailable
try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover
    tomllib = None  # type: ignore


CORE_FRONTMATTER_FIELDS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "allowed-tools",
}

OPENCODE_RECOGNIZED_FRONTMATTER = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
}

NON_CANONICAL_SKILL_SUBDIRS = {
    "resources": "references",
    "docs": "references",
    "examples": "references",
    "templates": "assets",
}

# Verified 2026 agent skill specifications & discovery paths (agentskills.io + vercel-labs/skills + primary docs)
AGENT_COMPATIBILITY_PROFILES: dict[str, dict[str, Any]] = {
    "agentskills_core": {
        "display_name": "Agent Skills Spec (agentskills.io)",
        "project_paths": [".agents/skills/"],
        "global_path": "client-defined",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": True,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "claude_code": {
        "display_name": "Claude Code",
        "project_paths": [".claude/skills/"],
        "global_path": "~/.claude/skills/",
        "reads_dot_agents": False,
        "name_required": False,
        "description_required": False,
        "strict_name_dir": False,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": True,
        "supports_disable_model_invocation": True,
        "supports_paths_filter": True,
        "supports_when_to_use": True,
        "supports_loadtime_bang": True,
        "strict_metadata_strings": False,
        "project_rules_file": "CLAUDE.md",
    },
    "openai_codex": {
        "display_name": "OpenAI Codex",
        "project_paths": [".agents/skills/", ".codex/skills/"],
        "global_path": "~/.agents/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "cursor": {
        "display_name": "Cursor",
        "project_paths": [".agents/skills/", ".cursor/skills/", ".claude/skills/", ".codex/skills/"],
        "global_path": "~/.cursor/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": False,
        "supports_context_fork": False,
        "supports_disable_model_invocation": True,
        "supports_paths_filter": True,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "antigravity": {
        "display_name": "Google Antigravity IDE/CLI",
        "project_paths": [".agents/skills/", ".agent/skills/"],
        "global_path": "~/.gemini/config/skills/",
        "reads_dot_agents": True,
        "name_required": False,
        "description_required": True,
        "strict_name_dir": False,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "kilo_code": {
        "display_name": "Kilo Code",
        "project_paths": [".agents/skills/", ".kilocode/skills/", ".kilo/skills/"],
        "global_path": "~/.kilo/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "opencode": {
        "display_name": "OpenCode",
        "project_paths": [".agents/skills/", ".opencode/skills/", ".claude/skills/"],
        "global_path": "~/.config/opencode/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": False,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": True,
        "project_rules_file": "AGENTS.md",
    },
    "pi_agent": {
        "display_name": "Pi Agent (pi-coding-agent)",
        "project_paths": [".agents/skills/", ".pi/skills/"],
        "global_path": "~/.pi/agent/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": False,
        "supports_context_fork": False,
        "supports_disable_model_invocation": True,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "qoder": {
        "display_name": "Qoder IDE/CLI",
        "project_paths": [".qoder/skills/"],
        "global_path": "~/.qoder/skills/",
        "reads_dot_agents": False,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "github_copilot": {
        "display_name": "GitHub Copilot",
        "project_paths": [".agents/skills/", ".github/skills/"],
        "global_path": "~/.copilot/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "windsurf": {
        "display_name": "Windsurf (Cascade)",
        "project_paths": [".agents/skills/", ".windsurf/skills/"],
        "global_path": "~/.codeium/windsurf/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": True,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "cline": {
        "display_name": "Cline",
        "project_paths": [".agents/skills/", ".cline/skills/", ".clinerules/skills/", ".claude/skills/"],
        "global_path": "~/.cline/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "roo_code": {
        "display_name": "Roo Code",
        "project_paths": [".agents/skills/", ".roo/skills/"],
        "global_path": "~/.roo/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "gemini_cli": {
        "display_name": "Gemini CLI",
        "project_paths": [".agents/skills/", ".gemini/skills/"],
        "global_path": "~/.gemini/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": False,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "GEMINI.md",
    },
    "kiro": {
        "display_name": "AWS Kiro CLI/IDE",
        "project_paths": [".kiro/skills/"],
        "global_path": "~/.kiro/skills/",
        "reads_dot_agents": False,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": False,
        "enforces_allowed_tools": False,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "amp": {
        "display_name": "Sourcegraph Amp",
        "project_paths": [".agents/skills/", ".claude/skills/"],
        "global_path": "~/.config/agents/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
    "openclaw": {
        "display_name": "OpenClaw",
        "project_paths": ["skills/", ".agents/skills/"],
        "global_path": "~/.openclaw/skills/",
        "reads_dot_agents": True,
        "name_required": True,
        "description_required": True,
        "strict_name_dir": True,
        "strict_6_keys": False,
        "supports_allowed_tools": True,
        "enforces_allowed_tools": True,
        "supports_context_fork": False,
        "supports_disable_model_invocation": False,
        "supports_paths_filter": False,
        "supports_when_to_use": False,
        "supports_loadtime_bang": False,
        "strict_metadata_strings": False,
        "project_rules_file": "AGENTS.md",
    },
}

IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}

VAGUE_SKILL_NAMES = {
    "helper",
    "helpers",
    "util",
    "utils",
    "misc",
    "tool",
    "tools",
    "common",
    "general",
    "stuff",
    "dig",
    "test",
    "skill",
    "agent",
}

TEXT_EXTENSIONS = {
    ".md",
    ".mdc",
    ".txt",
    ".py",
    ".sh",
    ".bash",
    ".zsh",
    ".ts",
    ".tsx",
    ".js",
    ".mjs",
    ".cjs",
    ".rb",
    ".yaml",
    ".yml",
    ".json",
    ".toml",
}

BINARY_BYTECODE_EXTS = {".pyc", ".pyo", ".so", ".dll", ".dylib", ".exe", ".bin"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico"}
MAX_READABLE_BYTES = 1_048_576  # 1 MiB per file safety ceiling
MAX_ARCHIVE_BYTES = 26_214_400  # 25 MiB uncompressed ceiling
MAX_ARCHIVE_FILES = 500

# Popular PyPI & npm packages frequently targeted by typosquatting attacks (SG10)
POPULAR_PACKAGES = (
    "requests", "urllib3", "httpx", "aiohttp", "pydantic", "fastapi", "flask", "django",
    "numpy", "pandas", "scipy", "torch", "transformers", "openai", "anthropic",
    "pyyaml", "cryptography", "boto3", "botocore", "pytest", "ruff", "mypy",
    "beautifulsoup4", "lxml", "pillow", "click", "typer", "rich", "tiktoken",
    "lodash", "express", "axios", "react", "next", "typescript", "zod", "chalk",
    "commander", "dotenv", "ws", "glob", "minimist", "semver", "eslint", "prettier",
    "playwright", "puppeteer", "mcp", "langchain", "litellm", "chromadb",
)

NEGATION_RE = re.compile(
    r"(?i)\b(never|do\s+not|don't|avoid|forbid|prohibit|anti-?pattern|disallowed)\b|(?:запрещ|нельзя|не\s+запускай|избегай|никогда\s+не)"
)

SECRET_PATTERNS = [
    ("OpenAI/Stripe-like secret", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("GitHub PAT", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("AWS Access Key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("Private Key Block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    (
        "Hardcoded Secret Assignment",
        re.compile(
            r"""(?i)\b(api_key|apikey|secret_key|access_token|auth_token|password)\s*[:=]\s*["'][A-Za-z0-9_\-./+=]{12,}["']"""
        ),
    ),
]

ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\ufeff]")
PIPE_SHELL_RE = re.compile(r"(?i)\b(curl|wget)\b[^\n|]{0,200}\|\s*(ba)?sh\b")
REMOTE_INSTR_RE = re.compile(
    r"(?i)\b(curl|wget|fetch)\b[^\n]{0,200}\.(md|txt|prompt|rules)\b"
)
PROMPT_INJ_RE = re.compile(
    r"(?i)(ignore\s+(all\s+)?(previous|prior|above)\s+instructions|disregard\s+system\s+prompt|override\s+your\s+guidelines|you\s+are\s+now\s+in\s+developer\s+mode)"
)
HTML_COMMENT_CMD_RE = re.compile(
    r"<!--[\s\S]*?(?i:ignore|execute|run\s+command|curl|wget|exfiltrate|secret|token|ssh)[\s\S]*?-->"
)
MEM_POISON_RE = re.compile(
    r"(?i)(write|append|modify|edit|echo\s+.*>>?)\s+[^\n]*\b(MEMORY\.md|SOUL\.md|~/\.claude/CLAUDE\.md|~/\.codex/AGENTS\.md)\b"
)
SENSITIVE_PATH_RE = re.compile(
    r"(?i)(~/\.ssh|/\.ssh/|~/\.aws|/\.aws/credentials|id_rsa|id_ed25519|\B\.env\b)"
)
HARDCODED_HOME_RE = re.compile(r"(/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|C:\\\\Users\\\\)")
BACKSLASH_PATH_RE = re.compile(
    r"\b(?:scripts|references|assets|agents|skills)\\[A-Za-z0-9_.\-\\]+"
)
VOLATILE_PREFIX_RE = re.compile(
    r"(?i)(\{\{\s*(now|timestamp|date|datetime|uuid|random)\s*\}\}|\$\(date\b|datetime\.now\(\)|time\.time\(\))"
)
LOADTIME_CMD_RE = re.compile(r"!\s*`([^`\n]{2,140})`")
DIRECT_SCRIPT_INV_RE = re.compile(r"(?<![A-Za-z0-9_/-])(\./scripts/[A-Za-z0-9_.-]+\.(?:sh|py|js|ts))\b")
CLAUDE_VAR_RE = re.compile(r"(\$\{CLAUDE_[A-Z0-9_]+\}|\$ARGUMENTS\b)")
PORTABLE_FALLBACK_HINT_RE = re.compile(
    r"(?i)(<skill[_a-z]*dir>|directory containing|relative to(?:\s+the)?\s+skill|SKILL\.md directory)"
)
CLIENT_HARDCODED_PATH_RE = re.compile(
    r"(~/\.claude/|(?<![A-Za-z0-9_.-])\.claude/(?:skills|commands|agents)/|"
    r"~/\.qoder/|(?<![A-Za-z0-9_.-])\.qoder/(?:skills|rules)/|"
    r"~/\.kilo/|(?<![A-Za-z0-9_.-])\.kilo(?:code)?/(?:skills|rules)/|"
    r"~/\.pi/|(?<![A-Za-z0-9_.-])\.pi/skills/|"
    r"~/\.kiro/|(?<![A-Za-z0-9_.-])\.kiro/(?:skills|agents)/)"
)
VENDOR_TOOL_RE = re.compile(
    r"\b(MultiEdit|TodoWrite|AskUserQuestion|grep_search|run_command|view_file|execute_command|write_to_file|search_files|StrReplace)\b"
)


def _strip_quotes(val: str) -> str:
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]
    return val


def _parse_scalar(val: str) -> Any:
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        if not inner:
            return []
        return [_strip_quotes(item.strip()) for item in inner.split(",") if item.strip()]
    low = val.lower()
    if low == "true":
        return True
    if low == "false":
        return False
    return _strip_quotes(val)


def parse_simple_yaml(raw_yaml: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse YAML frontmatter using PyYAML if present, else a solid stdlib parser (supports | / > blocks & lists)."""
    if yaml is not None:
        try:
            loaded = yaml.safe_load(raw_yaml)
            if loaded is None:
                return {}, None
            if not isinstance(loaded, dict):
                return None, "Frontmatter must deserialize to a YAML mapping/object."
            return loaded, None
        except Exception as exc:  # noqa: BLE001
            return None, f"YAML parse error: {exc}"

    result: dict[str, Any] = {}
    lines = raw_yaml.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent > 0:
            i += 1
            continue
        if ":" not in line:
            return None, f"Line {i + 1}: invalid YAML key/value syntax"
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()

        if val in {"|", "|-", ">", ">-"}:
            block_lines: list[str] = []
            block_indent: int | None = None
            j = i + 1
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip():
                    block_lines.append("")
                    j += 1
                    continue
                n_indent = len(nxt) - len(nxt.lstrip(" "))
                if n_indent == 0:
                    break
                if block_indent is None:
                    block_indent = n_indent
                block_lines.append(nxt[min(block_indent, len(nxt)) :])
                j += 1
            if val.startswith(">"):
                joined = " ".join(part.strip() for part in block_lines if part.strip())
            else:
                joined = "\n".join(block_lines).strip("\n")
            result[key] = joined
            i = j
            continue

        if not val:
            j = i + 1
            child_list: list[Any] = []
            child_map: dict[str, Any] = {}
            is_list = False
            while j < len(lines):
                nxt = lines[j]
                if not nxt.strip() or nxt.lstrip().startswith("#"):
                    j += 1
                    continue
                n_indent = len(nxt) - len(nxt.lstrip(" "))
                if n_indent == 0:
                    break
                stripped = nxt.strip()
                if stripped.startswith("- "):
                    is_list = True
                    child_list.append(_parse_scalar(stripped[2:]))
                elif ":" in stripped:
                    ck, _, cv = stripped.partition(":")
                    child_map[ck.strip()] = _parse_scalar(cv)
                j += 1
            result[key] = child_list if is_list else child_map
            i = j
            continue

        result[key] = _parse_scalar(val)
        i += 1

    return result, None


def extract_frontmatter(text: str) -> tuple[dict[str, Any] | None, str, str | None]:
    """Split Markdown text into (frontmatter_dict, body_text, error)."""
    normalized = text.replace("\r\n", "\n")
    if not normalized.startswith("---\n"):
        return None, normalized, "Missing opening YAML frontmatter delimiter '---'."
    end_match = re.search(r"\n---\s*(\n|$)", normalized[4:])
    if not end_match:
        return None, normalized, "Missing closing YAML frontmatter delimiter '---'."
    raw_yaml = normalized[4 : 4 + end_match.start()]
    body = normalized[4 + end_match.end() :]
    parsed, err = parse_simple_yaml(raw_yaml)
    return parsed, body, err


def estimate_tokens(text: str) -> int:
    words = len(re.findall(r"\S+", text))
    return int(round(words * 1.33))


def damerau_levenshtein(a: str, b: str) -> int:
    """Compute Damerau-Levenshtein edit distance for package typosquatting detection."""
    la, lb = len(a), len(b)
    if abs(la - lb) > 2:
        return 99
    d = [[0] * (lb + 1) for _ in range(la + 1)]
    for i in range(la + 1):
        d[i][0] = i
    for j in range(lb + 1):
        d[0][j] = j
    for i in range(1, la + 1):
        for j in range(1, lb + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + cost)
    return d[la][lb]


def check_package_typosquat(pkg_names: list[str]) -> list[dict[str, Any]]:
    suspects: list[dict[str, Any]] = []
    popular_set = set(POPULAR_PACKAGES)
    for raw in pkg_names:
        base = re.split(r"[<>=!~;\[\s]", raw.strip(), maxsplit=1)[0].lower()
        if not base or len(base) < 4 or base in popular_set:
            continue
        for pop in POPULAR_PACKAGES:
            if abs(len(base) - len(pop)) > 2:
                continue
            dist = damerau_levenshtein(base, pop)
            if 1 <= dist <= 2:
                suspects.append({"package": base, "similar_to": pop, "distance": dist})
                break
    return suspects


def check_markdown_syntax(md_text: str) -> dict[str, Any]:
    """Check balanced fenced code blocks and strip fenced regions for safe structural scanning."""
    in_fence = False
    fence_char = ""
    fence_len = 0
    fence_open_line = 0
    outside_lines: list[tuple[int, str]] = []

    for idx, line in enumerate(md_text.splitlines(), start=1):
        stripped = line.lstrip()
        m = re.match(r"^(`{3,}|~{3,})(.*)$", stripped)
        if m:
            marker = m.group(1)
            tail = m.group(2).strip()
            if not in_fence:
                in_fence = True
                fence_char = marker[0]
                fence_len = len(marker)
                fence_open_line = idx
            elif marker[0] == fence_char and len(marker) >= fence_len and not tail:
                in_fence = False
                fence_char = ""
                fence_len = 0
            continue
        if not in_fence:
            outside_lines.append((idx, line))

    return {
        "unclosed_fence": in_fence,
        "unclosed_fence_line": fence_open_line if in_fence else None,
        "outside_code_lines": outside_lines,
    }


def collect_files_and_coverage(root: Path) -> tuple[list[Path], dict[str, Any], list[dict[str, Any]]]:
    """Walk root without following symlinks; capture symlinks, binaries, and unreadable coverage gaps."""
    files: list[Path] = []
    symlinks: list[dict[str, Any]] = []
    unreadable_or_binary: list[dict[str, Any]] = []
    sec_hits: list[dict[str, Any]] = []
    root_resolved = root.resolve()
    inspected_text_count = 0

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        kept_dirs: list[str] = []
        for d in sorted(dirnames):
            if d in IGNORED_DIRS:
                continue
            dp = Path(dirpath) / d
            if dp.is_symlink():
                rel_d = dp.relative_to(root).as_posix()
                try:
                    target_resolved = dp.resolve()
                    escapes = not str(target_resolved).startswith(str(root_resolved) + os.sep) and target_resolved != root_resolved
                except Exception:  # noqa: BLE001
                    target_resolved = Path("<unresolvable>")
                    escapes = True
                symlinks.append({"file": rel_d, "target": str(target_resolved), "escapes_root": escapes})
                if escapes:
                    sec_hits.append({
                        "rule_id": "SEC-SYMLINK-ESCAPE",
                        "severity": "CRITICAL",
                        "file": rel_d,
                        "line": 1,
                        "snippet": f"Symlink directory points outside skill root: {target_resolved}",
                        "remediation": "Remove symlinks pointing outside the skill root (escape / marketplace cache failure).",
                    })
                continue
            kept_dirs.append(d)
        dirnames[:] = kept_dirs

        for fname in sorted(filenames):
            fp = Path(dirpath) / fname
            rel = fp.relative_to(root).as_posix()
            if fp.is_symlink():
                try:
                    target_resolved = fp.resolve()
                    escapes = not str(target_resolved).startswith(str(root_resolved) + os.sep) and target_resolved != root_resolved
                except Exception:  # noqa: BLE001
                    target_resolved = Path("<unresolvable>")
                    escapes = True
                symlinks.append({"file": rel, "target": str(target_resolved), "escapes_root": escapes})
                if escapes:
                    sec_hits.append({
                        "rule_id": "SEC-SYMLINK-ESCAPE",
                        "severity": "CRITICAL",
                        "file": rel,
                        "line": 1,
                        "snippet": f"Symlink file points outside skill root: {target_resolved}",
                        "remediation": "Replace external symlink with a self-contained file inside the skill directory.",
                    })
                else:
                    unreadable_or_binary.append({"file": rel, "reason": "internal symlink (marketplace cache risk)"})
                continue

            files.append(fp)
            ext = fp.suffix.lower()
            try:
                size = fp.stat().st_size
            except OSError as exc:
                unreadable_or_binary.append({"file": rel, "reason": f"stat error: {exc}"})
                continue

            if ext in BINARY_BYTECODE_EXTS:
                unreadable_or_binary.append({"file": rel, "reason": f"binary/bytecode ({ext})"})
                if ext in {".pyc", ".pyo"}:
                    sec_hits.append({
                        "rule_id": "SEC-PYC-BYTECODE",
                        "severity": "HIGH",
                        "file": rel,
                        "line": 1,
                        "snippet": f"Compiled Python bytecode '{rel}' shipped inside skill.",
                        "remediation": "Remove .pyc/.pyo binaries and ship verifiable Python source only.",
                    })
                continue

            if ext == ".png":
                png_chunks = inspect_png_metadata(fp)
                unreadable_or_binary.append({"file": rel, "reason": f"image binary ({ext})"})
                for chunk_type, preview in png_chunks:
                    if len(preview) > 40 or re.search(r"(?i)(ignore|system|prompt|execute|curl|instruction)", preview):
                        sec_hits.append({
                            "rule_id": "SEC-IMG-METADATA",
                            "severity": "HIGH",
                            "file": rel,
                            "line": 1,
                            "snippet": f"PNG {chunk_type} metadata text ({len(preview)} chars): {preview[:90]}",
                            "remediation": "Strip embedded tEXt/iTXt/zTXt text chunks from PNG assets.",
                        })
                continue

            if ext in IMAGE_EXTS:
                unreadable_or_binary.append({"file": rel, "reason": f"binary image ({ext})"})
                continue

            if ext not in TEXT_EXTENSIONS and fp.name not in {"SKILL.md", "AGENTS.md", "CLAUDE.md", "requirements.txt"}:
                unreadable_or_binary.append({"file": rel, "reason": f"unrecognized/non-text extension '{ext or '<none>'}'"})
                continue

            if size > MAX_READABLE_BYTES:
                unreadable_or_binary.append({"file": rel, "reason": f"exceeds {MAX_READABLE_BYTES} bytes scan cap ({size} B)"})
                continue

            inspected_text_count += 1

    coverage = {
        "complete": len(unreadable_or_binary) == 0,
        "total_files_discovered": len(files) + len(symlinks),
        "inspected_text_files": inspected_text_count,
        "unreadable_or_binary_files": unreadable_or_binary,
        "symlinks": symlinks,
    }
    return files, coverage, sec_hits


def inspect_png_metadata(path: Path) -> list[tuple[str, str]]:
    """Parse PNG chunks cleanly using stdlib struct to detect hidden tEXt/iTXt/zTXt text payloads."""
    hits: list[tuple[str, str]] = []
    try:
        data = path.read_bytes()
    except OSError:
        return hits
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        return hits
    pos = 8
    while pos + 8 <= len(data):
        length = struct.unpack(">I", data[pos : pos + 4])[0]
        chunk_type = data[pos + 4 : pos + 8].decode("ascii", errors="replace")
        payload_start = pos + 8
        payload_end = payload_start + length
        if payload_end > len(data):
            break
        if chunk_type in {"tEXt", "iTXt", "zTXt"}:
            preview = data[payload_start:payload_end].decode("utf-8", errors="replace").replace("\x00", ": ")
            hits.append((chunk_type, preview))
        pos = payload_end + 4
        if chunk_type == "IEND":
            break
    return hits


def extract_references_from_md(md_text: str) -> list[str]:
    refs: list[str] = []
    for m in re.finditer(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)]*)?\)", md_text):
        target = m.group(1).strip()
        if not target.startswith(("http://", "https://", "mailto:")):
            refs.append(target)

    for m in re.finditer(
        r"`((?:references|scripts|assets|agents|skills|evals)/[A-Za-z0-9_.\-/*]+)`",
        md_text,
    ):
        target = m.group(1).strip()
        if "*" not in target:
            refs.append(target)

    seen: set[str] = set()
    unique: list[str] = []
    for r in refs:
        clean = r.lstrip("./")
        if clean not in seen:
            seen.add(clean)
            unique.append(clean)
    return unique


def _extract_pep723_deps(text: str) -> list[str]:
    m = re.search(r"(?ms)^# /// script\s*\n(.*?)^# ///", text)
    if not m:
        return []
    body = "\n".join(ln.lstrip("# ") for ln in m.group(1).splitlines())
    if tomllib is not None:
        try:
            parsed = tomllib.loads(body)
            deps = parsed.get("dependencies", [])
            if isinstance(deps, list):
                return [str(d) for d in deps]
        except Exception:  # noqa: BLE001
            pass
    dm = re.search(r"dependencies\s*=\s*\[(.*?)\]", body, re.DOTALL)
    if not dm:
        return []
    return [x.strip().strip("\"'") for x in dm.group(1).split(",") if x.strip()]


def _call_qualname(node: ast.Call) -> str:
    f = node.func
    if isinstance(f, ast.Name):
        return f.id
    if isinstance(f, ast.Attribute):
        parts: list[str] = [f.attr]
        cur = f.value
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return ""


def _analyze_python_taint(tree: ast.AST) -> list[dict[str, Any]]:
    """Intraprocedural AST source->sink check for env/secret reads paired with network/exec sinks."""
    net_sinks = {
        "requests.post", "requests.get", "requests.put", "requests.request",
        "urllib.request.urlopen", "httpx.post", "httpx.get", "httpx.Client",
        "http.client.HTTPConnection", "http.client.HTTPSConnection", "socket.connect",
    }
    exec_sinks = {"os.system", "subprocess.run", "subprocess.Popen", "subprocess.call", "eval", "exec"}
    flows: list[dict[str, Any]] = []

    for fn in [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]:
        sources: set[str] = set()
        sinks: set[str] = set()
        for node in ast.walk(fn):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
                if node.value.id == "os" and node.attr == "environ":
                    sources.add("os.environ")
            elif isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute):
                if isinstance(node.value.value, ast.Name) and node.value.value.id == "os" and node.value.attr == "environ":
                    sources.add("os.environ[]")
            elif isinstance(node, ast.Call):
                q = _call_qualname(node)
                if q in {"os.getenv", "os.environ.get", "Path.home", "os.path.expanduser"}:
                    sources.add(q)
                if q == "open":
                    for arg in node.args[:1]:
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and SENSITIVE_PATH_RE.search(arg.value):
                            sources.add(f"open({arg.value})")
                if q in net_sinks or any(q.endswith("." + ns.split(".")[-1]) and ns.split(".")[0] in q for ns in net_sinks):
                    sinks.add(q)
                elif q in exec_sinks:
                    sinks.add(q)
        if sources and sinks:
            flows.append({"function": fn.name, "sources": sorted(sources), "sinks": sorted(sinks)})
    return flows


def inspect_script(path: Path, rel_path: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    non_comment_lines = [
        ln
        for ln in text.splitlines()
        if not ln.lstrip().startswith(("#", 'r"', "r'", '"remediation"', '"snippet"'))
    ]
    code_body = "\n".join(non_comment_lines)
    ext = path.suffix.lower()

    syntax_ok = True
    syntax_error: str | None = None
    imports: list[str] = []
    function_count = 0
    regex_call_count = 0
    max_string_literal_chars = 0
    taint_flows: list[dict[str, Any]] = []
    pep723_deps = _extract_pep723_deps(text) if ext == ".py" else []

    if ext == ".py":
        try:
            tree = ast.parse(text, filename=rel_path)
            imp_set: set[str] = set()
            compiled_vars: set[str] = set()
            re_methods = {"compile", "search", "match", "findall", "finditer", "sub", "fullmatch"}
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                    f = node.value.func
                    if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id == "re" and f.attr == "compile":
                        for t in node.targets:
                            if isinstance(t, ast.Name):
                                compiled_vars.add(t.id)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imp_set.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imp_set.add(node.module.split(".")[0])
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    function_count += 1
                elif isinstance(node, ast.Call):
                    if (
                        isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and (
                            (node.func.value.id == "re" and node.func.attr in re_methods)
                            or (node.func.value.id in compiled_vars and node.func.attr in re_methods)
                        )
                    ):
                        regex_call_count += 1
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    max_string_literal_chars = max(max_string_literal_chars, len(node.value))
            imports = sorted(imp_set)
            taint_flows = _analyze_python_taint(tree)
        except SyntaxError as exc:
            syntax_ok = False
            syntax_error = f"Line {exc.lineno}: {exc.msg}"
    else:
        regex_call_count = len(re.findall(r"\b(?:new RegExp|RegExp|grep|sed|awk)\b", code_body))
        function_count = len(re.findall(r"\b(?:function\s+\w+|const\s+\w+\s*=\s*\(|\w+\s*\(\)\s*\{)", code_body))

    typosquat_suspects = check_package_typosquat(pep723_deps)
    has_shebang_or_pep723 = text.startswith("#!") or "# /// script" in text
    has_help = bool(
        re.search(r"(--help|argparse|click\.|typer\.|optparse|getopts|Usage:)", text)
    )
    uses_interactive = bool(
        re.search(r"\b(input\s*\(|raw_input\s*\(|getpass\.|read\s+-p\b)", code_body)
    )
    uses_unpinned = bool(
        re.search(
            r"((?:npx|npm|uvx|bunx|deno)\S*@\s*latest|\bpip\s+install\s+(?!-r\b)[^=\n<>~]+\s*$)",
            code_body,
            re.MULTILINE,
        )
    )
    uses_shell_true = bool(
        re.search(r"\bshell\s*=\s*True\b|\bos\.system\s*\(|\beval\s*\(", code_body)
    )
    supports_structured = bool(
        re.search(r"(json\.dumps|csv\.|yaml\.|--format|sys\.stderr)", text)
    )
    has_error_affordance_hints = bool(
        re.search(r"(sys\.stderr|>&2|console\.error)", text)
    )
    return {
        "file": rel_path,
        "language": ext.lstrip("."),
        "lines": len(text.splitlines()),
        "syntax_ok": syntax_ok,
        "syntax_error": syntax_error,
        "imports": imports,
        "function_count": function_count,
        "regex_call_count": regex_call_count,
        "max_string_literal_chars": max_string_literal_chars,
        "pep723_dependencies": pep723_deps,
        "typosquat_suspects": typosquat_suspects,
        "taint_flows": taint_flows,
        "has_shebang_or_pep723": has_shebang_or_pep723,
        "has_help_support": has_help,
        "uses_interactive_input": uses_interactive,
        "uses_unpinned_install": uses_unpinned,
        "uses_shell_true_or_eval": uses_shell_true,
        "supports_structured_output": supports_structured,
        "has_error_affordance_hints": has_error_affordance_hints,
    }


def inspect_evals(path: Path, rel_path: str) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        data = json.loads(text)
        if isinstance(data, list):
            count = len(data)
        elif isinstance(data, dict) and isinstance(data.get("evals"), list):
            count = len(data["evals"])
        else:
            count = 1
        return {"file": rel_path, "valid_json": True, "case_count": count, "error": None}
    except Exception as exc:  # noqa: BLE001
        return {"file": rel_path, "valid_json": False, "case_count": 0, "error": str(exc)}


def inspect_ecosystem_configs(root: Path, rel_files: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, str]]]:
    """Validate companion ecosystem manifests: openai.yaml, .mcp.json, hooks.json, plugin.json, package.json, requirements.txt."""
    checks: list[dict[str, Any]] = []
    sec_hits: list[dict[str, Any]] = []
    smells: list[dict[str, str]] = []

    for rel in rel_files:
        fp = root / rel
        name = Path(rel).name.lower()
        if rel == "agents/openai.yaml" or name == "openai.yaml":
            raw = fp.read_text(encoding="utf-8", errors="replace")
            parsed, err = parse_simple_yaml(raw)
            notes: list[str] = []
            if err or not isinstance(parsed, dict):
                smells.append({"code": "CONFIG-PARSE-ERR", "severity": "error", "file": rel, "message": err or "Invalid openai.yaml"})
                checks.append({"file": rel, "kind": "openai.yaml", "valid": False, "notes": [err or "parse error"]})
            else:
                iface = parsed.get("interface") if isinstance(parsed.get("interface"), dict) else {}
                if not iface.get("display_name") and not iface.get("short_description"):
                    notes.append("openai.yaml lacks interface.display_name / short_description.")
                checks.append({"file": rel, "kind": "openai.yaml", "valid": True, "notes": notes})

        elif name in {".mcp.json", "mcp.json", "hooks.json", "plugin.json", "marketplace.json"}:
            raw = fp.read_text(encoding="utf-8", errors="replace")
            try:
                data = json.loads(raw)
                notes = []
                if name in {".mcp.json", "mcp.json"}:
                    servers = data.get("mcpServers", {}) if isinstance(data, dict) else {}
                    if isinstance(servers, dict):
                        for sname, sdef in servers.items():
                            cmd = json.dumps(sdef)
                            if "@latest" in cmd:
                                notes.append(f"MCP server '{sname}' uses unpinned @latest.")
                                sec_hits.append({
                                    "rule_id": "SEC-UNPINNED-DEP",
                                    "severity": "MEDIUM",
                                    "file": rel,
                                    "line": 1,
                                    "snippet": f"MCP server '{sname}' uses floating @latest.",
                                    "remediation": "Pin exact MCP server package version.",
                                })
                checks.append({"file": rel, "kind": name, "valid": True, "notes": notes})
            except Exception as exc:  # noqa: BLE001
                smells.append({"code": "CONFIG-PARSE-ERR", "severity": "error", "file": rel, "message": f"Invalid JSON in {rel}: {exc}"})
                checks.append({"file": rel, "kind": name, "valid": False, "notes": [str(exc)]})

        elif name == "package.json":
            raw = fp.read_text(encoding="utf-8", errors="replace")
            try:
                pkg = json.loads(raw)
                scripts = pkg.get("scripts", {}) if isinstance(pkg, dict) else {}
                deps = list((pkg.get("dependencies") or {}).keys()) + list((pkg.get("devDependencies") or {}).keys())
                for lcycle in ("preinstall", "install", "postinstall", "prepare"):
                    if isinstance(scripts, dict) and lcycle in scripts:
                        sec_hits.append({
                            "rule_id": "SEC-PKG-LIFECYCLE",
                            "severity": "HIGH",
                            "file": rel,
                            "line": 1,
                            "snippet": f"npm lifecycle script '{lcycle}': {str(scripts[lcycle])[:100]}",
                            "remediation": "Remove automatic npm lifecycle scripts from skill directories or require explicit execution.",
                        })
                for ts in check_package_typosquat(deps):
                    sec_hits.append({
                        "rule_id": "SEC-TYPOSQUAT",
                        "severity": "HIGH",
                        "file": rel,
                        "line": 1,
                        "snippet": f"Package '{ts['package']}' closely resembles '{ts['similar_to']}' (distance {ts['distance']}).",
                        "remediation": "Verify package spelling against official registry.",
                    })
                checks.append({"file": rel, "kind": "package.json", "valid": True, "notes": []})
            except Exception as exc:  # noqa: BLE001
                checks.append({"file": rel, "kind": "package.json", "valid": False, "notes": [str(exc)]})

        elif name == "requirements.txt":
            raw = fp.read_text(encoding="utf-8", errors="replace")
            pkgs = [ln.strip() for ln in raw.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
            for ts in check_package_typosquat(pkgs):
                sec_hits.append({
                    "rule_id": "SEC-TYPOSQUAT",
                    "severity": "HIGH",
                    "file": rel,
                    "line": 1,
                    "snippet": f"Requirement '{ts['package']}' closely resembles '{ts['similar_to']}' (distance {ts['distance']}).",
                    "remediation": "Verify Python dependency name on PyPI.",
                })
            checks.append({"file": rel, "kind": "requirements.txt", "valid": True, "notes": []})

        if name == "conftest.py" or re.match(r"^(test_.*\.py|.*\.test\.[jt]s|.*\.spec\.[jt]s)$", name):
            if not rel.startswith(("evals/", "tests/")):
                sec_hits.append({
                    "rule_id": "SEC-AUTO-EXEC-TEST",
                    "severity": "HIGH",
                    "file": rel,
                    "line": 1,
                    "snippet": f"Auto-discovered test hook '{rel}' outside evals/tests/ may execute automatically during pytest/npm test.",
                    "remediation": "Move fixtures into evals/ or verify non-malicious side effects.",
                })

    return checks, sec_hits, smells


def scan_security(root: Path, files: list[Path]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for fpath in files:
        if fpath.suffix.lower() not in TEXT_EXTENSIONS and fpath.name not in {"SKILL.md", "AGENTS.md", "CLAUDE.md"}:
            continue
        rel = fpath.relative_to(root).as_posix() if fpath != root else fpath.name
        try:
            if fpath.stat().st_size > MAX_READABLE_BYTES:
                continue
        except OSError:
            continue
        text = fpath.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()

        if ZERO_WIDTH_RE.search(text):
            findings.append(
                {
                    "rule_id": "SEC-PROMPT-INJ",
                    "severity": "CRITICAL",
                    "file": rel,
                    "line": 1,
                    "snippet": "Hidden zero-width Unicode control characters detected.",
                    "remediation": "Strip zero-width/bidi characters immediately.",
                }
            )

        for m in HTML_COMMENT_CMD_RE.finditer(text):
            line_no = text[: m.start()].count("\n") + 1
            findings.append(
                {
                    "rule_id": "SEC-PROMPT-INJ",
                    "severity": "CRITICAL",
                    "file": rel,
                    "line": line_no,
                    "snippet": m.group(0)[:120].replace("\n", " "),
                    "remediation": "Remove hidden instructions inside HTML comments.",
                }
            )

        for idx, line in enumerate(lines, start=1):
            is_prohibition = bool(NEGATION_RE.search(line))
            if PIPE_SHELL_RE.search(line) and not is_prohibition:
                findings.append(
                    {
                        "rule_id": "SEC-PIPE-SHELL",
                        "severity": "CRITICAL",
                        "file": rel,
                        "line": idx,
                        "snippet": line.strip()[:140],
                        "remediation": "Never pipe remote URLs to shell; bundle audited local scripts.",
                    }
                )
            if REMOTE_INSTR_RE.search(line) and not is_prohibition:
                findings.append(
                    {
                        "rule_id": "SEC-REMOTE-INSTR",
                        "severity": "CRITICAL",
                        "file": rel,
                        "line": idx,
                        "snippet": line.strip()[:140],
                        "remediation": "Vendor instructions locally instead of fetching prompts at runtime.",
                    }
                )
            if PROMPT_INJ_RE.search(line) and not is_prohibition:
                findings.append(
                    {
                        "rule_id": "SEC-PROMPT-INJ",
                        "severity": "CRITICAL",
                        "file": rel,
                        "line": idx,
                        "snippet": line.strip()[:140],
                        "remediation": "Remove role/instruction override phrasing.",
                    }
                )
            if MEM_POISON_RE.search(line) and not is_prohibition:
                findings.append(
                    {
                        "rule_id": "SEC-MEM-POISON",
                        "severity": "CRITICAL",
                        "file": rel,
                        "line": idx,
                        "snippet": line.strip()[:140],
                        "remediation": "Skills must not silently rewrite persistent agent memory files.",
                    }
                )
            for label, pat in SECRET_PATTERNS:
                if pat.search(line):
                    findings.append(
                        {
                            "rule_id": "SEC-SECRET-LEAK",
                            "severity": "CRITICAL",
                            "file": rel,
                            "line": idx,
                            "snippet": f"{label} pattern matched",
                            "remediation": "Remove hardcoded credential and read from runtime secret vault/env.",
                        }
                    )
            if (
                SENSITIVE_PATH_RE.search(line)
                and not is_prohibition
                and re.search(r"(?i)\b(curl|wget|post|upload|send|requests\.|urllib|http)\b", line)
            ):
                findings.append(
                    {
                        "rule_id": "SEC-EXFIL-VECTOR",
                        "severity": "CRITICAL",
                        "file": rel,
                        "line": idx,
                        "snippet": line.strip()[:140],
                        "remediation": "Sensitive path combined with network action detected.",
                    }
                )
            elif SENSITIVE_PATH_RE.search(line) and not is_prohibition:
                findings.append(
                    {
                        "rule_id": "SEC-SENSITIVE-ACCESS",
                        "severity": "HIGH",
                        "file": rel,
                        "line": idx,
                        "snippet": line.strip()[:140],
                        "remediation": "Avoid referencing raw .env/.ssh/.aws files directly unless strictly scoped and justified.",
                    }
                )
            if (
                fpath.suffix.lower() in {".py", ".sh", ".js", ".ts"}
                and not is_prohibition
                and not line.lstrip().startswith('"remediation":')
                and re.search(r"\bshell\s*=\s*True\b|\bos\.system\s*\(", line)
            ):
                findings.append(
                    {
                        "rule_id": "SEC-EVAL-EXEC",
                        "severity": "HIGH",
                        "file": rel,
                        "line": idx,
                        "snippet": line.strip()[:140],
                        "remediation": "Use argument arrays (subprocess.run([...], shell=False)) instead of shell=True.",
                    }
                )

    return findings


def _compute_capability_profile(combined_text: str, allowed_tools: str) -> dict[str, bool]:
    """Extract deterministic capability markers for SG09 Cross-Skill Privilege Chaining."""
    low_tools = allowed_tools.lower()
    untrusted_in = bool(
        re.search(r"(?i)\b(webfetch|websearch|github|issue|pr|pull request|external|http|scrape|mcp)\b", combined_text)
        or "webfetch" in low_tools
    )
    sensitive_rd = bool(
        SENSITIVE_PATH_RE.search(combined_text)
        or re.search(r"(?i)\b(os\.environ|os\.getenv|\.ssh|\.aws|keychain|secret|credential)\b", combined_text)
    )
    net_egress = bool(
        re.search(r"(?i)\b(curl|wget|requests\.(post|put|get)|urllib|httpx|socket\.connect|webhook|upload)\b", combined_text)
        or "webfetch" in low_tools
    )
    return {
        "untrusted_input": untrusted_in,
        "sensitive_read": sensitive_rd,
        "network_egress": net_egress,
    }


def inspect_subagent_contexts_and_wiring(
    root: Path,
    fm_dict: dict[str, Any],
    subagent_files: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Inspect subagent structural profiles and deterministic context:fork target wiring."""
    subagent_checks: list[dict[str, Any]] = []
    smells: list[dict[str, str]] = []

    if str(fm_dict.get("context", "")).lower() == "fork":
        agent_ref = str(fm_dict.get("agent", "")).strip()
        builtins = {"explore", "plan", "general-purpose", "bash", "browser"}
        subagent_stems = {Path(p).stem.lower() for p in subagent_files}
        if agent_ref and agent_ref.lower() not in builtins and agent_ref.lower() not in subagent_stems:
            smells.append({
                "code": "CONTRA",
                "severity": "error",
                "file": "SKILL.md",
                "message": f"Structural contradiction: context: fork references agent '{agent_ref}', which is neither built-in nor defined in subagent files.",
            })

    for sf in subagent_files:
        p = root / sf
        text = p.read_text(encoding="utf-8", errors="replace")
        sf_fm: dict[str, Any] = {}
        sf_body = text
        if p.suffix.lower() == ".toml" and tomllib is not None:
            try:
                sf_fm = tomllib.loads(text)
            except Exception:  # noqa: BLE001
                sf_fm = {}
            has_scoped_tools = "sandbox_mode" in sf_fm or "tools" in sf_fm
            is_ro = sf_fm.get("sandbox_mode") == "read-only"
            has_max_turns = "max_turns" in sf_fm or "max_threads" in sf_fm
            has_skills = bool(sf_fm.get("skills"))
            has_omit_claude = False
        else:
            parsed, sf_body, _ = extract_frontmatter(text)
            sf_fm = parsed if isinstance(parsed, dict) else {}
            tools_str = str(sf_fm.get("tools", ""))
            disallowed_str = str(sf_fm.get("disallowedTools", ""))
            has_scoped_tools = bool(tools_str or disallowed_str or "readonly" in sf_fm)
            is_ro = (
                sf_fm.get("readonly") is True
                or (bool(tools_str) and not re.search(r"\b(Write|Edit|MultiEdit)\b", tools_str))
                or bool(re.search(r"\bWrite\b", disallowed_str))
            )
            has_max_turns = "maxTurns" in sf_fm
            has_skills = "skills" in sf_fm
            has_omit_claude = sf_fm.get("omitClaudeMd") is True

        notes: list[str] = []
        if not has_scoped_tools:
            notes.append("No explicit tools/disallowedTools/readonly scope defined.")
        if not has_max_turns:
            notes.append("No maxTurns cap (FM-1.3 loop risk).")

        subagent_checks.append({
            "file": sf,
            "format": "toml" if p.suffix.lower() == ".toml" else "markdown",
            "has_scoped_tools": has_scoped_tools,
            "is_readonly_scoped": is_ro,
            "has_max_turns": has_max_turns,
            "has_skills_preload": has_skills,
            "has_omit_claude_md": has_omit_claude,
            "est_prompt_tokens": estimate_tokens(sf_body),
            "notes": notes,
        })

    return subagent_checks, smells


def _detect_install_scope(root: Path) -> tuple[str, set[str]]:
    """Detect current container directory scope and which agents natively auto-discover it."""
    norm = root.resolve().as_posix()
    if "/.agents/skills/" in norm or norm.endswith("/.agents/skills"):
        native = {k for k, v in AGENT_COMPATIBILITY_PROFILES.items() if k != "agentskills_core" and v["reads_dot_agents"]}
        return "shared-.agents", native
    if "/.agent/skills/" in norm:
        return "legacy-.agent", {"antigravity"}
    if "/.claude/skills/" in norm:
        return "claude-scoped", {"claude_code", "cursor", "opencode", "cline", "amp"}
    if "/.codex/skills/" in norm:
        return "codex-scoped", {"openai_codex", "cursor"}
    if "/.cursor/skills/" in norm:
        return "cursor-scoped", {"cursor"}
    if "/.qoder/skills/" in norm:
        return "qoder-scoped", {"qoder"}
    if "/.kiro/skills/" in norm:
        return "kiro-scoped", {"kiro"}
    if "/.kilocode/skills/" in norm or "/.kilo/skills/" in norm:
        return "kilo-scoped", {"kilo_code"}
    if "/.opencode/skills/" in norm:
        return "opencode-scoped", {"opencode"}
    if "/.pi/skills/" in norm or "/.pi/agent/skills/" in norm:
        return "pi-scoped", {"pi_agent"}
    if "/.windsurf/skills/" in norm:
        return "windsurf-scoped", {"windsurf"}
    if "/.cline/skills/" in norm or "/.clinerules/skills/" in norm:
        return "cline-scoped", {"cline"}
    if "/.roo/skills/" in norm:
        return "roo-scoped", {"roo_code"}
    if "/.gemini/skills/" in norm:
        return "gemini-scoped", {"gemini_cli"}
    if "/.github/skills/" in norm:
        return "copilot-scoped", {"github_copilot"}
    return "source-package", set()


def evaluate_cross_agent_compatibility(
    root: Path,
    fm_err: str | None,
    fm_dict: dict[str, Any],
    name_val: str,
    name_regex_ok: bool,
    name_matches_dir: bool,
    desc_val: str,
    desc_present: bool,
    extension_fields: list[str],
    outside_code_lines: list[tuple[int, str]],
    body_text: str,
    rel_files: list[str],
    subagent_files: list[str],
    load_time_cmds: list[str],
    self_audit_safe: bool = False,
) -> dict[str, Any]:
    """Deterministic cross-agent format compliance & auto-discovery assessment across 17 agents."""
    install_scope, native_discoverers = _detect_install_scope(root)
    is_flat_md = not (root / "SKILL.md").exists()

    # Non-canonical subdirectory names (resources/, docs/, examples/, templates/)
    top_dirs = {p.split("/")[0] for p in rel_files if "/" in p}
    non_canonical_dirs = sorted(
        f"{d}/ (prefer {NON_CANONICAL_SKILL_SUBDIRS[d]}/)"
        for d in top_dirs
        if d in NON_CANONICAL_SKILL_SUBDIRS
    )

    # Strict metadata string check (OpenCode expects map<string, string>)
    non_string_metadata_keys: list[str] = []
    md_obj = fm_dict.get("metadata")
    if isinstance(md_obj, dict):
        for mk, mv in md_obj.items():
            if not isinstance(mv, str):
                non_string_metadata_keys.append(str(mk))

    # Deterministic body portability markers outside code blocks
    unguarded_claude_vars: list[dict[str, Any]] = []
    client_path_locks: list[dict[str, Any]] = []
    vendor_tool_mentions: list[dict[str, Any]] = []

    for lineno, line in outside_code_lines:
        if NEGATION_RE.search(line):
            continue
        for cm in CLAUDE_VAR_RE.finditer(line):
            if not PORTABLE_FALLBACK_HINT_RE.search(line):
                unguarded_claude_vars.append({"line": lineno, "token": cm.group(1)})
        if not self_audit_safe:
            for pm in CLIENT_HARDCODED_PATH_RE.finditer(line):
                client_path_locks.append({"line": lineno, "path": pm.group(1)})
        for vm in VENDOR_TOOL_RE.finditer(line):
            vendor_tool_mentions.append({"line": lineno, "tool": vm.group(1)})

    # Companion equivalence checks (Codex openai.yaml, OpenCode metadata, sequential fallback)
    has_openai_yaml = "agents/openai.yaml" in rel_files
    openai_blocks_implicit = False
    if has_openai_yaml:
        oy_parsed, _ = parse_simple_yaml((root / "agents/openai.yaml").read_text(encoding="utf-8", errors="replace"))
        if isinstance(oy_parsed, dict) and isinstance(oy_parsed.get("policy"), dict):
            openai_blocks_implicit = oy_parsed["policy"].get("allow_implicit_invocation") is False

    opencode_autoinvoke_false = isinstance(md_obj, dict) and str(md_obj.get("opencode/autoinvoke", "")).lower() == "false"
    has_sequential_fallback_hint = bool(
        re.search(r"(?i)(sequential(?:ly)?|fallback|degrades? cleanly|single-threaded|without subagent)", body_text)
    )

    has_context_fork = str(fm_dict.get("context", "")).lower() == "fork"
    has_disable_model_inv = fm_dict.get("disable-model-invocation") is True
    has_allowed_tools = "allowed-tools" in fm_dict and bool(fm_dict.get("allowed-tools"))
    has_paths_filter = "paths" in fm_dict
    has_user_invocable = "user-invocable" in fm_dict
    has_when_to_use = "when_to_use" in fm_dict
    claude_only_fm_keys = sorted(
        k for k in extension_fields
        if k in {"hooks", "agent", "effort", "shell", "disallowed-tools", "argument-hint", "arguments", "background"}
    )

    agents_matrix: dict[str, dict[str, Any]] = {}
    ready_count = 0
    warn_count = 0
    fail_count = 0

    for agent_id, prof in AGENT_COMPATIBILITY_PROFILES.items():
        status = "PASS"
        reasons: list[str] = []

        if fm_err is not None:
            status = "FAIL"
            reasons.append(f"YAML frontmatter error: {fm_err}")
        if is_flat_md:
            status = "FAIL"
            reasons.append("Flat .md skill without <name>/SKILL.md directory loses sibling file references across agents.")
        if prof["name_required"] and (not name_val or not name_regex_ok):
            status = "FAIL"
            reasons.append("Requires valid lowercase kebab-case 'name' in frontmatter.")
        if prof["description_required"] and not desc_present:
            status = "FAIL"
            reasons.append("Requires non-empty 'description'; agent may omit skill if absent.")
        if prof["strict_name_dir"] and not name_matches_dir:
            status = "FAIL"
            reasons.append(f"Frontmatter name '{name_val}' must exactly match directory name '{root.name}'.")

        if status != "FAIL":
            if prof["strict_6_keys"] and extension_fields:
                status = "WARN"
                reasons.append(f"Uses extension frontmatter keys beyond core 6 ({extension_fields}); strict validators/claude.ai uploads may reject them.")
            if agent_id == "opencode":
                ignored_oc = sorted(k for k in fm_dict.keys() if k not in OPENCODE_RECOGNIZED_FRONTMATTER)
                if ignored_oc:
                    status = "WARN"
                    reasons.append(f"OpenCode only parses 5 standard frontmatter keys; ignores {ignored_oc}.")
                if non_string_metadata_keys:
                    status = "WARN"
                    reasons.append(f"OpenCode prefers string-valued metadata; non-string keys: {non_string_metadata_keys}.")
            if has_context_fork and not prof["supports_context_fork"]:
                status = "WARN"
                if has_sequential_fallback_hint or subagent_files:
                    reasons.append("Ignores 'context: fork'; falls back to prose instructions.")
                else:
                    reasons.append("Ignores 'context: fork' with no documented sequential fallback.")
            if has_allowed_tools:
                if not prof["supports_allowed_tools"]:
                    status = "WARN"
                    reasons.append("Does not support 'allowed-tools' frontmatter; mirror tool guardrails in body.")
                elif not prof["enforces_allowed_tools"]:
                    status = "WARN"
                    reasons.append("Does not enforce 'allowed-tools' permissions at runtime; keep safety boundaries in instructions.")
            if has_disable_model_inv and not prof["supports_disable_model_invocation"]:
                if agent_id == "openai_codex" and not openai_blocks_implicit:
                    status = "WARN"
                    reasons.append("Codex ignores 'disable-model-invocation'; add agents/openai.yaml policy.allow_implicit_invocation: false.")
                elif agent_id == "opencode" and not opencode_autoinvoke_false:
                    status = "WARN"
                    reasons.append("OpenCode ignores 'disable-model-invocation'; add metadata.opencode/autoinvoke: 'false' or opencode.json rule.")
                elif agent_id not in {"openai_codex", "opencode"}:
                    status = "WARN"
                    reasons.append("Ignores 'disable-model-invocation: true'; explicit manual-only rule should also be stated in body.")
            if has_paths_filter and not prof["supports_paths_filter"]:
                status = "WARN"
                reasons.append("Ignores 'paths:' glob filter (Claude Code / Cursor only).")
            if has_user_invocable and agent_id not in {"claude_code", "cursor", "agentskills_core"}:
                status = "WARN"
                reasons.append("Ignores 'user-invocable' flag.")
            if has_when_to_use and not prof["supports_when_to_use"]:
                status = "WARN"
                reasons.append("Ignores 'when_to_use' (Claude Code / Windsurf only); merge trigger cues into 'description'.")
            if claude_only_fm_keys and agent_id != "claude_code":
                status = "WARN"
                reasons.append(f"Ignores Claude Code frontmatter fields {claude_only_fm_keys}.")
            if load_time_cmds and not prof["supports_loadtime_bang"]:
                status = "WARN"
                reasons.append("Does not execute inline !`command` load-time injections (Claude Code only).")
            if unguarded_claude_vars and agent_id != "claude_code":
                status = "WARN"
                reasons.append(f"Uses Claude-only vars {[v['token'] for v in unguarded_claude_vars[:2]]} without portable directory fallback hint.")
            if client_path_locks and agent_id != "claude_code":
                status = "WARN"
                reasons.append(f"References client-specific paths {[c['path'] for c in client_path_locks[:2]]} in instructions.")

        if status == "PASS":
            ready_count += 1
        elif status == "WARN":
            warn_count += 1
        else:
            fail_count += 1

        if agent_id == "agentskills_core":
            auto_disc: bool | str = "spec-standard"
        elif install_scope == "source-package":
            auto_disc = "deploy-needed"
        else:
            auto_disc = agent_id in native_discoverers

        agents_matrix[agent_id] = {
            "display_name": prof["display_name"],
            "format_status": status,
            "auto_discovered_from_current_path": auto_disc,
            "project_paths": prof["project_paths"],
            "global_path": prof["global_path"],
            "project_rules_file": prof["project_rules_file"],
            "notes": reasons,
        }

    total_targets = len(AGENT_COMPATIBILITY_PROFILES)
    portability_score_pct = round(((ready_count * 1.0 + warn_count * 0.65) / total_targets) * 100.0, 1)

    recs: list[str] = []
    if install_scope == "source-package":
        recs.append(
            "Universal deployment: place skill in '.agents/skills/<name>/SKILL.md' for 13 native agents, and install/symlink into '.claude/skills/' (Claude Code), '.qoder/skills/' (Qoder), and '.kiro/skills/' (Kiro) — or run 'npx skills add <source> --all'."
        )
    elif install_scope == "shared-.agents":
        recs.append(
            "Skill resides in '.agents/skills/' (auto-discovered by Codex, Cursor, Antigravity, Kilo, OpenCode, Pi, Copilot, Windsurf, Cline, Roo, Gemini CLI, Amp, OpenClaw); also link/install into '.claude/skills/', '.qoder/skills/', and '.kiro/skills/' for Claude Code, Qoder & Kiro."
        )
    else:
        recs.append(
            f"Current location '{install_scope}' narrows auto-discovery ({len(native_discoverers)}/16 agents). Move primary copy to '.agents/skills/' + link Claude/Qoder/Kiro paths via 'npx skills add'."
        )
    if non_canonical_dirs:
        recs.append(f"Non-canonical directories detected: {non_canonical_dirs}. Canonical 'references/' / 'assets/' maximize cross-agent tool discovery.")
    if vendor_tool_mentions:
        uniq_tools = sorted({m["tool"] for m in vendor_tool_mentions})
        recs.append(f"Vendor-specific tool names detected in body ({uniq_tools}); pair with capability wording so non-matching harnesses (Pi, Antigravity, Roo, OpenCode) adapt cleanly.")

    compat_notes = list(recs)
    if has_context_fork:
        compat_notes.append("Uses 'context: fork' (Claude Code only); non-Claude harnesses run sequentially unless explicit subagent instructions exist.")
    if has_allowed_tools:
        compat_notes.append("Cursor, Pi, OpenCode, Gemini CLI, and Kiro do not enforce 'allowed-tools'; keep safety invariants explicit in prose.")

    core_status = agents_matrix["agentskills_core"]["format_status"]
    return {
        "agentskills_core": core_status,
        "claude_code": agents_matrix["claude_code"]["format_status"],
        "openai_codex": agents_matrix["openai_codex"]["format_status"],
        "cursor": agents_matrix["cursor"]["format_status"],
        "notes": compat_notes,
        "universal_portability": {
            "portability_score_pct": portability_score_pct,
            "total_targets": total_targets,
            "format_ready_count": ready_count,
            "format_warn_count": warn_count,
            "format_fail_count": fail_count,
            "detected_install_scope": install_scope,
            "native_discovery_count": len(native_discoverers) if install_scope != "source-package" else None,
            "extra_frontmatter_fields": extension_fields,
            "non_string_metadata_keys": non_string_metadata_keys,
            "non_canonical_dirs": non_canonical_dirs,
            "unguarded_claude_vars": unguarded_claude_vars,
            "client_path_locks": client_path_locks,
            "vendor_tool_mentions": vendor_tool_mentions,
            "recommendations": recs,
        },
        "agents": agents_matrix,
    }


def _detect_cross_skill_chaining(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    """Detect SG09 Lethal Trifecta / Cross-Skill Privilege Chaining across multi-skill sets."""
    if len(profiles) < 2:
        return {"detected": False, "chaining_risk": False, "summary": None}
    in_skills = [p["skill_name"] for p in profiles if p.get("untrusted_input")]
    rd_skills = [p["skill_name"] for p in profiles if p.get("sensitive_read")]
    out_skills = [p["skill_name"] for p in profiles if p.get("network_egress")]
    distinct_union = set(in_skills) | set(rd_skills) | set(out_skills)
    triad = bool(in_skills and rd_skills and out_skills and len(distinct_union) >= 2)
    pair_exfil = bool(rd_skills and out_skills and set(rd_skills) != set(out_skills))
    return {
        "detected": triad or pair_exfil,
        "lethal_trifecta": triad,
        "untrusted_input_skills": in_skills,
        "sensitive_read_skills": rd_skills,
        "network_egress_skills": out_skills,
        "summary": (
            f"SG09 cross-skill privilege chaining across {sorted(distinct_union)}: "
            f"read={rd_skills}, egress={out_skills}, untrusted_in={in_skills}"
            if (triad or pair_exfil)
            else None
        ),
    }


def audit_skill_package(
    target: Path, self_audit_safe: bool = False, recurse_children: bool = True
) -> dict[str, Any]:
    if target.is_file():
        skill_md_path = target
        root = target.parent
    else:
        root = target
        skill_md_path = root / "SKILL.md"

    if not skill_md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found at {skill_md_path}")

    raw_text = skill_md_path.read_text(encoding="utf-8", errors="replace")
    fm, body, fm_err = extract_frontmatter(raw_text)

    all_files, coverage, structural_sec = collect_files_and_coverage(root)
    rel_files = [f.relative_to(root).as_posix() for f in all_files]

    subagent_files = [
        p
        for p in rel_files
        if (
            (p.startswith("agents/") and p.endswith(".md"))
            or ".claude/agents/" in p
            or ".codex/agents/" in p
            or ".cursor/agents/" in p
        )
    ]
    child_skill_files = [
        p for p in rel_files if p != "SKILL.md" and p.endswith("/SKILL.md")
    ]
    reference_files = [p for p in rel_files if p.startswith("references/")]
    script_files = [p for p in rel_files if p.startswith("scripts/")]
    asset_files = [p for p in rel_files if p.startswith("assets/")]
    eval_files = [p for p in rel_files if p.startswith("evals/")]
    config_files = [
        p
        for p in rel_files
        if p.endswith((".mcp.json", "mcp.json", "openai.yaml", "config.toml", "plugin.json", "marketplace.json", "hooks.json", "package.json", "requirements.txt"))
        or ".claude/" in p
        or ".codex/" in p
        or ".cursor/" in p
    ]
    readme_inside = any(Path(p).name.lower() == "readme.md" and Path(p).parent == Path(".") for p in rel_files)

    fm_dict = fm if isinstance(fm, dict) else {}
    name_val = str(fm_dict.get("name", "")).strip()
    desc_val = str(fm_dict.get("description", "")).strip()
    name_regex_ok = bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", name_val))
    name_matches_dir = name_val == root.name if target.is_dir() else True
    desc_len = len(desc_val)
    desc_present = bool(desc_val)
    desc_has_xml = bool(re.search(r"<[a-zA-Z/][^>]*>", desc_val))
    desc_first_250 = desc_val[:250]
    extension_fields = sorted(k for k in fm_dict.keys() if k not in CORE_FRONTMATTER_FIELDS)

    has_fm_hooks = "hooks" in fm_dict and bool(fm_dict.get("hooks"))
    model_override_val = str(fm_dict.get("model", "")).strip() or None

    body_lines = len(body.splitlines())
    body_words = len(re.findall(r"\S+", body))
    body_tokens = estimate_tokens(body)
    raw_bytes = len(raw_text.encode("utf-8"))

    # Markdown syntax & !command load-time check (outside fenced code blocks)
    md_syntax = check_markdown_syntax(body)
    load_time_cmds: list[str] = []
    direct_script_invocations: list[str] = []
    for _, ln in md_syntax["outside_code_lines"]:
        if not NEGATION_RE.search(ln):
            for cm in LOADTIME_CMD_RE.finditer(ln):
                load_time_cmds.append(cm.group(1))
            for dm in DIRECT_SCRIPT_INV_RE.finditer(ln):
                direct_script_invocations.append(dm.group(1))

    # Full package token budget (activation + references + agents)
    ref_tokens_list: list[int] = []
    for rp in reference_files:
        fp = root / rp
        if fp.suffix.lower() in TEXT_EXTENSIONS and fp.stat().st_size <= MAX_READABLE_BYTES:
            ref_tokens_list.append(estimate_tokens(fp.read_text(encoding="utf-8", errors="replace")))
    agents_tokens_total = 0
    for ap in subagent_files:
        fp = root / ap
        if fp.suffix.lower() in TEXT_EXTENSIONS and fp.stat().st_size <= MAX_READABLE_BYTES:
            agents_tokens_total += estimate_tokens(fp.read_text(encoding="utf-8", errors="replace"))
    refs_total_tokens = sum(ref_tokens_list)
    max_ref_tokens = max(ref_tokens_list) if ref_tokens_list else 0
    total_pkg_tokens = body_tokens + refs_total_tokens + agents_tokens_total
    token_budget = {
        "skill_md_tokens": body_tokens,
        "references_total_tokens": refs_total_tokens,
        "max_single_reference_tokens": max_ref_tokens,
        "agents_total_tokens": agents_tokens_total,
        "total_package_tokens": total_pkg_tokens,
        "pct_of_200k_window": round((total_pkg_tokens / 200_000) * 100.0, 2),
    }

    # Link graph
    links_from_skill = extract_references_from_md(body)
    broken_links = [link for link in links_from_skill if not (root / link).exists()]

    managed_dirs = ("references/", "scripts/", "assets/", "agents/")
    linked_set = {l.rstrip("/") for l in links_from_skill}
    orphan_files: list[str] = []
    for rf in rel_files:
        if rf.startswith(managed_dirs):
            if rf not in linked_set and not any(rf.startswith(l + "/") for l in linked_set):
                orphan_files.append(rf)

    nested_chains: list[dict[str, str]] = []
    unclosed_ref_fences: list[str] = []
    for ref_rel in reference_files:
        ref_path = root / ref_rel
        if ref_path.suffix.lower() == ".md":
            ref_text = ref_path.read_text(encoding="utf-8", errors="replace")
            if check_markdown_syntax(ref_text)["unclosed_fence"]:
                unclosed_ref_fences.append(ref_rel)
            for sl in extract_references_from_md(ref_text):
                if (root / sl).exists() and sl not in linked_set and sl != "SKILL.md":
                    nested_chains.append({"from": ref_rel, "to_unlinked_in_skill": sl})

    backslash_paths = BACKSLASH_PATH_RE.findall(raw_text)
    hardcoded_homes = HARDCODED_HOME_RE.findall(raw_text)

    static_smells: list[dict[str, str]] = []
    if name_val in VAGUE_SKILL_NAMES or not name_regex_ok:
        static_smells.append({"code": "USN", "severity": "warning", "file": "SKILL.md", "message": f"Unclear or spec-invalid skill name '{name_val}'."})
    if desc_has_xml:
        static_smells.append({"code": "XID", "severity": "critical", "file": "SKILL.md", "message": "description contains XML-like tags (<...>)."})
    if not desc_val:
        static_smells.append({"code": "CSD", "severity": "error", "file": "SKILL.md", "message": "Missing required description field in frontmatter."})
    if md_syntax["unclosed_fence"]:
        static_smells.append({"code": "MD-UNCLOSED-FENCE", "severity": "error", "file": "SKILL.md", "message": f"Unclosed markdown code fence starting at body line {md_syntax['unclosed_fence_line']}."})
    for uref in unclosed_ref_fences:
        static_smells.append({"code": "MD-UNCLOSED-FENCE", "severity": "error", "file": uref, "message": "Unclosed markdown code fence."})
    if direct_script_invocations:
        static_smells.append({"code": "SCRIPT-EXEC-BIT-TRAP", "severity": "recommendation", "file": "SKILL.md", "message": f"Direct ./scripts invocation ({direct_script_invocations[:2]}) may fail if zip/plugin packaging strips +x bit; prefer explicit interpreter (python3/bash)."})
    if backslash_paths:
        static_smells.append({"code": "BP", "severity": "warning", "file": "SKILL.md", "message": f"Backslash paths detected: {backslash_paths[:3]}"})
    if hardcoded_homes:
        static_smells.append({"code": "PORT-ABS-PATH", "severity": "warning", "file": "SKILL.md", "message": f"Hardcoded user home path detected: {hardcoded_homes[:3]}"})
    if VOLATILE_PREFIX_RE.search("\n".join(body.splitlines()[:40])):
        static_smells.append({"code": "KV-VOLATILE-PREFIX", "severity": "warning", "file": "SKILL.md", "message": "Volatile dynamic timestamp/random token in top instruction prefix may bust KV-cache."})
    if body_lines > 120 and not re.search(r"(?im)(gotcha|warning|caveat|pitfall|caution|подводн|ограничен|важно)", body):
        static_smells.append({"code": "BG", "severity": "recommendation", "file": "SKILL.md", "message": "Advisory: long skill lacks visible caveats/pitfalls callouts."})
    if readme_inside:
        static_smells.append({"code": "README-IN-SKILL", "severity": "recommendation", "file": "README.md", "message": "README.md inside skill directory is discouraged by Anthropic guidelines."})
    if broken_links:
        static_smells.append({"code": "BROKEN-LINKS", "severity": "error", "file": "SKILL.md", "message": f"Broken relative references: {broken_links}"})
    if orphan_files:
        static_smells.append({"code": "ORPHAN-FILES", "severity": "warning", "file": "SKILL.md", "message": f"Files unlinked from SKILL.md: {orphan_files}"})
    if nested_chains:
        static_smells.append({"code": "DEEP-REF-CHAIN", "severity": "warning", "file": "references/", "message": f"References >1 level deep from SKILL.md: {nested_chains}"})

    # Scripts & AST taint / typosquat checks
    script_checks = [inspect_script(root / s, s) for s in script_files if (root / s).suffix.lower() in {".py", ".sh", ".js", ".ts"}]
    script_sec: list[dict[str, Any]] = []
    for sc in script_checks:
        if not sc["syntax_ok"]:
            static_smells.append({"code": "SCRIPT-SYNTAX-ERR", "severity": "error", "file": sc["file"], "message": sc["syntax_error"] or "Syntax error"})
        for ts in sc.get("typosquat_suspects", []):
            script_sec.append({
                "rule_id": "SEC-TYPOSQUAT",
                "severity": "HIGH",
                "file": sc["file"],
                "line": 1,
                "snippet": f"PEP 723 dependency '{ts['package']}' closely resembles '{ts['similar_to']}' (distance {ts['distance']}).",
                "remediation": "Verify PEP 723 dependency spelling on PyPI.",
            })
        for tf in sc.get("taint_flows", []):
            if any("environ" in s or "open(" in s for s in tf["sources"]) and any(
                any(n in sk for n in ("requests", "urllib", "httpx", "socket", "http.client"))
                for sk in tf["sinks"]
            ):
                script_sec.append({
                    "rule_id": "SEC-EXFIL-VECTOR",
                    "severity": "HIGH",
                    "file": sc["file"],
                    "line": 1,
                    "snippet": f"AST source->sink flow in '{tf['function']}': {tf['sources']} -> {tf['sinks']}",
                    "remediation": "Audit dataflow from environment/sensitive files to outbound network sinks.",
                })

    eval_checks = [inspect_evals(root / e, e) for e in eval_files if (root / e).suffix.lower() == ".json"]
    for ec in eval_checks:
        if not ec["valid_json"]:
            static_smells.append({"code": "EVAL-INVALID-JSON", "severity": "error", "file": ec["file"], "message": ec["error"] or "Invalid JSON"})

    # Ecosystem config validation
    eco_checks, eco_sec, eco_smells = inspect_ecosystem_configs(root, rel_files)
    static_smells.extend(eco_smells)

    subagent_context_checks, structural_smells = inspect_subagent_contexts_and_wiring(
        root, fm_dict, subagent_files
    )
    static_smells.extend(structural_smells)

    # Security scan
    if self_audit_safe:
        scan_targets = [
            f
            for f in all_files
            if not any(part in {"references", "evals"} for part in f.relative_to(root).parts)
            and f.relative_to(root).as_posix() not in {"scripts/static_audit.py", "scripts/self_test.py"}
        ]
    else:
        scan_targets = all_files

    security_findings = structural_sec + script_sec + eco_sec + scan_security(root, scan_targets)

    if load_time_cmds and not self_audit_safe:
        security_findings.append({
            "rule_id": "SEC-LOADTIME-EXEC",
            "severity": "HIGH",
            "file": "SKILL.md",
            "line": 1,
            "snippet": f"Inline !`command` template expansion executes at skill load: {load_time_cmds[:2]}",
            "remediation": "Review !`command` expansion carefully or replace with explicit model-invoked script.",
        })
    if has_fm_hooks and not self_audit_safe:
        security_findings.append({
            "rule_id": "SEC-LOADTIME-EXEC",
            "severity": "HIGH",
            "file": "SKILL.md",
            "line": 1,
            "snippet": "Frontmatter declares runtime hooks (PreToolUse/PostToolUse) outside user approval flow.",
            "remediation": "Audit hook shell commands for least-privilege and safety.",
        })

    # Recursive child-skill inspections + Cross-Skill SG09 Capability Profile
    combined_text = raw_text + "\n" + "\n".join(
        (root / p).read_text(encoding="utf-8", errors="replace")
        for p in (subagent_files + reference_files + script_files)
        if (root / p).suffix.lower() in TEXT_EXTENSIONS and (root / p).stat().st_size <= MAX_READABLE_BYTES
    )
    cap_profile = _compute_capability_profile(combined_text, str(fm_dict.get("allowed-tools", "")))
    cap_profile["skill_name"] = name_val or root.name

    child_skill_audits: list[dict[str, Any]] = []
    child_cap_profiles: list[dict[str, Any]] = [cap_profile]
    seen_sec_keys = {(f["rule_id"], f["file"], f["line"]) for f in security_findings}
    if recurse_children and child_skill_files:
        for cs_rel in child_skill_files:
            cs_path = root / cs_rel
            try:
                sub = audit_skill_package(cs_path.parent, self_audit_safe=self_audit_safe, recurse_children=False)
                child_rel_dir = cs_path.parent.relative_to(root).as_posix()
                for csf in sub["security_findings"]:
                    hoisted = dict(csf)
                    hoisted["file"] = f"{child_rel_dir}/{csf['file']}"
                    k = (hoisted["rule_id"], hoisted["file"], hoisted["line"])
                    if k not in seen_sec_keys:
                        seen_sec_keys.add(k)
                        security_findings.append(hoisted)
                if sub.get("capability_profile"):
                    child_cap_profiles.append(sub["capability_profile"])
                child_skill_audits.append(
                    {
                        "path": cs_rel,
                        "skill_name": sub["skill_name"],
                        "lines": sub["inventory"]["skill_md_lines"],
                        "est_tokens": sub["inventory"]["skill_md_est_tokens"],
                        "core_spec_pass": sub["platform_compatibility"]["agentskills_core"] == "PASS",
                        "smell_codes": [s["code"] for s in sub["static_smells"]],
                        "security_count": len(sub["security_findings"]),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                child_skill_audits.append({"path": cs_rel, "error": str(exc), "core_spec_pass": False})

    cross_skill_chaining = _detect_cross_skill_chaining(child_cap_profiles)
    if cross_skill_chaining["detected"]:
        static_smells.append({
            "code": "SG09-PRIVILEGE-CHAIN",
            "severity": "warning",
            "file": "skills/",
            "message": cross_skill_chaining["summary"] or "Cross-skill privilege chaining detected.",
        })

    has_mcp = bool(re.search(r"(?i)\b(mcp|mcpServers|model context protocol|tool_search|defer_loading)\b", combined_text)) or any("mcp" in p.lower() for p in config_files)
    has_subagent_signals = bool(
        subagent_files
        or child_skill_files
        or (str(fm_dict.get("context", "")).lower() == "fork")
    )

    if has_subagent_signals or child_skill_files or (root / ".claude-plugin/plugin.json").exists():
        detected_tier = "Tier 3: Complex Multi-Agent"
    elif has_mcp or len(script_files) > 0 or len(reference_files) >= 2:
        detected_tier = "Tier 2: Tool / Resource-Heavy"
    else:
        detected_tier = "Tier 1: Atomic Single-Workflow"

    if detected_tier == "Tier 1: Atomic Single-Workflow" and body_lines <= 250:
        recommended_path = "Light Single-Context (1 pass)"
    elif not has_subagent_signals and not child_skill_files and body_lines <= 350:
        recommended_path = "Balanced Dual-Pass (Architect + Security/Reliability)"
    else:
        recommended_path = "Full Multi-Agent (5+1 or Sequential Fallback)"

    platform_compat = evaluate_cross_agent_compatibility(
        root=root,
        fm_err=fm_err,
        fm_dict=fm_dict,
        name_val=name_val,
        name_regex_ok=name_regex_ok,
        name_matches_dir=name_matches_dir,
        desc_val=desc_val,
        desc_present=desc_present,
        extension_fields=extension_fields,
        outside_code_lines=md_syntax["outside_code_lines"],
        body_text=body,
        rel_files=rel_files,
        subagent_files=subagent_files,
        load_time_cmds=load_time_cmds,
        self_audit_safe=self_audit_safe,
    )
    up_info = platform_compat["universal_portability"]
    if up_info["non_canonical_dirs"]:
        static_smells.append({
            "code": "PORT-NONCANONICAL-DIR",
            "severity": "recommendation",
            "file": "SKILL.md",
            "message": f"Non-canonical directories {up_info['non_canonical_dirs']}; canonical references/ and assets/ improve cross-agent discovery.",
        })
    if up_info["unguarded_claude_vars"] or up_info["client_path_locks"] or load_time_cmds:
        static_smells.append({
            "code": "PORT-VENDOR-LOCK",
            "severity": "warning",
            "file": "SKILL.md",
            "message": "Claude/client-specific variables, paths, or !`command` expansions detected without portable fallback.",
        })
    if up_info["non_string_metadata_keys"]:
        static_smells.append({
            "code": "PORT-FRONTMATTER-DRIFT",
            "severity": "recommendation",
            "file": "SKILL.md",
            "message": f"Metadata keys {up_info['non_string_metadata_keys']} use non-string values (OpenCode strictly expects string values in metadata).",
        })

    return {
        "schema_version": "3.1.0",
        "target_path": str(root.resolve()),
        "target_type": "plugin-bundle" if (root / ".claude-plugin/plugin.json").exists() else "skill-package",
        "skill_name": name_val or root.name,
        "coverage": coverage,
        "tier_classification": {
            "detected_tier": detected_tier,
            "recommended_audit_path": recommended_path,
            "has_subagents": bool(subagent_files) or has_subagent_signals,
            "has_child_skills": bool(child_skill_files),
            "has_mcp_references": has_mcp,
            "has_scripts": bool(script_files),
            "has_references": bool(reference_files),
            "has_assets": bool(asset_files),
            "has_evals": bool(eval_files),
            "recommend_multi_agent_audit": recommended_path.startswith("Full"),
        },
        "frontmatter": {
            "present": fm is not None,
            "valid_yaml": fm_err is None,
            "yaml_error": fm_err,
            "fields": fm_dict,
            "extension_fields": extension_fields,
            "checks": {
                "name_valid_format": name_regex_ok,
                "name_matches_dir": name_matches_dir,
                "name_length": len(name_val),
                "description_present": bool(desc_val),
                "description_length": desc_len,
                "description_first_250": desc_first_250,
                "description_has_xml_tags": desc_has_xml,
                "has_frontmatter_hooks": has_fm_hooks,
                "has_model_override": model_override_val is not None,
                "model_override_value": model_override_val,
                "load_time_command_expansions": load_time_cmds,
            },
        },
        "inventory": {
            "primary_file": "SKILL.md",
            "skill_md_lines": body_lines,
            "skill_md_bytes": raw_bytes,
            "skill_md_words": body_words,
            "skill_md_est_tokens": body_tokens,
            "token_budget": token_budget,
            "total_files": len(rel_files),
            "subagent_files": subagent_files,
            "child_skill_files": child_skill_files,
            "reference_files": reference_files,
            "script_files": script_files,
            "asset_files": asset_files,
            "eval_files": eval_files,
            "readme_inside_skill": readme_inside,
            "config_files": config_files,
        },
        "capability_profile": cap_profile,
        "cross_skill_chaining": cross_skill_chaining,
        "ecosystem_config_checks": eco_checks,
        "child_skill_audits": child_skill_audits,
        "fleet_analysis": None,
        "link_graph": {
            "links_from_skill_md": links_from_skill,
            "broken_links": broken_links,
            "orphan_files": orphan_files,
            "nested_chain_depth_gt_1": nested_chains,
            "backslash_paths": backslash_paths,
        },
        "static_smells": static_smells,
        "script_checks": script_checks,
        "subagent_context_checks": subagent_context_checks,
        "eval_checks": eval_checks,
        "security_findings": security_findings,
        "platform_compatibility": platform_compat,
    }


def audit_agents_md(file_path: Path) -> dict[str, Any]:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    byte_size = len(text.encode("utf-8"))
    lines = len(text.splitlines())
    est_tokens = estimate_tokens(text)
    smells: list[dict[str, str]] = []

    if VOLATILE_PREFIX_RE.search("\n".join(text.splitlines()[:40])):
        smells.append({"code": "KV-VOLATILE-PREFIX", "severity": "warning", "file": file_path.name, "message": "Volatile timestamp/random token in top instruction prefix breaks KV-cache."})
    if HARDCODED_HOME_RE.search(text):
        smells.append({"code": "PORT-ABS-PATH", "severity": "warning", "file": file_path.name, "message": "Hardcoded user home directory detected."})
    if check_markdown_syntax(text)["unclosed_fence"]:
        smells.append({"code": "MD-UNCLOSED-FENCE", "severity": "error", "file": file_path.name, "message": "Unclosed markdown code fence."})

    sec = scan_security(file_path.parent, [file_path])
    upper_name = file_path.name.upper()
    is_agents_md = upper_name.startswith("AGENTS")
    is_claude_md = upper_name == "CLAUDE.MD"
    is_gemini_md = upper_name == "GEMINI.MD"

    codex_status = "PASS" if is_agents_md else "WARN"
    claude_status = "PASS" if is_claude_md else "WARN"
    notes = []
    if is_agents_md:
        notes.append("Claude Code does not auto-load AGENTS.md without symlink or @AGENTS.md import in CLAUDE.md; Gemini CLI defaults to GEMINI.md.")
    elif is_claude_md:
        notes.append("CLAUDE.md is Claude Code-native; most other agents (Codex, Cursor, OpenCode, Kilo, Pi, Qoder, Antigravity, Copilot, Windsurf) expect AGENTS.md.")
    elif is_gemini_md:
        notes.append("GEMINI.md is Gemini CLI-native; other agents expect AGENTS.md.")

    agents_rules_map: dict[str, dict[str, Any]] = {}
    ready_c = 0
    warn_c = 0
    fail_c = 0
    for aid, prof in AGENT_COMPATIBILITY_PROFILES.items():
        expected = prof["project_rules_file"]
        st = "PASS"
        rs: list[str] = []
        if is_agents_md and expected != "AGENTS.md":
            st = "WARN"
            rs.append(f"Prefers {expected} over AGENTS.md.")
        elif is_claude_md and expected != "CLAUDE.md":
            st = "WARN"
            rs.append(f"Reads {expected} natively instead of CLAUDE.md.")
        elif is_gemini_md and expected != "GEMINI.md":
            st = "WARN"
            rs.append(f"Reads {expected} natively instead of GEMINI.md.")
        if st == "PASS":
            ready_c += 1
        elif st == "WARN":
            warn_c += 1
        else:
            fail_c += 1
        agents_rules_map[aid] = {
            "display_name": prof["display_name"],
            "format_status": st,
            "auto_discovered_from_current_path": st == "PASS",
            "project_rules_file": expected,
            "notes": rs,
        }

    port_pct = round(((ready_c + warn_c * 0.65) / len(AGENT_COMPATIBILITY_PROFILES)) * 100.0, 1)

    return {
        "schema_version": "3.1.0",
        "target_path": str(file_path.resolve()),
        "target_type": "agents-md",
        "skill_name": file_path.name,
        "coverage": {"complete": True, "total_files_discovered": 1, "inspected_text_files": 1, "unreadable_or_binary_files": [], "symlinks": []},
        "tier_classification": {
            "detected_tier": "Tier 1: Project Context File",
            "recommended_audit_path": "Light Single-Context (1 pass)",
            "has_subagents": False,
            "has_child_skills": False,
            "has_mcp_references": bool(re.search(r"(?i)\bmcp\b", text)),
            "has_scripts": False,
            "has_references": False,
            "has_assets": False,
            "has_evals": False,
            "recommend_multi_agent_audit": False,
        },
        "frontmatter": {"present": False, "valid_yaml": True, "yaml_error": None, "fields": {}, "extension_fields": [], "checks": {}},
        "inventory": {"primary_file": file_path.name, "skill_md_lines": lines, "skill_md_bytes": byte_size, "skill_md_words": len(re.findall(r"\S+", text)), "skill_md_est_tokens": est_tokens, "token_budget": {"skill_md_tokens": est_tokens, "references_total_tokens": 0, "max_single_reference_tokens": 0, "agents_total_tokens": 0, "total_package_tokens": est_tokens, "pct_of_200k_window": round((est_tokens / 200_000) * 100.0, 2)}, "total_files": 1, "subagent_files": [], "child_skill_files": [], "reference_files": [], "script_files": [], "asset_files": [], "eval_files": [], "readme_inside_skill": False, "config_files": []},
        "ecosystem_config_checks": [],
        "child_skill_audits": [],
        "fleet_analysis": None,
        "link_graph": {"links_from_skill_md": extract_references_from_md(text), "broken_links": [], "orphan_files": [], "nested_chain_depth_gt_1": [], "backslash_paths": BACKSLASH_PATH_RE.findall(text)},
        "static_smells": smells,
        "script_checks": [],
        "subagent_context_checks": [],
        "eval_checks": [],
        "security_findings": sec,
        "platform_compatibility": {
            "agentskills_core": "PASS",
            "claude_code": claude_status,
            "openai_codex": codex_status,
            "cursor": "PASS" if is_agents_md else "WARN",
            "notes": notes,
            "universal_portability": {
                "portability_score_pct": port_pct,
                "total_targets": len(AGENT_COMPATIBILITY_PROFILES),
                "format_ready_count": ready_c,
                "format_warn_count": warn_c,
                "format_fail_count": fail_c,
                "detected_install_scope": "project-rules-file",
                "recommendations": notes,
            },
            "agents": agents_rules_map,
        },
    }


def audit_cursor_mdc(file_path: Path) -> dict[str, Any]:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    fm, body, fm_err = extract_frontmatter(text)
    fm_dict = fm if isinstance(fm, dict) else {}
    lines = len(body.splitlines())
    est_tokens = estimate_tokens(body)
    smells: list[dict[str, str]] = []
    if fm_err:
        smells.append({"code": "MDC-NO-FRONTMATTER", "severity": "error", "file": file_path.name, "message": fm_err})
    if fm_dict.get("alwaysApply") is True and est_tokens > 1200:
        smells.append({"code": "LSB", "severity": "warning", "file": file_path.name, "message": f"alwaysApply: true rule uses ~{est_tokens} tokens on every turn; scope with globs or description."})
    if not fm_dict.get("alwaysApply") and not fm_dict.get("globs") and not fm_dict.get("description"):
        smells.append({"code": "CSD", "severity": "recommendation", "file": file_path.name, "message": "Rule has neither alwaysApply, globs, nor description (manual @-only activation)."})
    if check_markdown_syntax(body)["unclosed_fence"]:
        smells.append({"code": "MD-UNCLOSED-FENCE", "severity": "error", "file": file_path.name, "message": "Unclosed markdown code fence."})

    sec = scan_security(file_path.parent, [file_path])
    return {
        "schema_version": "3.0.0",
        "target_path": str(file_path.resolve()),
        "target_type": "cursor-mdc",
        "skill_name": file_path.stem,
        "coverage": {"complete": True, "total_files_discovered": 1, "inspected_text_files": 1, "unreadable_or_binary_files": [], "symlinks": []},
        "tier_classification": {
            "detected_tier": "Tier 1: Cursor Rule (.mdc)",
            "recommended_audit_path": "Light Single-Context (1 pass)",
            "has_subagents": False,
            "has_child_skills": False,
            "has_mcp_references": False,
            "has_scripts": False,
            "has_references": False,
            "has_assets": False,
            "has_evals": False,
            "recommend_multi_agent_audit": False,
        },
        "frontmatter": {"present": fm is not None, "valid_yaml": fm_err is None, "yaml_error": fm_err, "fields": fm_dict, "extension_fields": sorted(fm_dict.keys()), "checks": {}},
        "inventory": {"primary_file": file_path.name, "skill_md_lines": lines, "skill_md_bytes": len(text.encode("utf-8")), "skill_md_words": len(re.findall(r"\S+", body)), "skill_md_est_tokens": est_tokens, "token_budget": {"skill_md_tokens": est_tokens, "references_total_tokens": 0, "max_single_reference_tokens": 0, "agents_total_tokens": 0, "total_package_tokens": est_tokens, "pct_of_200k_window": round((est_tokens / 200_000) * 100.0, 2)}, "total_files": 1, "subagent_files": [], "child_skill_files": [], "reference_files": [], "script_files": [], "asset_files": [], "eval_files": [], "readme_inside_skill": False, "config_files": []},
        "ecosystem_config_checks": [],
        "child_skill_audits": [],
        "fleet_analysis": None,
        "link_graph": {"links_from_skill_md": [], "broken_links": [], "orphan_files": [], "nested_chain_depth_gt_1": [], "backslash_paths": []},
        "static_smells": smells,
        "script_checks": [],
        "subagent_context_checks": [],
        "eval_checks": [],
        "security_findings": sec,
        "platform_compatibility": {"agentskills_core": "PASS" if fm_err is None else "FAIL", "claude_code": "WARN", "openai_codex": "WARN", "cursor": "PASS" if fm_err is None else "FAIL", "notes": ["Cursor .mdc frontmatter is client-specific; export core conventions to AGENTS.md or SKILL.md for portability."]},
    }


def audit_agent_profile(file_path: Path) -> dict[str, Any]:
    text = file_path.read_text(encoding="utf-8", errors="replace")
    fm_dict: dict[str, Any] = {}
    fm_err: str | None = None
    body = text
    if file_path.suffix.lower() == ".toml":
        if tomllib is not None:
            try:
                fm_dict = tomllib.loads(text)
            except Exception as exc:  # noqa: BLE001
                fm_err = str(exc)
    else:
        fm, body, fm_err = extract_frontmatter(text)
        fm_dict = fm if isinstance(fm, dict) else {}

    smells: list[dict[str, str]] = []
    if fm_err:
        smells.append({"code": "AGENT-PROFILE-PARSE", "severity": "error", "file": file_path.name, "message": fm_err})
    if not fm_dict.get("description") and not fm_dict.get("developer_instructions"):
        smells.append({"code": "CSD", "severity": "warning", "file": file_path.name, "message": "Agent profile lacks a clear delegation description/instructions."})
    sec = scan_security(file_path.parent, [file_path])

    est_tokens = estimate_tokens(body)
    return {
        "schema_version": "3.0.0",
        "target_path": str(file_path.resolve()),
        "target_type": "agent-profile",
        "skill_name": str(fm_dict.get("name", file_path.stem)),
        "coverage": {"complete": True, "total_files_discovered": 1, "inspected_text_files": 1, "unreadable_or_binary_files": [], "symlinks": []},
        "tier_classification": {
            "detected_tier": "Tier 3: Standalone Agent Profile",
            "recommended_audit_path": "Light Single-Context (1 pass)",
            "has_subagents": True,
            "has_child_skills": False,
            "has_mcp_references": bool(fm_dict.get("mcpServers")),
            "has_scripts": False,
            "has_references": False,
            "has_assets": False,
            "has_evals": False,
            "recommend_multi_agent_audit": False,
        },
        "frontmatter": {"present": bool(fm_dict), "valid_yaml": fm_err is None, "yaml_error": fm_err, "fields": fm_dict, "extension_fields": sorted(fm_dict.keys()), "checks": {}},
        "inventory": {"primary_file": file_path.name, "skill_md_lines": len(body.splitlines()), "skill_md_bytes": len(text.encode("utf-8")), "skill_md_words": len(re.findall(r"\S+", body)), "skill_md_est_tokens": est_tokens, "token_budget": {"skill_md_tokens": est_tokens, "references_total_tokens": 0, "max_single_reference_tokens": 0, "agents_total_tokens": est_tokens, "total_package_tokens": est_tokens, "pct_of_200k_window": round((est_tokens / 200_000) * 100.0, 2)}, "total_files": 1, "subagent_files": [file_path.name], "child_skill_files": [], "reference_files": [], "script_files": [], "asset_files": [], "eval_files": [], "readme_inside_skill": False, "config_files": []},
        "ecosystem_config_checks": [],
        "child_skill_audits": [],
        "fleet_analysis": None,
        "link_graph": {"links_from_skill_md": [], "broken_links": [], "orphan_files": [], "nested_chain_depth_gt_1": [], "backslash_paths": []},
        "static_smells": smells,
        "script_checks": [],
        "subagent_context_checks": [],
        "eval_checks": [],
        "security_findings": sec,
        "platform_compatibility": {"agentskills_core": "PASS" if fm_err is None else "FAIL", "claude_code": "PASS" if file_path.suffix == ".md" else "WARN", "openai_codex": "PASS" if file_path.suffix == ".toml" else "WARN", "cursor": "PASS" if file_path.suffix == ".md" else "WARN", "notes": ["Subagent profile format differs between Claude/Cursor (.md) and Codex (.toml)."]},
    }


def audit_skill_fleet(root: Path, self_audit_safe: bool = False) -> dict[str, Any]:
    skill_md_files = sorted(
        p for p in root.rglob("SKILL.md") if not any(part in IGNORED_DIRS for part in p.parts)
    )
    if not skill_md_files:
        raise FileNotFoundError(f"No SKILL.md files found under fleet root {root}")

    members: list[dict[str, Any]] = []
    desc_tokens_map: list[tuple[str, set[str], str]] = []
    cap_profiles: list[dict[str, Any]] = []
    total_index_chars = 0
    all_sec: list[dict[str, Any]] = []
    smells: list[dict[str, str]] = []
    unreadable_all: list[dict[str, Any]] = []
    symlinks_all: list[dict[str, Any]] = []

    stop_words = {"the", "and", "for", "with", "use", "when", "this", "that", "from", "into", "для", "или", "при", "когда", "что"}

    fleet_ports: list[float] = []
    for smd in skill_md_files:
        res = audit_skill_package(smd.parent, self_audit_safe=self_audit_safe, recurse_children=False)
        sname = res["skill_name"]
        desc = str(res["frontmatter"]["fields"].get("description", ""))
        total_index_chars += len(sname) + len(desc) + 20
        tokens = {
            w
            for w in re.findall(r"[a-zа-яё0-9-]{3,}", desc.lower())
            if w not in stop_words
        }
        desc_tokens_map.append((sname, tokens, smd.relative_to(root).as_posix()))
        if res.get("capability_profile"):
            cap_profiles.append(res["capability_profile"])
        up = res["platform_compatibility"].get("universal_portability") or {}
        if "portability_score_pct" in up:
            fleet_ports.append(float(up["portability_score_pct"]))
        unreadable_all.extend(res["coverage"]["unreadable_or_binary_files"])
        symlinks_all.extend(res["coverage"]["symlinks"])
        members.append(
            {
                "skill_name": sname,
                "path": smd.relative_to(root).as_posix(),
                "tier": res["tier_classification"]["detected_tier"],
                "lines": res["inventory"]["skill_md_lines"],
                "description_chars": len(desc),
                "core_spec_pass": res["platform_compatibility"]["agentskills_core"] == "PASS",
                "portability_score_pct": up.get("portability_score_pct"),
                "smell_codes": [s["code"] for s in res["static_smells"]],
                "security_count": len(res["security_findings"]),
            }
        )
        for sf in res["security_findings"]:
            sf_copy = dict(sf)
            sf_copy["file"] = f"{smd.parent.relative_to(root).as_posix()}/{sf['file']}"
            all_sec.append(sf_copy)

    collisions: list[dict[str, Any]] = []
    for i in range(len(desc_tokens_map)):
        n1, t1, _ = desc_tokens_map[i]
        for j in range(i + 1, len(desc_tokens_map)):
            n2, t2, _ = desc_tokens_map[j]
            if not t1 or not t2:
                continue
            jaccard = len(t1 & t2) / len(t1 | t2)
            if jaccard >= 0.42:
                collisions.append(
                    {
                        "skill_a": n1,
                        "skill_b": n2,
                        "keyword_overlap_jaccard": round(jaccard, 2),
                        "shared_keywords": sorted(t1 & t2)[:10],
                    }
                )

    chaining = _detect_cross_skill_chaining(cap_profiles)
    if total_index_chars > 8000:
        smells.append({"code": "FLEET-INDEX-8KB", "severity": "warning", "file": ".", "message": f"Combined startup metadata ({total_index_chars} chars) exceeds Codex 8,000-char fallback cap; some skills risk omission."})
    if collisions:
        smells.append({"code": "FLEET-TRIGGER-COLLISION", "severity": "warning", "file": ".", "message": f"Detected {len(collisions)} skill pairs with high description overlap (>=0.42 Jaccard)."})
    if chaining["detected"]:
        smells.append({"code": "SG09-PRIVILEGE-CHAIN", "severity": "warning", "file": ".", "message": chaining["summary"] or "Cross-skill privilege chaining detected."})

    mean_fleet_port = round(sum(fleet_ports) / len(fleet_ports), 1) if fleet_ports else 100.0
    return {
        "schema_version": "3.1.0",
        "target_path": str(root.resolve()),
        "target_type": "skill-fleet",
        "skill_name": root.name,
        "coverage": {
            "complete": len(unreadable_all) == 0,
            "total_files_discovered": len(skill_md_files),
            "inspected_text_files": len(skill_md_files),
            "unreadable_or_binary_files": unreadable_all,
            "symlinks": symlinks_all,
        },
        "tier_classification": {
            "detected_tier": "Tier 3: Multi-Skill Fleet",
            "recommended_audit_path": "Full Multi-Agent (5+1 or Sequential Fallback)",
            "has_subagents": True,
            "has_child_skills": True,
            "has_mcp_references": False,
            "has_scripts": False,
            "has_references": False,
            "has_assets": False,
            "has_evals": False,
            "recommend_multi_agent_audit": True,
        },
        "frontmatter": {"present": True, "valid_yaml": True, "yaml_error": None, "fields": {}, "extension_fields": [], "checks": {}},
        "inventory": {"primary_file": ".", "skill_md_lines": 0, "skill_md_bytes": total_index_chars, "skill_md_words": 0, "skill_md_est_tokens": estimate_tokens(" " * total_index_chars), "total_files": len(skill_md_files), "subagent_files": [], "child_skill_files": [m["path"] for m in members], "reference_files": [], "script_files": [], "asset_files": [], "eval_files": [], "readme_inside_skill": False, "config_files": []},
        "ecosystem_config_checks": [],
        "child_skill_audits": members,
        "fleet_analysis": {
            "skill_count": len(members),
            "total_startup_metadata_chars": total_index_chars,
            "exceeds_codex_8kb_cap": total_index_chars > 8000,
            "mean_portability_score_pct": mean_fleet_port,
            "trigger_collisions": collisions,
            "privilege_chaining": chaining,
        },
        "link_graph": {"links_from_skill_md": [], "broken_links": [], "orphan_files": [], "nested_chain_depth_gt_1": [], "backslash_paths": []},
        "static_smells": smells,
        "script_checks": [],
        "subagent_context_checks": [],
        "eval_checks": [],
        "security_findings": all_sec,
        "platform_compatibility": {
            "agentskills_core": "PASS" if all(m["core_spec_pass"] for m in members) else "FAIL",
            "claude_code": "PASS",
            "openai_codex": "WARN" if total_index_chars > 8000 else "PASS",
            "cursor": "PASS",
            "notes": [f"Audited fleet of {len(members)} skills ({total_index_chars} startup metadata chars, mean portability {mean_fleet_port}%)."],
            "universal_portability": {
                "portability_score_pct": mean_fleet_port,
                "total_targets": len(AGENT_COMPATIBILITY_PROFILES),
                "detected_install_scope": "fleet-root",
                "recommendations": [
                    f"Mean cross-agent portability across {len(members)} skills: {mean_fleet_port}%."
                ],
            },
        },
    }


def _audit_archive(archive_path: Path, target_type: str, self_audit_safe: bool) -> dict[str, Any]:
    """Safely inspect a .skill / .zip package with Zip-Slip and Zip-Bomb guards."""
    with tempfile.TemporaryDirectory(prefix="skill_audit_zip_") as tmpdir:
        tmp_root = Path(tmpdir).resolve()
        total_uncompressed = 0
        with zipfile.ZipFile(archive_path, "r") as zf:
            infos = zf.infolist()
            if len(infos) > MAX_ARCHIVE_FILES:
                raise ValueError(f"Zip-Bomb guard triggered: archive has {len(infos)} > {MAX_ARCHIVE_FILES} entries.")
            for info in infos:
                # Reject symlinks in zip external attributes (Unix mode 0o120000)
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError(f"Unsafe symlink inside archive rejected: {info.filename}")
                total_uncompressed += info.file_size
                if total_uncompressed > MAX_ARCHIVE_BYTES:
                    raise ValueError(f"Zip-Bomb guard triggered: uncompressed bytes exceed {MAX_ARCHIVE_BYTES}.")
                dest = (tmp_root / info.filename).resolve()
                if not str(dest).startswith(str(tmp_root) + os.sep) and dest != tmp_root:
                    raise ValueError(f"Zip-Slip path traversal rejected: {info.filename}")
                if info.is_dir():
                    dest.mkdir(parents=True, exist_ok=True)
                else:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info, "r") as src, open(dest, "wb") as dst:
                        dst.write(src.read())

        skill_roots = sorted(p.parent for p in tmp_root.rglob("SKILL.md"))
        if not skill_roots:
            raise FileNotFoundError(f"No SKILL.md found inside archive {archive_path}")
        scan_root = skill_roots[0] if len(skill_roots) == 1 else tmp_root
        rep = audit_target(scan_root, target_type=target_type if target_type != "auto" else ("skill" if len(skill_roots) == 1 else "fleet"), self_audit_safe=self_audit_safe)
        rep["target_path"] = str(archive_path.resolve())
        rep["archive_source"] = str(archive_path.resolve())
        return rep


def audit_target(target: Path, target_type: str = "auto", self_audit_safe: bool = False) -> dict[str, Any]:
    if target.is_file() and target.suffix.lower() in {".skill", ".zip"}:
        return _audit_archive(target, target_type=target_type, self_audit_safe=self_audit_safe)
    if target_type == "skill":
        return audit_skill_package(target, self_audit_safe=self_audit_safe)
    if target_type == "agents-md":
        f = target / "AGENTS.md" if target.is_dir() and (target / "AGENTS.md").exists() else (target / "CLAUDE.md" if target.is_dir() else target)
        return audit_agents_md(f)
    if target_type == "cursor-mdc":
        return audit_cursor_mdc(target)
    if target_type == "agent-profile":
        return audit_agent_profile(target)
    if target_type == "fleet":
        return audit_skill_fleet(target, self_audit_safe=self_audit_safe)

    if target.is_file():
        name_up = target.name.upper()
        if target.name == "SKILL.md":
            return audit_skill_package(target, self_audit_safe=self_audit_safe)
        if name_up in {"AGENTS.MD", "AGENTS.OVERRIDE.MD", "CLAUDE.MD", "GEMINI.MD"}:
            return audit_agents_md(target)
        if target.suffix.lower() == ".mdc":
            return audit_cursor_mdc(target)
        if target.suffix.lower() == ".toml" or any(seg in target.parts for seg in ("agents", ".claude", ".cursor", ".codex")):
            return audit_agent_profile(target)
        return audit_skill_package(target, self_audit_safe=self_audit_safe)

    if (target / "SKILL.md").exists():
        return audit_skill_package(target, self_audit_safe=self_audit_safe)
    if list(target.rglob("SKILL.md")):
        return audit_skill_fleet(target, self_audit_safe=self_audit_safe)
    if (target / "AGENTS.md").exists():
        return audit_agents_md(target / "AGENTS.md")
    if (target / "CLAUDE.md").exists():
        return audit_agents_md(target / "CLAUDE.md")

    raise FileNotFoundError(
        f"No SKILL.md, skill fleet, AGENTS.md, CLAUDE.md, .mdc, .skill archive, or agent profile found at {target}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deterministic static pre-audit for Agent Skills, .skill archives, AGENTS.md, .mdc rules, agent profiles, and fleets.",
        epilog="Exit codes: 0 = audit complete, 1 = invalid target/args, 2 = critical blocker with --fail-on-critical.",
    )
    parser.add_argument("target", help="Path to skill dir, .skill/.zip archive, SKILL.md, AGENTS.md, .mdc rule, agent profile, or skills fleet dir")
    parser.add_argument(
        "--target-type",
        choices=["auto", "skill", "agents-md", "cursor-mdc", "agent-profile", "fleet"],
        default="auto",
        help="Override target type detection (default: auto)",
    )
    parser.add_argument(
        "--output",
        "-o",
        default="-",
        help="Write JSON report to file path instead of stdout (default: stdout)",
    )
    parser.add_argument(
        "--fail-on-critical",
        action="store_true",
        help="Exit with code 2 if spec-breaking or CRITICAL security issues are detected",
    )
    parser.add_argument(
        "--self-audit-safe",
        action="store_true",
        help="Ignore pattern signature tables inside references/ and evals/ (for auditing auditor skills)",
    )

    args = parser.parse_args()
    target = Path(args.target)
    if not target.exists():
        print(f"Error: target path does not exist: {target}", file=sys.stderr)
        return 1

    try:
        report = audit_target(target, target_type=args.target_type, self_audit_safe=args.self_audit_safe)
    except Exception as exc:  # noqa: BLE001
        print(f"Error auditing target '{target}': {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output == "-":
        print(rendered)
    else:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(rendered + "\n", encoding="utf-8")
        print(f"Static audit written to {out_path}", file=sys.stderr)

    if args.fail_on_critical:
        has_critical_sec = any(
            f.get("severity") == "CRITICAL" for f in report.get("security_findings", [])
        )
        core_fail = report["platform_compatibility"]["agentskills_core"] == "FAIL"
        if has_critical_sec or core_fail:
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
