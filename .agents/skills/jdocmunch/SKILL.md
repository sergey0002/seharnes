---
name: jdocmunch
description: "Find documentation sections: найди в документации, где описано, подтяни контекст; documentation, architecture, harness, reports and dashboards via jdocmunch MCP. Not for code structure or database schemas."
---

# Jdocmunch MCP

## ⚠️ Kilo Code Mode: JSON-строка на выходе — ОБЯЗАТЕЛЬНЫЙ JSON.parse

**В Kilo Code Mode все инструменты jdocmunch возвращают JSON-строку, а не объект.**  
Прямое обращение к `r.results`, `r.repo` даёт `undefined` и ложный пустой результат (`count: 0` при рабочем индексе).

```js
const parse = (x) => (typeof x === "string" ? JSON.parse(x) : x);
const s = parse(await tools.jdocmunch.search_sections({...}));
const items = s.results || [];  // работает
```

См. [правило `.cursor/rules/mcp/jdocmunch.mdc`](../../../.cursor/rules/mcp/jdocmunch.mdc) раздел «Вызов в среде» и [документ сервера](docs/mcp/jdocmunch.md) П-11 — полный рабочий шаблон.

---

Use section search as the documentation discovery gate. Start documentation
discovery with `search_sections` for the selected corpus; after that, exact known
file paths can be read directly. The project's discovery gate takes precedence
over this shortcut. Code structure and database schemas use their own tools.

## Workflow

1. Read the [canonical rule](../../../.cursor/rules/mcp/jdocmunch.mdc) for the
   corpus table and [server document](docs/mcp/jdocmunch.md) for index operations.
2. Resolve the current documentation root with `doc_resolve_repo` or the project's
   launcher `--repo`; verify that the handle belongs to the current workspace.
   `doc_resolve_repo` takes the `.doc` directory, not the project root.
3. Call `search_sections` with explicit `repo`, `query`, `max_results` and the
   relevant `path_glob`. Separate architecture, harness, task and panel searches.
   Use lexical search; do not request semantic-only search without embeddings.
4. In Kilo Code Mode every tool returns a JSON string, not an object. Parse it with
   `JSON.parse` before reading fields; batch independent searches with `Promise.all`.
   A working `execute` snippet lives in the canonical rule.
5. Take section IDs from results. Use `get_section_context` for orientation,
   `get_section` for full text and `get_document_outline` for large documents.
6. Check returned paths against the selected corpus. On empty or stale results,
   inspect `get_index_overview`, `get_recent_changes` and `list_docs` before a
   scoped direct read. Report index lag instead of treating it as absent content.
7. Cite the actual document path and section. Index updates require explicit
   authorization and the documented launcher. `delete_index`, `doc_index_repo`
   and `define_repo_group` are mutations, never a side effect of an empty search.

## Isolation And Safety

- Always specify the current project's `repo`. Do not search another project's
  index or use cross-project groups such as `all` or `seinline`.
- Use `max_results`, not the ignored `limit` argument; do not fabricate section IDs.
- Do not start documentation discovery with a recursive file scan.
- Moved skill documents can lie outside the current indexed corpus. Read their
  known owning-skill paths after the discovery gate and report that index coverage
  limitation. If MCP is unavailable, report it and use the scoped fallback.
- Do not delete indexes, redefine repository groups or rebuild the corpus merely
   because a search is empty. If MCP is unavailable, state that before fallback.

## History

- 2026-11-11: documented the Kilo Code Mode return contract (JSON string, `JSON.parse`, `Promise.all`) and the `.doc` path for `doc_resolve_repo`.
- 2026-11-10: clarified the discovery gate, Russian triggers and explicit authorization for index mutations.
