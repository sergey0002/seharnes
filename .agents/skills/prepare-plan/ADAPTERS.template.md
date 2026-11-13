# ADAPTERS.template.md — project bindings for a portable skill (P11)

> Copy this file to `ADAPTERS.local.md` next to the skill `SKILL.md` and fill the
> values. `ADAPTERS.local.md` is developer-local: do not put secrets in it. Delete
> this template copy when porting the skill to another project.

| Adapter | Meaning | Value in this project |
|---|---|---|
| `DOCS_ROOT` | Project docs root (or empty when none) | |
| `DOCS_RULES` | Doc writing rules | |
| `DOCS_INDEX` | Architecture index / TOC | |
| `DOCS_SEARCH` | Documentation search handle and corpora | |
| `AUDIT_SKILL` | Skill that audits the finished plan | |
| `TASK_DIR` | Per-task folder pattern | |
| `TASK_BRIEF` | Tracker export / brief filename | |
| `TASK_EXPORT` | Command to refresh brief without branch switch | |
| `ROUTER` | HTTP entry map | |
| `MCP_CONFIG` | Where MCP servers are listed | |
| `TEXT_STYLE` | Chat/plan style rules | |
| `FIND_RELATED_TASKS` | Console script: arch-doc to ranked task IDs | |
| `TASKS_FILE_INDEX` | Machine index file-to-task IDs | |
| `TASKS_INDEX_MD` | Human index of tasks | |
| `TEST_CANON` | Requirement/branch matrix and stage-test rules | |
| `CODE_GRAPH_RULES` | Canonical tool signatures, order, freshness and paging | |
| `BLAST_RADIUS_LADDER` | Capability tiers mapped to installed tools | |

## Verification

After filling, run the skill's own preflight step (P0.1 in prepare-plan)
and confirm every adapter resolves: docs open, export runs, index queries
return rows. Unresolvable adapter = explicit `N/A: <reason>` in the plan,
never a guessed path.

Pass `--root` for nonstandard workspace layouts. There is no plan validator, JSON
plan model or research ledger to run.
