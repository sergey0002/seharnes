# Plan: REPLACE_TITLE

<!-- meta
type: task-plan
task: REPLACE_TASK_ID
status: draft
updated: REPLACE_DATE
related: [task.md]
tags: [plan]
scope_size: small
risk_level: low
audit_status: pending
plan_rev: 1
audit_passes: 0
last_audit: none
task_closure: 0%
research_complete: false
-->

**Diff principle:** 1 files

## Problem
Replace every REPLACE value with verified task evidence before handoff.

## Sources of truth
| ID | Kind | Where | Decides |
|---|---|---|---|
| T1 | brief | REPLACE_BRIEF | AC1 |
| T2 | code | path/to/file:1 | Existing behavior, from whole-file Read |

## Acceptance criteria
| AC-ID | Criterion | Source | Closed by | Test |
|---|---|---|---|---|
| AC1 | REPLACE_CRITERION | T1 | R1 | S1 |

## Related tasks
none: REPLACE_DISCOVERY_RESULT

## As-is
REPLACE_CODE_PATH. Include entry inventory, IN/OUT callers, invariants and docs/code
differences when applicable; otherwise record a concrete N/A reason.

## Git-история правок (git-task-blame)
| File:range | Task | Status | Change | Invariant | Risk | Scope | Resolution |
|---|---|---|---|---|---|---|---|
| path/to/file:1 | none | REPLACE_HISTORY_STATUS | REPLACE_CHANGE | REPLACE_INVARIANT | REPLACE_RISK | n/a | REPLACE_RESOLUTION |

## Research audit (MCP)
One row per tier. Decision is passed, n/a or red. Replace every reason with actual
evidence. Red requires the exact compensating method in the last column.

| Tier | Decision | Evidence / reason | Compensation |
|---|---|---|---|
| 0 | n/a | REPLACE_GRAPH_REASON | n/a |
| 0b | n/a | REPLACE_MODULE_REASON | n/a |
| 1 | n/a | REPLACE_CALL_GRAPH_REASON | n/a |
| 2 | n/a | REPLACE_SYMBOL_REASON | n/a |
| 3 | n/a | REPLACE_FULL_TEXT_REASON | n/a |
| 4 | n/a | REPLACE_HISTORY_REASON | n/a |
| 5 | n/a | REPLACE_SCHEMA_REASON | n/a |
| 6 | n/a | REPLACE_SECURITY_REASON | n/a |
| 7 | n/a | REPLACE_TYPES_REASON | n/a |
| 8 | n/a | REPLACE_RUNTIME_REASON | n/a |

## To-be
REPLACE_TARGET_BEHAVIOR

## Options
A: REPLACE_MINIMAL_SOLUTION. B only for a real trade-off.

### Architecture check (P4.1)
REPLACE_REUSE_LAYERING_VERDICT

## Decomposition
### R1. REPLACE_REASON
- **Closes:** AC1
- **Truth:** T1, T2
- **Docs:** none: REPLACE_REASON_OR_LINK
- **Independent because:** REPLACE_INDEPENDENCE
- **Files:** `path/to/file`
- **Verified by:** S1

#### S1
- **Layer:** manual
- **Method doc:** none: REPLACE_CANON_OR_EXACT_COMMAND
- **Precondition:** REPLACE_FIXTURE
- **Action:** REPLACE_EXACT_ACTION
- **Expected result:** REPLACE_LITERAL_RESULT
- **State after:** REPLACE_PERSISTED_STATE
- **Must not change:** REPLACE_INVARIANTS
- **If it fails:** REPLACE_STALE_TEST_AND_PATCH_CHECKS

## Правки по файлам
### `path/to/file`
**R:** R1
**Verified by:** S1
**Before:**
```text
REPLACE_UNIQUE_CURRENT_ANCHOR
```
**After:**
```text
REPLACE_COMPLETE_TARGET_TEXT
```

## Files summary
| Action | Count |
|---|---|
| Patch | 1 file |

Intentionally untouched: REPLACE_PATHS_AND_REASONS

## Coverage matrix
| AC-ID | R | S | Status |
|---|---|---|---|
| AC1 | R1 | S1 | open |

## Закрытие задачи
REPLACE_CLOSURE_STATUS. task_closure measures plan coverage, not implementation.

## Verification checklist
REPLACE_REPRODUCIBLE_CHECKS. Apply the behavior contract in plan-writing.md.
Keep the adjacent test.md requirements/branches matrix current.

## Risks and rollback
REPLACE_RISKS_AND_ROLLBACK

## Самопроверка (P5)
Pending. Run references/self-check.md and record the real result.

## Аудит плана
No passes yet. After the first audit add one row per pass. Every audit change also
gets a visible mark next to the changed block, for example:

> Правка аудита A1 (2026-11-10): критерий C1, уточнен блок After.

| Проход | Дата | Аудитор | plan_rev | Что изменено | Открытые находки | Вердикт |
|---|---|---|---|---|---|---|
| A1 | REPLACE_DATE | REPLACE_AUDITOR | 1 | REPLACE_CHANGES | REPLACE_OPEN | pass |

## History
REPLACE_DATE_AND_CHANGE. A re-audit records what the previous pass missed.
