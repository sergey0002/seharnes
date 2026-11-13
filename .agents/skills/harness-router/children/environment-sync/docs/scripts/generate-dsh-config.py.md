# Скрипт: `.agents/skills/harness-router/children/environment-sync/scripts/generate-dsh-config.py`

<!-- meta
type: script
status: actual
updated: 2026-11-09
related: [../../SKILL.md]
tags: [harness, script, generate-dsh-config, dsh, deepseek]
-->

## Суть
Генерирует два артефакта для DeepSeek Harness (DSH) из канона (`.cursor/rules`, `.cursor/mcp.json`, `.cursor/mcp.env`):
1. `.dsh/project.patch.yml` — loader patch для DSH. DSH не имеет rules-движка и rules-файла: workspace guidance инжектится из instruction-файлов (AGENTS.md, CLAUDE.md, настроенные extras), скилы берутся из проектных корней (`.agents/skills` среди них), MCP-серверы существуют только как явные плагины `dsh-mcp-client`. Patch патчит существующие строки по `id`; новые `mcp-client` инстансы добавляются через один `insert` список (patch по неизвестному id отклоняется лоадером).
2. `DSH-RULES.md` (или `DSH-BOOTSTRAP.md` при `--rules-mode compact`) — полный текст always-правил и on-demand указательную таблицу. Conditional-правила получают отдельный generated glob-блок, потому что DSH не прикрепляет правила автоматически по пути. Канонический текст правил остаётся в `.cursor/rules`.

МCP-профили (`--mcp-profile`): `full` (все), `research`, `implementation`, `verification` — подмножества серверов для стартового патча. Не переключают живую сессию — нужно явно передать patch при запуске `dsh --patch ...`.

## Когда запускать
- После изменений в `.cursor/rules/*.mdc`, `.cursor/mcp.json`, `.cursor/mcp.env`.
- При настройке DSH для проекта (первый запуск).
- В составе `sync-agent-views.sh` — полная синхронизация адаптеров.
- При смене профиля MCP (`--mcp-profile`) или режима правил (`--rules-mode`).
- В режиме `--check` — для CI проверки парности.

Если не запускать: DSH будет запускаться с устаревшими instruction-файлами, неправильным набором MCP-клиентов и без актуальных правил.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | Path | нет | cwd | Корень проекта |
| --patch-out |  | Path | нет | `<root>/.dsh/project.patch.yml` | Куда писать patch (варианты: `project.{profile}-{mode}.patch.yml`) |
| --rules-out |  | Path | нет | `<root>/DSH-RULES.md` | Куда писать правила (`DSH-BOOTSTRAP.md` для compact) |
| --rules-mode |  | choice | нет | full | `full` = инлайн always + таблица on-demand; `compact` = bootstrap-навигация |
| --mcp-profile |  | choice | нет | full | `full`, `research`, `implementation`, `verification` — стартовый набор MCP |
| --servers |  | string | нет | "" | CSV allow-list, перекрывает профиль |
| --exclude |  | string | нет | "" | CSV имена серверов для пропуска (xdebug уже disabled в каноне) |
| --no-mcp |  | flag | нет |  | Пропустить MCP entries в patch |
| --overlay |  | Path | нет | `<root>/.dsh/models.overlay.json` | DSH-only model overlay (llm_pi_ai, model_selection, subagent, workflow) |
| --no-llm |  | flag | нет |  | Убрать llm-pi-ai из patch (deepseek-account остаётся единственным маршрутом) |
| --no-model-selection |  | flag | нет |  | Форсировать `modelSelectionSettings=false` в subagent config |
| --check |  | flag | нет |  | Сравнить выходы без записи и без печати секретов; ручной patch считается непроверенным и возвращает ошибку |
| --force |  | flag | нет |  | Перезаписать ручно поддерживаемый `project.patch.yml` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (генерация или check passed) | Продолжить |
| 1 | Check failed (расхождения) или unreadable output | Запустить без --check или исправить входные данные |
| 2 | Аргумент/входная ошибка: не найден `.cursor/mcp.json` или `.cursor/rules`, конфликт путей, битый overlay | Исправить аргументы/входные файлы |

## Что читает и что пишет
**Читает (канон):**
- `.cursor/rules/**/*.mdc` — правила (frontmatter + тело)
- `.cursor/mcp.json` — MCP серверы
- `.cursor/mcp.env` — переменные окружения
- `.dsh/models.overlay.json` (опционально) — DSH-only entries: `llm_pi_ai`, `model_selection`, `subagent`, `workflow`

**Пишет:**
- `.dsh/project.patch.yml` (или вариант) — YAML patch:
  - `agent-instructions` (id) → `instructionFileCandidates`: `["AGENTS.md", "CLAUDE.md", "DSH-RULES.md"]`
  - `insert:` список `mcp-client-<name>` → `@deepseek-ai/dsh-mcp-client` с конфигом:
    - HTTP/SSE/remote → `transport: streamable-http`, `url`, `headers`, `toolCallTimeoutMs: 120000`
    - stdio → `transport: stdio`, `command`, `args`, `env` (merged envFile + inline, раскрыты токены), `cwd`, `toolCallTimeoutMs: 120000`
  - overlay entries (llm-pi-ai, tool-subagent, tool-workflow, model-selection-settings)
- `DSH-RULES.md` / `DSH-BOOTSTRAP.md`:
  - `full`: always правила инлайнены целиком (без frontmatter), on-demand содержит generated glob-таблицу и `| Rule | Trigger | File |`
  - `compact`: bootstrap-навигация с таблицей всех правил и напоминанием читать канон
- Относительные markdown-ссылки в телах правил ребейзятся от `.cursor/rules/` к корню репозитория.

## Побочные эффекты
- file writes (атомарная замена через временный файл, сохраняются права 0600)
- stdout: JSON со статусом, путями, списками added/skipped MCP, количеством entries
- patch и rules — независимые выводы (не транзакция)

## Окружение и зависимости
- Python 3.8+
- `rule_model` (локальный: `rule_frontmatter`, `classify`)
- Переменные окружения: `os.environ` + `.cursor/mcp.env` для `${env:VAR}` (в patch раскрываются, в rules — нет)
- Файл `.cursor/mcp.env` (KEY=VALUE, `export`, комментарии, кавычки)

## Примеры
```bash
# Полная генерация (default profile full, rules full)
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-dsh-config.py --root .

# Research профиль + compact rules (bootstrap)
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-dsh-config.py --root . --mcp-profile research --rules-mode compact

# Явный allow-list серверов
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-dsh-config.py --root . --servers "codebase-memory-mcp,serena,mysql" --patch-out .dsh/project.custom.patch.yml

# Проверка парности (CI)
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-dsh-config.py --root . --check

# Запуск DSH с сгенерированным патчем
dsh --patch .dsh/project.patch.yml web --no-open
```

## Ограничения
- Patch и rules — разные файлы, не транзакция. Если упало на середине — одно обновилось, другое нет.
- Не удаляет ручно созданный `project.patch.yml` без `--force` (детектируется по маркеру в заголовке).
- MCP-профили влияют только на стартовый patch. Живую сессию не переключают — нужно рестартовать с новым patch.
- `xdebug` disabled в каноне по умолчанию. При включении в Antigravity view получает порт 9004, здесь — обычный stdio конфиг.
- Overlay JSON читается один раз при генерации. Битый overlay = exit 2.
- `--no-llm` и `--no-model-selection` — deliberate environment switches, чтобы сгенерированный patch не правили руками после генерации.
- При выборе серверов или моделей в режиме full/full нужно явно указать `--patch-out`, чтобы не перезаписать стандартный patch.
- `instructionFileCandidates` включает `DSH-RULES.md` (или `DSH-BOOTSTRAP.md`) — DSH сам выберет первый существующий.

## Связи
- Вызывается: `sync-agent-views.sh`, `new-project` миграция, ручной запуск.
- Зависит от: `rule_model.py`, `.cursor/mcp.json`, `.cursor/mcp.env`, `.cursor/rules`, `.dsh/models.overlay.json`.
- Генерирует вход для: DeepSeek Harness (`.dsh/project.patch.yml`, `DSH-RULES.md`).
- Связанные документы: `.doc/harnes/state/01-canon-envs.md`, `.doc/harnes/state/04-mcp.md`, `.doc/harnes/state/15-mcp-stack.md`.

## История изменений
- 2026-11-07: полная документация на основе анализа кода
- 2026-11-09: описан generated glob-блок conditional-правил DSH
- 2026-11-09: проверка ручного patch возвращает ошибку; выбор серверов и моделей требует явного пути нестандартного patch.
