---
name: skill-creator
description: "Designs, scaffolds, and packages portable 17-agent AI Skills from scratch or chat workflows (Claude, Codex, Cursor, OpenCode, Kilo, Antigravity, Pi, Qoder). Use when creating a new skill, building scripts/openai.yaml/evals, or packaging .skill archives — включая «создай скил», «подготовь SKILL.md». Do NOT use for standalone audits of existing skills (use skill-auditor) or general app coding."
license: MIT
compatibility: "Requires Python 3.10+ (standard library; optional PyYAML). Auto-integrates with sibling skill-auditor when present."
metadata:
  author: "skill-creator"
  version: "1.0.0"
  standard: "agentskills-v1.0-17agents"
---

# Skill Creator

Build lean, frontier-ready Agent Skill packages grounded in observed failure modes and verified across 17+ agent runtimes. Read [config.json](config.json) for default output language (`ru`) and cross-agent mirror targets.

## Workflow

### 1. Capture Intent & Establish the Baseline Gap
- **Extract first:** When creating a skill from the current session or existing repo artifacts, mine observed steps, tool calls, corrections, and environment facts before asking questions.
- **Resolve open branches (`grill-me` style):** Ask concise targeted questions only for unresolved design forks:
  1. What concrete mistakes or conventions does a strong frontier model miss without this skill (**Red Baseline**)?
  2. Should it auto-trigger (**model-invoked**) or fire manually (`disable-model-invocation: true`, or a **router skill** for 4+ manual commands)?
  3. Which inputs/outputs, verification gates, and target runtimes apply?
- **Done when:** Skill name (`^[a-z0-9]+(-[a-z0-9]+)*$`), baseline gap, invocation mode, and target archetype are explicit.

### 2. Design Architecture & Deterministic Boundaries
- Load [the authoring methodology](references/authoring-methodology.md) when deciding splitting, invocation tradeoffs, completion criteria, leading words, or script boundaries.
- Load [the 17-agent portability guide](references/portability-and-packaging-17.md) when configuring frontmatter, `.agents/skills/` mirroring, or `agents/openai.yaml`.
- Pick the lightest sufficient template from [the SKILL.md blueprints](assets/skill-md-blueprints.md) (`atomic`, `script`, `multi-agent`, or `user-invoked`).
- **Script boundary:** Offload only deterministic formatting, AST/schema/file validation, or packaging into `scripts/`. Keep semantic judgment, interviewing, and prose synthesis with the LLM.
- **Done when:** Every planned file earns its context/cognitive load and no deterministic task is left to error-prone prose (nor semantic prose forced into regex scripts).

### 3. Scaffold Deterministically
Run [the deterministic scaffolder](scripts/scaffold_skill.py) to create canonical layout, string-typed `metadata`, optional cross-agent symlinks, and [Codex UI config](references/agents/openai.yaml) without empty placeholder folders:
```bash
python3 scripts/scaffold_skill.py "<skill-name>" \
  --output-dir "<target-parent>" \
  --archetype "<atomic|script|multi-agent|user-invoked>" \
  --resources "<scripts,references,assets,agents,evals>" \
  --description "<trigger-description>" \
  --json
```
Pass `--mirror-project "<repo-root>"` to symlink the skill across all cross-agent mirror folders listed in [config.json](config.json) (see [the 17-agent portability guide](references/portability-and-packaging-17.md)).
- **Done when:** Scaffolder exits `0` and created files match the chosen archetype.

### 4. Author Content & Verification Evals
- **Positive frontier instructions:** State desired behavior and *why* it matters; replace bare negations (*"never X"*) with the positive invariant and target replacement.
- **Checkable completion criteria:** End every workflow step with an observable done condition so the agent finishes legwork before advancing.
- **Context pointers:** Put branch-specific detail in `references/` (one hop deep) with explicit load conditions, leaving universal steps in `SKILL.md`. Front-load leading trigger words in `description` without summarizing workflow steps (`CSO-LEAK`).
- **Evals & triggers:** Consult [the evals and trigger guide](references/evals-and-trigger-guide.md) when generating `evals/evals.json` (mark each case `AB_MEANINGFUL` or `WITH_SKILL_ONLY`) and 16–20 near-miss vs positive queries in `evals/trigger_evals.json` (omit `trigger_evals.json` for user-invoked skills). Use [tests/evals/evals.json](tests/evals/evals.json) and [tests/evals/trigger_evals.json](tests/evals/trigger_evals.json) as structural reference formats.
- **Done when:** All placeholders are replaced with concrete domain rules, real runnable examples, and verifiable eval assertions.

### 5. Clean-Context Review, Preflight & Package
1. **No-op & design review:** Dispatch [the independent skill reviewer](references/agents/skill-reviewer.md) in a fresh context window (if the runtime lacks parallel subagent spawning, run a clean sequential self-review pass following that file's exact checklist). Delete any sentence whose removal leaves frontier behavior unchanged.
2. **Verify & package:** Run [the packager and 17-agent verifier](scripts/package_and_verify.py) (automatically invokes sibling `skill-auditor` if installed alongside `skill-creator`):
   ```bash
   python3 scripts/package_and_verify.py "<path/to/skill-name>" --json
   ```
   Use `--verify-only` if a `.skill` archive is not requested yet. Run [the creator self-test suite](scripts/self_test.py) after modifying `skill-creator` itself.
- **Done when:** Preflight returns `PASS` with `0` errors, independent reviewer reports `SHIP_READY`, sibling audit (if available) has `0` security findings and `0` portability failures, and the delivered files/archive match user requirements.

## Gotchas
- **OpenCode string metadata:** Non-string values (`version: 1.0`, booleans, arrays) under `metadata` break strict Go parsers; quote every `metadata` value as a string and avoid top-level `version`/`author`/`category`.
- **Workflow leaks in `description` (`CSO-LEAK`):** Summarizing internal steps inside `description` causes agents to execute the summary instead of reading `SKILL.md`. Put intent symptoms and negative exclusions in `description`; keep steps inside the body.
- **Meaningless baseline evals:** Never request blind `without_skill` comparisons for `WITH_SKILL_ONLY` skills that depend on custom scripts or internal conventions unavailable to a raw model.
- **Vendor lock traps:** Avoid Claude-only inline command expansion macros, non-canonical directories (place docs in `references/` and templates in `assets/`), hardcoded user paths, and unabstracted vendor tool names in `SKILL.md`.
