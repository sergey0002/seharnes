# MCP: индексация и работа с текущим проектом

Канон (полный текст): [rebase_project.md - MCP: индексация CBM и Sourcegraph](./rebase_project.md#mcp-индексация-cbm-и-sourcegraph) (раздел legacy, агентский маршрут теперь graphify).

Сценарий только среды (без app): [rebase_project.md - AI-kit only](./rebase_project.md#сценарий-c-ai-kit-only-среда-без-app). Промпт агенту: [самодостаточность](./rebase_project.md#самодостаточность-и-промпт-агенту).

Кратко: пути CBM/SG в `.cursor/mcp.json` **не задаются**. Open Folder сам индекс не переключает.

| MCP | Привязка |
|-----|----------|
| serena / git / phpstan | `${workspaceFolder}` |
| **CBM** | `index_repository` + параметр `project` в вызовах |
| **Sourcegraph** (legacy, выключен) | `repos.conf` + фильтр `repo:^src-serve-git-3434/repos/{имя}$` |
| **leantime** (опц.) | `.agents/skills/task-router/children/leantime/scripts/launch.sh` + `.doc/skil_data/leantime/mcp/mcp.env`; UI/API `http://localhost:8095` |
| **graphify** | `graphify-out/graph.json`; stdio через `.cursor/scripts/graphify-mcp-serve.sh`/`.cmd` или один HTTP-контейнер, `http://127.0.0.1:7811/mcp` плюс `project_path` |

CBM: «Проиндексируй этот проект через codebase-memory-mcp»  
graphify: `graphify update .` → `graphify-out/graph.json`; SG-стек только по явной необходимости.

Детали: [`harnes/mcp/codebase-memory-mcp.md`](harnes/mcp/codebase-memory-mcp.md), [`.cursor/graphify-mcp.md`](../.cursor/graphify-mcp.md), [`sourcegraph-local/README.md`](../sourcegraph-local/README.md) (legacy).

Полная таблица 18 MCP-серверов (14 включённых; запуск, статусы, роли): [state/04-mcp.md](harnes/state/04-mcp.md).
