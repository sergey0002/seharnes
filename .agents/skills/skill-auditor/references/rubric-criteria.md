# Evaluation Rubric & Frontier-First Criteria (v3.1 — 8 Dimensions)

Score applicable dimensions/criteria on a **0–5** scale (`0 = Critical failure`, `1 = Deficient`, `2 = Weak`, `3 = Adequate`, `4 = Strong`, `5 = Exemplary`).
Base weights sum to **100**. When a dimension is `applicable: false`, `scripts/score_aggregator.py` redistributes its weight proportionally across active dimensions.

*(Semantic vs Deterministic Boundary: `scripts/static_audit.py` inspects ONLY objective parser limits, link graphs, AST/regex counts, and security patterns. All natural-language quality judgments — `FLUFF`, `AMBIG`, `CAGE`, `SCAR`, `SCRIPT-OVERREACH`, `NTPD`, `CSD` text quality, and semantic `CONTRA` — are evaluated by LLM specialists, never brittle script keyword dictionaries.)*

---

## Core Design Philosophy: High Signal + Invariants, Zero Unnecessary Cages

Optimize for **strong modern frontier models**: maximize unique domain information, edge-case traps, and verifiable invariants while giving the model freedom over *how* to reason and solve the task.

1. **Hard Invariants (Always Enforce):**
   - Platform compatibility facts: `name` matches the folder and kebab-case, `description` is present, zero `<xml>` tags. Client parser ceilings stay documented as facts about clients, not as audit thresholds.
   - Security & trust boundaries (no prompt injection, no unverified pipe-to-shell, no secret leaks, explicit untrusted-data boundary).
   - Verifiable grounding (`file:line` citations, zero broken/orphan links, deterministic math/validation scripts where precision matters).
2. **Frontier Freedom Rules (Never Overload Strong Models):**
   - **No boilerplate quotas:** A crisp 35–100 line skill packing real non-obvious domain knowledge is **exemplary**, never "too short".
   - **Do NOT enforce rigid form:** Never penalize a clear frontier skill for omitting numbered `Step 1` lists (`TSW`), redundant examples (`ME`), or a literal `## Gotchas` heading (`BG`) when warnings and intent are clear.
   - **Penalize `CAGE` (Over-Constrained Frontier Cage):** Flag prompts that micromanage strong models with arbitrary numerical counts ("strictly 4 paragraphs of 3 sentences"), forced reasoning templates, or walls of `MUST/ALWAYS/NEVER` on subjective judgment tasks where outcomes suffer when model intelligence is boxed in.
   - **Respect domain fit:** Keep `D5 = N/A` for pure reasoning, editorial, strategy, or design skills that need no scripts or MCP tools.

---

## Complexity & Execution Tiers

- **Tier 1 (Atomic / Focused Single-Workflow)**: Single `SKILL.md` (or standalone `AGENTS.md` / `.mdc` / agent profile), 0 subagents, 0 child skills, 0 MCPs. `D4` is `N/A` unless severe role mixing or context rot occurs inside one window.
- **Tier 2 (Tool / Resource-Heavy)**: Uses external scripts, APIs, MCP servers, or multiple `references/`/`assets/` in a single-agent loop. `D4` is `N/A` unless actual parallel scale or generator-vs-verifier separation is needed.
- **Tier 3 (Complex / Multi-Agent / Hierarchical)**: Contains or delegates to subagents (`agents/`, `.claude/agents/`, `.codex/agents/`, `.cursor/agents/`), child sub-skills (`skills/*/SKILL.md`), `context: fork`, multi-MCP orchestration, or plugin bundles. **`D4` is MANDATORY.**

---

## D1. Triggering & Discoverability — Weight: 14%
*Owner: `trigger-context-auditor`*

- **D1.1 Spec & Naming Validity (Hard Invariant)**: `name` matches parent directory, lowercase alphanumeric+hyphens, descriptive. `description` is non-empty, valid YAML, zero XML/HTML tags (`XID`).
- **D1.2 Trigger Triad & Front-Loading (Hard Invariant)**: Covers `[What it does] + [When to use] + [High-signal keywords]` near the start of `description`, so clients that truncate it keep the primary intent.
- **D1.3 Point-of-View, CSO Discipline & Clarity**: Third-person/imperative routing phrasing (`"Reviews..."`, `"Use when..."`) without bloated trigger essays in body or **CSO Workflow-Leak (`CSO-LEAK`)** — do NOT summarize internal workflow steps inside `description`, or strong models may execute from the summary alone without loading `SKILL.md` invariants.
- **D1.4 Negative Boundaries, Collisions & Scope Containment**: States clear scope boundaries (`Do NOT use for...`) so it neither hijacks adjacent skills nor suffers **Unrequested Audit Escalation (`UNREQ-ESCALATION`)** (specialized review/audit/hardening firing on ordinary related tasks, or implying task approval expands scope/permissions).
- **D1.5 Ecosystem Discovery, Auto-Discovery Paths & Multilingual Fit**: Mitigates under-triggering (Vercel: 56% unreferenced miss rate via `AGENTS.md`/`CLAUDE.md` pointer), supports cross-agent discovery (`.agents/skills/` + `.claude/skills/`/`.qoder/skills/`/`.kiro/skills/` via `npx skills add`), and covers relevant team languages/synonyms.

---

## D2. Context Engineering & Progressive Disclosure — Weight: 16%
*Owner: `trigger-context-auditor`*

- **D2.1 Information Density & Progressive Disclosure**: Concise metadata; `SKILL.md` stays dense and free of duplicated manuals, with **full-package `token_budget`** reported as a metric across `references/` and `agents/` and valid balanced Markdown code fences (`MD-UNCLOSED-FENCE`). Short high-density frontier skills earn `5/5`; heavy schemas/manuals/templates belong in `references/`, `scripts/`, `assets/`, `agents/`. No line or token ceiling is scored.
- **D2.2 One-Level-Deep Link Discipline**: Supporting files linked directly from `SKILL.md` with forward slashes (`BP`), clear **conditional loading cues**, zero broken links, zero orphans, and zero hidden `a.md -> b.md` chains.
- **D2.3 Signal-to-Noise, Zero `FLUFF` & Non-Redundancy**: Passes the **Zero-Gain Deletion Test** — if generic platitudes (*"clean code", "best practices", "handle errors properly"*) were deleted, rich domain heuristics, edge cases, and non-obvious invariants still remain. Zero textbook basics, zero cross-file duplication (`ETH Zurich` dilution), and zero `alwaysApply: true` bloat.
- **D2.4 KV-Cache, Prefix & Thinking-Chain Stability**: Append-only prefix discipline — zero volatile live timestamps, random IDs, mid-loop tool-roster mutations, or earlier-turn rewrites that bust KV-cache or invalidate interleaved `thinking` blocks.
- **D2.5 Long-Horizon Window Ladder & Memory Hygiene**: Uses the lightest context-control lever first: (1) **Tool-result pruning & spill-to-file** (>25K outputs written to files with path previews), (2) **clean context resets** between phases with file handoffs (avoiding premature *Context Anxiety* compaction), (3) **compaction** with explicit preservation rules only when continuous state demands it. If persistent memory (`/memories` / `MEMORY.md`) is used, excludes memory tools from auto-clearing and enforces anti-duplication/staleness rules.

---

## D3. Prompt & Procedural Engineering — Weight: 14%
*Owner: `workflow-reliability-auditor`*

- **D3.1 Path Freedom vs Fragility Guardrails (Anti-`CAGE` / Anti-`SOC`)**: Gives maximum real context, edge-case facts, and clear **Invariants / Constraints** while leaving reasoning & execution strategy free for strong models on adaptive tasks; reserves strict sequences ONLY for genuinely fragile operations (migrations, financial writes, destructive ops). Penalize `CAGE` (arbitrary formatting/count quotas, forced step choreography) and `SOC`!
- **D3.2 Self-Contained Theses, Internal Consistency & Observable Done-When**:
  - **Context-Free Autonomy (`AMBIG`):** Every rule and thesis is self-contained without external chat or tribal lore — names exact targets, concrete conditions, and observable thresholds (zero dangling *"as discussed / our standard / that file / etc."*).
  - **Zero Internal Contradictions (`CONTRA`):** `description`, `SKILL.md`, `agents/`, `references/`, and `scripts/` agree on permissions, scope, and outputs; overlapping rules state explicit precedence.
  - **Observable Done-When:** Clear Goal, rich domain inputs, and verifiable completion criteria.
- **D3.3 Decision Criteria & Sane Defaults**: Clear trade-off criteria and one recommended default where choices collide (`TOB` avoidance) without over-scripting every branch.
- **D3.4 Output Contracts & High-Signal Examples**: Explicit schemas/templates ONLY where downstream parsers or strict artifacts require them (`MT`); brief non-obvious examples ONLY when prose alone cannot convey exact shape.
- **D3.5 Rationale, Real Traps & Anti-Rationalization**: Explains *why* critical constraints exist and surfaces genuine non-obvious traps cleanly (dedicated `## Gotchas` or inline callouts) + closes verification shortcuts and common high-pressure rationalizations (`RL`, *"too trivial to test"*) on high-stakes workflows.
- **D3.6 Compensating Scar Audit (`SCAR`), Over-Generalization & Positive Intent**: Separates **Descriptive** domain rules from **Compensating** weak-model crutches (*"think step by step"*, *"before finishing double-check every item"*, *"if in doubt MUST call tool X"*) and **Over-Generalization** (turning one past incident or preference into an unconditional `ALWAYS/MUST`) that trigger over-verification, over-triggering, or rigidity on Opus 4.6+/5 and GPT-5+. Prefers positive goal framing with clear rationale over stacked bare `NEVER / DO NOT` walls.

---

## D4. Multi-Agent, Sub-Skills & Orchestration Architecture — Weight: 16%
*Owner: `orchestration-subagent-auditor`* *(Mandatory for Tier 3. Mark `N/A` for Tier 1–2 unless context rot or generator-vs-verifier bias degrades single-window execution.)*

- **D4.1 Pattern Fit & Anti-Overengineering**: Uses the lightest topology needed; avoids unnecessary subagent fan-out on tasks a strong frontier model handles cleanly in one context.
- **D4.2 Bidirectional Context Hygiene (Input Diet + Output Isolation)**:
  - **Minimum Sufficient Input IN:** Orchestrator passes **scoped context slices and pointers** (file paths, line ranges, artifact IDs) strictly tailored to each worker's role — NEVER dumping full chat history or unrelated `references/*`. Workers declare tight `tools:`/`disallowedTools`/`skills:` and consider `omitClaudeMd: true` for blind reviewers, receiving an autonomous **4-part spawn brief** *(Parent Goal + Exact Invariants + Scoped Input Pointers + Output Contract)* so they never waste turns hunting for context.
  - **Compact Isolated Output OUT:** Subagents/child skills execute in isolated windows and return compact structured summaries or file paths — never raw multi-file transcript dumps.
- **D4.3 Child-Skill Mechanics & Recursive Integrity**: Acyclic `skills/*/SKILL.md` wiring; explicit `skills:` preloading (or path injection) in Claude Code subagents.
- **D4.4 Typed Handoff Contracts, MAST Defenses & Cross-Skill Privilege Isolation (`SG09`)**: Clean I/O contracts, explicit read/write role boundaries (`FM-1.1`/`FM-1.2`), bounded turns/depth (`FM-1.3`, `FM-1.5`), no hidden constraints across handoffs (`FM-2.4`/`FM-2.5`), independent verification (`FM-3.2`/`FM-3.3`), and zero unguarded **Cross-Skill Privilege Chaining (`SG09` / Lethal Trifecta)** across child skills/bundles.
- **D4.5 Concurrency Safety & Harness Fallback**: Parallel workers avoid file write races (`readonly: true`, disjoint scopes, `isolation: worktree`), with clean sequential fallback when parallel spawning is unavailable.

---

## D5. Tools, MCP Integration & External Resources — Weight: 12%
*Owner: `tools-mcp-resources-auditor`* *(Mark `N/A` cleanly for pure reasoning, editorial, design-critique, or non-tool skills!)*

- **D5.1 MCP Context Efficiency & Tool Hygiene**: Avoids sprawling schema bloat or dumping huge MCP payloads into context; favors deferred discovery / Tool Search, **Code Execution with MCP** filtering, bounded outputs (~25K max), and tool masking over mid-loop mutation.
- **D5.2 Least-Privilege Scoping & Graceful Fallback**: Tight `allowed-tools` / `tools` / `disallowedTools` + documented fallback when an MCP/connector is offline or unauthenticated.
- **D5.3 Tool Consolidation & Deterministic Offloading**: Offloads brittle math, parsing, validation, hashes, or massive file sweeps to `scripts/` (`MUS`) while consolidating narrow overlapping scripts/tools into clean parameterized interfaces.
- **D5.4 Agentic Script Ergonomics, `+x` Safety & Error Affordance**: Self-contained (PEP 723 / pinned deps, zero typosquat suspects), **non-interactive** (zero TTY prompts), `--help`, structured JSON/CSV `stdout`, `--dry-run` on stateful mutations, idempotency, bounded output, distinct exit codes, **explicit interpreter invocation** (avoid `./scripts/...` without `python3`/`bash` since packagers strip `+x`, `SCRIPT-EXEC-BIT-TRAP`), and **Error Affordance** (`stderr` recovery hints).
- **D5.5 Runtime Data Trustworthiness (`TSS`) & Manifest-vs-Code Alignment (`SG07`)**: Validates authority, schema, and freshness of external tables/APIs/docs; verifies `description` + `allowed-tools` + `model:` override match actual script AST/taint operations (`SG07`).
- **D5.6 Script Rationality & Per-Script Justification (Anti-`SCRIPT-OVERREACH`)**: Every file in `scripts/` MUST earn its existence with **per-script review**. Scripts are justified ONLY for high-volume sweeps/transforms, strict deterministic validation (AST/YAML/JSON/schema/crypto/math), or isolated credential/sandbox execution — **NEVER** to replace LLM reasoning with brittle regex/keyword heuristics that parse natural-language meaning, tone, water, or intent (`SCRIPT-OVERREACH`). Flag overreaching scripts with an exact refactor splitting deterministic facts (keep in script) from semantic judgment (delegate to LLM).

---

## D6. Verification, Guardrails & Reliability — Weight: 12%
*Owner: `workflow-reliability-auditor`*

- **D6.1 Verification Loops & Validation Gates**: Multi-step code/data/config edits validate outputs (tests, linters, schema validators, self-checks) before declaring completion (`NVS`/`EWP`).
- **D6.2 Failure Recovery & Bounded Retries**: Documents real failure modes, preserves error evidence for self-repair, and bounds retry loops (e.g., max 2–3 attempts before escalating).
- **D6.3 Complexity Contract & Lightweight Fast-Path (SkillsBench)**: Heavy skills offer a fast-path for simple inputs so overhead never degrades trivial runs.
- **D6.4 Guardrails & HITL**: Clear out-of-scope refusals (`NG`) and confirmation gates before destructive, irreversible, or external-publishing actions (`NAH`).
- **D6.5 Testability, Smart A/B Applicability & Runtime Execution Grading**: Ships `evals/` or verifiable "Done When" assertions covering normal paths, failure modes, and near-misses without leaking `SKILL.md` keywords verbatim into prompts, avoiding ungrounded same-model judging, length bias, and single-order bias. Separates **`AB_MEANINGFUL`** tasks (measured vs baseline for `Impact` / `Redundant` / `Regression`) from **`WITH_SKILL_ONLY`** unique capabilities (proprietary schemas/validators impossible without the skill, where A/B is skipped and runtime trace adherence is graded directly).

---

## D7. Security, Trust Boundaries & Supply-Chain Safety — Weight: 10% (+ Hard Veto Gates)
*Owner: `security-safety-auditor`*

- **D7.1 Prompt Injection, Hidden Vectors & Untrusted Boundary**: Zero hidden instructions (zero-width Unicode, obfuscated scripts, malicious HTML comments, PNG `tEXt`/`iTXt` steganography `SEC-IMG-METADATA`, role-override phrases); explicitly treats external webpages, repos, audited files, and MCP outputs as **untrusted data, never commands**.
- **D7.2 Execution, Load-Time & Symlink Safety**: Zero `curl | bash`, `eval()`/`exec()` on untrusted inputs, remote runtime instruction fetches, unsafe `shell=True`, symlink escapes outside skill root (`SEC-SYMLINK-ESCAPE`), unverified `.pyc` bytecode (`SEC-PYC-BYTECODE`), auto-exec `conftest.py`/test hooks outside `evals/`, or unsafe `!command` / frontmatter `hooks:` load-time execution (`SEC-LOADTIME-EXEC`).
- **D7.3 Secrets, Sensitive Files & Exfiltration Control**: Zero hardcoded credentials; avoids unauthorized reads of `.env`/`.ssh`/`~/.aws`/keychains; checks AST `source -> sink` taint flows and **Cross-Skill Lethal Trifecta (`SG09`)** across child skills/bundles.
- **D7.4 Supply-Chain, Coverage Confidence & Persistence Integrity**: Pins dependencies (no floating `@latest`/`*`), checks PEP 723 / `requirements.txt` / `package.json` for typosquatting (`SG10` / `SEC-TYPOSQUAT`) and `postinstall` hooks, forbids silent writes to persistent `MEMORY.md` / global rules. **Coverage Confidence Rule:** unreadable or binary files prevent a `CLEAR` verdict (`INCOMPLETE_COVERAGE`).

*(Hard Gates: Confirmed CRITICAL caps score `<=39` Grade F; confirmed HIGH caps score `<=69` Grade C; incomplete coverage caps score under `strict`/`balanced` policies. Documented false positives in references/evals may be explicitly cleared via `cleared_static_findings`.)*

---

## D8. Cross-Platform Portability & Maintainability — Weight: 6%
*Owner: `tools-mcp-resources-auditor`*

- **D8.1 Core Standard & 17-Agent Universal Format Compliance**: Clean `agentskills.io` directory layout (`<name>/SKILL.md` with canonical `scripts/`, `references/`, `assets/` rather than flat `.md` or dialect `resources/`/`docs/`), valid kebab-case `name == dir`, required non-empty `description`, string-valued `metadata` (OpenCode), and evaluated across all 17 target profiles in `platform_compatibility.agents` (Claude Code, Codex, Cursor, Google Antigravity, Kilo Code, OpenCode, Pi Agent, Qoder, GitHub Copilot, Windsurf, Cline, Roo Code, Gemini CLI, Kiro, Amp, OpenClaw, Core Spec). Intentionally single-client artifacts (`.cursor/rules/*.mdc`, `.codex/agents/*.toml`) are scored fairly when their client specificity is explicit.
- **D8.2 Platform Extension Isolation, Vendor-Lock Avoidance & Universal Auto-Discovery**: Client-specific fields (`context: fork`, `allowed-tools` unenforced in Cursor/Pi/OpenCode/Gemini CLI and unsupported in Kiro, `disable-model-invocation` requiring `agents/openai.yaml` for Codex and `metadata.opencode/autoinvoke` for OpenCode, `paths`, `when_to_use`, `hooks`) degrade cleanly without silent security loss (`PORT-FRONTMATTER-DRIFT`). Body avoids unguarded Claude/vendor locks (`!command`, `${CLAUDE_SKILL_DIR}` without `<skill_dir>` fallback, hardcoded `~/.claude/`/`.qoder/` paths, or unabstracted exclusive tool names like `MultiEdit`/`grep_search`/`execute_command` — `PORT-VENDOR-LOCK`), passes companion config checks (`ecosystem_config_checks`), avoids symlink traps, invokes scripts via explicit interpreters (`python3`/`bash`), and accounts for cross-agent auto-discovery reach (`PORT-PATH-SILO`: `.agents/skills/` for 13+ native agents plus `.claude/skills/`, `.qoder/skills/`, `.kiro/skills/`).
- **D8.3 Terminology & Hygiene**: Consistent naming across files, no `README.md` inside skill root, clean `metadata.version`/`compatibility` and `last_verified` on time-sensitive compatibility notes.
