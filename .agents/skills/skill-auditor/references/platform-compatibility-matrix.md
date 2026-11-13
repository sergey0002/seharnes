# Cross-Agent Compatibility Matrix (17+ Agents & `agentskills.io` Ecosystem)
*Last Verified: 2026-11-10 (Primary docs + `vercel-labs/skills` registry supporting 75+ agents)*

Use this matrix when auditing `D8` (Cross-Platform Portability & Auto-Discovery), `D1.5` (Universal Discovery Paths), and `D4`/`D5` platform-specific extensions.

---

## 1. Master 17-Agent Discovery, Spec & Feature Matrix

> **Universal `.agents/skills/` Convergence:** 13 of 16 concrete harnesses below auto-discover `.agents/skills/<name>/SKILL.md` natively. **Exceptions that do NOT read `.agents/skills/` natively:** **Claude Code** (`.claude/skills/`), **Qoder** (`.qoder/skills/`), and **AWS Kiro** (`.kiro/skills/`). To guarantee 100% cross-agent auto-discovery across a repository or workstation, publish at `.agents/skills/<name>/SKILL.md` and deploy/symlink via `npx skills add <source> --all` (or mirror into `.claude/skills/`, `.qoder/skills/`, `.kiro/skills/`).

| Agent / Standard | Project Discovery Path(s) | Global Discovery Path | Reads `.agents/skills/` | `name` / `description` Rules | `allowed-tools` | `context: fork` / `hooks` | Project Rules File & Cap | Key Runtime / Loader Quirks |
|---|---|---|---|---|---|---|---|---|
| **Agent Skills Core (`agentskills.io`)** | `.agents/skills/<name>/SKILL.md` | Harness-defined | Yes | Both **required**; `^[a-z0-9-]+$` <=64; `name == dir`; `desc <=1024` | Core optional (6-key whitelist) | No / No | `AGENTS.md` | Strict uploaders (`claude.ai` / `package_skill.py`) allow **only 6 core keys**: `name, description, license, compatibility, metadata, allowed-tools` |
| **Claude Code** | `.claude/skills/<name>/SKILL.md` (+ plugin `skills/`) | `~/.claude/skills/` | **No** | Optional in Claude Code, but omit breaks portability | Enforced (`Bash(...)`) | **Yes / Yes** | `CLAUDE.md` (no native `AGENTS.md`) | Only client supporting `!command`, `${CLAUDE_SKILL_DIR}`, `$ARGUMENTS`, `context: fork`, `agent`, `effort`, `shell`, `hooks`, `disallowed-tools`; truncates index desc ~250 chars |
| **OpenAI Codex** | `.agents/skills/`, `.codex/skills/` | `~/.agents/skills/` | **Yes** | Both **required**; `name == dir` | Partial | No / No | `AGENTS.md` (**32 KiB** cap!) | Startup metadata capped at **2% context / 8,000 chars**; uses `agents/openai.yaml` (`policy.allow_implicit_invocation: false`) instead of `disable-model-invocation`; `$skill-name` |
| **Cursor (v2.4+)** | `.agents/skills/`, `.cursor/skills/`, `.claude/skills/`, `.codex/skills/` | `~/.cursor/skills/` | **Yes** | Both **required**; `name == dir` | Parsed, **NOT enforced** | No / Hooks only | `AGENTS.md`, `.cursor/rules/*.mdc` | Supports `paths`, `icon`, `color`, `user-invocable`, `disable-model-invocation`; never rely solely on `allowed-tools` for Cursor security |
| **Google Antigravity IDE/CLI** | `.agents/skills/` (legacy `.agent/skills/`) | `~/.gemini/config/skills/` | **Yes** | `description` required; `name` optional (defaults to folder) | Supported | No / No | `AGENTS.md` | Built-in tools differ (`run_command`, `grep_search`, `view_file`); legacy `.agent/skills/` still seen in older repos |
| **Kilo Code** | `.agents/skills/`, `.kilocode/skills/`, `.kilo/skills/`, `skills-<mode>/` | `~/.kilo/skills/` | **Yes** | Both **required**; `name == dir` | Partial | No / No | `AGENTS.md`, `.kilo/rules/` | Mode-specific dirs (`skills-code/`, `skills-architect/`); reads `.claude/skills/` only if compatibility toggle is enabled |
| **OpenCode** | `.agents/skills/`, `.opencode/skills/`, `.claude/skills/` | `~/.config/opencode/skills/` | **Yes** | Both **required**; `name == dir`; ID derived from path | Ignored (uses `opencode.json`) | No / No | `AGENTS.md` | **Strict parser:** recognizes only `name, description, license, compatibility, metadata`; expects `metadata` as **`map<string,string>`**; uses `metadata.opencode/autoinvoke: "false"`; flat `skills/*.md` loses sibling files; invokes via `skill({ name })` |
| **Pi Agent (`pi-coding-agent`)** | `.agents/skills/`, `.pi/skills/` | `~/.pi/agent/skills/`, `~/.agents/skills/` | **Yes** | Both **required** (**omits skill if `description` missing!**); `name == dir` | Ignored | No / No | `AGENTS.md` | **No `Skill` tool** — uses `read` tool and `/skill:name`; supports `disable-model-invocation: true`; flat `.md` misses helper files |
| **Qoder IDE/CLI** | `.qoder/skills/` | `~/.qoder/skills/` | **No** | Both **required**; `name == dir` | Supported | No / No | `AGENTS.md` (**100K chars** cap), `.qoder/rules/` | Auto-discovers `.qoder/skills/` only; supports `REFERENCE.md`/`EXAMPLES.md` patterns, prefers canonical `references/` for universal sync |
| **GitHub Copilot** | `.agents/skills/`, `.github/skills/` | `~/.copilot/skills/` | **Yes** | Both **required**; `name == dir` | Supported | No / Yes | `AGENTS.md`, `.github/copilot-instructions.md` | Custom agents require `*.agent.md` extension under `.github/agents/` (plain `*.md` ignored as agent profile) |
| **Windsurf (Cascade)** | `.agents/skills/`, `.windsurf/skills/` | `~/.codeium/windsurf/skills/`, `~/.agents/skills/` | **Yes** | Both **required**; `name == dir` | Supported | No / No | `AGENTS.md`, `.windsurf/rules/` | Supports `when_to_use` field (ignored elsewhere unless duplicated in `description`) |
| **Cline** | `.agents/skills/`, `.cline/skills/`, `.clinerules/skills/`, `.claude/skills/` | `~/.cline/skills/`, `~/.agents/skills/` | **Yes** | Both **required**; `name == dir` | Supported | No / No | `AGENTS.md`, `.clinerules/` | Often uses `docs/`/`templates/` in examples; global overrides project on collision; uses `read_files` / `execute_command` / `write_to_file` |
| **Roo Code** | `.agents/skills/`, `.roo/skills/`, `skills-<mode>/` | `~/.roo/skills/`, `~/.agents/skills/` | **Yes** | Both **required**; `name == dir` | Supported | No / No | `AGENTS.md`, `.roo/rules/` | Mode-specific dirs (`skills-code/`, `skills-architect/`) override generic; tools `read_file`, `execute_command`, `write_to_file`, `search_files` |
| **Gemini CLI** | `.agents/skills/`, `.gemini/skills/` | `~/.gemini/skills/` | **Yes** | Both **required**; `name == dir` | Parsed, not enforced | No / No | **`GEMINI.md`** | Uses `GEMINI.md` by default (can configure `AGENTS.md`); progressive `activate_skill` loading |
| **AWS Kiro CLI/IDE** | `.kiro/skills/` | `~/.kiro/skills/` | **No** | Both **required**; `name == dir` | **Unsupported** | No / No | `AGENTS.md`, `.kiro/steering/` | Default agent auto-loads `.kiro/skills/`; **custom agents** in `.kiro/agents/<agent>.json` require explicit `"resources": ["skill://.kiro/skills/**/SKILL.md"]` |
| **Sourcegraph Amp** | `.agents/skills/`, `.claude/skills/` | `~/.config/agents/skills/` | **Yes** | Both **required**; `name == dir` | Supported | No / No | `AGENTS.md` | Scans up to 5 levels deep; supports `mcpServers` in frontmatter or sibling `mcp.json`; 200 files / 25 MiB cap |
| **OpenClaw** | `skills/`, `.agents/skills/` | `~/.openclaw/skills/`, `~/.agents/skills/` | **Yes** | Both **required**; `name == dir` on nodes | Supported | No / No | `AGENTS.md` | Scans up to 6 levels; gating via `metadata` env/bins/OS; workspace `workspace-skill://` paths |

### Broader `vercel-labs/skills` Ecosystem (75+ Agents)
Additional popular tools following `SKILL.md` (`name` + `description`) via `npx skills add`:
- **Native `.agents/skills/`**: Droid, Firebender, Replit, Deep Agents, Zed, Warp, Kimi Code CLI, Dexto, PromptScript.
- **Tool-scoped dirs**: Junie (`.junie/skills/`), Trae (`.trae/skills/`), Continue (`.continue/skills/`), Goose (`.goose/skills/`), Crush (`.crush/skills/`), OpenHands (`.openhands/skills/`), Augment (`.augment/skills/`), Qwen Code (`.qwen/skills/`), Mistral Vibe (`.vibe/skills/`), Tabnine CLI (`.tabnine/agent/skills/`), Zencoder (`.zencoder/skills/`).
- **Custom manifest discovery**: `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`, and `skills.sh.json` (`"paths": ["./tools/skills"]`).

---

## 2. Subagent & Companion File Compatibility

| Feature | Claude Code (`.claude/agents/*.md`) | OpenAI Codex (`.codex/agents/*.toml`) | Cursor (`.cursor/agents/*.md`) | GitHub Copilot (`.github/agents/*.agent.md`) | Portable In-Skill (`<skill>/agents/*.md`) |
|---|---|---|---|---|---|
| **Format** | Markdown + YAML | TOML + `config.toml` | Markdown + YAML | `.agent.md` + YAML | Markdown role prompts loaded via `SKILL.md` |
| **Key Controls** | `tools`, `disallowedTools`, `model`, `effort`, `maxTurns`, `skills`, `mcpServers`, `hooks`, `isolation: worktree`, `omitClaudeMd` | Built-ins (`default`/`worker`/`explorer`), `max_threads`, `sandbox_mode`, `model`, `timeout` | `name`, `description`, `model`, `tools`, `readonly: true` | `tools`, `description` (`*.md` ignored!) | Role prompt + typed JSON handoff + explicit sequential fallback when subagents unsupported |

---

## 3. Golden Rules for 100% Universal Auto-Discovery & Execution

1. **Frontmatter Safe Core (`agentskills.io` 6-Key Whitelist):** Always include valid lowercase kebab-case `name` (exact match to parent folder name, `<=64` chars) and non-empty `description` (`<=1024` chars, front-loaded in first `250` chars, string-valued `metadata`). Keep non-core extensions (`context: fork`, `paths`, `when_to_use`, `disable-model-invocation`) strictly optional or backed by portable equivalents (`agents/openai.yaml`, `metadata.opencode/autoinvoke`, prose guardrails).
2. **Never Rely on Flat `.md` or Dialect Subdirs:** Always ship `<skill-name>/SKILL.md` with canonical `scripts/`, `references/`, `assets/` (avoid `resources/`, `docs/`, `examples/` as top-level replacements for `references/`).
3. **Zero Silent Vendor-Locks in Body:** Never depend solely on `!command`, `${CLAUDE_SKILL_DIR}`, `$ARGUMENTS`, or client-specific paths (`~/.claude/skills/`, `.qoder/skills/`) without providing a directory-relative portable fallback (`<skill_dir>/scripts/...` resolved relative to `SKILL.md`). Phrase tool instructions by capability or provide cross-agent parity rather than locking to `MultiEdit` / `grep_search` / `execute_command` / `skill({ ... })`.
4. **Universal Discovery Deployment (`AGENTS.md` + Skill Paths):**
   - Put canonical project skills in **`.agents/skills/<name>/SKILL.md`** (instant auto-discovery by 13+ major tools) AND mirror/install into **`.claude/skills/`**, **`.qoder/skills/`**, and **`.kiro/skills/`** (e.g., via `npx skills add <source> --all`).
   - Use **`AGENTS.md`** as the universal project context hub, and add `@AGENTS.md` in `CLAUDE.md` (for Claude Code) + reference in `GEMINI.md` (for Gemini CLI).
5. **Packager Traps:** Never put symlinks *inside* a skill directory (`getsentry/skills #117`); invoke bundled scripts via explicit interpreter (`python3 scripts/x.py`, `bash scripts/x.sh`) because packagers strip `+x`; never ship `README.md` inside a skill root.
