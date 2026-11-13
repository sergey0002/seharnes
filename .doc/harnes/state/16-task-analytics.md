# Task analytics: автономный анализ диалогов

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [../index.md, ./02-skills.md, ./05-scripts.md]
tags: [harness, kilo-db, analytics, tasks, tokens]
-->

---

## Суть

Отдельный Python-инструмент читает локальную базу Kilo в режиме read-only, строит
по каждой сессии детерминированные факты, привязывает сессии к задачам и
раскладывает результат по `.doc/tasks/{N}/dialogs/`. Модель не вызывается, сеть не
нужна. Скилы больше не считают статистику сами: агент читает готовый артефакт.

Код инструмента живет в `.agents/skills/task-router/children/analytics/scripts/`, схемы
и пороги в `assets/` того же скила, результаты прогонов в `.doc/task-analytics/out/`.
Это локальный контур: `.doc/` не входит в git, данные не покидают машину.

---

## 1. Источники

| Источник | Что берется |
|---|---|
| `~/.local/share/kilo/kilo.db` | `session`, `message`, `part`; только `mode=ro` |
| `session` | `cost`, `tokens_*`, `model`, `agent`, время, `parent_id` |
| `message.data.tokens` | `input`, `output`, `reasoning`, `cache.read`, `cache.write` |
| `part.data` | `tool`, `callID`, `state.status/input/output`, `metadata.toolCalls` |
| `.doc/tasks/{N}/_dialogs/anchor.json` | точная привязка диалога к задаче |
| `.agents/skills/task-router/children/analytics/assets/config/*.json` | пороги, обязательные вызовы, маски срезов |
| git-коммиты | не читаются: коммит не является триггером анализа |

Поля `reasoning` не декодируются: 93 тыс. записей не нужны, токены reasoning
берутся из сообщения. Полный текст команд не хранится, только короткий redacted
фрагмент.

---

## 2. Устройство

```text
.agents/skills/task-router/children/analytics/
├── scripts/task-analytics.py  CLI
├── scripts/lib/db.py          read-only доступ, селекторы, проверка схемы
├── scripts/lib/facts.py       нормализация part, redaction, маркеры плана
├── scripts/lib/attribute.py   вероятностная привязка к задачам
├── scripts/lib/metrics.py     метрики, находки, окна, леджер токенов
├── scripts/lib/compliance.py  обязательные вызовы по фазам скилов
├── scripts/lib/slices.py      срезы планов
├── scripts/lib/corpus.py      отпечаток workflow, антипаттерны, история метрик
├── scripts/lib/render.py      атомарная запись, индексы, манифест, очистка дублей
├── assets/config/             thresholds, required-calls, slices
├── assets/schemas/            facts, analysis, index
└── tests/                     unit-тесты на fixture-базе

.doc/task-analytics/out/
├── unassigned/                сессии без уверенной привязки
├── stats/                     tools.json, antipatterns.json, metrics-history.jsonl
└── state/                     manifest.json с sha256, detached.json
```

## 3. Команды

```bash
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan --task 2628
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan --session ses_x
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan --latest 30
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py scan --dry-run
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py report --task 2628
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py report --append-history
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py anchor --task N --branch B --quote Q
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py backfill-anchors
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py assign --session ses_x --task N
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py detach --session ses_x --task N --reason R
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py validate
```

Коды выхода: `0` complete, `1` открытая сессия или лаг базы (данные записаны),
`2` ошибка схемы или аргументов. `scan` - единственная пишущая команда.
Глобальные `out/stats/` и `manifest.json` обновляет только полный scan без
фильтров.

## 4. Куда пишет

```text
.doc/tasks/{N}/dialogs/index.json       сессии задачи
.doc/tasks/{N}/dialogs/ses_xxx.json     анализ сессии
.doc/tasks/{N}/_dialogs/anchor.json     якорь задачи
.doc/tasks/{N}/_dialogs/plan-state.json последний статус плана
.doc/task-analytics/out/unassigned/     сессии без уверенной привязки
.doc/task-analytics/out/stats/          tools.json, antipatterns.json, metrics-history.jsonl
.doc/task-analytics/out/state/          manifest.json с sha256, detached.json
```

Полный scan удаляет копии сессии, которые остались в старой задаче после
переатрибуции, и чистит индексы. Без этого появлялись дубли файлов.

В каждом `ses_*.json` есть `first_user_text`: первое сообщение пользователя
после `facts.redact`, одной строкой, до 160 символов. Панель берет его как
заголовок сессии без задачи.

## 5. Привязка к задачам

Вероятность считается по формуле `p = 1 - произведение(1 - вес)`.

| Сигнал | Вес | Условие |
|---|---:|---|
| `anchor` | 1.0 | первый текст начинается с quote, в quote есть номер задачи |
| `task_path` | 0.9 | доля `.doc/tasks/{N}/` не ниже 0.6 и минимум 5 вхождений |
| `early_task_file` | 0.8 | `.doc/tasks/{N}/task.md` или `gototask` в первых 5 событиях |
| `first_message_directive` | 0.85 | "перейди к задаче N", "go to task N" |
| `first_message_declarative` | 0.7 | "задача N" |
| `first_message_ct` | 0.7 | `CT-N` |
| `first_message_bare` | 0.45 | голый `#N`, назначить не может |
| `early_branch` | 0.5 | ветка с `#N` в первых 10 событиях |

Правила:

- якорь всегда выигрывает;
- назначение при `p >= 0.75` и отрыве от второго кандидата не меньше 0.15;
- при `p >= 0.6` и единственном кандидате назначение разрешено;
- иначе `attribution_status: ambiguous`, задача не ставится, кандидаты с
  вероятностями сохраняются в `task_candidates`;
- ручная фиксация: `assign --session ses_x --task N`;
- исключение из привязки: `detach --session ses_x --task N`; scan оставляет
  сессию без задачи и переносит файл в `out/unassigned/`.

Якорь принимается только по отличимой цитате с номером задачи и совпадению
начала первого сообщения. Общие фразы без номера задачу не привязывают.

### 5.1 Как парсится gototask

`gototask` уже входит в диалоговый анализ, отдельный парсер не нужен.

| Шаг | Где | Что происходит |
|---|---|---|
| 1 | `lib/facts.py` | для `tool=skill` сохраняется `skill_name`; вызов `gototask` попадает в `events[]` |
| 2 | `lib/attribute.py` | `gototask` в первых 5 событиях и путь `.doc/tasks/{N}/` дают сигнал `early_task_file` с весом 0.8 |
| 3 | `gototask` шаг 5b | пишет `.doc/tasks/{N}/_dialogs/anchor.json` через `task-analytics.py anchor`; якорь имеет вес 1.0 |
| 4 | `backfill-anchors` | создает якоря для старых задач по уверенным сессиям |

Следствия:

- привязка диалога к задаче уже работает по диалогу, а не по `task.md`;
- `prepare-plan` не участвует в атрибуции;
- `prepare-plan` нужен только для P0.7, то есть для чтения накопленных antipatterns;
- `unassigned` сессии появляются из-за отсутствия якоря, пути задачи или неоднозначной атрибуции, а не из-за неразобранного `gototask`.

---

## 6. Метрики

По сессии: вызовы по инструментам, ошибки и таймауты, непарные вызовы, повторы,
ретраи, загрузка скилов, MCP по серверам, длительность и активное время.

Токены: `input_total` (свежий ввод, Kilo уже отдает его без кэша),
`incoming_total` (полный контекст запросов вместе с кэшем), `cache_read`,
`cache_write`, `output`, `reasoning`, `cache_hit_ratio`, `requests` (число
запросов к модели), `by_model` (по модели: свежий ввод, кэш, исходящие),
`by_phase`. `incoming_total` больше `input_total` во столько раз, сколько раз
контекст перечитан из кэша; это не уникальные токены.

Панель показывает два разных итога:

- "Токены без кэша" - свежий ввод, исходящие и reasoning, так считает Kilo;
- "Обработано контекста" - свежий ввод и кэш, то есть полный промпт каждого запроса.

Рядом выводятся "Запросов" и "Средний контекст на запрос" (`incoming_total / requests`).
Эти итоги не складываются и не заменяют друг друга.
MCP: `mcp_servers[]` с вызовами и токенами по серверу (оценка: токены
`execute`-сообщения делятся поровну между серверами вызова).
Bash: `cli_tools[]` - разбивка по CLI (`git`, `python3`, `jsondoc.py`, `grep`,
`docker`), с вызовами и токенами; токены сообщения делятся между инструментами
этого сообщения.

Время: `active_ms` - сумма интервалов между событиями, каждый не больше
15 минут; долгие паузы не учитываются. `duration_ms` - календарный диапазон
от первого до последнего события. `idle_trimmed_ms` равен `active_ms` для
совместимости.

Находки: `error`, `unpaired`, `repeat`, `repeat_same_target`, `retry_identical`,
`skill_reloaded`, `reasoning_heavy`, `token_spike`, `batchable_series`,
`mandatory_call_missing`. Окна потерь не превышают 20 процентов событий.

`batchable_series` вместе с числом серий отдает `saved_calls` и `saved_ms`.

По корпусу: отпечаток workflow по скилам и доменам файлов, `antipatterns.json`
со статусом `candidate` при count не меньше 3, append-only
`metrics-history.jsonl`. Stage F (переходы статусов и P0.7) спроектирован
в плане, но не реализован.

## 7. Интеграция

| Компонент | Что делает |
|---|---|
| `gototask` | шаг 5b пишет `anchor.json` после успешного apply |
| `prepare-plan` | P0.7 спроектирован, но пока не подключен; `antipatterns.json` не читается |
| панель `.doc/web` | вкладка "Аналитика" и блок "Диалоги и метрики" читают `dialogs/` и `out/`; показывают "Токены без кэша", "Обработано контекста", "Запросов" и средний контекст на запрос; KPI, графики Chart.js (при недоступном CDN - HTML-полосы), активность Jira, бизнес-отчет, фильтры по релизу и ответственному |

Инструмент не зависит от скилов. Скилы только читают артефакты и пишут якорь.

## 8. Инварианты

- база открывается только `mode=ro` и `PRAGMA query_only`;
- повторный прогон закрытых сессий побайтово идентичен;
- секреты маскируются до записи, транскрипты не копируются;
- `event_id` стабилен, JSON сортируется по ключам;
- `final: false` у открытой сессии, `db_lag_seconds` только у незакрытых;
- валидатор ловит битые ссылки, неверную схему и расхождение `session_id`.

## 9. Замеры 2026-10-30

170 сессий, около 162 тыс. `part`, полный прогон 14 с. Привязано 107 сессий,
24 задачи, 63 без задачи, 1 `ambiguous`. Точность на 95 сессиях с
путем-ground-truth: 1.0. Входящие токены 4.68 млрд, из них кэш 92.8 процента.
Активное время 208.3 часа, календарный диапазон сессий 731.2 часа. Свежие
метрики лежат в `.doc/task-analytics/out/stats/`.


## 10. Что сделано 2026-10-30

- Создан автономный инструмент `.doc/skil_data/analytics/`: чтение `kilo.db`,
  вероятностная привязка к задачам, отчеты и раскладка по `.doc/tasks/{N}/dialogs/`.
- `gototask` пишет `anchor.json` шагом 5b.
- Jira-экспорт и JSONdoc: в `tracker.snapshot` попадают даты `created`/`updated`,
  статус, исполнитель, комментарии с датами и changelog. Обновляется только
  `tracker`, остальные секции задачи сохраняются.
- Панель `.doc/web`: вкладка "Аналитика", блок "Диалоги и метрики", лента
  активности Jira, блок бизнес-аналитики, фильтры по релизу и ответственному,
  статус Jira в списке, формат дат `дд.мм.гггг чч:мм:сс`, полноценный HTML
  бизнес-отчета по `/files/tasks/{N}/reports/change-report/report.html`.
- Метрики: MCP и bash-CLI по токенам (входящие, кэш, исходящие), модели по
  токенам, активное время без пауз больше 15 минут.
- Перенос: `task-analytics` добавлен в `rebase_project.ps1` (`$docDirs`,
  must-check), `out/` исключен и считается на новом проекте заново.

---

## 11. Что сделано 2026-11-01

- В леджер добавлен `requests`; полный scan обновляет поле у всех сессий.
- Панель разделила итоги токенов: "Токены без кэша" и "Обработано контекста",
  добавила "Запросов" и "Средний контекст на запрос".
- Добавлена команда `detach` и состояние `out/state/detached.json`; повторный
  scan не возвращает отвязанную сессию в задачу.
- `write_session` удаляет старые копии сессии из других задач и обновляет их
  `index.json`, поэтому смена задачи или detach не оставляет дублей.
- Проверено: 14 unit-тестов, `validate` без ошибок, страница задачи 2630 и
  вкладка "Аналитика" показывают согласованные итоги.

---

## Связи

- [Точка входа](../index.md) - карта каталога харнеса
- [Скилы](./02-skills.md) - карта; изменения в `gototask` - в [карточке](../../../.agents/skills/task-router/children/gototask/SKILL.md)
- [Скрипты](./05-scripts.md) - место инструмента среди остальных контуров
- [Скил аналитики](../../../.agents/skills/task-router/children/analytics/SKILL.md) - команды и устройство

## Известные проблемы и ограничения

### П-1: Локальность

- Симптом: артефакты не переносятся между машинами.
- Причина: `.doc/` исключен из git (`.gitignore:44`), база Kilo тоже локальная.
- Решение: код переносится, данные считаются заново на месте.

### П-2: Стоимость не пишется

- Симптом: `cost = 0` во всех сессиях этой версии Kilo.
- Причина: клиент не заполняет поле.
- Ограничение: считаются токены и время, деньги недоступны.

### П-3: Один диалог может менять задачу

- Симптом: первый текст про 2618, работа идет по 2612.
- Причина: модель привязки ставит одну задачу на сессию.
- Решение: такие случаи помечаются `ambiguous`; в будущем - сегменты по времени.

### П-4: Срезы планов неполные

- Симптом: 41 из 62 срезов `unknown`.
- Причина: `plan.md` пишется через `jsondoc` в файл, статус не попадает в команду.
- Решение: `plan-state.json` пишется по видимым маркерам; для точности нужен
  маркер от `prepare-plan` при смене статуса.

### П-5: Ground truth приблизительный

- Симптом: точность 1.0 измерена относительно доминирующего пути задачи.
- Причина: путь - прокси, а не разметка человека.
- Ограничение: цифра показывает согласованность сигналов, не абсолютную истину.

## История изменений

- 2026-10-30: создан инструмент `task-analytics`: чтение `kilo.db`, привязка,
  метрики, срезы, корпус. Скилы переведены на чтение артефакта, `gototask`
  пишет якорь.
- 2026-10-30: привязка переведена на вероятностную модель, добавлены
  `backfill-anchors`, `assign`, `plan-state.json`, MCP по серверам, экономия
  batch, разделение токенов и время работы.
- 2026-10-30: Jira JSON: `tracker.snapshot` с датами, статусом, ответственным,
  комментариями и changelog; панель получила аналитику, ленту активности,
  бизнес-блок и фильтры; bash разбит по CLI, токены по MCP/моделям/CLI;
  активное время с отсечкой пауз 15 минут.
- 2026-10-30: задокументировано, что gototask уже парсится по диалогу через `skill_name`, `early_task_file` и `anchor.json`. Stage F (переходы статусов, история, P0.7) остается нереализованным, план дополнен.
- 2026-11-01: в леджер добавлен `requests`, панель показывает два итога
  ("Токены без кэша" и "Обработано контекста") и средний контекст на запрос.
  Добавлена команда `detach` с состоянием `out/state/detached.json`; повторный
  scan не возвращает отвязанную сессию в задачу.
- 2026-11-02: в анализ сессии добавлен `first_user_text` (redacted, одной
  строкой, до 160 символов). Панель использует его как заголовок диалога без
  задачи и ищет по нему в фильтре.
- 2026-11-11: пути приведены к коду: код и схемы в
  `.agents/skills/task-router/children/analytics/`, вывод в
  `.doc/task-analytics/out/`; каталог `.doc/skil_data/analytics/` удален как
  легаси.
