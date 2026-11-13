# Designing Evals & Trigger Optimization Sets

Great skills ship with **verification**, not hope. Follow this guide to build `evals/evals.json` and `evals/trigger_evals.json` compatible with both `skill-auditor`'s AI-gated `eval_runner.py` and `anthropics/skills` benchmarks.

## 1. Functional Evals (`evals/evals.json`)

Write **3–6 realistic prompts** covering:
1. Primary happy path (representative realistic phrasing, file names, domain context).
2. Secondary branch / edge case (error handling, missing inputs, partial artifacts).
3. Safety / refusal / user-invoked boundary (when the skill should refuse, clarify, or block a bad mutation).

### Critical Rule: AI-Gated Applicability (`AB_MEANINGFUL` vs `WITH_SKILL_ONLY`)
Not every skill benefits from blind `with_skill` vs `without_skill` A/B benchmarking:
- **`AB_MEANINGFUL`:** use when a base model can attempt the task without the skill (code style, refactoring, report formatting, architectural decisions), and the skill proves measurable delta in accuracy, safety, or adherence.
- **`WITH_SKILL_ONLY`:** use when the skill provides custom scripts, proprietary internal conventions, domain files, or external workflow integrations **impossible to invent without the skill**. Running a baseline `without_skill` run on `WITH_SKILL_ONLY` wastes tokens proving the model lacks a secret script.

Record this classification explicitly per case (or default) using `eval_mode`:
```json
{
  "skill_name": "<skill-name>",
  "default_eval_mode": "AB_MEANINGFUL | WITH_SKILL_ONLY",
  "evals": [
    {
      "id": 1,
      "eval_mode": "AB_MEANINGFUL",
      "prompt": "Realistic user request...",
      "expected_output": "Observable outcome description",
      "files": [],
      "expectations": [
        "Specific, objectively verifiable assertion (file created, JSON field present, command exited 0)"
      ]
    }
  ]
}
```
Prefer **3–5 crisp, verifiable assertions** per eval checking structural/semantic correctness rather than fragile string matching.

## 2. Trigger Evals (`evals/trigger_evals.json`)
Skip `trigger_evals.json` ONLY for user-invoked skills (`disable-model-invocation: true`) that never trigger autonomously.

For model-invoked skills, create **16–20 queries** split **50/50** (should-trigger vs near-miss should-not-trigger):
- **Should-trigger (`true`, 8–10 queries):** vary phrasing across formal, casual, terse, typo-tolerant, implicit symptoms (not naming the skill directly), and multilingual requests if relevant (e.g., EN + RU).
- **Near-miss should-not-trigger (`false`, 8–10 queries):** use adjacent domain vocabulary that belongs to a **neighboring skill** or general coding (avoid trivially unrelated queries like *"write a Fibonacci function"* — those prove nothing).
- **Anti-Overfitting Split (`60/40`):** when iterating on `description` (`run_loop` style), hold out 40% of queries as validation and select the best description by **validation pass rate**, not training fit.
- **Zero `CSO-LEAK`:** optimize phrasing with intent cues and negative boundaries (`"Do NOT use for..."`), never leaking internal steps into `description`.
