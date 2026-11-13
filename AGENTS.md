# Copytrust shared agent instructions

Canonical source: `.agents/skills/` for skills, `.cursor/` for rules and MCP.

- Rules: `.cursor/rules/*.mdc`.
- Skills and bundled scripts: `.agents/skills/`. Codex and Cursor read this canon directly; do not generate `.codex/skills` or `.cursor/skills` copies.
- MCP source: `.cursor/mcp.json`, `.cursor/mcp.env`.
- Codex adapters: `.codex/config.toml`, `.codex/go-task.ps1`, `.codex/task-diff.ps1`.
- Kilo adapter: `.kilo/kilo.jsonc`.
- Qoder adapter: `.qoder/rules/*.md`, `.qoder/skills/`, `.qoder/settings.json` are generated from `.cursor/rules`, `.agents/skills` and `.cursor/mcp.json` by the same sync. Qoder reads `AGENTS.md` natively; local additions go to the canon or to `~/.qoder/`.
- Qwen Code adapter: `.qwen/rules/*.md` and `.qwen/settings.json` are generated from `.cursor/rules` and `.cursor/mcp.json`; `.agents/skills` and `AGENTS.md` are read natively, so skills are not duplicated. Local settings go to `.qwen/settings.json` (merged) or `~/.qwen/`.
- Antigravity adapter: `.agents/` is the workspace view (rules, skills, MCP config with expanded paths), built by `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`. Legacy `.antigravity/` and `.gemini/` are removed and not generated.
- `.codex/rules`, `.kilo/rules`, `.agents/rules`, `.qoder/rules`, `.qoder/skills`, `.qwen/rules` are generated mirror views, not symlinks. `.agents/skills` is canon. Do not edit mirrors independently; edit the canon and re-run the sync.
- This is a legacy PHP + Vue project.
- Before code changes read `.doc/architecture/index.md`.
- Before writing under `.doc/`, read `.doc/harnes/doc_rules.md`.
- User message has priority. No git push without explicit request. Do not commit local agent setup.
- For `gototask` and `task-diff`, use `.codex/go-task.ps1` and `.codex/task-diff.ps1`; do not read their SKILL.md through shell.
- Read relevant `.cursor/rules/*.mdc` before project work.
- Отчёты в диалогах (ответ, статус, итог, разбор, сводка, план, таблица результатов) писать по скилу `neiroslop`: `.agents/skills/neiroslop/SKILL.md`. Норма и границы в `.cursor/rules/text-style.mdc`.
- Правка кода: порядок и границы Serena в `.cursor/rules/code-editing.mdc` (PHP полный набор, JS только файловые правки).
- MCP order: codebase-memory-mcp, codegraph, mysql, Serena, context7, Playwright, PHPStan/Semgrep. Sourcegraph выключен (legacy), graphify выведен.
- Documentation search: any mention of docs, a panel, task, architecture, harness, report or dashboard, or a request to "pull context", starts with jdocmunch `search_sections` (repo resolved with `doc_resolve_repo` for the current workspace `.doc`). Choose the corpus with `path_glob` per the rule: `tasks/*`, `architecture/*`, `harnes/*`, `harnes/mcp/*`, `web/*`; separate calls per corpus. Direct Grep of `.doc/` only after an empty MCP result. See `.cursor/rules/mcp/jdocmunch.mdc`.
- MCP карта: `.cursor/rules/mcp.mdc` (назначение, порядок, ссылки). Отдельные правила: `.cursor/rules/mcp-{server}.mdc`; документы: `.doc/harnes/mcp/{server}.md`.
- Shared MCP stack: `.cursor/mcp-stack/{add-project,verify,export,restore}.sh`; topology in `.doc/harnes/state/15-mcp-stack.md`.
- Project isolation: CBM calls pass `project` from `list_projects`; codegraph calls pass `projectPath=<absolute project root>`; serena has one unit per project (9121 testdeploydocker, 9122 cms). Never query another project's graph.
- «тестируй задачу» → `.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md` (Codeception `-g`, не весь suite). Canon: `.doc/harnes/tests.md`.
- Database schema only through mysql `describe_table`; `mysql execute` only with explicit permission.
