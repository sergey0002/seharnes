# Adapters: CopyTrust

Локальные значения проекта. Не переносится. Файл помечен `transferable: false` в узле карты.

| Adapter | Значение | Источник |
|---|---|---|
| `CANON_ROOT_RULES` | `.cursor/rules` | canon-paths.yaml |
| `CANON_ROOT_SKILLS` | `.agents/skills` | canon-paths.yaml |
| `CANON_ROOT_MCP` | `.cursor/mcp.json` | canon-paths.yaml |
| `CANON_ROOT_SCRIPTS` | `.cursor/scripts` | canon-paths.yaml |
| `CANON_ROOT_MCP_SERVERS` | `.tools/mcp-servers` | canon-paths.yaml |
| `DATA_DIR` | `.doc/skil_data/mirror` | локально |
| `PANEL_DIR` | `.doc/web` | локально |
| `VIEWER_AUTOSTART` | сервис `copytrust-tools` на `127.0.0.1:8077`, отдельный 8090 не используется | локально |
| `PANEL_START` | `cd .doc/web && docker compose -p copytrust-tools -f compose.tools.yml up -d` | локально |
| `PANEL_PORT` | `8077`, переопределяется `WEB_PANEL_PORT` | локально |
| `VIEWER_URL` | `http://127.0.0.1:8077/harness/` | локально |
| `EDITOR_URL` | `http://127.0.0.1:8077/harness/` | локально |
| `EDITOR_START` | `cd .doc/web && docker compose -p copytrust-tools -f compose.tools.yml up -d` | локально |
| `PARITY_CHECK` | `python3 .cursor/scripts/harness/verify_parity.py` | canon-paths.yaml |
| `SYNC` | `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` | canon-paths.yaml |
| `REGISTRY` | `.cursor/skills/harness-router/children/improvement/scripts/component_registry.json` | canon-paths.yaml |
| `TEST` | `uvx --quiet pytest .agents/skills/harness-router/children/mirror/tests/test_harness_mirror.py -q` | локально |

## Пути

- Скрипт: `.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py`
- Узлы: `.doc/skil_data/mirror/nodes/*.json`
- Граф: `.doc/skil_data/mirror/graph.json`
- Кеш: `.doc/skil_data/mirror/cache.map`
- Просмотрщик: `.doc/skil_data/mirror/index.html`

Каталог данных лежит вне скила, не копируется в зеркала и не переносится между проектами. Просмотр и правка идут через панель `http://127.0.0.1:8077/harness/`, отдельный процесс `serve` не запускается.

## Область

По умолчанию: `.cursor/rules`, `.cursor/scripts`, `.cursor/mcp-stack`, `.agents/skills`.

Зеркала: `--include-mirrors` добавляет `.codex`, `.kilo`, `.agents`. Legacy `.antigravity` и `.gemini` не генерируются. DSH: `--include-dsh`.

Канон по поддереву: `.cursor/rules`, `.cursor/scripts` и `.agents/skills` дают узлы без суффикса среды. Копии в `.codex`, `.kilo`, `.antigravity`, `.gemini`, `.dsh` и `.agents/rules` остаются зеркалами с суффиксом `@среда`.

Не сканируются: `.doc/` целиком (документация, задачи, состояние), продуктовый код, `.kilo/worktrees`, `.cursor/tools`, каталог данных. Связи на такие пути отбрасываются, поэтому документация и скилы не зависят друг от друга.

## Секреты

`mcp.env`, `*.env`, `*.key`, `*.pem`, файлы с `secret`, `credential`, `token` в имени не разбираются. Файл, в тексте которого найдено значение, похожее на токен, пропускается с сообщением в stderr. Значения переменных в узлы не попадают.

## Синхронизация

После правки канона:

```bash
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py scan --include-mirrors
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py build
```

Скилл не заменяет `sync-agent-views.sh` и `verify_parity.py`, только читает их результат через хеши зеркал.
