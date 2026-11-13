# Skill Authoring Methodology (2026 Frontier Synthesis)

Synthesizes `agentskills.io`, `anthropics/skills` (`skill-creator`), `mattpocock/skills` (`writing-for-agents` + `SKILL-MECHANICS.md` + `grill-me`), `obra/superpowers` (`writing-skills` TDD-for-docs), `openai/skills` (`$skill-creator`), and `skill-auditor` v3.1.0 quality gates.

## 1. Baseline-First Justification (Why This Skill Exists)
Before drafting, establish the **concrete gap** a strong modern frontier model has without the skill:
- **Red-Baseline Mindset (Superpowers):** Identify where an unassisted agent fails, guesses wrong APIs, skips validation, or drifts off convention. Everything the model already does reliably out of the box is a **no-op** and stays out of `SKILL.md`.
- **Two Loads Budget (Matt Pocock):**
  - **Context load:** always-loaded tokens (`description` in startup index, `AGENTS.md`). High recurring cost across every turn -> prune ruthlessly.
  - **Cognitive load:** human burden of remembering a manual `/skill-name` exists. Spend context load only when autonomous triggering or skill-to-skill calls matter.

## 2. Invocation Mode & Splitting Decision
Choose the lightest footprint matching usage:

| Mode | When to use | Frontmatter & Metadata |
|---|---|---|
| **Model-invoked** (default) | Agent should discover & fire autonomously from user intent or another skill needs to call it | Omit `disable-model-invocation`; write sharp trigger `description`; `agents/openai.yaml`: `allow_implicit_invocation: true` |
| **User-invoked** (zero startup load) | Side-effecting workflows (`/deploy`, `/release`) or manual-only routines | Set `disable-model-invocation: true`, `agents/openai.yaml`: `allow_implicit_invocation: false`, `metadata.opencode/autoinvoke: "false"`; make `description` a 1-line human summary |
| **Router skill** | 4+ user-invoked skills overload human memory | One user-invoked router listing sibling `/names` and when to reach for each |

**Split only when earned:**
- **Sequence cut:** split into sub-step or isolated fresh subagent (`context: fork` / subagent file) when post-completion steps tempt the model to rush the active step.
- **Branch / Invocation cut:** split into separate skills when a distinct leading trigger should activate independently.
- **Never duplicate shared reference across two user-invoked skills** — push shared reference to a plain external/shared file both point at.

## 3. Information Hierarchy & Context Pointers
Organize knowledge strictly by frequency of need (Tier 1 -> Tier 3):
1. **In-file steps (`SKILL.md`):** core ordered workflow + hard invariants needed on **every** run (`< 500` lines, ideally `40–150` lines for atomic/tier-2, `< 200` lines for orchestrators).
2. **In-file reference (`SKILL.md`):** concise decision table, `Gotchas`, or single best runnable example needed across most branches.
3. **Disclosed reference (`references/*.md`, max 1 hop deep):** deep schemas, checklists, platform tables, or branch-specific rules loaded **only when that branch fires**.

**Writing sharp Context Pointers (to `SKILL.md` `description` and `references/` links):**
- **Front-load the leading word** (strong pretrained concept token in the first 250 chars).
- **One trigger per branch** (collapse synonyms; each listed case must route to a genuinely distinct case).
- **State explicit load condition** on every `references/` link (`"Read references/foo.md when <condition>"`), never bare filenames (`WEAK-POINTER`).
- **Co-location:** keep a concept's definition, invariant, and gotcha together under one heading instead of scattering across sections.
- **No `CSO-LEAK`:** `description` states `[What it does] + [Symptoms/When to trigger] + [Key negative boundary]`. Never summarize internal workflow steps in `description` (models follow the summary and skip loading `SKILL.md`).

## 4. Frontier Prompt Engineering (High Freedom, Zero Bloat)
Target capable 2026 frontier reasoning models:
- **Positive Framing over Negation (`Elephant` rule):** "NEVER use X" primes X into attention. Lead with the positive target behavior; pair hard invariants with the **reason why** (Theory of Mind) and the preferred replacement.
- **Leading Words over Paragraph Bloat:** prefer crisp anchor tokens (`red/green`, `tracer bullet`, `read-only`, `single source of truth`) over repeating multi-clause explanations.
- **Checkable & Exhaustive Completion Criteria:** close every non-trivial step with an observable done condition (`"Every generated file exists and passes script X with 0 errors"`), blocking premature completion.
- **Calibrated Specificity (Freedom Scale):**
  - *High freedom (guidelines + invariants):* creative synthesis, architecture, prose, code review.
  - *Medium freedom (parameterized workflow):* multi-step integrations, structured reports.
  - *Low freedom (pinned script/CLI flags):* destructive migrations, schema validation, binary packaging.
- **Environment as Truth (No Cache):** do not transcribe `package.json`, directory listings, or `--help` flags that the agent can inspect directly in 1 command; document only unwritten conventions, architectural rationale, and non-obvious gotchas.
- **Zero Anti-Patterns:** no `FLUFF` (filler/textbook explanations), no `CAGE` (arbitrary line/word quotas, forced monologue scripts), no `SCAR` (ALL-CAPS yelling `CRITICAL NEVER EVER` without rationale), no `AMBIG` (unanchored *"as above"*, *"our policy"*), no `CONTRA` (conflicting rules across sections or subfiles).

## 5. Scripts vs LLM Boundary (`D5.6` — Zero `SCRIPT-OVERREACH`)
- **Write a deterministic script (`scripts/`) ONLY when:**
  - Exact formatting/scaffolding/packaging/checksum/AST/schema parsing is required;
  - High-volume computation or repeatable environment verification is fragile via prose;
  - Output must be machine-verifiable (`JSON`, `.skill` ZIP, exit codes, SARIF).
- **Keep with the LLM (NEVER script):**
  - Semantic judgment, regex-guessing intent/quality from prose, interview questioning, domain adaptation, or writing natural instructions.
- **Script quality floor:** standard library first, clean CLI `--help` + `--json`, explicit exit codes, path validation against traversal (`..`) and symlinks, no `shell=True`, no dynamic `eval`/`exec`.
