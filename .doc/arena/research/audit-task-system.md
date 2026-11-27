# Система задач harness — детальный аудит

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** **полное описание системы задач** — задачи в `.doc/tasks`, все скрипты и скилы, их взаимодействие, все CLI. Особое внимание — **gototask** (переход к задаче) и **task-diff/getdiff** (получение diff задачи).
**Методы:** структурный анализ, чтение SKILL.md/skill.json, прогон CLI (`harness_mirror`, task-analytics, task_spec, intake_state).

---

## 1. Что такое система задач

Система задач — фреймворк для работы с задачами трекеров (Jira, Kaiten, Bitbucket-legacy): от постановки, через переход, diff, аудит, ревью, тесты — до отчётов и документации. Задачи живут в **`.doc/tasks/{N}/`** — это **локальное состояние, gitignored** (в repo только шаблон `task.json`).

**Все задачи скомплексированы в скилах `task-router/children/*`** (13 скилов + вложенные testing/reporting). Совместно с `documentation-router/children/task-doc` (jsondoc) — документация задач.

### 1.1 Структура задачи (`.doc/tasks/{N}/`)

```
.doc/tasks/{N}/
├── task.md           # человекочитаемое описание задачи (из Jira/экспорт)
├── task.json         # машинная metadata (структура из шаблона)
├── doc.md            # бизнес-правила / документация задачи
├── plan.md           # план реализации (prepare-plan / audit-plan)
├── diff.md           # diff задачи (task-diff) — коммиты с номером
├── diff.files.md     # список файлов diff задачи
├── test.md           # описание теста задачи (prepare-task-test)
├── tests/            # Cest-тесты задачи ({Slug}Cest.php, вне git)
├── test-runs/        # прогоны тестов (дата_группа/)
├── attachments/      # вложения из Jira
├── _dialogs/         # диалоги (anchor.json — якорь аналитики)
├── reports/          # отчёты (change-report, workflow-context.json)
└── dialogs/          # сессии диалогов (index.json, ses_*.json)
```

### 1.2 Шаблон `task.json` (машинная metadata)

```json
{
  "id": "T-001", "title": "", "priority": 2, "phase": null,
  "status": "draft", "parent": null, "depends_on": [], "parallelizable": false,
  "module": null, "problem": null, "goals": [], "acceptance": [],
  "in_scope": [], "out_of_scope": [], "context": [], "files_hint": [],
  "steps": [], "verify": [], "open_questions": [], "owner": null,
  "started_at": null, "blocked_reason": null, "notes": [], "change_kind": null,
  "created_at": null, "due": null, "estimate_h": null, "kind": "default",
  "release": null, "source": null, "comments": [], "report": null,
  "extra": {}, "refs": [], "artifacts": []
}
```
**Трекеры:** Jira (`CT-{N}`), локальный (`0_N`), Kaiten (документы-контракт).

---

## 2. Дерево task-скилов (overview)

`task-router` (orchestrator) → **13 children**:

```
task-router/children/
├── task-core          — базовые правила источников задач (fallback)
├── task-intake        — заводит задачу из Jira, доводит документацию
├── task-spec          — постановка задачи из переписки
├── gototask           — переход к ветке задачи (особое внимание §4)
├── task-diff          — получение diff задачи (особое внимание §5)
├── audit-plan         — аудит плана реализации
├── git-task-blame     — git-история задач по фрагменту кода
├── task-code-review   — ревью только своих коммитов задачи
├── analytics          — аналитика задач (метрики, факты, compliance)
├── jira               — адаптер Jira (экспорт task.md, MCP jira-task)
├── kaiten             — контракт адаптера Kaiten (docs-only)
├── testing-router/    — тестирование задач
│   ├── browser-verify       — браузерная проверка UI-флоу
│   ├── prepare-task-test    — конструктор теста задачи (Cest)
│   └── test-task            — оркестратор «тестируй задачу»
└── reporting-router/  — отчёты
    ├── task-change-report   — HTML-отчёт по изменениям
    └── task-report          — короткий комментарий в трекер
```

---

## 3. Обзор каждого скила по смыслу

### 3.1 `task-core` — ядро задач (fallback)
- **Смысл:** базовые правила источников задач и идентификаторов. Родительский скил для трекеров; общая логика источников/отчётов здесь.
- **Применение:** подключение/перенос адаптера трекера; понимание источника и формата `task_id`; изменение экспорта/аналитики.
- **Маршрутизация:** к `jira`, `kaiten`, `analytics`, `testing-router`, `reporting-router`, `documentation-router`.
- **Скрипты:** (routing-only, без scripts).

### 3.2 `task-intake` — завод задачи
- **Смысл:** один прогон приводит задачу к «в системе есть всё»: источник Jira, diff, бизнес-правила, `doc.md`, индекс. Только оркестрирует существующие инструменты, не пишет артефакты своим кодом.
- **Триггеры:** «заведи задачу», «импортируй задачу», «догони документацию задачи», «задокументируй задачу с нуля», «обнови задачу по новым правилам».
- **Ситуации:** задачи без папки, устаревшая документация, оформлено по старым правилам.
- **Скрипты:** `intake_state.py` (preflight), `intake_orchestrator.py` (state+Jira-export+tracker+diff), `intake_analysis.py` (каркас diff-анализа), `doc_sections.py` (применение doc-sections).

### 3.3 `task-spec` — постановка задачи
- **Смысл:** ведёт один черновик постановки в свободной переписке. Фиксирует каждое сообщение/скриншот/файл, отвечает коротким подтверждением. По команде «сформулируй задачу» исследует код/документы, декомпозирует, пишет `task.md` как идеальный постановщик.
- **Триггеры:** «постановка задачи», «поставь задачу», «собери требования», «сформулируй задачу», «просто фиксирую».
- **Скрипты:** `task_spec.py` (start/add/attach/show/finalize/current/use/list).

### 3.4 `audit-plan` — аудит плана
- **Смысл:** проверяет и сразу исправляет план. План пишет `prepare-plan`, проверяет/дополняет этот скил. На выходе один `plan.md`, готовый к исполнению, с метками аудиторских правок.
- **Триггеры:** «проведи аудит плана», «аудит плана», «audit the plan», «проверь план перед реализацией».
- **Не применять:** для первого плана (prepare-plan), реализации, тестов, документации, code review.

### 3.5 `git-task-blame` — git-история задач по коду
- **Смысл:** отвечает «какие задачи и ветки уже трогали эти строки, и что сломает моя правка» — через фактическую git-историю диапазона (не память/докстринги). Встраивается в P1 (blast radius) и P7.4a (аудит плана) prepare-plan.
- **Отличие от task-code-review:** git-task-blame смотрит **чужие** задачи, которые раньше трогали код; task-code-review — **свою** задачу.
- **Скрипты:** (routing-only).

### 3.6 `task-code-review` — ревью своей задачи
- **Смысл:** ревью **только** своих коммитов задачи по артефактам `diff.md`/`diff.files.md`. Легаси-код в тех же файлах — вне зоны. Проверяет ownership хунков по коммитам задачи.
- **Триггеры:** «task code review», «review task diff», «audit task changes», «verify hunk belongs to a task».
- **Скрипты:** (routing-only).

### 3.7 `analytics` — аналитика задач
- **Смысл:** метрики, факты и compliance задач. Привязка диалогов к задачам (anchor), атрибуция, отчёты.
- **Скрипты:** `task-analytics.py` (scan/report/attribute/anchor/assign/detach/backfill-anchors/validate), `lib/`.

### 3.8 `jira` — адаптер Jira
- **Смысл:** экспорт `task.md`, чтение задач, MCP `jira-task`.
- **Скрипты:** `server.php` (PHP-сервер, главный экспортёр), `export_task.py` (fallback на Python, если php/docker unavailable), `src/`, `diag-auth.php`, тесты.

### 3.9 `kaiten` — контракт адаптера Kaiten
- **Смысл:** docs-only контракт; код появится после API-клиента.

### 3.10 `testing-router` — тестирование задач
- **`browser-verify`:** браузерная проверка UI-флоу и регрессии. Codeception Acceptance (детерминированно, 0 токенов), Playwright MCP для логики без покрытия. Браузер всегда видимый.
- **`prepare-task-test`:** конструктор теста задачи из Page/Step-объектов и фрагментов AcceptanceTester. Кладёт `tests/{Slug}Cest.php` + `test.md`.
- **`test-task`:** оркестратор «тестируй задачу». Resolve TASK_ID → impact → prepare-task-test (если нет Cest) → browser-verify → отчёт test-runs.

### 3.11 `reporting-router` — отчёты
- **`task-change-report`:** универсальный HTML-отчёт по изменениям задачи (`report-model.json` → HTML). Объясняет бизнес-логику, правки, связи, сценарии, диаграммы, проверки.
- **`task-report`:** короткий комментарий в трекер (Jira/Kaiten) в стиле Sergey0002: прежняя логика, проблема, новая логика, исходы ошибок. Последняя строка «релиз X.Y.Z».

---

## 4. GOTOTASK — переход к задаче (особое внимание)

**Скил:** `task-router/children/gototask`. **Скрипт:** `scripts/gototask.ps1` (PowerShell, единственный вход).
**Суть:** переключение на ветку задачи Jira по номеру: обновляет `task.md` из Jira, ищет ветку на origin, создаёт от релизной ветки или вмерживает релиз в существующую, синхронизирует рабочую копию.

### 4.1 Воображение (CLI)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber {N} -Action {action} [параметры]
```

### 4.2 Actions
| Action | Когда |
|--------|-------|
| `inspect` | Первый шаг — JSON со всем состоянием |
| `export-task` | Только выгрузить `task.md`/tracker и обновить `task.json`; ветка не меняется |
| `create-branch` | Ветки нет — создать от релиза из Jira |
| `merge-release` | Ветка есть — **всегда** вмержить релиз из Jira |
| `checkout` | Только если явно нужен checkout без merge (не штатный) |
| `sync` | Checkout ветки и fast-forward до origin без merge релиза |

### 4.3 Параметры
- `-ReleaseBranch` — релиз (из Jira Version).
- `-TaskBranch` — `exact` или `suggestedBranch`.
- `-LocalChanges` — `keep` (оставляет + вопрос) / `stash` / `discard` (требует `-ConfirmDiscard`).
- `-SkipTaskExport` — не обращаться в Jira, читать локальный `task.md`.
- `-ConfirmCreateBranch`, `-ConfirmMerge`, `-ConfirmDiscard` — обязательные для create/merge/discard при открытых вопросах.
- `-RepoPath`, `-ConfigPath`.

### 4.4 Коды выхода
- `0` — успех; `2` — merge с конфликтами (`needsConflictResolution: true`); `3` — apply заблокирован открытым вопросом; `1` — необработанная ошибка.

### 4.5 Workflow (7 шагов)
1. **inspect** (всегда) — JSON со `task`, `releaseBranches`, `taskBranches`, `branchExists`, `recommendedAction`, `needsUserInput`. Скрипт сам: экспорт task.md из Jira, скачивание вложений, `git fetch origin`.
2. **AskQuestion** — только по `needsUserInput` (ветка/префикс/локальные правки).
3. **apply** — нет ветки → `create-branch`; есть → `merge-release` (релиз из Jira).
4. **Конфликты** — разрешить, согласовать, commit (`gototask: merge …`), **не push без просьбы**.
5. **Отчёт** — задача, task.md, ветка, релиз, действие, merge, локальные правки, codegraph.
6. **Якорь аналитики** — `task-analytics.py anchor`.
7. **MCP smoke test** — `test-mcp-servers.mjs`.

### 4.6 Автоправила (без вопросов)
1. Релиз всегда из Jira (Fix Version).
2. Ветка есть → всегда `merge-release`.
3. Если `needsUserInput` не пуст — AskQuestion обязателен, `recommendedAction` игнорируется.

### 4.7 Зависимости
- PHP в PATH или Docker `copytrust-dev-php-apache-1`; `.doc/skil_data/jira/config.env` (`read:jira-work`); Git remote `origin`.
- Legacy Bitbucket: читает номер из `task.md` (`Imported from` / `| Bitbucket | N |`), ищет legacy-ветки.

---

## 5. TASK-DIFF (getdiff) — получение diff задачи (особое внимание)

**Скил:** `task-router/children/task-diff`. **Скрипт:** `scripts/task-diff.ps1`.
**Суть:** генерирует `.doc/tasks/{N}/diff.md` + `diff.files.md` — диф **только по задаче** (коммиты с номером в subject), плюс незакоммиченные правки.

### 5.1 Воображение (CLI)
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/task-router/children/task-diff/scripts/task-diff.ps1 -TaskNumber {N}
# или канонический: .codex/task-diff.ps1
```

### 5.2 Actions
- `generate` (default) — создать/перезаписать diff.md.
- `inspect` — состояние, найденные ветки.

### 5.3 Параметры
- `-Mode full` (default) — все коммиты с номером задачи, даже влитые в релиз.
- `-Mode ahead` / `-AheadOnly` — только коммиты, которых ещё нет в релизе.
- `-StrictMatch` — subject строго начинается с номера.
- `-NoReleaseBase` — без метаданных релиза.
- `-SkipFetch` — не ходить в origin, только локальные refs.
- `-ForkCommit` — якорь диапазона вместо merge-base.

### 5.4 Как считается diff (источник истины — коммиты с номером)
1. Tip ветки с origin (`features/#N`/`bugfixes/#N`); локальный HEAD — только если потомок origin tip.
2. Фильтр subject: `N`, `#N`, `CT-N`, legacy из `task.md`.
3. `full` — полный диф; `ahead` — остаток до релиза.
4. Релиз для метаданных: `-ReleaseBranch` → суффикс → Jira Version → config.
5. Метаданные: `alreadyInRelease`, `aheadOfRelease`.
6. Незакоммиченные — `git diff HEAD` на ветке задачи.
7. Нет ветки — режим `any-ref`: коммиты по номеру во всех refs (`--all`), `Branch mode: any-ref`.

### 5.5 Resilience (SSH/network)
- Не падает при проблемах `git fetch`/SSH: `originSync` = `fetched`|`ls-remote`|`local-fallback`|`skipped`.
- При смене host key — `originHint` с командой для `known_hosts` (сам known_hosts не правит).

### 5.6 Результат
- `.doc/tasks/{N}/diff.md` — коммиты + summary.
- `.doc/tasks/{N}/diff.files.md` — список файлов.

### 5.7 Ограничения
- Не push, не commit. Не вызывать MCP jira-task — diff только из git.

---

## 6. Все CLI-команды системы задач

### 6.1 Python-CLI (по скиллам)

#### `task-analytics.py` (analytics)
`python3 .../analytics/scripts/task-analytics.py [--db DB] [--root ROOT] {scan,report,attribute,anchor,assign,detach,backfill-anchors,validate}`
- `scan`: `--task`, `--session`, `--latest`, `--after`, `--before`, `--dry-run`, `--allow-partial`, `--idle-minutes`.
- `report`: `--task`, `--append-history`, `--stage`.
- `attribute`: `--task`, `--session`, `--latest`, `--after`, `--before`, `--dry-run`, `--allow-partial`, `--idle-minutes`.
- `anchor`: `--task`, `--branch`, `--quote`, `--created-at`.
- `assign`: `--session`, `--task`, `--branch`, `--force`. `detach`: `--session`, `--task`, `--reason`.
- `backfill-anchors`, `validate`: —.

**Пример вывода (реальный):**
```
$ task-analytics.py validate
{"status": "ok", "checked": 0, "errors": []}
```

#### `task_spec.py` (task-spec)
`python3 .../task-spec/scripts/task_spec.py [--root ROOT] {start,add,attach,show,finalize,current,use,list}`
- `start`: `--title`, `--slug`. `add`: `--text`, `--stdin`, `--kind {remark,bug,requirement,decision,question}`, `--id`. `attach`: `--path`, `--caption`, `--id`. `show`: `--id`. `use`: `--id`. `finalize`: `--file`, `--title`, `--id`.

**Пример вывода (реальный):**
```
$ task_spec.py list
{"drafts": []}
$ task_spec.py current
{"current": null}
```

#### `intake_state.py` / `intake_orchestrator.py` / `intake_analysis.py` / `doc_sections.py` (task-intake)
- `intake_state.py [--path PATH] [--root ROOT] [--task TASK]` — компактный preflight (JSON с next_action).
- `intake_orchestrator.py --root ROOT --task TASK [--force] [--skip-export] [--skip-diff] [--no-network]` — deterministic intake.
- `intake_analysis.py --root ROOT --task TASK [--output OUTPUT]` — каркас diff-анализа.
- `doc_sections.py --root ROOT --task TASK --input INPUT [--apply] [--finalize] [--no-network]` — применение doc-sections.

**Пример вывода (реальный):**
```
$ intake_state.py
{"status": "error", "error": "task must be digits"}   # без --task
```

#### `jsondoc.py` (task-doc — документация задач)
`python3 .../task-doc/scripts/jsondoc.py --root ROOT [--docs-dir DOCS_DIR] {selftest,execution,baseline,get,search,related,apply,render,validate,batch,ingest-tracker,ingest-git,recover}`
- `get`: `--task`, `--arch`, `--keys`, `--select`, `--limit`, `--record-id`.
- `search`: `--kind {task,architecture}`, `--text`, `--tag`, `--tag-mode`, `--file`, `--release`, `--branch`, `--tasks`, `--limit`.
- `ingest-tracker`: `--task`, `--input INPUT` (передаёт Jira-snapshot).
- `render`: `--task`, `--arch`. `validate`: `--task`, `--arch`, `--all`, `--links`.

### 6.2 PowerShell-CLI (gototask / task-diff / jira)

#### `gototask.ps1`
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .../gototask/scripts/gototask.ps1 -TaskNumber {N} -Action inspect
powershell ... -TaskNumber {N} -Action create-branch -ReleaseBranch "releases/5.7.4" -TaskBranch "features/#2538" -ConfirmCreateBranch
powershell ... -TaskNumber {N} -Action merge-release -ReleaseBranch "releases/5.7.4" -TaskBranch "bugfixes/#2538" -ConfirmMerge
```

#### `task-diff.ps1`
```powershell
powershell ... -File .../task-diff/scripts/task-diff.ps1 -TaskNumber {N}
powershell ... -TaskNumber {N} -Mode ahead
powershell ... -TaskNumber {N} -SkipFetch
```

#### Jira-адаптер
- `jira/scripts/server.php` — PHP-сервер (главный экспорт task.md; понимает URL `…/browse/CT-2538` и ключ `CT-2538`).
- `jira/scripts/export_task.py` — Python-fallback экспортёр (если php/docker unavailable).

### 6.3 test-task (shell)
`bash .../test-task/scripts/task-test.sh {N} [--group …] [--filter …] [--profile …]` — прогон тестов задачи + артефакты + verdict.
Доп: `gates.py`, `doctor.py`, `run-phpunit.py`, `check-ac-matrix.py`, `qa-lint.py`, `cleanup-test-runs.py` (см. CLI-справочник).

---

## 7. Потоки системы задач

### 7.1 Полный цикл задачи
```
постановка (task-spec) → задача в системе (task-intake)
→ переход (gototask) → diff (task-diff)
→ план (prepare-plan) → аудит плана (audit-plan)
→ реализация → ревью (task-code-review, git-task-blame)
→ тесты (test-task → prepare-task-test → browser-verify)
→ отчёт (task-change-report / task-report) → документация (task-doc/jsondoc)
→ аналитика (analytics: anchor/attribute/report)
```

### 7.2 Ключевые артефакты и их создатели
| Артефакт | Создает |
|----------|---------|
| `task.md`, `task.json` | jira-адаптер / task-intake / gototask (export-task) |
| `diff.md`, `diff.files.md` | **task-diff** |
| `plan.md` | prepare-plan → **audit-plan** |
| `tests/{Slug}Cest.php`, `test.md` | prepare-task-test |
| `test-runs/` | test-task / browser-verify |
| `report-model.json` + HTML | task-change-report |
| `anchor.json` | analytics (anchor, после gototask) |
| doc.md / индекс задач | task-intake / task-doc |

### 7.3 Связи (dependencies) ключевых скилов
- `gototask` → `test-mcp-servers.mjs`, `jira/server.php`, `task-analytics.py`.
- `task-intake` → `check-doc-text.py`, `task-identity.py`, `validate-docs.ps1`, `jsondoc.py`.
- `audit-plan` → `prepare-plan` (required), `jdocmunch`, `task-router`.
- `task-code-review` → `diff.md`, `diff.files.md` (артефакты task-diff).

---

## 8. Аудит через harness_mirror

Mirror — semantic-граф канона; можно аудитировать task-скиллы:

```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . scan
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . audit --skill task-router
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . bundle --skill task-router
```

**Реальные результаты прогона (этот аудит):**
- `scan` → `{"status":"ok","written":1120,"skipped":0,"nodes":1120}` (построен граф из 1120 узлов).
- `audit --skill task-router` → JSON: `coverage {files:210, with_details:19, with_summary:100, pending:210}`, `files[]` со описанием каждого файла задач-системы:
  - `skill:task-router` — «Задача: постановка, переход, diff, аудит плана, ревью, тесты, Jira/Kaiten, отчёт, документация.»
  - `skill:analytics` — «Аналитика задач: метрики, факты и compliance.»
- task-CLI (`task-analytics validate`, `task_spec list/current`, `intake_state`) — чистый JSON, корректно работает.

**Оценка:** mirror-аудит подтверждает структуру task-системы; task-CLI работоспособны.

---

## 9. Нахождения (findings)

### Ф-ЗАДАЧИ-1. **Задачи — локальное состояние (gitignored)**
- `.doc/tasks/` в `.gitignore` (line 51). В repo только шаблон `task.json`; реальные задачи — локальное состояние проекта.
- **Класс:** архитектурный (не дефект). Система задач — фреймворк, действующий на локальное состояние.

### Ф-ЗАДАЧИ-2. **Два параллельных экспортёра Jira**
- `jira/server.php` (PHP, главный) + `jira/export_task.py` (Python-fallback).
- **Ф-ЗАДАЧИ-2b:** `export_task.py` содержит **SyntaxError** (f-string backslash, Python <3.12) — fallback-экспортёр **не запускается**.
- **Класс:** дефект (fallback-путь).

### Ф-ЗАДАЧИ-3. **gototask: PowerShell-зависимость**
- `gototask.ps1` и `task-diff.ps1` — PowerShell (Windows/WSL); требуют PHP в PATH или Docker, `.doc/skil_data/jira/config.env`.
- **Класс:** платформа-зависимость (не дефект логики, но hard-contract).

### Ф-ЗАДАЧИ-4. **`kaiten` — docs-only (без кода)**
- Контракт адаптера, код ещё не написан.
- **Класс:** стадия разработки.

### Ф-ЗАДАЧИ-5. **task-spec/task-intake — управляются агентом (не fully-automated)**
- task-spec — ведёт черновик в переписке (агент-driven); task-intake — оркестратор существующих инструментов.
- **Класс:** дизайн (не дефект).

### Ф-ЗАДАЧИ-6. **task-diff/gototask — resilience умеют падать мягко**
- task-diff не падает при SSH-проблемах (local-fallback); gototask не падает при недоступной сети (`originState: fetch_failed`).
- **Класс:** сильный side — устойчивость.

---

## 10. Вердикт

**Система задач — зрелый, детальный фреймворк** с чётким разделением по этапам.

**Сильные стороны:**
- **Полный цикл задачи:** постановка → intake → переход → diff → план/аудит → ревью → тесты → отчёт → документация → аналитика.
- **gototask** — надёжный, fail-closed переход (7-шаговый workflow, автоправила, коды выхода, кодграф-индекс, MCP-smoke).
- **task-diff** — устойчивый diff (источник истины — коммиты с номером; resilience к SSH/сети; legacy Bitbucket).
- **Явные артефакты** (`task.md`, `diff.md`, `plan.md`, `report-model.json`, `anchor.json`) с чёткими создателями.
- **Mirror-аудит** подтверждает структуру; task-CLI работоспособны.
- **Два трекера** (Jira + Kaiten-контракт), legacy-Bitbucket.

**Неровности:**
- Задачи — локальное состояние (gitignored), фреймворк без реальных данных в repo.
- `export_task.py` (Jira-fallback) — SyntaxError (не запускается).
- PowerShell-зависимость gototask/task-diff.
- `kaiten` — docs-only.

**Общая оценка: 8.5 из 10.** Полнота и детализация системы высоки; gototask и task-diff — зрелые, устойчивые скилы. Главный функциональный дефект — SyntaxError в Jira-fallback.

---

## 11. Рекомендации

1. **Ф-ЗАДАЧИ-2b (приоритет):** исправить SyntaxError в `jira/export_task.py` (f-string backslash) — включить Python-fallback экспорта.
2. **Ф-ЗАДАЧИ-3:** задокументировать PowerShell/PHP/Docker как hard-contract для gototask/task-diff.
3. **kaiten:** по добавлении API-клиента включить адаптера в цикл (наравне с jira).
4. **Контроль:** добавить `task-analytics validate` и проверку task-артефактов в pre-commit/CI (где задачи есть).
5. **Mirror:** включить `harness_mirror audit --skill task-router` в регулярный аудит дерева.

---

## 12. Связи

- CLI-справочник: `.doc/arena/research/cli-reference-all-commands.md`.
- Аудит дерева скилов: `.doc/arena/research/audit-skill-tree-and-web-panels.md`.
- Аудит скилов/переноса: `.doc/arena/research/audit-python-scripts-deep.md`.
- Конфиги: `.doc/arena/research/reference-all-system-configs.md`.
- Web-панель (задачи/документация): `.doc/web/`, `.doc/web2/`.
- mirror-граф: `harness_mirror.py` → `.doc/skil_data/mirror/graph.json`.

*Аудит выполнен по структурному анализу task-скилов, чтению SKILL.md/skill.json, прогону harness_mirror и task-CLI.*
