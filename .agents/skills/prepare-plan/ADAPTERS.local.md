# Prepare Plan — local adapters (this repo)

<!-- Not part of the portable skill core. Safe to delete when copying the skill elsewhere. -->

| Adapter | Value in this repo |
|---------|-------------------|
| `DOCS_ROOT` | `.doc/` |
| `DOCS_RULES` | `.doc/harnes/doc_rules.md` |
| `DOCS_INDEX` | `.doc/architecture/index.md` |
| `DOCS_SEARCH` | MCP `jdocmunch`, repo `local/testdeploy-arch`, `search_sections` первым вызовом |
| `TASK_DIR` | `.doc/tasks/{N}/` |
| `TASK_BRIEF` | `task.md` |
| `TASK_EXPORT` | `.agents/skills/task-router/children/gototask/scripts/gototask.ps1 -Action export-task`; Codex: `.codex/go-task.ps1 -Action export-task` |
| `ROUTER` | `m_router.php` + `.doc/architecture/routes.md`, кандидаты проверяются в коде |
| `MCP_CONFIG` | `.cursor/mcp.json`, `.codex/config.toml` |
| `TEXT_STYLE` | `.cursor/rules/text-style.mdc` |
| `AUDIT_SKILL` | `.agents/skills/task-router/children/audit-plan/SKILL.md` |
| `FIND_RELATED_TASKS` | `powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc {name}.md -Json -Limit 12` |
| `TASKS_FILE_INDEX` | `.doc/tasks/_map/file-to-tasks.tsv`, пересборка `build-tasks-index.ps1 -AlsoTsv` |
| `TASKS_INDEX_MD` | `.doc/tasks/index.md` |
| `TEST_CANON` | `.doc/harnes/testaudit.md`, раздел 9 |
| `CODE_GRAPH_RULES` | `.cursor/rules/mcp/codebase-memory-mcp.mdc`, `.cursor/rules/mcp/codegraph.mdc`, `.cursor/rules/mcp/codeprism.mdc` |

План это только авторский Markdown. JSON-модели, генерируемого view,
механического валидатора и research-ledger нет. Бизнес-аналитик снят с харнеса,
бизнес-правила в план не подтягиваются. Graphiti не используется.

## Docs discovery order (this repo)

1. **Домен или симптом** → `.doc/architecture/index.md`, раздел дерева решений.
   Вопрос формулируется по процессу: оформление заказа, депонирование, отмена,
   тарифы.
2. **Поиск** → `jdocmunch` `search_sections` с `path_glob` по корпусу.

| Корпус | `path_glob` |
|---|---|
| Архитектура домена | `architecture/*` |
| Харнес и правила | `harnes/*` |
| MCP-серверы | `harnes/mcp/*` |
| Задача N | `tasks/{N}/*` |
| Локальная панель | `web/*` |

3. **Чтение** найденного раздела через `get_section_context` или `get_section`.
   Прямое чтение известного пути допустимо после поиска по корпусу или когда
   путь уже известен из `task.md`.
4. **Связанные задачи** → `find-related-tasks.ps1 -Json` по каждому доменному
   документу, score 20 и выше.
5. **Файл в задачи** → `_map/file-to-tasks.tsv`, когда пути патчей известны.
6. **Точные строки** → `git-task-blame`.

```powershell
# пересобрать индекс, если TSV нет
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1 -AlsoTsv

# доменный документ в связанные задачи
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc deposition.md -Json -Limit 12
```

## `BLAST_RADIUS_LADDER` — concrete tools for P1

Источник правил: `CODE_GRAPH_RULES` и `AGENTS.md`. Таблица задает привязку
уровней, а не заменяет порядок из `references/tool-routing.md`. Точные сигнатуры
проверяются при первом вызове.

| Tier | Tool in this repo | Call |
|---|---|---|
| 0 — graph/dependency | `codebase-memory-mcp` | `search_graph`, `trace_path`, `query_graph`, `detect_changes` |
| 0b — module/impact | `codegraph` | `codegraph_explore` с `projectPath` |
| 0b — module/impact | `codeprism` | `get_graph_stats`, `get_context`, `get_callers`, `get_impact`, `get_module_summary` |
| 1 — real call graph (PHP) | `php-deps-mcp` | `phpda_analyze`, `phpcallgraph_generate` |
| 2 — symbol/LSP | `serena` | PHP `find_referencing_symbols`, `find_declaration`; JS, Vue и TPL символьные операции не поддерживаются |
| 3 — full-text | `multi-search` | `multi-search.sh` (rg) по glob для литералов и шаблонов |
| 4 — git history | `git-task-blame` | `git log -L` и `git blame` по диапазону, экспорт task.md |
| 5 — DB schema | `mysql` | `describe_table` |
| 6 — pattern/security | `semgrep` | `semgrep_scan`, `semgrep_findings` |
| 7 — type/static | `phpstan-mcp` | `phpstan_analyze` по файлам и вызывающим |
| 8 — runtime/browser | `playwright`, Codeception | `browser_navigate`, `browser_snapshot`; сначала Cest |

Ограничения:

- `codeprism` и `codegraph` не индексируют Markdown, `.doc`, Smarty. Для них
  только поиск по тексту.
- Свежесть графа проверяется по `indexed_at` из `index_status`, не по факту
  ответа сервера.
- Отключенные серверы `sourcegraph`, `xdebug`, `deepwiki`, `bitbucket-task` в
  маршрут не входят.
- `graphiti` не используется.
- `jira-task` напрямую не вызывается, экспорт идет через `gototask`.

Красный уровень: `rg` по тому же набору расширений, затем чтение целиком и
запись `уровень N красный, компенсирован` в план.

## Timeouts

Это бюджеты ожидания, а не измеренная задержка. Фактический таймаут клиента
проверяется при первом вызове, дата проверки не выдумывается.

| Operation | Cold | Warm | Note |
|---|---|---|---|
| MCP tool call | 90 | 60 | затем уровень помечается timeout, без слепого повтора |
| `git log -L` on a range | 120 | 60 | диапазон, не весь файл |
| `gototask export-task` | 120 | 60 | Jira и проверка ветки |
| `find-related-tasks.ps1` | 120 | 60 | холодный старт PowerShell |
| `build-tasks-index.ps1 -AlsoTsv` | 180 | 90 | пересборка один раз за сессию |
