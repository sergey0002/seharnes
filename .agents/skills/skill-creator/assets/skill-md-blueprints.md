# SKILL.md Archetype Blueprints (Pick Lightest Sufficient Form)

Choose the lightest blueprint that solves the baseline gap. Keep every line testable against the no-op rule (*"If deleted, does a frontier model regress?"*).

---

## 1. Atomic Frontier Skill (Target: 35–75 lines)
Best for focused conventions, reviews, or domain workflows where a single cohesive document suffices.

```markdown
---
name: <kebab-case-name>
description: <What it produces>. Use when <specific trigger branches/symptoms>. Do NOT use for <adjacent exclusions>.
license: MIT
metadata:
  author: "<owner>"
  version: "1.0.0"
---

# <Title>

<One-sentence role and non-obvious invariant.>

## Workflow
1. **<Step 1 — observable action>** -> Done when: <checkable completion criterion>.
2. **<Step 2 — core synthesis/execution>** -> Done when: <checkable criterion>.
3. **<Step 3 — verification>** -> Done when: <passing check or diff verified>.

## Reference Rules & Gotchas
- **<Domain rule>:** <Positive instruction + why it prevents failure.>
- **<Edge-case gotcha>:** <Exact failure observed without the skill and the concrete fix.>
```

---

## 2. Script-Backed Skill (Tier 2, Target: 60–120 lines)
Best when exact schemas, AST/file parsing, formatting, or packaging need deterministic scripts (`scripts/`) alongside LLM judgment.

```markdown
---
name: <kebab-case-name>
description: <What it automates and evaluates>. Use when <trigger scenarios>. Do NOT use for <exclusions>.
license: MIT
compatibility: "Requires Python 3.10+ (standard library)."
metadata:
  author: "<owner>"
  version: "1.0.0"
---

# <Title>

<Why deterministic script + semantic LLM split is used.>

## Workflow
1. **Inspect inputs** -> Done when target paths and constraints are confirmed.
2. **Run [the deterministic check](scripts/<helper>.py):**
   ```bash
   python3 scripts/<helper>.py "<target>" --json
   ```
   -> Done when exit code is `0` and JSON report is captured.
3. **Apply domain judgment** using [the domain guide](references/<guide>.md) (load when handling `<branch condition>`) -> Done when all findings are resolved.
4. **Verify & deliver** -> Done when re-running the script passes clean.

## Gotchas
- **<Common script/env trap>:** <Concrete recovery action.>
```

---

## 3. Multi-Agent Orchestrator (Tier 3, Target: 90–180 lines)
Best for complex pipelines needing fresh subagent context windows (`agents/*.md`) and shared `references/`/`evals/`.

```markdown
---
name: <kebab-case-name>
description: <Multi-stage capability>. Use when <high-complexity triggers>. Do NOT use for <simple single-step tasks>.
license: MIT
metadata:
  author: "<owner>"
  version: "1.0.0"
---

# <Title>

<Mission + orchestration invariant (e.g., isolate independent checks in fresh context windows).>

## Pipeline
1. **Preflight & Dispatch** -> Run `scripts/<preflight>.py` and dispatch independent checks from `agents/`.
   - **Sequential Fallback:** If the host runtime lacks parallel subagent spawning, run each role sequentially with clean handoff notes.
   -> Done when every delegated artifact is returned.
2. **Deep Reference Routing (Branch-Conditional)**
   - Load [criteria](references/<criteria>.md) before scoring edge cases.
   - Load [templates](assets/<template>.md) only when rendering final output.
3. **Synthesize & Verify** -> Done when schema validation passes and every claim cites observed file paths/outputs.

## Gotchas
- **Cross-file consistency:** keep single source of truth across `SKILL.md`, `agents/`, and `references/`.
```

---

## 4. User-Invoked / Router Skill (Zero Startup Context Load)
Best for explicit manual slash-commands (`/deploy`, `/release`) or a router indexing 4+ manual sibling skills.

```markdown
---
name: <kebab-case-name>
description: <One-line human-facing summary for skill picker.>
disable-model-invocation: true
license: MIT
metadata:
  author: "<owner>"
  version: "1.0.0"
  opencode/autoinvoke: "false"
---

# <Title>

<Preconditions + explicit confirmation gate before side effects.>

## Manual Routines / Sibling Router
- **`/<sibling-a>`** — reach for when `<concrete situation A>`.
- **`/<sibling-b>`** — reach for when `<concrete situation B>`.

## Execution Steps
1. Verify prerequisites (`git status`, target env, dry-run diff) -> Done when preflight prints clean.
2. Request explicit user confirmation before irreversible mutations.
3. Execute and verify post-state -> Done when health check passes.
```
*(Pair with `agents/openai.yaml` setting `policy.allow_implicit_invocation: false`.)*
