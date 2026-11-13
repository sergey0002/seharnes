---
name: codebase-memory-mcp
description: "Explore code structure, callers and diff impact: CBM, search_graph, trace_path, граф кода, кто вызывает. Not for documentation or database schemas; use jdocmunch or mysql. Uses only the current project's codebase-memory-mcp index."
---

# Codebase Memory MCP

Use the graph for code structure and reuse discovery before codegraph and Serena.
Use jdocmunch for documentation and mysql for the actual database schema.

## Workflow

1. Read the [canonical rule](../../../.cursor/rules/mcp/codebase-memory-mcp.mdc)
   for method arguments and the [server document](docs/mcp/codebase-memory-mcp.md)
   for configuration, index coverage and operational history.
2. Call `list_projects` with `detail: stats`; select only the entry whose root
   matches the current workspace. Check `index_status` and its `indexed_at`.
3. Inspect `get_graph_schema` and `get_architecture` for unfamiliar modules.
4. Use `search_graph` to obtain an exact qualified name, then `trace_path`
   for callers and callees. Read source with `get_code_snippet` or
   `get_file_outline`; read the entire affected file before editing.
5. Use `detect_changes` for diff impact. Follow pagination and truncation
   indicators; use `check_index_coverage` before interpreting missing symbols.
6. Report the selected project, source paths, affected callers and coverage gaps.

## Isolation And Safety

- Take `project` from `list_projects`; never query another repository's graph.
- Do not infer freshness from a running watcher. Do not enable `auto_index`.
- Request approval for `index_repository` and `delete_project`. Before an
  explicitly requested push, follow the canonical commit/index/push order.
- Do not reset indexes, ingest traces or change ADR content as a search fallback.
- If the graph is unavailable or stale, report the limitation and use scoped
   source inspection. Missing graph results do not prove missing code.

## History

- 2026-11-10: moved the code-only scope and adjacent-tool boundaries into the discovery description.
