# Скрипт: `.agents/skills/task-router/children/analytics/scripts/task-analytics.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, ../scripts/lib/__init__.py]
tags: [harness, script, task-analytics, kilo, dialog-analysis]
-->

## Суть
Детерминированный анализатор диалогов Kilo: читает `kilo.db` (SQLite) в режиме read-only, строит факты сессий, атрибутирует их к задачам (CT-N), и записывает результаты анализа в `.doc/tasks/{N}/dialogs/` и `.doc/task-analytics/out/`. Поддерживает несколько подкоманд: полный скан (`scan`), отчёт (`report`), привязка сессий к задачам (`anchor`, `assign`, `detach`, `backfill-anchors`), валидация записанных файлов (`validate`). Не вызывает LLM — работает только с уже записанными в БД данными.

## Когда запускать
- После завершения диалога (или пачки диалогов) — команда `scan` для записи аналитики
- Для получения сводки по задаче или глобально — команда `report`
- При ручной корректке атрибуции — `assign` / `detach` / `anchor`
- В CI/периодически — `validate` для проверки целостности записанных файлов
Запускает человек или автоматизация (например, после `gototask` или в конце дня). Если не запускать `scan` — аналитика не накопляется, `report` показывает пустые данные, `task-intake` не видит историю диалогов.

## Аргументы

### Общие аргументы (для всех подкоманд)
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--db` | | string | нет | `~/.config/kilo/kilo.db` | Путь к kilo.db |
| `--root` | | string | нет | Корень проекта (6 уровней вверх) | Корень проекта для поиска `.doc/` |
| `--tasks-root` | | string | нет | `<root>/.doc/tasks` | Каталог задач |
| `--out` | | string | нет | `<root>/.doc/task-analytics/out` | Каталог выходных артефактов |

### Подкоманда `scan` — основной скан БД и запись файлов
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--task` | | string | нет | | Обработать только сессии, атрибутированные к задаче N |
| `--session` | | string | нет | | Обработать только конкретную сессию (ses_*) |
| `--latest` | | int | нет | | Обработать последние N сессий |
| `--after` | | string | нет | | ISO-время или мс: только сессии после |
| `--before` | | string | нет | | ISO-время или мс: только сессии до |
| `--dry-run` | | flag | нет | | Не писать файлы, только печатать summary |
| `--allow-partial` | | flag | нет | | Не считать незавершённые сессии ошибкой (exit 1) |
| `--idle-minutes` | | float | нет | 15.0 | Порог бездействия для разбиения сессии на срезы (idle trim) |

### Подкоманда `report` — сводка по задаче или глобально
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--task` | | string | нет | | Сводка только по задаче N (если нет — глобальная) |
| `--append-history` | | flag | нет | | Дописать строку в `stats/metrics-history.jsonl` |
| `--stage` | | string | нет | A | Стадия для history line |

### Подкоманда `attribute` — dry-run атрибуции (алиас scan с dry-run=true)
Те же аргументы что `scan`, но `--dry-run` и `--allow-partial` включены по умолчанию.

### Подкоманда `anchor` — записать точный якорь атрибуции для задачи
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--task` | | string | **да** | | Номер задачи |
| `--branch` | | string | **да** | | Имя git-ветки (features/#N или bugfixes/#N) |
| `--quote` | | string | **да** | | Уникальная цитата из первого пользовательского сообщения |
| `--created-at` | | string | нет | now | ISO-время создания якоря |

### Подкоманда `assign` — закрепить сессию за задачей вручную
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--session` | | string | **да** | | ID сессии (ses_*) |
| `--task` | | string | **да** | | Номер задачи |
| `--branch` | | string | нет | "" | Ветка (если известна) |
| `--force` | | flag | нет | | Перезаписать существующий якорь на другую задачу |

### Подкоманда `detach` — исключить сессию из атрибуции
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--session` | | string | **да** | | ID сессии |
| `--task` | | string | нет | | Задача, от которой открепляем (для записи в detached) |
| `--reason` | | string | нет | | Причина открепления |

### Подкоманда `backfill-anchors` — создать якоря для задач с уверенными сессиями
Без аргументов. Проходит по всем задачам, у которых есть сессии с confidence >= 0.9 и уникальной цитатой, и создаёт `anchor.json`.

### Подкоманда `validate` — проверить целостность записанных файлов
Без аргументов. Проверяет `index.json`, существование файлов сессий, соответствие `session_id`, `schema_version`.

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (scan: записано; report: напечатано; validate: ошибок нет) | Продолжить |
| 1 | `scan`: есть незавершённые сессии (partial) и не задан `--allow-partial` | Перезапустить с `--allow-partial` или дождаться завершения сессий |
| 2 | Ошибка: схема БД, файл не найден, неверный JSON, конфликт анкера без `--force` | Прочитать stderr, исправить причину |

## Что читает и что пишет
**Читает:**
- `kilo.db` — таблицы `sessions`, `messages`, `events`, `tools`, `mcp_servers`, `cli_tools`, `token_ledger`
- `.doc/tasks/{N}/dialogs/index.json` — индекс сессий задачи
- `.doc/tasks/{N}/_dialogs/anchor.json` — точные якоря атрибуции
- `.doc/task-analytics/out/state/detached.json` — список откреплённых сессий
- Конфиги: `assets/config/thresholds.json`, `assets/config/required-calls.json`, `assets/config/slices.json`

**Пишет (при `scan` без `--dry-run`):**
- `.doc/tasks/{N}/dialogs/ses_*.json` — полный анализ сессии (schema_version 1.0)
- `.doc/tasks/{N}/dialogs/index.json` — обновлённый индекс (appends session entry)
- `.doc/tasks/{N}/_dialogs/plan-state.json` — статус плана из последнего среза (если сессия с `prepare-plan`)
- `.doc/task-analytics/out/unassigned/ses_*.json` — сессии без атрибуции
- `.doc/task-analytics/out/state/detached.json` — состояние откреплённых сессий
- `.doc/task-analytics/out/state/manifest.json` — манифест скана (db, sessions, written)
- `.doc/task-analytics/out/stats/antipatterns.json` — агрегированные антипаттерны (только full scan)
- `.doc/task-analytics/out/stats/tools.json` — статистика инструментов/CLI/MCP (только full scan)

## Побочные эффекты
- Создаёт/обновляет файлы в `.doc/tasks/*/dialogs/` и `.doc/task-analytics/out/`
- Не меняет `kilo.db` (read-only)
- Не вызывает внешние API/LLM

## Окружение и зависимости
- Python 3.10+
- Внутренние модули `lib/`:
  - `db.py` — подключение к SQLite, схемы, запросы
  - `facts.py` — построение фактов сессии, редукция PII
  - `metrics.py` — анализ токенов, инструментов, окон, overflow
  - `attribute.py` — атрибуция сессий к задачам (якоря, ключевые слова, ветки)
  - `compliance.py` — проверка required calls
  - `corpus.py` — агрегация, history line, fingerprint workflow
  - `slices.py` — разбивка на срезы по маркерам этапов
  - `render.py` — атомарная запись JSON, индексы, манифесты
- Стандартная библиотека: `argparse`, `json`, `re`, `datetime`, `pathlib`, `sys`

## Примеры
```bash
# Полный скан всех новых сессий
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan

# Скан только последних 5 сессий
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan --latest 5

# Скан только сессий задачи 2538
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan --task 2538

# Dry-run для проверки атрибуции
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py attribute --task 2538

# Глобальный отчёт
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py report

# Отчёт по задаче с дописью в историю метрик
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py report --task 2538 --append-history

# Создать якорь для задачи 2538
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py anchor --task 2538 --branch "bugfixes/#2538" --quote "нужно починить расчёт тарифа"

# Вручную закрепить сессию за задачей
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py assign --session ses_abc123 --task 2538

# Открепить сессию
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py detach --session ses_abc123 --task 2538 --reason "wrong attribution"

# Создать якоря для всех задач с уверенными сессиями
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py backfill-anchors

# Валидация записанных файлов
python .agents/skills/task-router/children/analytics/scripts/task-analytics.py validate
```

## Ограничения
- Работает только с локальным `kilo.db` — не подключается к удалённым инстансам
- Не делает семантический анализ содержимого диалогов — только структурный (токены, инструменты, атрибуция по якорам/ключевым словам)
- Атрибуция эвристическая: без `anchor.json` может ошибаться на похожих задачах
- `scan` не перезаписывает уже записанные сессии (пропускает по `session_id` в индексе), если не изменилось `db_lag_seconds` — для перезаписи удалите файл сессии вручную
- `backfill-anchors` создаёт якоря только для задач с confidence >= 0.9 и уникальной цитатой
- Не генерирует HTML-отчёты — только JSON для программного потребления

## Связи
- Вызывается: вручную, автоматизация после диалогов, CI (`validate`)
- Зависит от: `kilo.db` (создаётся Kilo), конфигов в `config/`, внутренних модулей `lib/`
- Результат потребляет: `task-intake` (история диалогов), человек (через `report`), дашборд аналитики
- Связанные скрипты: `task-intake` (scripts/intake_orchestrator.py использует атрибуцию), `analytics` SKILL.md

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода

## Все аргументы (плоский список для аудита)
| Аргумент | Подкоманда | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|---|
| `--db` | (общий) | | string | нет | `~/.config/kilo/kilo.db` | Путь к kilo.db |
| `--root` | (общий) | | string | нет | Корень проекта (6 уровней вверх) | Корень проекта для поиска `.doc/` |
| `--tasks-root` | (общий) | | string | нет | `<root>/.doc/tasks` | Каталог задач |
| `--out` | (общий) | | string | нет | `<root>/.doc/task-analytics/out` | Каталог выходных артефактов |
| `--task` | scan | | string | нет | | Обработать только сессии, атрибутированные к задаче N |
| `--session` | scan | | string | нет | | Обработать только конкретную сессию (ses_*) |
| `--latest` | scan | | int | нет | | Обработать последние N сессий |
| `--after` | scan | | string | нет | | ISO-время или мс: только сессии после |
| `--before` | scan | | string | нет | | ISO-время или мс: только сессии до |
| `--dry-run` | scan | | flag | нет | | Не писать файлы, только печатать summary |
| `--allow-partial` | scan | | flag | нет | | Не считать незавершённые сессии ошибкой (exit 1) |
| `--idle-minutes` | scan | | float | нет | 15.0 | Порог бездействия для разбиения сессии на срезы (idle trim) |
| `--task` | report | | string | нет | | Сводка только по задаче N (если нет — глобальная) |
| `--append-history` | report | | flag | нет | | Дописать строку в `stats/metrics-history.jsonl` |
| `--stage` | report | | string | нет | A | Стадия для history line |
| `--task` | attribute | | string | нет | | Обработать только сессии, атрибутированные к задаче N |
| `--session` | attribute | | string | нет | | Обработать только конкретную сессию (ses_*) |
| `--latest` | attribute | | int | нет | | Обработать последние N сессий |
| `--after` | attribute | | string | нет | | ISO-время или мс: только сессии после |
| `--before` | attribute | | string | нет | | ISO-время или мс: только сессии до |
| `--dry-run` | attribute | | flag | нет | true | Не писать файлы (включено по умолчанию) |
| `--allow-partial` | attribute | | flag | нет | true | Не считать незавершённые ошибкой (включено по умолчанию) |
| `--idle-minutes` | attribute | | float | нет | 15.0 | Порог бездействия для разбиения сессии на срезы |
| `--task` | anchor | | string | **да** | | Номер задачи |
| `--branch` | anchor | | string | **да** | | Имя git-ветки (features/#N или bugfixes/#N) |
| `--quote` | anchor | | string | **да** | | Уникальная цитата из первого пользовательского сообщения |
| `--created-at` | anchor | | string | нет | now | ISO-время создания якоря |
| `--session` | assign | | string | **да** | | ID сессии (ses_*) |
| `--task` | assign | | string | **да** | | Номер задачи |
| `--branch` | assign | | string | нет | "" | Ветка (если известна) |
| `--force` | assign | | flag | нет | | Перезаписать существующий якорь на другую задачу |
| `--session` | detach | | string | **да** | | ID сессии |
| `--task` | detach | | string | нет | | Задача, от которой открепляем (для записи в detached) |
| `--reason` | detach | | string | нет | | Причина открепления |

## Аргументы (аудит: 2 колонки)
| Аргумент | Описание |
|---|---|
| `--db` | Путь к kilo.db |
| `--root` | Корень проекта для поиска `.doc/` |
| `--tasks-root` | Каталог задач |
| `--out` | Каталог выходных артефактов |
| `--task` | scan: обработать только сессии задачи N |
| `--session` | scan: обработать только сессию ses_* |
| `--latest` | scan: обработать последние N сессий |
| `--after` | scan: только сессии после (ISO/ms) |
| `--before` | scan: только сессии до (ISO/ms) |
| `--dry-run` | scan: не писать файлы, только summary |
| `--allow-partial` | scan: не считать незавершённые ошибкой |
| `--idle-minutes` | scan: порог бездействия для idle trim (default 15.0) |
| `--task` | report: сводка только по задаче N |
| `--append-history` | report: дописать строку в metrics-history.jsonl |
| `--stage` | report: стадия для history line (default A) |
| `--task` | attribute: те же что scan, dry-run по умолчанию |
| `--session` | attribute: конкретная сессия |
| `--latest` | attribute: последние N сессий |
| `--after` | attribute: только после (ISO/ms) |
| `--before` | attribute: только до (ISO/ms) |
| `--dry-run` | attribute: не писать файлы (default true) |
| `--allow-partial` | attribute: не считать ошибкой (default true) |
| `--idle-minutes` | attribute: порог бездействия (default 15.0) |
| `--task` | anchor: номер задачи (обязателен) |
| `--branch` | anchor: git-ветка features/#N или bugfixes/#N (обязателен) |
| `--quote` | anchor: уникальная цитата из первого сообщения (обязателен) |
| `--created-at` | anchor: ISO-время создания якоря (default now) |
| `--session` | assign: ID сессии ses_* (обязателен) |
| `--task` | assign: номер задачи (обязателен) |
| `--branch` | assign: ветка (default пусто) |
| `--force` | assign: перезаписать якорь на другую задачу |
| `--session` | detach: ID сессии (обязателен) |
| `--task` | detach: задача для записи в detached |
| `--reason` | detach: причина открепления |