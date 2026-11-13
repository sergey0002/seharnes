---
name: doc-verify
description: >-
  Сверка architecture/*.md с кодом (1=1): MCP Gate codebase-memory-mcp +
  codegraph + serena, связи, задачи, Obsidian. Use when: сверка документации,
  продолжи сверку, verify docs, doc-verify.
---

# Doc Verify

Канон этого скила: `.agents/skills/documentation-router/children/doc-verify/SKILL.md` (зеркала генерируются, править только канон).
MCP Gate: раздел `## MCP обязательно` ниже в этом файле.
Правило: [`.cursor/rules/doc-verify.mdc`](../../../.cursor/rules/doc-verify.mdc)

## MCP обязательно (при ready)

| # | Server | Tools |
|---|--------|-------|
| 1 | `codebase-memory-mcp` (`mcp__codebase-memory-mcp__*` в DSH) | `list_projects`, `index_status`, `search_graph`, `trace_path`, `get_code_snippet` |
| 2 | `codegraph` (`mcp__codegraph__*` в DSH) | `codegraph_explore`, `codegraph_search`, `codegraph_callers`, `codegraph_impact`, `codegraph_status`; `projectPath` для другого проекта |
| 3 | `serena` (`mcp__serena__*` в DSH) | `find_symbol`, `find_referencing_symbols` |

Правило CBM: [mcp-codebase-memory](../../../../../.cursor/rules/mcp/codebase-memory-mcp.mdc). Правило codegraph: [mcp/codegraph.mdc](../../../../../.cursor/rules/mcp/codegraph.mdc). Доки: [codebase-memory-mcp.md](../../../codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md), [codegraph.md](../../../codegraph/docs/mcp/codegraph.md). Sourcegraph выключен (legacy).

## Цикл

V1 batch → V2 Read md → **V3 MCP Gate** → V4 F → V5 L → V6 T → V7 O → V8 write → V9 mark → V10 report (+ блок MCP)
