# Скрипт: `.agents/skills/harness-router/children/environment-sync/scripts/generate-agent-configs.py`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-09
related: [../../SKILL.md]
tags: [harness, script, generate-agent-configs, codex, kilo]
-->

## Суть
Генерирует нативные представления для Codex и Kilo из канонического харнеса (`.cursor/rules`, `.agents/skills`, `.cursor/mcp.json`, `.cursor/mcp.env`). Codex читает `.agents/skills` напрямую; копия `.codex/skills` не создаётся. Kilo читает `.agents/skills` напрямую, но нужен `.kilo/kilo.jsonc` с MCP-конфигурацией в формате Kilo (JSONC, `${workspaceFolder}` раскрыт в абсолютный путь, `${env:VAR}` не инлайнятся — секреты остаются в `mcp.env` и подгружаются через общий враппер `run-with-mcp-env.sh`). Правила `.cursor/rules/*.mdc` конвертируются в `.md` без frontmatter; `alwaysApply` правила попадают в `instructions` Kilo, остальные — в `.kilo/rules-index.md`. Для conditional-правил генератор добавляет в индексы Kilo и Codex блок `glob -> rule`, потому что эти среды не умеют автоматическое прикрепление по пути.

## Когда запускать
- После любых изменений в `.cursor/rules/*.mdc` (добавление/удаление/правка правил).
- После изменений в `.cursor/mcp.json` или `.cursor/mcp.env` (MCP-серверы, envFile, переменные).
- После изменений в `.agents/skills` (новые скилы, обновлённые SKILL.md).
- При переносе харнеса в новый проект (`new-project` migrate/update) — для инициализации зеркал Codex и Kilo.
- В составе `sync-agent-views.sh` — полная синхронизация всех адаптеров.

Если не запускать: Codex и Kilo будут работать с устаревшими правилами, навыками и MCP-конфигурацией.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--check-discovery` | | flag | нет | false | Проверка регистрации и bootstrap без записи |
| root (позиционный) |  | string | да | (текущая директория) | Корень проекта (ожидается `.cursor` внутри) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: `.codex` и `.kilo` сгенерированы/обновлены | Продолжить |
| 1 | Не найден `.cursor` в указанном корне | Указать верный корень проекта |

## Что читает и что пишет
**Читает (канон):**
- `.cursor/rules/**/*.mdc` — правила с frontmatter (alwaysApply, globs, description)
- `.cursor/mcp.json` — конфигурация MCP-серверов
- `.cursor/mcp.env` — переменные окружения для MCP
- `.agents/skills/**` - каноническое дерево скилов для discovery

**Пишет (Codex):**
- `.codex/rules/**/*.md` — правила без frontmatter
- `.codex/rules-index.md` — индекс правил (обязательные + по требованию) и generated glob-блок conditional-правил
- `AGENTS.md` - управляемый bootstrap: gate-правила и обязательное чтение индекса
- `.agents/skills.json` - регистрация вложенных скилов Antigravity
- `.dsh/skills/<name>/SKILL.md` - discovery-указатели вложенных скилов на канон
- `.codex/scripts/**` — копия legacy-пула `.cursor/scripts`, если он существует; иначе каталог удаляется
- `.codex/mcp.json` — копия `.cursor/mcp.json` (pretty-print)
- `.codex/mcp.env` — копия `.cursor/mcp.env`
- `.codex/AGENTS.md` — копия корневого `AGENTS.md` с указателем на индекс правил Codex

**Пишет (Kilo):**
- `.kilo/rules/**/*.md` — правила без frontmatter
- `.kilo/rules-index.md` — индекс agent-requested правил и generated glob-блок conditional-правил
- `.kilo/scripts/**` — копия legacy-пула `.cursor/scripts`, если он существует; иначе каталог удаляется
- `.kilo/mcp.env` — копия `.cursor/mcp.env`
- `.kilo/kilo.jsonc` — MCP конфигурация Kilo (JSONC с комментариями-заголовками):
  - stdio серверы → `type: local`, `command` с враппером `bash run-with-mcp-env.sh ...`
  - http/sse серверы → `type: remote`, `url`, `headers`
  - `${workspaceFolder}` → абсолютный путь проекта
  - `${env:VAR}` — не раскрываются, передаются через враппер + `mcp.env`
  - `alwaysAllow` / `disabledTools` → в заголовок комментариев + `.kilo/kilo-permissions.fragment.jsonc`

## Побочные эффекты
- file writes (создание/обновление `.codex/`, `.kilo/`)
- stdout: сводка по количеству правил, скилов, MCP-серверов
- удаляет лишние файлы из управляемых каталогов правил, скилов и скриптов Codex и Kilo

## Окружение и зависимости
- Python 3.8+
- `rule_model` (локальный модуль: `.agents/skills/harness-router/children/environment-sync/scripts/rule_model.py`)
- Переменные окружения: читает `os.environ` для разрешения `${env:VAR}` в `.cursor/mcp.json`
- Файл `.cursor/mcp.env` (KEY=VALUE, поддерживает `export`, комментарии, кавычки)

## Примеры
```bash
# Стандартный запуск из корня проекта
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-agent-configs.py .

# Явный корень
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-agent-configs.py /home/user/project
```

## Ограничения
- Управляемые каталоги перезаписываются: локальные файлы, отсутствующие в каноне, удаляются.
- `.codex/config.toml` не генерируется этим скриптом.
- Не поддерживает MCP-типы кроме `stdio`/`local` и `http`/`sse`/`remote` — остальные пропускаются с предупреждением.
- Для Kilo: `${env:VAR}` намеренно не инлайнятся (секреты в `mcp.env`), stdin-серверы не поддерживаются.
- `run-with-mcp-env.sh` оборачивает только те stdio-серверы, у которых есть `envFile` и argv ещё не содержит враппер (например, `mysql` уже вызывает его сам).
- Codex не имеет триггер-движка: все правила копируются, `alwaysApply` — в обязательные, остальные — в индекс.
- Kilo не раскрывает `${workspaceFolder}` — скрипт раскрывает его заранее в абсолютный путь.

## Связи
- Вызывается: `sync-agent-views.sh` (основной сценарий), `new-project` миграция.
- Зависит от: `rule_model.py` (парсинг frontmatter, классификация правил).
- Генерирует входы для: Codex (`.codex/`), Kilo (`.kilo/`).
- Связанные документы: `.doc/harnes/state/01-canon-envs.md`, `.doc/harnes/state/03-rules.md`.

## История изменений
- 2026-11-07: полная документация на основе анализа кода
- 2026-11-09: описана генерация glob-блока для conditional-правил Kilo и Codex
- 2026-11-09: добавлено удаление лишних файлов зеркал и генерация инструкций Codex из корневого `AGENTS.md`.

## Изменения 2026-11-12

Ссылки перемещённых правил сохраняют каноническую цель. Синхронизация проверяет native discovery отдельно от parity. Codex и Cursor используют канонические скилы; Antigravity получает строковый globs и манифест вложенных скилов, DSH получает discovery-указатели. Bootstrap Codex находится в корневом AGENTS.md и не заменяет встроенные инструкции. Отличающиеся старые копии сохраняются в `.doc/skil_data/environment-sync/backups/`; receipt discovery находится в `.doc/skil_data/environment-sync/discovery.json`.
