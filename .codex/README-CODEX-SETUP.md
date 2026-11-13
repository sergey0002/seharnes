# Codex MCP setup — testdeploydocker



Портативный kit в этой папке [`.codex/`](README.md) — зеркало [`.cursor/`](../.cursor/README.md) для **OpenAI Codex CLI**.



## Быстрый старт



```powershell

cd tools\docker-dev

copy .env.dist .env   # если нет .env

docker compose up -d mysql php-apache



cd ..\..

.\.codex\setup.ps1

```



1. **Trust** этот репозиторий в Codex (иначе `.codex/config.toml` не подхватится).

2. Открыть **корень** `testdeploydocker` (не папку `copytrust` выше).

3. `powershell .codex\scripts\verify-codex-mcp.ps1` — проверка trust и файлов.

4. `codex mcp list` или `/mcp` в панели — serena, mysql, git, …

5. Секреты: `.codex/mcp.env` (из `mcp.env.example`). `SOURCEGRAPH_MCP_TOKEN=token sgp_...`



## Отличия от Cursor



| Cursor | Codex |

|--------|-------|

| `.cursor/mcp.json` | **`.codex/config.toml`** (runtime) + `.codex/mcp.json` (зеркало) |

| `envFile` в JSON | `run-with-mcp-env.ps1` + `mcp.env` |

| `.cursor/rules/*.mdc` | `AGENTS.md` + `.codex/rules/*.md` |

| Skills в `.cursor/skills` | `.codex/skills` (канон для Codex); `.agents/` — **deprecated**, не создавать дубли SKILL.md |



Инструкции агента: [`AGENTS.md`](AGENTS.md).



Smoke-test:



```powershell

node .codex\scripts\test-mcp-servers.mjs

```



Подробности Docker/MySQL/PHP: [README-MCP-SETUP.md](README-MCP-SETUP.md).

