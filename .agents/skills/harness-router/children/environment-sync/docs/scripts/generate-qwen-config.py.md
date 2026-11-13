# Скрипт: `.agents/skills/harness-router/children/environment-sync/scripts/generate-qwen-config.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, generate-qwen-config, qwen]
-->

## Суть
Генерирует проектное представление для Qwen Code из канона (`.cursor/rules`, `.agents/skills`, `.cursor/mcp.json`, `.cursor/mcp.env`). Qwen читает:
- правила: `.qwen/rules/**/*.md` — baseline (без `paths`) или conditional (с `paths:`). Agent-requested правила (только `description`) превращаются в скилы `.qwen/skills/rule-<name>/SKILL.md`, потому что у Qwen нет model-decision триггера, а baseline копия висела бы в каждом запросе.
- скилы проекта Qwen читает нативно из `.agents/skills`.
- MCP: `.qwen/settings.json` → `mcpServers`:
  - HTTP/streamable-http → `httpUrl`
  - SSE/remote → `url`
  - stdio → `command`/`args` через враппер `bash run-with-mcp-env.sh`, секреты в `mcp.env`
  - `alwaysAllow` → `trust: true`, `includeTools`/`disabledTools` → `includeTools`/`excludeTools`
  - отключённые в каноне серверы → в `mcp.excluded` (удаляются из merged view)

Скрипт удаляет лишние правила, сгенерированные скилы `rule-*` и MCP-серверы. Прочие скилы и настройки Qwen сохраняются.

## Когда запускать
- После изменений в `.cursor/rules/*.mdc`, `.agents/skills`, `.cursor/mcp.json`, `.cursor/mcp.env`.
- При настройке Qwen Code для проекта.
- В составе `sync-agent-views.sh` — полная синхронизация адаптеров.
- В режиме `--check` — для CI проверки парности.

Если не запускать: Qwen будет использовать устаревшие правила, скилы и MCP-конфигурацию.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта (где лежит `.cursor/`) |
| --check |  | flag | нет |  | Только проверить актуальность, не писать. Вывод JSON со статусом |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Проверка пройдена (в --check) или генерация успешна | Продолжить |
| 1 | Найдены расхождения (в --check) | Запустить без --check для исправления |
| 2 | Не найден канонический `.cursor/mcp.json` | Указать верный `--root` |

## Что читает и что пишет
**Читает (канон):**
- `.cursor/rules/**/*.mdc` — правила с frontmatter
- `.cursor/mcp.json` — MCP серверы
- `.cursor/mcp.env` — переменные окружения
- `.agents/skills/**` — дерево скилов

**Пишет (в `.qwen/`):**
- `rules/**/*.md` — baseline/conditional правила:
  - frontmatter: `description` (опционально), `paths: [...]` (только для conditional)
  - имя файла = плоское: `mcp-server.md`, `code-editing.md`
- `skills/rule-<name>/SKILL.md` — для agent-requested правил (name = `rule-<sanitized>`)
- `settings.json` — MCP конфигурация:
  - `httpUrl` для HTTP/streamable-http, `url` для SSE/remote
  - stdio: `command`, `args`, `env` (с враппером), `MCP_ENV_FILE`, `cwd`
  - `trust`, `includeTools`, `excludeTools`, `timeout`
  - `mcp.excluded` — список отключённых в каноне серверов
  - список MCP-серверов и `mcp.excluded` заменяются по канону; другие настройки сохраняются

## Побочные эффекты
- file writes (`.qwen/rules/`, `.qwen/skills/`, `.qwen/settings.json`)
- stdout: JSON со статусом `written`/`passed`/`failed`, счётчиками
- `--check` сообщает о лишних управляемых правилах, скилах и MCP-серверах

## Окружение и зависимости
- Python 3.8+
- `rule_model` (локальный: парсинг frontmatter, классификация ALWAYS/CONDITIONAL/AGENT_REQUESTED/MANUAL)
- Переменные окружения: `os.environ` + `.cursor/mcp.env` для `${env:VAR}`
- Файл `.cursor/mcp.env` (KEY=VALUE, `export`, комментарии, кавычки)

## Примеры
```bash
# Генерация/обновление Qwen view
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-qwen-config.py --root .

# Проверка парности (CI)
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-qwen-config.py --root . --check
```

## Ограничения
- Локальные правила и скилы `rule-*` удаляются, если отсутствуют в каноне; остальные скилы Qwen сохраняются.
- Имена файлов правил плюскуются с санитизацией не-алфавитно-цифровых символов в `-`.
- Agent-requested правила (только description) → скилы `rule-<name>`, потому что Qwen не имеет model_decision триггера.
- Qwen не имеет `envFile` — stdio через `bash run-with-mcp-env.sh`, секреты в `mcp.env`.
- `disabled` в каноне → попадает в `mcp.excluded` и удаляется из merged view.
- HTTP: `streamable-http` → `httpUrl`, SSE/remote → `url` (разные поля у Qwen).

## Связи
- Вызывается: `sync-agent-views.sh`, `new-project` миграция, ручной запуск.
- Зависит от: `rule_model.py`, `.cursor/mcp.json`, `.cursor/mcp.env`, `.agents/skills`.
- Генерирует вход для: Qwen Code (`.qwen/`).
- Связанные документы: `.doc/harnes/state/01-canon-envs.md`, `.doc/harnes/state/03-rules.md`.

## История изменений
- 2026-11-07: полная документация на основе анализа кода
- 2026-11-09: управляемые правила и MCP приведены к строгому зеркалу.

## Изменения 2026-11-12

Ссылки перемещённых правил сохраняют каноническую цель. Синхронизация проверяет native discovery отдельно от parity. Codex и Cursor используют канонические скилы; Antigravity получает строковый globs и манифест вложенных скилов, DSH получает discovery-указатели. Bootstrap Codex находится в корневом AGENTS.md и не заменяет встроенные инструкции. Отличающиеся старые копии сохраняются в `.doc/skil_data/environment-sync/backups/`; receipt discovery находится в `.doc/skil_data/environment-sync/discovery.json`.

### Вложенные скилы (2026-11-12)

Qwen сканирует корень скилов на один уровень. Для вложенных канонических скилов `generate-agent-configs.py` создаёт короткие указатели `.qwen/skills/<name>/SKILL.md`. Они требуют прочитать канон целиком, не копируют ресурсы и отслеживаются discovery receipt. `skills.directories` не используется: такие скилы получают personal scope, что меняет модель доверия.

Источник: [Qwen skills](https://qwenlm.github.io/qwen-code-docs/en/users/features/skills/).
