# 17-Agent Cross-Platform Portability & Packaging Standard (2026)

Generated skills must load cleanly without edits across **Claude Code, OpenAI Codex, Cursor, Google Antigravity, Kilo Code, OpenCode, Pi Agent, Qoder, GitHub Copilot, Windsurf, Cline, Roo Code, Gemini CLI, Kiro, Amp, OpenClaw, and VS Code / `agentskills.io`**.

## 1. Canonical Directory Layout & Discovery Paths

```text
<skill-name>/                # Lowercase kebab-case ^[a-z0-9]+(-[a-z0-9]+)*$ (<=64 chars)
├── SKILL.md                 # REQUIRED (exact uppercase filename; name == folder)
├── agents/                  # OPTIONAL: subagent roles (Claude/Cursor) + openai.yaml (Codex)
├── scripts/                 # OPTIONAL: deterministic helpers (with chmod +x for sh/py/ts)
├── references/              # OPTIONAL: on-demand docs (max 1 hop from SKILL.md)
├── assets/                  # OPTIONAL: templates, starter configs, data files
├── evals/                   # OPTIONAL: evals.json + trigger_evals.json
└── config.json              # OPTIONAL: local non-secret configuration defaults
```

- **Avoid legacy/proprietary directories:** do NOT create `workflows/`, `commands/`, `guides/`, `prompts/`, or `docs/` inside a skill package (`PORT-NONCANONICAL-DIR`); fold those into `references/` or `assets/`.
- **Universal Project Installation Root:**
  - Canonical shared path (auto-discovered natively by **Codex, Cursor, Antigravity, Kilo, OpenCode, Pi, Copilot, Gemini CLI, Amp, Kiro**, and `npx skills`): `.agents/skills/<skill-name>/`
  - Explicit mirrors/symlinks when targeting **Claude Code** (`.claude/skills/`), **Qoder** (`.qoder/skills/`), and **Kiro** (`.kiro/skills/`) — `scripts/scaffold_skill.py --mirror-all` automates safe relative symlinks or copies.
  - Project rules interoperability: use `AGENTS.md` as source of truth and symlink `CLAUDE.md -> AGENTS.md` (with `GEMINI.md` awareness when Gemini CLI workspace instructions exist).

## 2. Frontmatter Portability Rules (6-Key Strict Core)

Keep YAML frontmatter strictly within the **`agentskills.io` v1.0** 6-key core for maximum portability:
1. `name` *(required)*: matches folder name (`^[a-z0-9]+(-[a-z0-9]+)*$`, `1..64` chars, no leading/trailing/double `-`).
2. `description` *(required)*: single scalar string (`1..1024` chars; most critical info in first `250` chars; `Pi Agent` and `OpenCode` fail/hide skills without it).
3. `license` *(optional)*: SPDX identifier (e.g., `MIT`, `Apache-2.0`).
4. `compatibility` *(optional)*: concise environment/runtime dependencies (`<=500` chars), e.g., `"Requires Python 3.10+ (standard library only; optional PyYAML)."`.
5. `metadata` *(optional — **STRING VALUES ONLY**)*:
   - **OpenCode constraint:** OpenCode parses `metadata` as `map[string]string`; numeric/boolean/array/nested-object values break strict parsers (`PORT-METADATA-NONSTRING`). Quote every value: `"version": "1.0.0"`, `"author": "..."`, `"opencode/autoinvoke": "false"`.
6. `allowed-tools` *(optional — omit unless least-privilege enforcement is required)*:
   - Note: `Claude Code`, `Antigravity`, `OpenClaw`, `Kilo`, `Copilot` support/honor tool restrictions, whereas **Cursor, OpenCode, Pi Agent, Gemini CLI, and Kiro** ignore `allowed-tools` at runtime. Omit wide `allowed-tools` for creator/builder skills (achieving 100% 17/17 PASS), or pair narrow `allowed-tools` on read-only/auditor skills with an explicit behavioral fallback inside `Gotchas`.

**Keys to relocate or avoid:**
- Move `version`, `author`, `category`, `tags`, `platform` inside `metadata` as string pairs (`PORT-FRONTMATTER-DRIFT`).
- `disable-model-invocation` and `user-invocable` are supported on Claude/Codex/Copilot/OpenCode (via `metadata` fallback), **only** emit them when user-only invocation is genuinely desired, and mirror them into `agents/openai.yaml` (`policy.allow_implicit_invocation`).
- Avoid Claude-only `context: fork`, `agent`, `hooks`, or `model` unless the skill explicitly declares Claude-only scope and documents an isolated sequential fallback for non-forking runtimes.

## 3. Codex `agents/openai.yaml` Companion
When creating any reusable skill, include `agents/openai.yaml`:
```yaml
interface:
  display_name: "Human Title"
  short_description: "25-64 char summary for UI cards"
  default_prompt: "Use $<skill-name> to <primary action>."
policy:
  allow_implicit_invocation: true  # false when disable-model-invocation: true
```
`agents/openai.yaml` is additive, ignored harmlessly by non-Codex harnesses, and elevates Codex/UI discovery.

## 4. Body & Tool Portability Guardrails (`PORT-VENDOR-LOCK`)
- **Zero `!command` inline shell macros:** Claude-specific preprocessing breaks or prints literally on the other 16 agents. Instruct the agent to run the script via its terminal tool instead.
- **Relative paths only:** refer to `scripts/...`, `references/...`, `assets/...` relative to the skill directory root. Guard `${CLAUDE_SKILL_DIR}` unless paired with relative fallback; never hardcode `/Users/...`, `/home/...`, or `~/` paths.
- **Abstract tool actions:** say *"read files"*, *"search files/text"*, *"run shell command"*, *"edit files"* instead of vendor-locked tool names (`MultiEdit`, `grep_search`, `execute_command`, `NotebookEdit`) — reserving exact tool tokens only for dedicated subagent files (`agents/*.md`).
- **Safe `.skill` archive packaging:** standard ZIP containing `<skill-name>/...` root entry, preserving executable permissions (`+x`) on scripts, excluding `.git`, `__pycache__`, `.venv`, `node_modules`, `.DS_Store`, secrets, and rejecting symlinks pointing outside the skill root.
