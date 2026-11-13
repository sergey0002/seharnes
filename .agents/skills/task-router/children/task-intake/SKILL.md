---
name: task-intake
description: >-
  Заводит задачу из Jira в систему по номеру и доводит её документацию до
  актуальной: task.md и tracker, диф по коммитам, бизнес-правила, doc.md и
  индекс задач. Работает для задач без папки, с устаревшей документацией и для
  старых задач, оформленных не по текущим правилам. Use when the user says
  заведи задачу, импортируй задачу, догнать документацию задачи,
  задокументируй задачу с нуля, обнови задачу по новым правилам, task-intake.
---

# Task Intake (task-intake)

Один прогон приводит задачу к состоянию "в системе есть всё": источник Jira, диф,
бизнес-правила, `doc.md` и индекс. Скил только оркестрирует существующие
инструменты и не пишет артефакты своим кодом.

## Когда применять

| Ситуация | Признак |
|---|---|
| Задачи нет в системе | нет `.doc/tasks/{N}/` или нет `task.md` |
| Документация устарела | старый `diff.md`, новые комментарии Jira, `doc.md` без последних правок |
| Оформлено по старым правилам | нет `task.json`, нет бизнес-фактов, текст не проходит `check-doc-text.py` |

Не применять вместо узких скилов:

- обычный переход к задаче и работа с веткой: `gototask`;
- только диф: `task-diff`;
- только текст документации: `task-doc`;
- отдельный HTML-отчёт: `task-change-report` по прямой команде пользователя,
  intake его не запускает.

## Адаптеры (CopyTrust)

| Что | Значение |
|---|---|
| Папка задачи | `.doc/tasks/{N}` |
| Снимок состояния | `.cursor/skills/task-router/children/task-intake/scripts/intake_state.py` |
| Быстрый проход 0-3 | `.cursor/skills/task-router/children/task-intake/scripts/intake_orchestrator.py` |
| Каркас разбора дифа | `.cursor/skills/task-router/children/task-intake/scripts/intake_analysis.py` |
| Секции doc.md из JSON | `.cursor/skills/task-router/children/task-intake/scripts/doc_sections.py` |
| Экспорт Jira | `gototask.ps1 -Action export-task` |
| Регистрация источника | `jsondoc.py ingest-tracker` |
| Диф | `task-diff.ps1` |
| Документация | `task-doc` |
| Индекс задач | `build-tasks-index.ps1 -AlsoTsv` (вызывает `task-doc`) |
| Проверка текста | `.agents/skills/documentation-router/children/project-doc/scripts/check-doc-text.py` |
| Проверка личности | `.agents/skills/documentation-router/children/project-doc/scripts/task-identity.py` |

## Инварианты

- Jira только читается. Комментарии и поля не меняются.
- Ветка не переключается и не создаётся. `export-task` это read-only экспорт.
- Нет commit и push. Результат intake это артефакты `.doc/`, а не код.
- Канон задачи это `task.json`. `doc.md` это рендер. Ручная правка generated
  `doc.md` запрещена (`VIEW_CONFLICT`).
- Нет выдуманных фактов. Пустой диф, пустая история и отсутствие цитаты
  фиксируются явно, а не заменяются догадкой.
- Повторный запуск идемпотентен: тот же снимок Jira даёт no-op, секции и
  решения не дублируются.
- Intake выполняется в основном checkout. В `.kilo/worktrees/*` нет `.doc/`,
  писать некуда.
- HTML-отчёт не является результатом intake. Скил заканчивается на `doc.md`,
  архитектуре и индексе. Отчёт формируется только отдельным прямым вызовом
  `сформируй html отчет` через `task-change-report`.

## Вход

Номер задачи: только цифры. `CT-1178` и ссылку `.../browse/CT-1178` приводи к
`1178`. Если номер не назван, спросить, не угадывать.

**Импортированные задачи.** Если в `task.md` есть `Imported from
https://bitbucket.org/.../issues/{X}` или поле `| Bitbucket | X |`, номер X это
legacy. `task-diff` и `gototask` сами читают его из `task.md`, отдельно
заполнять не нужно. Номер попадает в отчёт и в шапку `diff.md`. Ссылка на
Bitbucket без `Imported from` legacy не считается.

## Workflow

```
TaskIntake:
- [ ] 0. снимок состояния
- [ ] 1. экспорт Jira
- [ ] 2. регистрация в JSONdoc
- [ ] 3. диф
- [ ] 3b. разбор дифа и кода (files, findings, decisions, requirements)
- [ ] 4. бизнес-правила
- [ ] 5. документация и запись анализа (task-doc)
- [ ] 6. проверки и итог intake
```

### Шаг 0. Снимок состояния

Один проход, без сканирования всего каталога:

```bash
python3 .cursor/skills/task-router/children/task-intake/scripts/intake_state.py --root . --task {N}
```

Скрипт только читает и печатает компактный JSON: какие артефакты есть, какие
ветки найдены, legacy-номера, статус `task-identity`, свежесть дифа и документации
и `next_action` (`fetch`, `diff`, `doc`, `verify`). Наличие HTML-отчёта и
`dialogs/index.json` показывается только как справка.

Если скрипта нет в среде, выполнить те же проверки вручную:

```bash
test -d .doc/tasks/{N} && ls -la .doc/tasks/{N}
git for-each-ref --format='%(refname:short)' refs/heads refs/remotes | grep -E "#{N}([^0-9]|$)"
python3 .agents/skills/documentation-router/children/project-doc/scripts/task-identity.py {N}
```

`task-identity.py` запускать только если `task.md` уже есть. При конфликте
идентификаторов или неполных данных остановиться до записи, проверить источник и
результат экспорта и импорта, затем повторить гейт. Различие авторского
`metadata.title` и названия Jira выводится как предупреждение.

Что означает снимок:

| Найдено | Вывод |
|---|---|
| папки нет | новый импорт |
| есть `task.md`, нет `task.json` | старый формат, нужен ingest |
| есть `task.json`, нет `doc.md` | документацию создать |
| есть всё, но диф старее задачи | обновить диф и `doc.md` |
| ветки нет, коммиты есть | диф в режиме `any-ref` |

Быстрый путь: один вызов вместо шагов 0-3.

```bash
python3 .cursor/skills/task-router/children/task-intake/scripts/intake_orchestrator.py --task {N} --no-network
```

Скрипт сам вызывает state, экспорт, ingest и диф, но только для шагов, которые
нужны по `next_action`. Свежие артефакты не пересобираются. Возвращает один JSON:
`steps` (что запускалось), `errors`, `warnings`, `state`, `next_action`. Ветку не
переключает, документацию и правила не пишет. Шаги ниже остаются ручным
fallback и объясняют, что именно делает оркестратор.

### Шаг 1. Экспорт Jira

```text
вызови скил gototask с задачей {N} в режиме export task
```

Проверить в JSON поля `taskExport.ok` и статус импорта JSONdoc. Скрипт пишет `task.md` и
`.doc/tasks/{N}/_jsondoc/work/tracker.json`, а после успешного экспорта сам
вызывает `jsondoc ingest-tracker`. Ветку не трогает, вопросов не задаёт.

Если Jira или экспортёр недоступен (нет PHP/Docker, нет доступа, нет
`.doc/skil_data/jira/config.env`): остановиться и назвать причину. Частичную задачу без
источника не создавать.

### Шаг 2. Регистрация в JSONdoc

Обычно этот шаг уже выполнен внутри экспорта. Запускать его отдельно только
если после шага 1 `task.json` отсутствует или старше `tracker.json`.

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . ingest-tracker --task {N} \
  --input .doc/tasks/{N}/_jsondoc/work/tracker.json
```

Статус `created` значит, что `task.json` появился из снимка Jira: заголовок,
тип задачи и ветка берутся из `summary` и типа Jira, а не из шаблонных значений.
`updated` обновляет только `tracker`, не затирая `business_logic`, `summary` и
заметки. `noop` значит, что снимок не изменился.

`ingest-tracker` не создаёт `doc.md`. Если читаемый view нужен сразу, а не после
`task-doc`, отрендерить его отдельно:

```bash
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . render --task {N}
```

Повторный render идемпотентен.

После ingest повторить `task-identity.py {N}`. Если CLI JSONdoc или receipt
недоступны, работать по legacy-пути `doc.md`, но отметить это в отчёте.

Не менять `metadata.title` автоматически: название документа может отличаться
от названия Jira. При несовпадении экспорта и снимка установить источник ошибки,
обновить снимок штатным экспортом и повторить проверку. Отсутствие ветки старой
задачи фиксировать в отчёте.

### Шаг 3. Диф

```text
вызови скил task-diff с задачей {N}
```

Разбор результата:

| Поле | Что делать |
|---|---|
| `branchMode=branch` | штатный диф по ветке |
| `branchMode=any-ref` | ветки нет, коммиты найдены по subject во всех refs |
| `commitCount=0` | проверить legacy-номера (см. ниже), затем записать вывод в `doc.md` |
| `alreadyInRelease` / `aheadOfRelease` | показать в отчёте, не менять вывод |
| `legacyNumbers` | номер Bitbucket из `Imported from`, показать в отчёте |
| `originSync=local-fallback` или `skipped` | сеть не мешает, диф собран по локальным refs |

При недоступном или медленном origin использовать `-SkipFetch`. Не чинить SSH
в рамках intake.

Если `commitCount=0`, а `legacyNumbers` не пуст, проверить, нет ли коммитов со
ссылкой на старый номер:

```bash
git log --all --no-merges --format='%h %ad %s' --date=short --grep "issues/{LEGACY}"
```

Найденные коммиты это факт реализации, а не повод писать "реализация не найдена".
Собрать по ним `files` и факты, а в отчёте указать, что штатный диф их не
сопоставил. Если коммитов нет, только тогда писать "реализация не найдена".

`any-ref` эвристика: в diff могут попасть коммиты других задач, где номер
упомянут в subject. Перед записью в `doc.md` сверить subject и файлы, спорные
коммиты отметить как "совпадение по номеру, требует проверки".

### Шаг 3b. Разбор дифа и кода

Диф это основной источник для `files`, `findings`, `decisions`, `requirements`.
Без этого шага панель показывает нули, даже когда импорт прошёл.

1. Собрать каркас разбора одной командой:

```bash
python3 .cursor/skills/task-router/children/task-intake/scripts/intake_analysis.py --root . --task {N}
```

Скрипт пишет `_jsondoc/work/intake-analysis.scaffold.json`: файлы со `state`,
домен и `doc_refs` из `file-registry.tsv`, число добавленных и удалённых строк,
привязку коммитов к файлам и список `suspicions` (legacy URL в subject, коммит
сильно вне даты задачи, чужой номер, файл удалён или отсутствует в реестре).
Скрипт не пишет симптомы, причины и решения.

2. Читать `diff.md` не целиком, а диапазоны `diff_range` из каркаса для файлов
   в scope. Полный диф открывать только если диапазоны не покрывают зависимость.
3. Для каждого файла открыть текущий код (Read whole, если файл до 300 строк) и
   определить роль в системе, что менялось и в каком файл состоянии.
4. Проверить каждый `suspicion`: объяснить связь или исключить коммит и файл.
5. Сопоставить патч с текстом Jira: симптом, причина, решение.
6. Записать результат в `.doc/tasks/{N}/_jsondoc/work/intake-analysis.json`:
   `files[]`, `findings[]`, `decisions[]`, `requirements[]`.
7. Передать файл в `task-doc` на шаге 4: он пишет коллекции через JSONdoc.

Правила разбора:

- `files`: полный путь, роль и изменение. `state=current` для живых файлов,
  `state=historical` только если файл удалён.
- `findings`: только то, что видно в диффе или коде. Симптом из Jira, причина из
  патча, решение из нового кода. Нет причины - `cause=null`, а не догадка.
- `decisions`: выбор, который виден в коде. Альтернатива только если она реально
  обсуждалась или прямо следует из удалённого кода.
- `requirements`: условия из Jira. `state=closed`, если исправление есть в диффе.
- `source_ids`: ссылки на sources из `task.json` (task.md, diff.md).
- `business_logic` здесь не заполняется. Бизнес-аналитик снят с харнеса; правила
  из Jira в task.json не извлекаются.

### Шаг 4. Документация и запись анализа

Следовать `.cursor/skills/documentation-router/children/task-doc/SKILL.md`, режим B целиком. Скил сам создаёт
`doc.md` по шаблону, если файла нет, и выполняет B3, B3.3, B3.7, B4, B4.5.

В `task-doc` передать: task id, `task.md`, tracker, `diff.md`, `diff.files.md` и
`intake-analysis.json` из шага 3b. Диалога у импортированной задачи нет, поэтому
источник для `files`, `findings`, `decisions`, `requirements` это диф и код.
Коллекции писать операциями JSONdoc с `actor=task-doc` до B4, затем render.

Секции пишутся одним JSON, а не тринадцатью объектами update-envelope. Агент
собирает `.doc/tasks/{N}/_jsondoc/work/sections.json`:

```json
{
  "sections": {
    "Краткое описание": "текст раздела",
    "Подводные камни": "Симптом: ...\nРешение: ..."
  }
}
```

Допустим и список, если нужны ссылки на источники:

```json
{
  "sections": [
    {"title": "Краткое описание", "body": "текст", "source_ids": ["SRC-1"]}
  ]
}
```

Скрипт сам разбирает JSON, строит upsert, сохраняет id и anchor существующих
секций и при `--finalize` делает apply, render, индекс и проверки:

```bash
python3 .cursor/skills/task-router/children/task-intake/scripts/doc_sections.py --root . --task {N} \
  --input .doc/tasks/{N}/_jsondoc/work/sections.json --finalize
```

Пустой `body`, дубль заголовка и отсутствие `task.json` дают ошибку до записи.
Markdown с заголовками `##` еще принимается как старый вариант, но по умолчанию
используется JSON.

Коллекции `files`, `findings`, `decisions`, `requirements` по-прежнему пишутся
через `intake-analysis.json`: у них есть поля и ссылки, которых нет в тексте
секций.

Границы, которые intake передаёт в `task-doc`:

- писать только документацию. HTML-отчёт и комментарий в Jira в intake не
  входят, для них нужна отдельная прямая команда;
- источник фактов: `task.md`, `tracker`, `diff.md`, код и результаты проверок;
- устаревшее помечать `~~устарело~~` и заменять, не удаляя без команды;
- архитектурные файлы править только в scope задачи и с обратной ссылкой;
- `architecture/*.md` это generated view с первой строкой
  `generated from architecture:...`; править их напрямую нельзя, только
  `jsondoc.py apply --arch` и затем `render --arch`. Проверить маршрут заранее:
  `intake_state.py --root . --path .doc/architecture/NAME.md`.

### Шаг 5. Проверки и итог intake

```bash
python3 .agents/skills/documentation-router/children/project-doc/scripts/check-doc-text.py --task {N}
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1 -Path .doc/tasks/{N}/doc.md
python3 .agents/skills/documentation-router/children/project-doc/scripts/task-identity.py {N}
```

Ошибки текста исправляются в модели через `jsondoc.py apply`, затем `render`.
Не править generated `doc.md` руками.

Индекс задач пересобирает `task-doc` на шаге B4.5. Повторно не вызывать.

Формат итогового сообщения intake, не HTML-отчёта:

```
Задача #{N}: {title}
Источник: task.md + tracker ({created|updated|noop})
Legacy: {номера Bitbucket | none}
Диф: {branch|any-ref}, коммитов {K}, в релизе {R}, вне релиза {A}
Анализ дифа: файлов {F}, находок {P}, решений {D}, условий {R2}
Бизнес-правила: active {X}, quarantine {Y}, rejected {Z} | none
Документация: doc.md {создан|обновлён}, архитектура {N документов}
Проверки: check-doc-text {ok|errors}, validate-docs {ok|errors}, identity {ok|mismatch}
Ограничения: {список}
```

## Три сценария

**Задача новая.** Все шаги с 1 по 5. Первый `doc.md` создаётся из минимальной
модели и дополняется фактами. Если реализации нет, в `doc.md` прямо сказано
"реализация не найдена".

**Задача есть, документация устарела.** Шаг 0 покажет старый диф и новые
комментарии. `ingest-tracker` обновит `tracker`, `task-diff` пересоберёт диф,
`task-doc` дополнит секции. Существующие факты не удаляются.

**Задача оформлена по старым правилам.** Нет `task.json` или текст не проходит
проверку. Intake создаёт `task.json`, переносит знания по правилам `task-doc`
(заголовки без эмодзи, обязательные секции, расшифровка кодов), затем
`check-doc-text.py` закрывает ошибки формулировок.

## Ограничения

- Экспорт Jira требует PHP в PATH или Docker и настроенный `.doc/skil_data/jira/config.env`.
- `any-ref` диф не доказывает принадлежность всех коммитов задаче, спорные
  случаи проверяются по subject и файлам.
- Intake не заменяет `prepare-plan`, `test-task` и `send-to-git`. Это отдельные
  шаги после появления документации.
- Повторный intake не должен переписывать подтверждённые решения и заметки
  пользователя.

## Связи

- [gototask](../gototask/SKILL.md) - экспорт `task.md` и `tracker.json`
- [task-diff](../task-diff/SKILL.md) - диф по коммитам, режим `any-ref`
- [task-doc](../task-doc/SKILL.md) - запись `doc.md`, архитектура, индекс
- [JSONdoc](../../../.doc/harnes/jsondoc.md) - `ingest-tracker`, `apply`, `render`
- [doc_rules.md](../../../.doc/harnes/doc_rules.md) - формат документации
