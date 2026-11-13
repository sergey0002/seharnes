## Codebase-memory-mcp (CBM) при индексации

MCP-сервер `codebase-memory-mcp` — **граф кода** (не markdown). При индексации architecture/*.md
используй его **максимально**, чтобы не читать репозиторий вслепую и правильно заполнить `## Связи`.

Полная инструкция: [правило mcp-codebase-memory](../../../../../../.cursor/rules/mcp/codebase-memory-mcp.mdc) и [документация CBM](../../../../codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md)

### Когда вызывать

| Режим | CBM |
|-------|-----|
| MAP | обзор hotspots → приоритеты `_priority.md` |
| SECTION | полный CBM Gate (S4.6) |
| SYNC | `detect_changes` + `search_graph` по изменённым символам |
| AUDIT / VALIDATE | не обязателен (достаточно docscripts) |

### CBM — обзор перед MAP

```
list_projects → index_status
get_architecture → hotspots, routes overview
search_graph query: "[имя крупного модуля из hot-files]" limit: 10
```

Сопоставь hotspots CBM с 🔴A/🟡Б из map-project.ps1. Если CBM показывает высокую связность модуля,
который скрипт занизил — предложи повысить приоритет.

### Лимиты токенов (CBM)

```
✓ search_graph limit: 20 на запрос
✓ trace_path: макс. 3 символа × depth 2 на раздел
✓ get_code_snippet: макс. 5 на раздел — только подтверждённые qualified names
✓ cross_service: обязателен для разделов с Vue/JS + PHP API
✓ semantic_query — массив строк, не одна строка

✗ Не вызывать index_repository без необходимости (проверь index_status)
✗ Не сканировать репо через search_code там, где достаточно search_graph / get_code_snippet
✗ manage_adr — не использовать; ADR живут в .doc/architecture/
✗ Не путать CBM graph (код) с Obsidian graph (.doc/)
```

### Таблица инструментов CBM для project-doc

| Инструмент | SECTION | MAP | SYNC |
|------------|---------|-----|------|
| `list_projects` | ✅ | ✅ | ✅ |
| `index_status` / `index_repository` | ✅ | ✅ | — |
| `get_graph_schema` | 1×/сессия | 1× | — |
| `get_architecture` | ✅ | ✅ | — |
| `search_graph` | ✅ | ✅ | ✅ |
| `trace_path` | ✅ | — | — |
| `get_code_snippet` | ✅ | — | — |
| `search_code` | при front/back | — | ✅ |
| `detect_changes` | S5.1 | — | ✅ |
| `query_graph` | редко | — | редко |
| `manage_adr` | ✗ | ✗ | ✗ |

---
