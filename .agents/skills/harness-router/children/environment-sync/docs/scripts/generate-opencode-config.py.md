# Скрипт: `.agents/skills/harness-router/children/environment-sync/scripts/generate-opencode-config.py`

<!-- meta
type: script
status: actual
updated: 2026-11-20
related: [../../SKILL.md]
tags: [harness, script, generate-opencode-config, opencode]
-->

## Суть
Генерирует проектное представление для OpenCode v2 из канона (`.cursor/rules`, `.cursor/mcp.json`, `.cursor/mcp.env`). OpenCode читает `AGENTS.md` и `.agents/skills` нативно, поэтому генерируются только правила и MCP:

- правила: `.opencode/rules/**/*.md` без YAML frontmatter, ссылки перебазированы;
- индекс: `.opencode/rules-index.md` с glob-блоком и таблицей правил по требованию;
- MCP: `opencode.json` в корне проекта, серверы под `mcp.servers` в формате v2;
- права: `.opencode/permissions.fragment.json` для ручного слияния, как у Kilo.

Маппинг правил:
- `alwaysApply: true` попадает в `instructions` и грузится в каждый запрос;
- остальные правила попадают в `.opencode/rules-index.md` и читаются по триггеру.

## Когда запускать
- После изменений в `.cursor/rules/*.mdc`, `.cursor/mcp.json`, `.cursor/mcp.env`.
- При настройке OpenCode для проекта.
- В составе `sync-agent-views.sh` перед проверками parity.
- В режиме `--check` для CI и `doctor`.

Если не запускать: OpenCode будет видеть устаревшие правила и MCP-конфигурацию.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта, где лежат `.cursor/` и `.agents/` |
| --check |  | flag | нет |  | Только проверить актуальность, не писать. Вывод JSON со статусом |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Генерация успешна или проверка пройдена | Продолжить |
| 1 | Найдены расхождения в `--check` | Запустить без `--check` |
| 2 | Не найден канонический `.cursor/mcp.json` или `.cursor/rules` | Указать верный `--root` |

## Что читает и что пишет
**Читает (канон):**
- `.cursor/rules/**/*.mdc` - правила и frontmatter для классификации;
- `.cursor/mcp.json` - MCP серверы;
- `.cursor/mcp.env` - переменные окружения.

**Пишет:**
- `.opencode/rules/**/*.md` - тело правила без frontmatter, плоские имена сохраняют вложенность `mcp/*.md`;
- `.opencode/rules-index.md` - glob-блок и таблица правил по требованию;
- `.opencode/permissions.fragment.json` - `alwaysAllow`/`disabledTools` из канона, ручное слияние;
- `opencode.json`:
  - `$schema`: `https://opencode.ai/config.json`;
  - `instructions`: always-правила и `.opencode/rules-index.md`;
  - `mcp.servers`: `type: local` с массивом `command` или `type: remote` с `url`;
  - отключённые в каноне серверы получают `disabled: true`;
  - локальные серверы и прочие ключи существующего `opencode.json` сохраняются.

## Побочные эффекты
- file writes (`.opencode/`, `opencode.json`);
- stdout: JSON со статусом `written`/`passed`/`failed` и счётчиками;
- `--check` ничего не пишет.

## Окружение и зависимости
- Python 3.8+;
- `rule_model` (классификация ALWAYS/CONDITIONAL/AGENT_REQUESTED/MANUAL, снятие frontmatter, перебазирование ссылок);
- `.cursor/mcp.env` и `os.environ` для `${env:VAR}`;
- обёртка `.tools/scripts/run-with-mcp-env.sh` для stdio-серверов с `envFile`.

## Примеры
```bash
# Генерация/обновление OpenCode view
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-opencode-config.py --root .

# Проверка парности (CI, doctor)
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-opencode-config.py --root . --check
```

## Ограничения
- OpenCode не раскрывает `${workspaceFolder}` и `${env:VAR}` в JSON, поэтому пути пишутся абсолютными, а заголовки переводятся в `{env:NAME}`.
- У OpenCode нет `envFile`: stdio-серверы идут через `run-with-mcp-env.sh`, секреты остаются в `.cursor/mcp.env`.
- `timeout` канона не переносится: в v2 `mcp.servers` это объект `{startup, catalog, execution}`, а не число.
- В v2 отключение задаётся `disabled`, поля `enabled` в `mcp.servers` нет.
- `alwaysAllow`/`disabledTools` не попадают в `opencode.json` автоматически: они лежат в fragment для ручного слияния.
- У отключённого сервера заголовки не переносятся: секрет не попадает в `opencode.json`, пока сервер снова не включат и не перезапустят генерацию.
- `opencode.json` генерируется в корне и исключается из git как локальная настройка агента.

## Связи
- Вызывается: `sync-agent-views.sh`, `harness_cli.py doctor` (gate `opencode-view`), ручной запуск.
- Зависит от: `rule_model.py`, `.cursor/mcp.json`, `.cursor/mcp.env`.
- Генерирует вход для: OpenCode v2 (`.opencode/`, `opencode.json`).
- Проверяется: `verify_rule_triggers.py --opencode`, `verify_mcp_views.py --opencode`.
- Связанные документы: `.doc/harnes/state/01-canon-envs.md`, `.doc/harnes/add-editor-environment.md`.

## История изменений
- 2026-11-20: создан скрипт и документация для среды OpenCode v2.
