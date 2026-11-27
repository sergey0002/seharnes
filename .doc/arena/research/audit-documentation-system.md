# Система документации — обзор и аудит

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** **система документации** — правила документирования, планирования и разработки, CLI, организация работы с документацией задач и архитектурной документацией, **индексирование файлов**.
**Методы:** структурный анализ, чтение SKILL.md/SKILL-скриптов, чтение стандартов `doc_rules.md`/`jsondoc.md`, прогон CLI (`jsondoc --help`, `check-doc-text --help`, `check-links --help`).

---

## 1. Что это — система документации

Система документации — **унифицированный фреймворк**, который описывает и индексирует:
1. **Проект как целое** — архитектурная документация (`.doc/architecture/*.md`).
2. **Задачи** — документация задач (`.doc/tasks/{N}/doc.md`).
3. **Знание задач/архитектуры** — машиночитаемая модель `JSONdoc` + индекс.

Документация управляется **skilaми `documentation-router/children/*`** (3 скилла) + **стандартами** `.doc/harnes/doc_rules.md` (44 КБ, единый стандарт) и `.doc/harnes/jsondoc.md` (208 КБ, контракт JSONdoc).

**Важно:** как и задачи, архитектурная документация `.doc/architecture/` — **локальное состояние (gitignored)**, в repo только стандарты и скиллы.

---

## 2. Дерево documentation-скиллов

```
documentation-router/children/
├── task-doc      — документирование задачи (doc.md задачи)
├── project-doc   — документирование проекта (архитектура + индексация)
└── doc-verify    — сверка architecture/*.md с кодом (1=1)
```

### 2.1 `documentation-router` — роутер
- **Смысл:** только маршрутизация. Выбирает ровно **один** дочерний скил по таблице, читает его `SKILL.md`, выполняет шаги.
- **Приоритет:** сначала узкие скилы; `harness-core`/`task-core` — fallback.
- **Триггеры:** «задокументируй проект/задачу», «продолжи индексацию», «сверь документацию с кодом».

### 2.2 `task-doc` — документация задачи (Режим B)
- **Смысл:** фиксирует прогресс, подводные камни, решения и ссылки на архитектуру в `doc.md` задачи; аудит актуальности архитектурной документации.
- **Триггеры:** «задокументируй задачу», «document task», «обнови документацию задачи», «зафикси прогресс».
- **Ключевые шаги:**
  - **B0** — обязательное чтение `.doc/harnes/doc_rules.md` перед любой записью в `.doc/`.
  - **B1** — определить задачу/файлы; проверить актуальность task/diff/doc (обновить через `task-diff`).
  - **B1.5** — **JSONdoc batch** доступ (чтение+запись, лимит `MAX_CALLS=20`).
  - **B2** — сбор данных из диалога (файлы, подводные камни, решения, замечания, статус).
  - **B2.5 — MCP Reuse Gate** (обязательно): не дублировать существующую реализацию (codebase-memory-mcp + codegraph + serena + mysql).
  - **B2.6 — MCP Impact Gate** (обязательно): риск поломки соседних модулей (trace_path, codegraph_impact, phpstan/semgrep/playwright).
  - **B3** — обработка архитектурной документации (сбор ссылок + аудит актуальности).
  - **B4/B4.5** — запись `doc.md`, регистрация hashes.
- **Скрипты:** `jsondoc.py` (+ пакет `jsondoc/`), `schemas/`.
- **Связи:** `doc_rules.md`, `index.md`, `jsondoc.md`, `task-change-report` (workflow-context), `task-diff`, `gototask`.

### 2.3 `project-doc` — документация проекта (архитектура + индексация)
- **Смысл:** инициализация, анализ карты, документирование разделов с **продолжением с места остановки**, аудит, валидация, синхронизация.
- **Триггеры:** «задокументируй проект», «проанализируй карту проекта», «задокументируй раздел», «продолжи индексацию», «resume indexing», «bootstrap documentation», «document section», «исправь ошибки валидации», «обнови устаревшие документы».
- **Режимы:**
  - **MAP** — карта проекта (tree, hot-files, метрики, приоритет A/Б/В).
  - **SECTION** — документирование одного раздела (batch).
  - **AUDIT** — аудит docs (сломанные/устаревшие/без meta).
  - **VALIDATE** — валидация структуры.
  - **SYNC** — синхронизация docs с изменениями кода.
- **Скрипты:** `map-project.ps1`, `get-indexing-batch.ps1`, `mark-noise.ps1`, `audit-docs.ps1`, `validate-docs.ps1`, `sync-docs.ps1`, `generate-doc-index.ps1`, `generate-file-registry.ps1`, `build-tasks-index.ps1`, `check-doc-text.py`, `check-links.py`, `task-identity.py`, `_batch-ai-links.py`, `_fix_indexed_files_order.py`, `_restore_cicd_from_transcript.py`.
- **Статистика скриптов:** 16 скриптов — самый насыщенный doc-скилл.

### 2.4 `doc-verify` — сверка docs↔код
- **Смысл:** сверка `architecture/*.md` с кодом **1=1** через MCP Gate (codebase-memory-mcp + codegraph + serena), связи, задачи, Obsidian.
- **Триггеры:** «сверка документации», «продолжи сверку», «verify docs», «doc-verify».
- **Цикл:** `V1 batch → V2 Read md → V3 MCP Gate → V4 F → V5 L → V6 T → V7 O → V8 write → V9 mark → V10 report`.
- **MCP Gate (обязательный при ready):** codebase-memory-mcp, codegraph, serena. Sourcegraph выключен (legacy).
- **Скрипты:** `get-verify-batch.ps1`, `find-related-tasks.ps1`, `mark-verify-done.ps1`.

---

## 3. Правила документирования (`doc_rules.md`)

Единый стандарт работы с документацией проекта. **Читать первым** перед любой записи в `.doc/`.

### 3.1 Принципы (6)
1. **Простота важнее полноты.**
2. **Единственный источник правды** — код.
3. **Ссылки вместо копирования.**
4. **Близость к коду.**
5. **Контекст для агента = контекст для человека.**
6. **Самодостаточный тезис.**

### 3.2 Структура папки
- `.doc/architecture/` — архитектурные документы.
- `.doc/architecture/index.md` — оглавление (hub).
- `.doc/architecture/_map/` — реестр-очередь (`file-registry.tsv`), индекс docs (`doc-index.tsv`).
- MCP-серверы: один сервер, один файл.
- **JSONdoc:** `doc.md` — представление (render), а не источник; источник — JSON.

### 3.3 Формат каждого файла (строго в порядке)
```markdown
# Название раздела
<!-- meta type=... status=... updated=... related=... tags=... -->
## Суть
## [Основные секции по теме]
## Связи
## Известные проблемы и ограничения
## История изменений
```
- **`type`** строго из списка: `architecture | rules | api | model | flow | config | index`. Для `doc.md` задачи — `flow` (`task`/`task-doc` — неизвестные для валидатора).
- **Обязательные секции:** `## Суть`, `## Связи`, `## Известные проблемы и ограничения`, `## История изменений` (без эмодзи, без изменения текста).

### 3.4 Правила ссылок
- Формат ссылок: между files `.doc/architecture/`; из `tasks/{N}/doc.md` на архитектуру/правила; из архитектуры на файлы проекта — только code-блок.
- **Запрещено:** ...
- **Якоря:** `## Как устроено → #как-устроено`, `## API / Интерфейс → #api--интерфейс`, `## Проблемы и решения → #проблемы-и-решения`, `## TODO → #todo`.
- **Правило обратных ссылок** (A→B обязывает B→A).
- **Правило ссылок из задач** (B3.3).
- **Doc-verify:** сверка architecture ↔ код ↔ задачи.
- **Obsidian и граф.**
- **Блок «AI: когда читать»** (обязателен в hub-доках).
- **Factual audit** (сверка с кодом, не только git-даты).

### 3.5 Маркеры статуса (meta + таблица index.md)
| Маркер | В meta | В index.md | Значение |
|--------|--------|-----------|----------|
| ✅ | `status: actual` | ✅ актуально | проверено, соответствует коду |
| ⚠️ | `status: outdated` | ⚠️ устарело | известно, не соответствует |
| 📝 | `status: draft` | 📝 черновик | не проверено, по памяти |
| 🔒 | `status: frozen` | 🔒 заморожено | не меняется намеренно (легаси) |

### 3.6 Callouts и теги
- Callouts: `[!NOTE]`, `[!WARNING]`, `[!INFO]`, `[!TIP]` (Obsidian-читаемые).
- Теги: в meta (для агентов), в конце (для Obsidian-графа); из общего словаря.

### 3.7 Index Gate (обязательно перед созданием `architecture/*.md`)
1. Прочитать `.doc/architecture/index.md`.
2. Просмотреть существующие `*.md` (кроме `_*.md` и `_map/`).
3. Найти наиболее подходящий по имени/таблице/tags/H1+## Суть.
4. Если найден → **дописать**, не создавать новый.
5. Если не найден → предложить имя + AskQuestion.
6. После создания/дополнения → **обязательно обновить `index.md`**.
**Блоки index.md:** 1. Архитектура и основы; 2. Маршруты и контроллеры; 3. Фронтенд; 4. Бизнес-процессы; 5. Инфраструктура и интеграции.

---

## 4. Индексирование файлов (project-doc)

**Философия:** не «1 файл = 1 док», а **бизнес-процессы** (фронт+бэк); файлы берутся из очереди **пакетами**, автоматически отсортированные по директориям — **один батч = один модуль**.

### 4.1 Oчередь и реестр (стейт прогресса)
- `.doc/architecture/_map/file-registry.tsv` — реестр-очередь (progress между сессиями).
- `.doc/architecture/_map/doc-index.tsv` — индекс docs (Index Gate).
- `.doc/architecture/index.md` — оглавление.

### 4.2 Batch-цикл (B0–B4)
- **B0** — `get-indexing-batch.ps1 -Status` (прогресс-бар покрытия).
- **B1** — `get-indexing-batch.ps1 -Count 15` (N файлов из очереди, сгруппировано по директориям).
  - `-Kind css` — фильтр по типу; `-Skip N` — параллельные агенты.
- **B2** — анализ: определить бизнес-процесс; **не документировать 1-к-1**; **фильтрация шума** через `mark-noise.ps1 -Paths`.
- **B3** — создать/дополнить документ; **бектики на файлы кода обязательны** (map-project.ps1 обновляет статус на `indexed`).
- **B4** — `map-project.ps1` + `get-indexing-batch.ps1 -Status`; остановиться и отчёт.
- **B5 — автономный режим** (`/goal` в Antigravity).

### 4.3 MAP-режимы (M1–M4)
- **M1.1** — отделение app-кода от vendor/minified шума (классификация по путям: vendor/app/minified/unknown).
- **M2** — `_priority.md` (🔴A подробно / 🟡Б кратко / 🟢В пропустить).
- **M3** — старт batch-индексации.
- **M4** — отчёт.

### 4.4 AUDIT / VALIDATE / SYNC
- **AUDIT** (`audit-docs.ps1`): сразу исправить сломанные ссылки; план на устаревшие/без meta.
- **VALIDATE** (`validate-docs.ps1`): ошибки — исправить (AskQuestion); предупреждения — план.
- **SYNC** (`sync-docs.ps1`): для каждого устаревшего документа — читать **только** изменившиеся секции, обновить + `<!-- updated: {date}, sync -->` + meta + История изменений.

### 4.5 Правила экономии токенов
```
✓ Скрипты дают структуру — не сканируй папки сам
✓ Читай только сигнатуры, не тела методов
✓ Один батч = один модуль = один документ
✓ file-registry.tsv хранит прогресс между сессиями
✓ Index Gate перед каждым новым architecture/*.md
✓ CBM Gate (S4.6) при доступном MCP
✓ index.md обновляется в том же проходе SECTION — не опционально
✗ Не сканируй vendor/ node_modules/ cache/
✗ Не создавай architecture/*.md без Index Gate и без index.md
✗ Не читай doc_rules.md дважды за сессию
```

---

## 5. JSONdoc — план и модель документации задач/архитектуры

**`.doc/harnes/jsondoc.md` (208 КБ)** — контракт JSONdoc. Это **машиночитаемый знание-модель**: `task.json` — источник, `doc.md` — render.

### 5.1 Суть
JSONdoc — единственная точка входа для знания задач/архитектуры. `doc.md` задачи — **представление (view)**, а не источник. Запись через единый store (`Store.apply`, атомарно, под lock, CAS по `expected_revision`).

### 5.2 Хранение и архетектура
- Знание хранится в `task.json`/arch-JSON; `doc.md` — производный view.
- `render.py` — пересоздает MD view из JSON; **не пишет task.json**.
- `migrate.py` — lossless-миграция.
- `promote_rules.py` — бизнес-правила.

### 5.3 CLI (13 команд) — `jsondoc.py --root .`
| Команда | Смысл |
|---------|-------|
| `get` | read карточку/pointers (`--task`, `--arch`, `--keys`, `--select`, `--record-id`, `--limit`) |
| `search` | поиск tasks/arch (`--kind`, `--text`, `--tag`+`--tag-mode`, `--file`, `--release`, `--branch`, `--tasks`, `--not-in`) |
| `related` | связанные задачи (`--profile discovery-v1/legacy-v1`) |
| `apply` | запись update envelope (`--input`, `--dry-run`) |
| `render` | пересоздать MD view |
| `validate` | read-only schema + `--links` |
| `batch` | N read + один apply (лимит `MAX_CALLS=20`) |
| `ingest-tracker` | Jira-снимок (структурный JSON, не парсит markdown) |
| `ingest-git` | git-проекция (read-only, без сети) |
| `ingest-artifact` | регистрация артефакта (plan/diff/отчёт) с auto-hash |
| `stages` | стадиальная картина задачи |
| `selftest`/`execution`/`baseline`/`recover` | тесты/стейт-машина/бейзлин/recover |

### 5.4 Лимиты, envelope и коды выхода
- Default `limit=10`, `max_bytes=16384`. `--limit 0` = все (byte cap остаётся).
- Envelope: `status`, `data`, `counts`, `coverage`, `page`, `warnings`, `errors`, `next_action`.
- Coverage: `{discovered,converted,legacy,missing,invalid,stale,unresolved_refs,complete}`.
- **Коды выхода:** `0` ok (вкл. пустой search); `1` target не найден; `2` validation/CLI/coverage failure; `3` concurrency conflict; `4` recovery required.
- stdout — ровно один JSON envelope даже при ошибке.

### 5.5 Кто и как пишет `task.json`
| Пишущий | Что меняет | Режим |
|---------|------------|-------|
| `Store.apply` | единственная точка записи | атомарно, lock, CAS |
| `ingest-tracker` | `tracker`, release/branch | operations |
| `ingest-git` | `git_state`, branch | operations |
| `ingest-artifact`/`plan_writer` | `artifacts`, `stages` | operations (upsert) |
| `promote_rules.py` | `business_logic` | operations (set) |
| `migrate.py::apply_cutover` | создание из staging | full document при rev=0 |
| `render.py` | `doc.md` view | не пишет task.json |
| `.doc/skil_data/jira` | `task.md`, work/tracker.json | task.json не пишет |
| `.doc/web` | ничего | только чтение |

**Запрет перезаписи:** `contract.validate_update` (document только при `expected_revision=0`) + `Store._check_cas` (`create_target_exists`).

### 5.6 Реальные прогоны (этот аудит)
```
$ jsondoc.py --help   → 13 команд (selftest,execution,baseline,get,search,related,apply,render,validate,batch,ingest-tracker,ingest-git,recover)
$ jsondoc.py selftest  → "the following arguments are required: --run" (корректный argparse)
```

---

## 6. Все CLI-команды системы документации

### 6.1 Python-CLI

#### `jsondoc.py` (task-doc) — знание-модель
`python3 .../task-doc/scripts/jsondoc.py --root . [--docs-dir] {selftest,execution,baseline,get,search,related,apply,render,validate,batch,ingest-tracker,ingest-git,recover}`
- Подробный контракт §5.

#### `check-doc-text.py` (project-doc) — текстовая валидация
`python3 .../project-doc/scripts/check-doc-text.py [--root] [--task] [--file] [--baseline] [--write-baseline]`

#### `check-links.py` (project-doc) — проверка ссылок
`python3 .../project-doc/scripts/check-links.py [--root] [--only] [--skip] [--skip-historical] [--quiet]`

#### `task-identity.py` (project-doc) — идентификация задачи
`python3 .../project-doc/scripts/task-identity.py`

#### `_batch-ai-links.py` (project-doc) — AI-линки batch

### 6.2 PowerShell-CLI (project-doc / doc-verify)
| Скрипт | Смысл |
|--------|-------|
| `map-project.ps1` | карта проекта: tree, hot-files, метрики, regeneration registry+doc-index |
| `get-indexing-batch.ps1 -Status/-Count N/-Skip N/-Kind` | выдача батчей из очереди |
| `mark-noise.ps1 -Paths "..."` | исключить шум из очереди навсегда |
| `audit-docs.ps1` | Gaps, устаревшие, сломанные |
| `validate-docs.ps1` | ошибки структуры |
| `sync-docs.ps1` | список устаревших доков |
| `generate-doc-index.ps1` | генерация index.md |
| `generate-file-registry.ps1` | генерация file-registry.tsv |
| `build-tasks-index.ps1 -AlsoTsv` | владелец `.doc/tasks/index.md` + `_map/file-to-tasks.tsv` |
| `doc-verify/get-verify-batch.ps1` | батчи сверки docs↔код |
| `doc-verify/find-related-tasks.ps1` | P0.5a/V6 (score>=20, legacy-v1) |
| `doc-verify/mark-verify-done.ps1` | отметить сверку выполненной |

---

## 7. Организация работы с документацией задач

### 7.1 Документация задачи (task-doc, Режим B)
- **Где:** `.doc/tasks/{N}/doc.md` (view), задачи по правилам `doc_rules.md`.
- **Что фиксируется:** прогресс, подводные камни, решения, связи на архитектуру.
- **MCP-Gates:** Reuse Gate (B2.5) + Impact Gate (B2.6) — обязательны при доступном MCP.
- **JSONdoc:** `doc.md` — view; задача через `jsondoc` (batch, apply, render).

### 7.2 Индекс задач
- `.doc/tasks/index.md` — оглавление задач (owner: `build-tasks-index.ps1 -AlsoTsv`).
- `.doc/tasks/_map/file-to-tasks.tsv` — файл→задачи индекс.

### 7.3 Связь задач и архитектуры
- Из `tasks/{N}/doc.md` → архитектура/правила (по правилам ссылок из задач).
- Обратные ссылки: архитектура ↔ задачи.
- `doc-verify` сверка architecture ↔ код ↔ задачи.

---

## 8. Организация архитектурной документации (project-doc)

### 8.1 Архитектурные документы
- `.doc/architecture/` (gitignored) — разделы по бизнес-процессам.
- `.doc/architecture/index.md` — hub с навигацией, тегами, статусом документации.
- Создание/дополнение — через **Index Gate**.

### 8.2 Планирование и разработка
- **Планирование:** `task.json` (шаги, verify, acceptance), `plan.md` задачи; JSONdoc `stages`.
- **Разработка:** документация ведётся **параллельно** с разработкой (task-doc фиксирует решения, project-doc индексирует).
- **Синхронизация:** `sync-docs.ps1` при изменениях кода.

---

## 9. Потоки документации

### 9.1 Полный цикл документации
```
задача (task-doc) ─┐
                   ├─→ знание-модель (JSONdoc: task.json/arch-JSON)
архитектура (project-doc ─┤     │
  MAP → SECTION → AUDIT)    │     ├─→ doc.md (render)
                          │     │
                          └─→ doc-verify (сверка docs↔код 1=1)
                          │
                          └─→ index.md + file-registry.tsv (индекс)
```

### 9.2 Ключевые артефакты и их создатели
| Артефакт | Создает |
|----------|---------|
| `.doc/architecture/*.md` | project-doc (SECTION/MAP) + Index Gate |
| `.doc/architecture/index.md` | project-doc / generate-doc-index.ps1 |
| `_map/file-registry.tsv` | map-project.ps1 / generate-file-registry.ps1 |
| `_map/doc-index.tsv` | generate-doc-index.ps1 |
| `.doc/tasks/{N}/doc.md` | task-doc (view) + jsondoc render |
| `.doc/tasks/index.md` | build-tasks-index.ps1 |
| `_map/file-to-tasks.tsv` | build-tasks-index.ps1 -AlsoTsv |
| `task.json` (knowledge) | jsondoc store / ingest-* |
| `doc.md` (arch view) | render.py |

### 9.3 Связи скилов
- `task-doc` → `jsondoc.py`, `task-diff`, `doc_rules.md`, `task-change-report` (workflow-context).
- `project-doc` → `doc_rules.md`, `map-project.ps1`, `get-indexing-batch.ps1`, `codebase-memory-mcp`.
- `doc-verify` → codebase-memory-mcp + codegraph + serena, `get-verify-batch.ps1`.

---

## 10. Нахождения (findings)

### Ф-ДОК-1. **Два крупных стандарта — `doc_rules.md` (44 КБ) и `jsondoc.md` (208 КБ)**
- `doc_rules.md` — единый стандарт формата/ссылок/статусов (читать первым).
- `jsondoc.md` — 208 КБ, очень детализированный контракт (может быть тяжел для варьирования, но ориентированный).
- **Класс:** норма (не дефект). Концентрированная канония.

### Ф-ДОК-2. **Индексирование — batch-очередь с стейтом (file-registry.tsv)**
- Организовано как очередь с прогрессом между сессиями; Index Gate; CBM Gate.
- **Класс:** сильный side — устойчивая, resume-able система.

### Ф-ДОК-3. **`doc.md` — view, не источник; JSONdoc — store**
- Чёткое разделение: JSON — источник, MD — render; `render.py` не пишет task.json.
- **Класс:** сильный side (однозначный источник правды).

### Ф-ДОК-4. **MCP-зависимость (Reuse/Impact/Verify Gates)**
- task-doc/doc-verify **обязательны** при доступном MCP (codebase-memory-mcp + codegraph + serena).
- **Класс:** hard-contract (MCP должен быть ready).

### Ф-ДОК-5. **PowerShell-зависимость index-скриптов**
- `map-project.ps1`, `get-indexing-batch.ps1`, `validate-docs.ps1`, `sync-docs.ps1` — PowerShell.
- **Класс:** платформа-зависимость (не дефект логики).

### Ф-ДОК-6. **`.doc/architecture/` — gitignored локальное состояние**
- Как задачи: в repo только стандарты/скиллы.
- **Класс:** архитектурный (не дефект).

### Ф-ДОК-7. **Index Gate + обратные ссылки — защита от дублирования**
- Index Gate (order↔orders), правило обратных ссылок (A→B ⇒ B→A).
- **Класс:** сильный side.

---

## 11. Вердикт

**Система документации — зрелый, продуманный фреймворк** с чётким разделением: **архитектурная документация** (project-doc) + **документация задач** (task-doc) + **сверка с кодом** (doc-verify) + **знание-модель** (JSONdoc).

**Сильные стороны:**
- **Единый стандарт** (`doc_rules.md`) — формат, ссылки, статусы, Index Gate.
- **Индексирование с стейтом** — batch-очередь, resume-able, CBM Gate, Index Gate.
- **JSONdoc** — машиночитаемая модель, store/render разделены, CAS, ingest-tracker/git, batch.
- **MCP-интеграция** — Reuse/Impact/Verify Gates (codebase-memory-mcp + codegraph + serena).
- **Сверка docs↔код 1=1** (doc-verify).
- **Исключение шума** (mark-noise.ps1).

**Неровности:**
- Два крупных стандарта (44 КБ + 208 КБ) — тяжевы для варьирования.
- MCP-hard-contract (gates обязательны при ready).
- PowerShell-зависимость index-скриптов.
- Архитектурные docs — gitignored (локальное состояние).

**Общая оценка: 8.5 из 10.** Полнота и детализация высоки; индексирование и JSONdoc — зрелые. МКП-зависимость — hard-contract.

---

## 12. Рекомендации

1. **Ф-ДОК-1:** при росту `jsondoc.md` (208 КБ) разбить на модули-подразделы (контракт/CLI/миграция) для вариации.
2. **Ф-ДОК-4:** задокументировать MCP-ready как prerequisite для task-doc/doc-verify gates.
3. **Ф-ДОК-5:** PowerShell-скрипты индексации — задокументировать platform-contract.
4. **Контроль:** включить `check-links.py`, `check-doc-text.py`, `jsondoc validate` в pre-commit/CI (где есть документация).
5. **Mirror:** `harness_mirror audit --skill documentation-router` в регулярный аудит.

---

## 13. Связи

- CLI-справочник: `.doc/arena/research/cli-reference-all-commands.md`.
- Система задач: `.doc/arena/research/audit-task-system.md`.
- Дерево скилов: `.doc/arena/research/audit-skill-tree-and-web-panels.md`.
- Стандарты: `.doc/harnes/doc_rules.md`, `.doc/harnes/jsondoc.md`, `.doc/harnes/testaudit.md`.
- Скилы: `.agents/skills/documentation-router/children/{task-doc,project-doc,doc-verify}`.
- Архитектурная документация: `.doc/architecture/` (локальное состояние).

*Обзор выполнен по структурному анализу documentation-скиллов, чтению стандартов `doc_rules.md`/`jsondoc.md`/`references/indexing.md` и прогону doc-CLI.*
