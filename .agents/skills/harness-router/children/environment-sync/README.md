# environment-sync

Назначение.
Синхронизация правил, скилов и MCP между средами.

Как работает.
Генерирует представления правил, скилов и MCP из канона, проверяет parity и единый visibility-контракт. Гейт-правила должны быть inline; path-правила сохраняют glob-срабатывание или получают сгенерированный glob-блок в средах без glob-механизма. `render_agent_views.py` запускает те же Python-генераторы для project-local views и поддерживает `--check`; полный `sync-agent-views.sh` дополнительно синхронизирует глобальные настройки и выполняет все проверки parity.

Что нужно.
Корень проекта и .

Чего не делает.
Не дублирует библиотеку и не хранит состояние.
Постоянные резервные копии представлений не создаются. Старые копии скилов и распознанный legacy `.codex/AGENTS.md` удаляются без сохранения; управляемые файлы Qoder заменяются после preflight. Неизвестные файлы, симлинки и MCP-серверы Qoder блокируют запись. Замена отличающихся управляемых MCP требует просмотра и `--replace-managed-mcp`.

Перед sync, rebuild или doctor запрещено создавать самодельные tar-архивы и полные снимки Mirror.

## Самостоятельная копия workspace

Workspace получает независимую локальную копию: `setup-workspace.py` копирует SOURCE в пустой TARGET, пересобирает конфиги включённых сред внутри TARGET и пишет `.workspace-ready.json`. `workspace-gate.py` проверяет маркер, входные точки, свежесть представлений и отсутствие пути SOURCE в MCP, затем запускает клиента. `workspace-mcp.py` отдаёт ACP один из трёх локальных stdio серверов из cwd сессии и закрепляет `MCP_WORKSPACE` за TARGET.

```sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/setup-workspace.py --source /ABS_SOURCE --target "$PWD"
python3 .agents/skills/harness-router/children/environment-sync/scripts/workspace-gate.py -- omp acp
python3 .agents/skills/harness-router/children/environment-sync/scripts/workspace-mcp.py --server phpstan-mcp
```

Границы: gate и wrapper работают только из физического TARGET, повторный setup в готовую папку запрещён, секреты копируются, но не печатаются. Публикация prefix и каталога Kandev остаётся отдельным действием оператора.

## Native discovery

Codex и Cursor читают `.agents/skills` без зеркал. Генератор добавляет управляемый bootstrap в корневой `AGENTS.md`: полные gate-правила и требование прочитать обязательные правила из индекса. Остальные always-правила не объявляются inline. `model_instructions_file = "AGENTS.md"` удаляется как старое подключение; пользовательские другие значения не меняются.

Antigravity получает манифест 50 вложенных скилов (состав определяется при генерации), DSH получает плоские discovery-указатели на канон. Qoder сохраняет своё представление, Qwen читает канон. OpenCode читает `.agents/skills` и `AGENTS.md` нативно, получает `opencode.json` (`mcp.servers`) и `.opencode/rules` с компактным индексом. omp читает `.cursor/rules`, `.agents/skills` и `AGENTS.md` нативно и получает только `.omp/mcp.json`; корневые файлы это роутеры, вложенные правила и скилы читаются по ссылкам из них и в зеркало не попадают не находит. Ссылки в перемещённых правилах перенаправляются на канонические ресурсы. Полный набор файлов скилов копирует только Qoder; Qwen получает 28 `rule-*` и однострочные discovery-указатели, DSH только discovery-указатели, Codex и Kilo копий скилов не делают.

### Включение сред

В `.agents/skills/harness-router/children/harness-core/assets/environments.json` измените `enabled` у нужного `id` и запустите `sync-agent-views.sh --local-only` через Bash. `agents` управляет представлением Antigravity/Gemini, `dsh` управляет DeepSeek Harness. `cursor` использует канон напрямую: отключение среды не удаляет `.cursor` и `.agents/skills`.

Синхронизация и перенос используют `render_agent_views.py`. В целевом проекте renderer читает только переключатели `enabled`; генераторы и список управляемых путей берутся из установки, которая запустила renderer. Для добавления среды используйте генератор с `--root` и `--check`, запись в реестре с `generator` и `generated`, адаптер и тесты формата. Специфичные проверки MCP и видимости пока подключаются отдельно.

`compact_agent_views.py --root . --check` показывает кандидатов на очистку всех сред; `--apply` применяет очистку. Для обычного отключения одной среды используйте синхронизацию по `enabled`, без полной очистки.

`generate-agent-configs.py ROOT --check-discovery` проверяет файлы регистрации и bootstrap без записи. Совпадение файлов не доказывает фактическую загрузку клиентом; runtime-проверка выполняется в новой сессии каждой среды.
