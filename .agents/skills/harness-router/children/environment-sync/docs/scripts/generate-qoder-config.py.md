# Скрипт: `.agents/skills/harness-router/children/environment-sync/scripts/generate-qoder-config.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, generate-qoder-config, qoder]
-->

## Суть
Генерирует проектное представление для Qoder IDE / Qoder CLI из канона (`.cursor/rules`, `.agents/skills`, `.cursor/mcp.json`, `.cursor/mcp.env`). Qoder читает:
- правила: `.qoder/rules/**/*.md` с frontmatter `trigger` (`always_on`, `glob`, `model_decision`, `manual`) и опционально `glob`;
- скилы: `.qoder/skills/{skill}/SKILL.md` (плоское зеркало `.agents/skills`);
- MCP: `.qoder/settings.json` → `mcpServers` (stdio через общий враппер `run-with-mcp-env.sh`, секреты в `mcp.env`).

Маппинг Cursor → Qoder:
- `alwaysApply: true` → `trigger: always_on`
- `globs`/`paths` → `trigger: glob` + `glob: [...]`
- только `description` → `trigger: model_decision`
- без сигналов → `trigger: manual`

Перед записью скрипт останавливается, если находит неизвестные правила, скилы, ссылки или MCP-серверы Qoder. Изменённые файлы по управляемым путям сохраняются в резервную копию. Прочие настройки клиента сохраняются.

## Когда запускать
- После изменений в `.cursor/rules/*.mdc`, `.agents/skills`, `.cursor/mcp.json`, `.cursor/mcp.env`.
- При настройке Qoder для проекта (первый запуск).
- В составе `sync-agent-views.sh` — полная синхронизация адаптеров.
- В режиме `--check` — для CI проверки парности.

Если не запускать: Qoder будет использовать устаревшие правила, скилы и MCP-конфигурацию.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта (где лежит `.cursor/`) |
| --check |  | flag | нет |  | Только проверить актуальность, не писать. Вывод JSON со статусом |
| --preflight |  | flag | нет |  | Без записи проверить неизвестные файлы, ссылки и MCP-серверы перед синхронизацией |
| --replace-managed-mcp |  | flag | нет | false | После отдельного просмотра разрешить замену совпадающих MCP-серверов; предварительно сохранить settings.json |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Проверка пройдена (в --check) или генерация успешна | Продолжить |
| 1 | Найдены расхождения (в --check) | Запустить без --check для исправления |
| 2 | Не найден канонический `.cursor/mcp.json` | Указать верный `--root` |
| 3 | Неизвестные данные Qoder или ошибка резервной копии | Проверить пути и принять решение до повторного запуска |

## Что читает и что пишет
**Читает (канон):**
- `.cursor/rules/**/*.mdc` — правила с frontmatter
- `.cursor/mcp.json` — MCP серверы
- `.cursor/mcp.env` — переменные окружения
- `.agents/skills/**` — дерево скилов

**Пишет (в `.qoder/`):**
- `rules/**/*.md` — правила с frontmatter `trigger`, `description`, `glob` (имя файла = плоское имя: `mcp-server.md` или `code-editing.md`)
- `skills/**` — копия `.agents/skills`; неизвестные локальные файлы блокируют запись
- `settings.json` — MCP конфигурация:
  - HTTP/SSE/remote → `type: http`/`sse`, `url`, `headers`
  - stdio → `type: stdio`, `command`, `args`, `env` (с враппером `bash run-with-mcp-env.sh` если есть `envFile`), `MCP_ENV_FILE` для нестандартных envFile
  - `alwaysAllow` → `alwaysAllow`, `includeTools` → `includeTools`, `disabledTools` → `excludeTools`
  - `enabledProjectMcpServers` — список включённых серверов
  - список MCP-серверов полностью заменяется каноническим

## Побочные эффекты
- file writes (`.qoder/rules/`, `.qoder/skills/`, `.qoder/settings.json`); изменённые файлы сохраняются в `.doc/skil_data/environment-sync/backups/qoder-preflight/`
- stdout: JSON со статусом `written`/`passed`/`failed`, счётчиками правил/файлов скилов/MCP
- `--check` сообщает о лишних правилах, файлах скилов и MCP-серверах

## Окружение и зависимости
- Python 3.8+
- `rule_model` (локальный: парсинг frontmatter, классификация, извлечение globs/paths)
- Переменные окружения: `os.environ` + `.cursor/mcp.env` для `${env:VAR}`
- Файл `.cursor/mcp.env` (KEY=VALUE, `export`, комментарии, кавычки)

## Примеры
```bash
# Генерация/обновление Qoder view
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-qoder-config.py --root .

# Проверка парности (CI)
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-qoder-config.py --root . --check
```

## Ограничения
- Неизвестные файлы, каталоги, симлинки и MCP-серверы Qoder блокируют запись, включая запуск с `--replace-managed-mcp`. Разрешить конфликт нужно вручную; скрипт не удаляет их автоматически. Изменённые управляемые файлы заменяются после резервного копирования. Различия существующего MCP-сервера или его статуса блокируют замену до отдельного просмотра и явного `--replace-managed-mcp`.
- Имена файлов правил плюскуются: `mcp/server.mdc` → `mcp-server.md`. Коллизии имен вызывают exit 2.
- Qoder не имеет `envFile` — stdio серверы идут через `bash run-with-mcp-env.sh`. Секреты остаются в `mcp.env`.
- HTTP серверы: `streamable-http` мапится на `http`, остальные на `sse`.
- `disabled` в каноне → `disabled: true` в Qoder.
- `timeout` из канона прокидывается как есть.

## Связи
- Вызывается: `sync-agent-views.sh`, `new-project` миграция, ручной запуск.
- Зависит от: `rule_model.py`, `.cursor/mcp.json`, `.cursor/mcp.env`, `.agents/skills`.
- Генерирует вход для: Qoder IDE / CLI (`.qoder/`).
- Связанные документы: `.doc/harnes/state/01-canon-envs.md`, `.doc/harnes/state/03-rules.md`.

## История изменений
- 2026-11-07: полная документация на основе анализа кода
- 2026-11-09: управляемые правила, скилы и MCP приведены к строгому зеркалу.

## Изменения 2026-11-12

Ссылки перемещённых правил сохраняют каноническую цель. Синхронизация проверяет native discovery отдельно от parity. Codex и Cursor используют канонические скилы; Antigravity получает строковый globs и манифест вложенных скилов, DSH получает discovery-указатели. Bootstrap Codex находится в корневом AGENTS.md и не заменяет встроенные инструкции. Отличающиеся старые копии сохраняются в `.doc/skil_data/environment-sync/backups/`; receipt discovery находится в `.doc/skil_data/environment-sync/discovery.json`.
