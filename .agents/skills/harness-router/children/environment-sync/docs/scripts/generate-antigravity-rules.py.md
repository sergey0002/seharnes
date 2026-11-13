# Скрипт: `.agents/skills/harness-router/children/environment-sync/scripts/generate-antigravity-rules.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, generate-antigravity-rules, antigravity]
-->

## Суть
Генерирует плоский набор правил для Antigravity из канонических `.cursor/rules/**/*.mdc`. Antigravity читает только `.agents/rules/*.md` с обязательным полем `trigger` в frontmatter (`always_on`, `model_decision`, `glob`, `manual`). Скрипт:
- Плющит вложенность: `.cursor/rules/mcp/server.mdc` → `.agents/rules/mcp-server.md`
- Маппит классификацию `rule_model.classify` на Antigravity triggers:
  - `alwaysApply: true` → `always_on`
  - `globs`/`paths` → `glob` + `globs: [...]`
  - только `description` → `model_decision`
  - без сигналов → `manual`
- Копирует тело правила без изменений, добавляя frontmatter с `trigger`, `description`, `globs`.

Удаляет из `.agents/rules/` все файлы и каталоги, отсутствующие в генерируемом представлении.

## Когда запускать
- После изменений в `.cursor/rules/*.mdc` (добавление/удаление/правка правил).
- При настройке Antigravity для проекта.
- В составе `sync-agent-views.sh` — полная синхронизация адаптеров.
- В режиме `--check` — для CI проверки парности.

Если не запускать: Antigravity будет использовать устаревшие правила или правила без правильного `trigger`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --rules-dir |  | string | нет | .cursor/rules | Путь к каноническим правилам |
| --out |  | string | нет | .agents/rules | Куда писать сгенерированные правила |
| --check |  | flag | нет |  | Только проверить актуальность, не писать. Вывод JSON |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Проверка пройдена (в --check) или генерация успешна | Продолжить |
| 1 | Найдены расхождения (в --check) | Запустить без --check для исправления |
| 2 | Не найден `--rules-dir` или коллизия имён файлов | Исправить путь или устранить коллизию |

## Что читает и что пишет
**Читает:**
- `.cursor/rules/**/*.mdc` — правила с frontmatter (`alwaysApply`, `globs`, `paths`, `description`, `trigger`)

**Пишет (в `.agents/rules/`):**
- `*.md` — правила с frontmatter:
  - `trigger: always_on|model_decision|glob|manual`
  - `description: "..."` (если была в каноне)
  - `globs: [...]` (только для `trigger: glob`)
  - тело правила — без изменений
- Имена файлов: плоские, `mcp/server.mdc` → `mcp-server.md`, `code-editing.mdc` → `code-editing.md`

## Побочные эффекты
- file writes (`.agents/rules/*.md`)
- stdout: JSON со статусом `written`/`passed`/`failed`, количеством правил
- `--check` сообщает о лишних файлах и не изменяет представление

## Окружение и зависимости
- Python 3.8+
- `rule_model` (локальный: `split_frontmatter`, `classify`, `rule_paths`)
- Нет внешних зависимостей

## Примеры
```bash
# Генерация/обновление Antigravity правил
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-antigravity-rules.py --root .

# Проверка парности (CI)
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-antigravity-rules.py --root . --check

# Кастомные пути
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-antigravity-rules.py --root /home/user/project --rules-dir .cursor/rules --out .agents/rules
```

## Ограничения
- При генерации `.agents/rules/` полностью пересоздается; локальные файлы не сохраняются.
- Коллизии имён (например, `foo/bar.mdc` и `foo-bar.mdc` оба дают `foo-bar.md`) вызывают exit 2.
- Antigravity не имеет `alwaysApply`/`globs` движка — всё решается через `trigger` поле.
- Если в каноне уже есть `trigger` в frontmatter — он используется как есть (приоритет над маппингом).
- Не обрабатывает MCP конфигурацию — только правила. MCP для Antigravity генерирует `generate-mcp-config.py`.

## Связи
- Вызывается: `sync-agent-views.sh`, `new-project` миграция, ручной запуск.
- Зависит от: `rule_model.py`, `.cursor/rules/**/*.mdc`.
- Генерирует вход для: Antigravity (`.agents/rules/`).
- Пара: `generate-mcp-config.py` (MCP конфиг для Antigravity).
- Связанные документы: `.doc/harnes/state/01-canon-envs.md`, `.doc/harnes/state/03-rules.md`.

## История изменений
- 2026-11-07: полная документация на основе анализа кода
- 2026-11-09: включено удаление лишних правил и проверка вложенных файлов.

## Изменения 2026-11-12

Ссылки перемещённых правил сохраняют каноническую цель. Синхронизация проверяет native discovery отдельно от parity. Codex и Cursor используют канонические скилы; Antigravity получает строковый globs и манифест вложенных скилов, DSH получает discovery-указатели. Bootstrap Codex находится в корневом AGENTS.md и не заменяет встроенные инструкции. Отличающиеся старые копии сохраняются в `.doc/skil_data/environment-sync/backups/`; receipt discovery находится в `.doc/skil_data/environment-sync/discovery.json`.
