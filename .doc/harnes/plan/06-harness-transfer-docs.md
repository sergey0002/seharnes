# Перенос всего харнеса и его документации в другую папку

<!-- meta
type: plan
status: draft
updated: 2026-11-25
related: [../index.md, ../state/14-project-migration.md, ../state/01-canon-envs.md, ./harnesmigrations.md, ../../rebase_project.md]
tags: [harness, migration, export, docs, sync, portability]
-->

## Суть

Задача: перенести из рабочего проекта в другой каталог весь харнес и всю его
документацию, а не только рабочие файлы движка. Сейчас `export_kit.py` переносит
файлы kit, но у него нет режима и модели приоритета для документации, нет учёта
документов, которых нет в источнике, и нет понятия «целевой харнес ушёл вперёд».

План вводит явный контракт переноса документации: режим `harness-docs`, шесть
классов документа харнеса, политику `copy_policy` из `canon-paths.yaml` как
источник истины и отдельный отчёт по каждому документу. Целевой результат -
повторяемая операция с приоритетом целевой папки по умолчанию и явной командой
на повышение приоритета эталона.

## 1. Что уже есть в движке

| Возможность | Где | Состояние |
|---|---|---|
| Состав kit по профилю | `kit.json` + `profile_manifest.py` | работает |
| Режимы install, update, mirror | `lib/transfer_modes.py` | работают |
| Слияние `mcp.json` и `AGENTS.md` | `export_kit._merge_mcp_bytes`, `transfer_merge` | работает |
| Подмена путей Source на Target | `lib/kit_adapt.rewrite_source_paths` | работает |
| Отчёт и маркер | `.doc/.rebase-report.md`, `.doc/.rebase-kit.json` | работает |
| Точные решения по файлам | `harness_transfer.py plan/approve/apply` | работает, отдельный receipt |
| Политика `copy_policy` для документации | `canon-paths.yaml` раздел `distribution` | **не читается экспортом** |
| Режим только для документации | нет | **отсутствует** |
| Приоритет по классу документа | нет | **отсутствует** |
| Стирание document service на Target при переносе | шаг `_scaffold` | **нет, только добавление** |

Вывод: движок переносит файлы, но не управляет документацией как отдельной
сущностью. Режим `harness-docs`, на который ссылается архивный README в
`seharnes/.doc/web/README.md`, в текущем движке не существует.

## 2. Терминология и стороны переноса

| Имя | Значение |
|---|---|
| Source | папка-эталон, откуда берут (например `testdeploydocker`) |
| Target | папка, куда переносят (например `seharnes`) |
| Baseline | хеши Source на момент прошлого переноса, лежат в receipt Target |
| Локальный документ | документ Target, которого нет в Source |
| Пропавший документ | документ есть в Baseline, но нет ни в Source, ни в Target |
| Конфликт | документ есть в обоих, хеши разные |

Три исхода для конфликта: взять Source (приоритет эталона), оставить Target
(приоритет цели), сохранить оба с суффиксом (ручной разбор). Четвёртый исход для
локального документа: удалить, если владелец Source и документ удалён из Source.

## 3. Классы документа харнеса

Разделение нужно, потому что у классов разная судьба при переносе. Один
`copy_policy` на все документы даёт ошибку в одну или другую сторону.

| Класс | Пример | Судьба при переносе |
|---|---|---|
| Канон | `doc_rules.md`, `skill-format.md`, `component-docs.md`, `state/canon-paths.yaml` | Копировать всегда, конфликт решает Source |
| Состояние | `state/*.md`, `state/*.json` | Копировать канон, целевые значения среды оставить |
| Планы | `plan.md`, `plan/*.md`, `idea/*.md` | Копировать, Target может иметь свои планы |
| Архив | `archive/*`, `dsh/*` | Копировать, только справочно |
| Заглушка | `# Stub` первой строкой | Не переносить из Target, заменить реальным документом Source |
| Локальное | `ADAPTERS.local.md`, `*.local.md`, `*.local.json` | Не копировать, не удалять |

Правило определения класса выводится из пути и из первой строки файла. Явную
таблицу путь-класс держит `kit.json` в новом разделе `docClasses`, чтобы не
угадывать по имени.

## 4. Политика приоритета по умолчанию

Предлагаемое поведение для новой операции, по убыванию силы:

| Правило | Действие |
|---|---|
| Документ локальный (`*.local.*`, `ADAPTERS.local.md`) | не трогать ни в каком режиме |
| Документ Target это заглушка `# Stub` | перезаписать документом Source, даже в `install` |
| Документ Target старше Baseline, Source новее Baseline | приоритет Source |
| Документ Target новее Baseline, Source не менялся | оставить Target, записать в отчёт |
| Документ Target новее Baseline и Source тоже менялся | конфликт, требует решения |
| Документ есть только в Source | добавить |
| Документ есть только в Target и владелец Source | удалить в режиме `mirror`, оставить в `update` |

По умолчанию операция переноса документации работает как `update`: Source
обновляет то, что он владеет, но не затирает более новую целевую правку
молча. Повышение приоритета эталона это отдельный флаг.

## 5. Опции приоритета

| Опция | Приоритет | Когда применять |
|---|---|---|
| `--docs-priority target` | Target по умолчанию | эталон моложе, есть ценные целевые правки |
| `--docs-priority source` | Source по умолчанию | эталон эталонный, Target только принимает |
| `--docs-priority source --mode mirror` | Source и удаление лишнего | делаем точную копию эталона |
| `--docs-classes canon,state` | только эти классы участвуют | точечный перенос канона |
| `--docs-exclude PATH` | исключить путь | пропустить `astra_plan`, `web2`, продуктовые флоу |
| `--docs-keep PATH` | всегда Target для пути | локальные расширения эталона |
| `--docs-report PATH` | только отчёт, без записи | предпросмотр документации без файлов kit |

Приоритет уровня всего переноса уже задаёт `--mode`. Новый набор `--docs-*`
задаёт приоритет внутри документации и не конфликтует с режимом файлов kit.

## 6. Различия Source и Target на момент 2026-11-25

Сверка Source `testdeploydocker` и Target `seharnes`, профиль `developer`, без
runtime-зависимостей, 3920 файлов kit.

| Категория | Файлов | Разбор |
|---|---|---|
| Отсутствует в Target | 2413 | 2352 это `.doc/harnes/astra_plan`, остальное реально нужное |
| Отличается содержимым | 134 | 90 в `.agents`, 27 в `.doc`, 17 в адаптерах и `.tools` |
| Только в Target внутри kit-корней | 42 | 4 старых PS1 и 4 их дока, 6 `ADAPTERS.local.md`, `login-as-user`, `docker-dev`, `php85-scan`, 3 архивных дока |

Сверх `astra_plan` в Target отсутствует 61 файл: 28 QA-флоу, 18 файлов скилов
(10 environment-sync, 5 new-project, 1 harness-core, 1 test-task, 1 todone),
6 файлов Codeception, 4 аудита, 2 файла `.kilo`, 1 DSH-json, 1 `rename_skill.md`,
план `06-harness-transfer-docs.md`.

### Документация по классам

| Наблюдение | Значение |
|---|---|
| Отсутствует в Target документов | 2387 |
| Из них `astra_plan/evidence` | 2325 |
| Из них `astra_plan` планы | 35 |
| Отличается документов | 27 |
| Из 27 Target это заглушка `# Stub` | 10 |
| Из 27 обе стороны содержат реальный текст | 16 |
| Из 27 рантайм-состояние | 1 |

Заглушки в Target покрывают 5471 строку реального текста Source: `субагенты.md`,
`deepseek.md`, `04-knowledge-store-and-queue.md`, `03-web-testing-system.md`,
`02-project-index-and-business-knowledge.md`, `01-subagent-planning-and-audit.md`,
`05-bug-hunt-and-modernization.md`, `idea/01-roadmap-hpta.md`,
`archive/mcp/sourcegraph-local.md`, `dsh/deepseek-harness-02-ustanovka.md`.
Причина заглушек: ранний перенос считал эти документы локальными проекту и
подставлял адрес ссылки. Сейчас Source их владеет, значит приоритет Source.

Из 16 реальных конфликтов 11 это правки движка и удалённого DSH, где Source
правее: `state/14-project-migration.md` (64 строки), `add-editor-environment.md`,
`component-install.md`, `index.md`, `jsondoc.md`, `readmy_doc.md`, `doc_readme.md`,
`state/05-scripts.md`, `state/22-panel-service.md`, `rebase_project.md`,
`state/13-agent-migration.md`. Ещё 1 файл это рантайм `.validate-rules-last.json`.

Остальные требуют ручного решения, потому что Target содержит обновление,
которого нет в Source:

| Документ | Что в Target новее |
|---|---|
| `state/01-canon-envs.md` | строка среды omp и запись истории 2026-11-24 |
| `state/16-task-analytics.md` | запись о переносе аналитики |
| `tests.md` | раннер Codeception на Docker PHP 8.3, запись 2026-11-24 |
| `web/README.md` | ссылка на `27-panel-architecture.md` вместо `22-panel-service.md` |
| `state/26-tools.md` | строки про симлинки `.tools` в общей папке |

`state/22-panel-service.md` и `state/26-tools.md` дополнительно чистят битые
относительные ссылки. Это же делает движок при переносе, конфликт ложный.

### Что ушло вперёд в Target

- Коммит `81adfaf` от 2026-11-25: среда omp, DSH-доки, mirror, jira-экспорт.
  Часть этих правок есть и в Source: `01-canon-envs.md` про omp, `generate-omp-config.py`.
- `.doc/web2` на 34 файла: в Source такого каталога нет.
- `.tools/docker-dev` (13 файлов), `.tools/php85-scan` (6 файлов), 6 файлов
  `.doc/web/state`. В Source `docker-dev` и `php85-scan` есть как симлинки на
  общую папку, содержимое живёт вне проекта.

### Что ушло вперёд в Source

- Весь новый движок: `export_kit.py`, `kit_selection.py`, `kit_adapt.py`,
  `transfer_modes.py`, тесты.
- Профиль Core с политиками, слияние `mcp.json`, подмена путей, receipt.
- 2325 файлов evidence `astra_plan` и 35 планов `astra_plan`.
- 28 QA-флоу, 18 файлов скилов, 6 файлов Codeception.
- Правки документации под новый движок от 2026-11-25.

## 6a. Полная инвентаризация различий

Метод: сверка по байтам по списку kit профиля `developer` без runtime-зависимостей,
плюс обратная сверка файлов Target, которые в выборку не попали. Дата 2026-11-25,
Source `5e8e7b7a3`, Target `81adfaf`.

### 6a.1 Сводка по категориям

| Категория | Файлов | Комментарий |
|---|---|---|
| Совпадают побайтно | 1373 | ядро kit идентично |
| Только в Source и не `astra_plan` | 61 | добавляются при первом `update` |
| Только в Source из `astra_plan` | 2352 | evidence и планы, ссылок нет |
| Отличаются | 134 | 90 в `.agents`, 27 в `.doc`, 17 в адаптерах и `.tools` |
| Только в Target внутри kit-корней | 42 | из них 8 старый движок, 6 локальных конфигов, продуктовые `.tools` |
| Только в Target вне kit | 45 tracked | `web2`, `docker-dev`, `php85-scan`, `EXPORT_NEXT_STEPS.md`, `.gitignore` |

### 6a.2 Только в Source: 61 файл вне `astra_plan`

| Группа | Файлов | Природа |
|---|---|---|
| `.agents/skills/harness-router/children/environment-sync` | 10 | `generate-omp-config.py`, `setup-workspace.py`, `workspace-gate.py`, `workspace-mcp.py` и их документы и тесты |
| `.agents/skills/harness-router/children/new-project` | 5 | `export_kit.py`, `kit_selection.py`, `kit_adapt.py`, `transfer_modes.py` |
| `.agents/skills/harness-router/children/harness-core` | 1 | `adapters/omp.py` |
| `.agents/skills/task-router/children/testing-router` | 1 | `test-task/docs/scripts/lib.sh.md` |
| `.agents/skills/todone` | 1 | `docs/scripts/tdcore/cli.py.md` |
| `.kilo` | 2 | `agent/shnyr.md`, `package.json` |
| `.doc/qa` | 28 | `index.md`, `fragments.md`, `browser-setup.md`, 19 флоу, `docker/Dockerfile`, `eslint/patch-max.js`, `_map/data-test.tsv`, `README.md` |
| `.doc/harnes/audit` | 4 | `1.md`, `2.md`, `4.md`, `summ.md` |
| `.doc/harnes` (без `audit`) | 3 | `rename_skill.md`, `dsh/deepseek-harness-02-ustanovka.json`, план `06-harness-transfer-docs.md` |
| `.tools/codeception` | 6 | `.env.dist`, `tests/Acceptance.suite.yml`, 4 `*Cest.php` |

### 6a.3 Только в Source: `astra_plan` 2352 файла

| Часть | Файлов | Размер | Решение |
|---|---|---|---|
| `astra_plan/evidence` | 2325 | 31 МБ | исключить по умолчанию |
| `astra_plan/*.md` планы 00-30 и `audit.md` | 35 | 1.2 МБ | включать явно флагом |
| Входящие ссылки из других документов | 0 | - | безопасно исключать |

### 6a.4 Отличаются: 134 файла

| Группа | Файлов | Кто правее | Как решать |
|---|---|---|---|
| `.agents` правки движка и документации | 90 | Source | приоритет Source |
| `.doc` заглушки Target | 10 | Source | заменить заглушку |
| `.doc` реальные конфликты | 16 | смешанно | 11 в Source, 5 в Target, см. 6a.6 |
| `.doc` рантайм-состояние | 1 | исключить | `.validate-rules-last.json` |
| `.codex`, `.cursor` README и сниппеты | 6 | Source | приоритет Source |
| `.tools` продуктовые Page и скрипты | 8 | Source | приоритет Source |
| `.kilo/.gitignore` | 1 | Target | оставить Target |
| `.serena/project.yml` | 1 | Target | имя проекта Target |
| `AGENTS.md` | 1 | Source | слияние managed block |

### 6a.5 Разбор `.agents`: 90 файлов

| Поддерево | Файлов | Причина расхождения |
|---|---|---|
| `task-router/children` | 22 | testing-router 11 (PHP 7.4 и `ac-matrix` в `run-phpunit.py`, `gates.py`, доки), gototask 4 (`Get-DocRepoRoot`, путь `.agents`), reporting-router 4, task-diff 2, task-intake 1 |
| `harness-router/children/environment-sync` | 16 | Source добавил `environment_policy.py`, `generate-omp-config.py`, `omp` в политику; Target коммитил свою версию |
| `harness-router/children/new-project` | 12 | новый движок `export_kit.py` и удаление PS1; в Target старый `profile_manifest.py` и `harness_transfer.py` без `export` |
| `harness-router/children/harness-core` | 7 | `harness_cli.py` (omp-view, export через Python), `manifest.py`, `kit.json`, `environments.json`, `skill.json`, `test_doctor_parity.py`, док CLI |
| `harness-router/children/migration-review` | 3 | ссылки на `export_kit.py` |
| `harness-router/children/mirror` | 2 | `harness_mirror.py` и тест |
| `harness-router/children/project-setup` | 1 | `onboard-project.py.md` |
| Корневые `SKILL.md` | 27 | разница ровно одна пара строк: описание скила от 2026-11-24 |

Сумма строк таблицы равна 90. 27 корневых `SKILL.md` отличаются минимально:
одна строка описания. Автоматический выбор Source безопасен для них, но
направление проверяется пачкой до записи.

### 6a.6 Разбор `.doc`: 27 файлов

| Файл | Target | Source | Куда | Строк диффа |
|---|---|---|---|---|
| `add-editor-environment.md` | реальный | реальный | Source | 29 |
| `archive/mcp/sourcegraph-local.md` | **заглушка** | реальный | Source | 159 |
| `component-install.md` | реальный | реальный | Source | 19 |
| `doc_readme.md` | реальный | реальный | Source | 2 |
| `dsh/deepseek-harness-02-ustanovka.md` | **заглушка** | реальный | Source | 229 |
| `idea/01-roadmap-hpta.md` | **заглушка** | реальный | Source | 406 |
| `index.md` | реальный | реальный | Source | 4 |
| `jsondoc.md` | реальный | реальный | Source | 4 |
| `plan/01-subagent-planning-and-audit.md` | **заглушка** | реальный | Source | 507 |
| `plan/02-project-index-and-business-knowledge.md` | **заглушка** | реальный | Source | 412 |
| `plan/03-web-testing-system.md` | **заглушка** | реальный | Source | 383 |
| `plan/04-knowledge-store-and-queue.md` | **заглушка** | реальный | Source | 902 |
| `plan/05-bug-hunt-and-modernization.md` | **заглушка** | реальный | Source | 390 |
| `plan/deepseek.md` | **заглушка** | реальный | Source | 853 |
| `plan/субагенты.md` | **заглушка** | реальный | Source | 1230 |
| `readmy_doc.md` | реальный | реальный | Source | 7 |
| `state/.validate-rules-last.json` | рантайм | рантайм | исключить | 2 |
| `state/01-canon-envs.md` | реальный | реальный | **Target** | 3 |
| `state/05-scripts.md` | реальный | реальный | Source | 7 |
| `state/13-agent-migration.md` | реальный | реальный | Source | 2 |
| `state/14-project-migration.md` | реальный | реальный | Source | 64 |
| `state/16-task-analytics.md` | реальный | реальный | **Target** | 2 |
| `state/22-panel-service.md` | реальный | реальный | Source | 10 |
| `state/26-tools.md` | реальный | реальный | **Target** | 9 |
| `tests.md` | реальный | реальный | **Target** | 10 |
| `web/README.md` | реальный | реальный | **Target** | 2 |
| `.doc/rebase_project.md` | реальный | реальный | Source | 6 |

Итого 10 заглушек, 16 реальных и 1 рантайм: 11 реальных решает Source, 5 решает Target, рантайм исключается.

### 6a.7 Пять конфликтов, где Target правее

| Файл | Что есть только в Target | Почему нельзя просто взять Source |
|---|---|---|
| `state/01-canon-envs.md` | строка среды omp и запись истории 2026-11-24 | Source тоже добавил omp, но формулировки разные, нужно объединить |
| `state/16-task-analytics.md` | запись о переносе аналитики | Source строку не менял |
| `state/26-tools.md` | симлинки `.tools` на общую папку и запись 2026-11-14 | описывает реальную раскладку Target |
| `tests.md` | раннер Codeception в Docker PHP 8.3 | описывает фактическую среду Target |
| `web/README.md` | ссылка на `27-panel-architecture.md` | файла нет ни в одной папке, обе ссылки битые, взять Source и поправить на `22-panel-service.md` |

`state/22-panel-service.md` и `state/26-tools.md` отличаются ещё и нормализацией
ссылок. После нормализации обеих сторон разница сокращается.

### 6a.8 Только в Target: 42 файла внутри kit-корней

| Путь | Файлов | Судьба |
|---|---|---|
| `new-project/scripts/*.ps1` и их доки | 8 | удалить, старый движок |
| `ADAPTERS.local.md` в трёх скилах и `.doc/web` | 4 | сохранить, локальный конфиг |
| `prepare-plan/ADAPTERS.local.md` | 1 | сохранить |
| `login-as-user` | 3 | продуктовый скил, исключён из kit, сохранить |
| `todone/scripts/tdcore/vendor/mermaid` | 6 | vendor, сохранить |
| `todone/assets/flows/*.autodoc.bak` | 4 | мусор, удалить по согласованию |
| `.doc/harnes/plan/harnesaudit-2026-11-02.md`, `harnesmigrations.md` | 2 | заглушки, удалить |
| `.doc/harnes/archive/buisnes_analis/plan.md` | 1 | архивная заглушка, удалить |
| `.doc/harnes/idea/СКАН БАЗЫ.txt` | 1 | локальный артефакт 104 КБ, решить |
| `.tools/docker-dev` | 6 | сохранить, продуктовый стенд |
| `.tools/php85-scan` | 6 | сохранить, продуктовый инструмент |
| `.tools/mcp-servers/php-toolchain/package-lock.json` | 1 | сохранить, lock |

### 6a.9 Только в Target вне kit-корней

| Путь | Файлов | Что это |
|---|---|---|
| `.doc/web2` | 34 | новая панель, подмножество Source `.doc/web1` на 392 файла |
| `.doc/web/state` | 106 | рантайм панели, защищён |
| `.doc/task-analytics/out` | 1 | состояние |
| `.doc/auditskil777.md` | 1 | локальная копия, есть и в Source |
| `EXPORT_NEXT_STEPS.md` | 1 | артефакт прошлого экспорта, перезаписать |
| `.gitignore` | 1 | allowlist эталона, не в kit, сохранить |
| `mcp.index.md` | 1 | в Source только `.doc/mcp.index.md`, сверить |

### 6a.10 Состояние Target сегодня

`doctor` в seharnes падает на 9 гейтах: `mirror-check`, `parity`,
`opencode-view`, `mcp-views`, `registry`, `structure`, `docs-components`,
`docs-scripts`, `render-check`. Причины: нет `.kilo/kilo.jsonc` и `.opencode`
конфигов, устаревший манифест parity, битые ссылки в документе. До переноса
Target чинить не обязательно, но после него все девять должны стать зелёными,
это и есть критерий приёмки.

### 6a.11 Что потеряется, если взять Source слепо

| Потеря | Где | Восстановление |
|---|---|---|
| omp формулировка про политику среды | `01-canon-envs.md` | ручное слияние |
| запись об аналитике | `16-task-analytics.md` | ручное слияние |
| симлинки `.tools` | `26-tools.md` | ручное слияние |
| раннер Docker 8.3 | `tests.md` | ручное слияние |
| панель `web2` | `.doc/web2` | вне kit, не затрагивается |
| продуктовые Page-объект правки | `.tools/codeception` | Source новее, правки сохраняются |
| `.tools/docker-dev`, `php85-scan` | `.tools` | вне выборки kit |

### 6a.12 Что потеряется, если взять Target слепо

| Потеря | Где |
|---|---|
| 5471 строка планов из заглушек | `plan/*`, `idea/*`, `archive/mcp`, `dsh` |
| новый движок и его тесты | `new-project`, `harness-core` |
| omp генератор и workspace-скрипты | `environment-sync` |
| PHP 7.4 канон и `ac-matrix` в прогоне | `test-task` |
| 2325 evidence `astra_plan` | `astra_plan` |
| 28 QA-флоу и 6 файлов Codeception | `.doc/qa`, `.tools/codeception` |
| `.codex/rules`, `.kilo/kilo.jsonc` и конфиги сред | адаптеры |

## 7. Подводные камни

| Камень | Симптом | Решение |
|---|---|---|
| Заглушки затирают реальные документы | после `update` в Target вместо документа остаётся `# Stub` | заглушку Target всегда перезаписывать Source |
| Потеря целевых обновлений | `mirror` затирает правку omp, Docker PHP 8.3, `web2` | `tv`-сравнение по Baseline, конфликт в отчёт |
| Ложные конфликты ссылок | `22-panel-service.md`, `26-tools.md` отличаются только нормализацией | нормализацию применять к обеим сторонам до сравнения |
| Зависимость от путей | `scriptdoc.md` содержит `file:///home/newuser/.../testdeploydocker` | расширить `rewrite_source_paths` на `file://` и прогонять перед сравнением |
| `astra_plan/evidence` | 31 МБ, 2325 файлов мусора в эталоне | `--docs-exclude .doc/harnes/astra_plan/evidence` по умолчанию |
| Два receipts | `export` пишет `.doc/.rebase-kit.json`, plan-движок пишет `.doc/web/state/transfer/receipt.json` | одну операцию вести одним движком, receipt один |
| `web` против `web2` | в Target новая панель лежит в `web2`, движок переносит `web` | решить явно, обновлять `web2` или держать `web` как эталон |
| Продуктовые флоу в эталоне | `.doc/qa/flows`, `*Cest.php` про CopyTrust | профиль эталона без `.doc/qa` и без `Acceptance` |
| Секреты | `mcp.env`, `config.env`, `.env` | уже исключены из kit, проверить после переноса |
| `.serena/project.yml` | имя проекта Source в Target | `--project-name` обязателен для эталона |
| `ADAPTERS.local.md` | локальный файл эталона удалит `mirror` | добавить в защищённые имена |
| Права и переводы строк | сравниваются байты, режим файла не проверяется | добавить режим в receipt |
| Слишком широкое зеркало | `mirror` удаляет `login-as-user`, `docker-dev`, `php85-scan` | защищённые корни `.tools` целиком или белый список |
| Регистр и NFC | пути с кириллицей (`субагенты.md`) | сравнивать по нормализованной форме |

### 7a. Дополнительные камни, найденные при глубокой сверке

| Камень | Симптом на этой паре папок | Решение |
|---|---|---|
| Слепой Source удаляет реальную среду | Target описывает Docker PHP 8.3 и симлинки `.tools`, Source держит старую версию | ручное слияние пяти документов из 6a.7 |
| Разные раскладки путей | `.codex/README.md`, `.cursor/README.md`, `gototask.ps1` в Target ссылаются на `.cursor/skills`, которого нет ни в одной папке | нормализовать `.cursor/skills` в `.agents/skills` перед сравнением |
| `web2` не обновляется | в Target новая панель, движок переносит только `web` | решить, что эталон панели, обновлять `web2` отдельно |
| 27 `SKILL.md` с минимальной разницей | автоматический выбор Source перезапишет одну строку описания в 27 файлах | диффы по одной строке проверить пачкой, решение Source безопасно |
| Восстановление `.tools/php-toolchain/package-lock.json` | `install` сохраняет, `mirror` удалит, если считать lock лишним | добавить `package-lock.json` в защищённые имена |
| три `.autodoc.bak` в `todone` | мусор попадает в `preserved` | удалить вручную, в отчёт как «к удалению» |
| `СКАН БАЗЫ.txt` 104 КБ | локальный артефакт, в Source нет | добавить в `--docs-exclude` |
| `EXPORT_NEXT_STEPS.md` | в Target уже есть от прошлого экспорта | перезаписывать всегда, не считать локальным |
| `.doc/mcp.index.md` против `mcp.index.md` | два разных файла с одним смыслом | сверить перед переносом, лишний убрать |
| `.doc/harnes/state/.validate-rules-last.json` | рантайм-состояние, меняется каждым прогоном | исключить из сравнения и из kit |
| Отсутствие `.codex/rules` в Target | `doc_readme.md` и `03-web-testing-system.md` ссылаются на `.codex/rules` и `.codex/skills`, которых нет | ссылки в Source битые уже сейчас, нормализация переведёт их в текст |
| `.codex/README-CODEX-SETUP.md` с CRLF | `diff` показывает 78 строк, содержимое одинаковое | сравнивать после нормализации переводов строк |
| `login-as-user` в Target | скила нет в kit Source, `mirror` его удалит | защищённое имя или `--docs-keep` |
| `todone` vendor mermaid | 6 файлов vendor, не в Source | защищённый путь `.agents/skills/*/vendor` |
| офсетная нумерация `state/20-jdocmunch.md` | ссылка в `index.md` на удалённый файл, битая в обеих папках | заменить строкой «раздел `mcp/jdocmunch.md`» |
| `AGENTS.md` с одной строкой | простая перезапись сработает, но при обратном переносе потеряется строка Target | слияние managed block, как сейчас |
| Права файлов | `README-CODEX-SETUP.md` в Target исполняемый, в Source нет | после копирования нормализовать режим по Source |
| Рантайм-файлы панели | `.doc/web/state` 106 файлов, `.doc/web2` 34 | защищены, в отчёт как «локальные» |
| Дубли receipt | `export` и plan-движок пишут разные файлы, второй прогон «не видит» первого | один receipt, `.doc/.rebase-kit.json` |
| Удаление удалённых из Source документов | `harnessmigrations.md` и `harnesaudit-2026-11-02.md` стали заглушками в Source, но в Target это реальные исторические документы | в `update` не удалять, в `mirror` удалять после ревью |

## 8. Целевое поведение операции

Одна команда, один проход, предсказуемые отчеты.

### Вход

- Source и Target абсолютными путями;
- профиль kit: `core`, `developer`, `project`;
- режим файлов kit: `install`, `update`, `mirror`;
- приоритет документации: `target` или `source`;
- классы документа, список исключений, список «всегда Target».

### Шаги

1. Проверить окружение: Source и Target существуют, не совпадают, не вложены.
2. Прочитать Baseline из receipt Target, если он есть.
3. Построить список файлов kit по профилю.
4. Построить список документов по классам и правилам `--docs-*`.
5. Нормализовать обе стороны перед сравнением: подмена путей, нормализация
   ссылок на отсутствующие файлы, NFC.
6. Классифицировать каждый документ: добавление, обновление Source, обновление
   Target, конфликт, удаление, заглушка.
7. Записать план и отчёт, показать счётчики по классам и приоритетам.
8. Выполнить запись с backup перезаписанных и удалённых файлов.
9. Пересобрать представления сред в Target.
10. Записать receipt и `EXPORT_NEXT_STEPS.md`, запустить `doctor` в Target.

### Выход

- `.doc/.rebase-report.md` с разделом `## Документация` по классам;
- `.doc/.rebase-docs-plan.json` полный список решений по документам;
- `.doc/.rebase-conflicts.json` список конфликтов с причиной;
- `.doc/.rebase-kit.json` с хешами Source, Target и Baseline;
- `EXPORT_NEXT_STEPS.md` с ручными шагами после переноса.

## 9. Что доработать в движке

| Изменение | Файл | Проверка |
|---|---|---|
| Читать `distribution` и `copy_policy` из `canon-paths.yaml` | `lib/kit_selection.py` | нет расхождения с `canon-paths.yaml` |
| Новый раздел `docClasses` в `kit.json` | `assets/kit.json` | покрывает все `.doc/harnes` пути |
| Классификация документов | новый `lib/doc_classes.py` | тесты на путь и первую строку |
| Сравнение по Baseline с классами | `export_kit.py` | `target` и `source` дают ожидаемые счётчики |
| Нормализация обеих сторон перед сравнением | `lib/kit_adapt.py` | ложные конфликты исчезают |
| Расширить подмену путей на `file://` | `lib/kit_adapt.py` | `scriptdoc.md` без пути Source |
| Флаги `--docs-*` | `export_kit.py`, `harness_cli.py` | help и прогон |
| Защита `*.local.*` и `ADAPTERS.local.md` в `mirror` | `export_kit._protected` | `mirror` их не удаляет |
| Режим `harness-docs` как профиль только документации | `profile_manifest.py` | набор ровно `.doc/harnes`, `.doc/qa`, `.doc/rebase_project.md` |
| Отчёт по документам | `export_kit._report` | раздел `## Документация` |
| Тесты | `tests/test_doc_classes.py`, `test_export_docs_modes.py` | падают на старом коде |
| Нормализация раскладки `.cursor/skills` и `.codex/skills` в `.agents/skills` перед сравнением | `lib/kit_adapt.py` | `.codex/README.md` без расхождения |
| Нормализация переводов строк перед сравнением | `lib/kit_adapt.py` | `README-CODEX-SETUP.md` без ложного диффа |
| Защита путей `*/vendor`, `package-lock.json`, `*.autodoc.bak` в `mirror` | `export_kit._protected` | vendor сохраняется |
| Исключение `.doc/harnes/state/.validate-rules-last.json` из сравнения | `kit.json` | нет рантайма в диффе |
| Отчёт «к удалению вручную» для 3 заглушек Target | `export_kit._report` | список в `.rebase-report.md` |
| Режим `--docs-mode adoption` без Baseline | новый флаг | первый прогон по Target с доверием к нему |

Минимальность: новый модуль классов, новые флаги и правка двух функций. Правку
источника истины о политике вести в `canon-paths.yaml`, а не в отдельном списке.

## 10. Проверки

1. Unit: классификация документов по пути и по `# Stub`.
2. Unit: правила `--docs-priority target` и `source` на восьмидокументном
   фикстуре, покрывающем все классы и исходы.
3. Интеграция: перенос документации в чистую папку, `doctor` в Target зелёный.
4. Интеграция: второй прогон без изменений даёт `0 added, 0 overwritten`.
5. Интеграция: `--docs-priority target` сохраняет правку Target, пишет конфликт.
6. Интеграция: заглушка Target заменяется документом Source.
7. Интеграция: `mirror` удаляет документ Source-владельца и не трогает
   `*.local.*` и `ADAPTERS.local.md`.
8. Реальный прогон в `seharnes`: 10 заглушек заменены, 5 конфликтов в отчёт,
   evidence `astra_plan` исключён, `doctor` зелёный, коммит только после ревью.
9. Нормализация: `README-CODEX-SETUP.md` (CRLF) и `.codex/README.md`
   (`.cursor/skills`) не попадают в список конфликтов.
10. Защита: `mirror` не удаляет `login-as-user`, `vendor/mermaid`,
    `ADAPTERS.local.md`, `package-lock.json`, `.doc/web/state`, `web2`.
11. Прогон `doctor` в seharnes после переноса: все 9 сегодняшних падений стали
    зелёными, включая `mcp-views`, `registry`, `parity`.
12. Обратный прогон: после переноса повторная сверка даёт 0 конфликтов и
    0 добавлений, 1373 одинаковых превращаются в полный набор.

## 11. Порядок выполнения для эталона seharnes

1. Тег отката: `git -C /home/newuser/projects/seharnes tag before-docs-merge`.
2. Добавить `--docs-exclude .doc/harnes/astra_plan/evidence` и `--docs-priority target`.
3. Предпросмотр и разбор `.doc/.rebase-docs-plan.json`: 10 заглушек, 11
   правок движка, 5 ручных конфликтов, 1 рантайм.
4. Ручные решения записать в `--docs-keep` для `state/16`, `tests.md`,
   `web/README.md`, `state/26-tools.md`, `state/01-canon-envs.md`. После переноса
   объединить в этих пяти файлах обе стороны: Target-абзац плюс Source-правку.
   Проверить вручную `web/README.md`: обе ссылки битые, поставить
   `22-panel-service.md`.
5. Ожидаемый результат первого `update`: 2414 добавлено, 134 перезаписано,
   1373 без изменений, 30 сохранено как локальные, 0 удалено.
6. Прогон без `--dry-run`, затем `doctor` в `seharnes`.
7. Удалить в `seharnes` 8 файлов старого движка и 8 документов.
8. Удалить мусор по согласованию: 4 `*.autodoc.bak`, 3 архивных заглушки,
   `idea/СКАН БАЗЫ.txt` или внести в `--docs-exclude`.
9. Решить судьбу `web2` и продуктовых флоу в эталоне.
10. Обновить `seharnes/.doc/web/README.md`: убрать несуществующие режимы
    `harness | harness-docs | project`, поставить актуальное имя операции.
11. Коммит после ревью, затем push.

## 12. Открытые вопросы

| Вопрос | Варианты | Кто решает |
|---|---|---|
| `astra_plan` в эталоне | исключить evidence, включить планы | пользователь |
| `web2` против `web` | эталон в `web`, `web2` локально | пользователь |
| Продуктовые QA и Codeception в эталоне | исключить по профилю | пользователь |
| Режим по умолчанию для эталона | `source` для первого переноса, потом `target` | пользователь |
| Судьба plan-движка `harness_transfer.py` | оставить для точных решений или свести к одному receipt | нужно решение |
| 27 `SKILL.md` с разницей в одну строку | какой вариант описания эталонный | пользователь |
| `idea/СКАН БАЗЫ.txt` | исключить или перенести в Source | пользователь |
| 4 `*.autodoc.bak` в `todone` | удалить в Target | пользователь |
| 3 архивные заглушки Target | удалить или оставить как историю | пользователь |
| `.doc/mcp.index.md` против корневого `mcp.index.md` | какой оставить | пользователь |

## 13. Затронутые файлы

| Файл | Роль | Изменение |
|---|---|---|
| `.agents/skills/harness-router/children/new-project/scripts/export_kit.py` | движок переноса | флаги `--docs-*`, раздел отчёта, защита локальных |
| `.agents/skills/harness-router/children/new-project/scripts/lib/kit_selection.py` | состав kit | чтение `copy_policy` и классов |
| `.agents/skills/harness-router/children/new-project/scripts/lib/kit_adapt.py` | нормализация | `file://`, обе стороны |
| `.agents/skills/harness-router/children/harness-core/assets/kit.json` | состав и классы | раздел `docClasses` |
| `.agents/skills/harness-router/children/new-project/scripts/lib/doc_classes.py` | новый модуль | классификация документов |
| `.agents/skills/harness-router/children/new-project/SKILL.md` | документация операции | новые флаги и режим |
| `.agents/skills/harness-router/children/new-project/docs/scripts/export_kit.py.md` | документ скрипта | новые аргументы |
| `.doc/harnes/state/14-project-migration.md` | карта переноса | описание документации и приоритетов |
| `/home/newuser/projects/seharnes/.doc/web/README.md` | Target | убрать несуществующие режимы |

## История изменений

- 2026-11-25: план создан по сверке Source и Target, собраны классы документов,
  исходы конфликтов и различия на этот день.
- 2026-11-25: частично реализовано: в `export_kit.py` добавлены `--exclude` и
  `--keep`; первый перенос в seharnes выполнен режимом `update` с приоритетом
  Source, `astra_plan` исключён, `login-as-user` и старый движок удалены.
- 2026-11-25: добавлена полная инвентаризация 6a по 134 различиям, 60 недостающим
  файлам, 42 файлам только в Target и пяти конфликтам, где Target правее; раздел
  7a с 17 дополнительными камнями и точными признаками; уточнены доработки,
  проверки и порядок для seharnes.
