# Ref22: детальный архитектурный план рефакторинга харнеса

<!-- meta
type: plan
status: ready
updated: 2026-11-04
related: [../state/13-agent-migration.md, ../state/14-project-migration.md, ../skill-format.md, ../skills/README.md, ../doc_rules.md, ../index.md]
tags: [harness, migration, refactor, skills, mcp, cli, environments, plan, architecture]
-->

---

## Суть

План фиксирует полную перестройку подсистемы миграции, синхронизации и хранения инструментов харнеса. В соответствии с каноническими решениями проекта (`project.md_Constraints_harness_scripts_in_skills`, `project.md_Decisions_migration_artifacts_as_harness`) весь исполняемый код и скрипты убираются из директории `.doc/` и оформляются как полноценные артефакты харнеса: скилы стандарта `skill-format.md`, MCP-серверы, правила `.cursor/rules/mcp/*.mdc`, тесты и документация.

В каталоге `.doc/` из программных компонентов остаётся **исключительно локальная веб-панель** (`.doc/web/`). Все остальные служебные утилиты, парсеры, экстракторы, раннеры и генераторы распределяются по скилам с чётким разделением ответственности, единой точкой конфигурации сред (`environments.json`), реестром переносимых каталогов (`kit.json`) и общим консольным CLI (`harness_cli.py`).

План содержит результаты аудита существующей структуры, инвентаризацию всех 32 поддиректорий `.doc/`, целевую иерархию скилов с двумя корневыми оркестраторами (`harness-router` и `task-router`), контракты пакетов работ WP0–WP10, тесты и критерии приёмки.

---

## 1. Решения и стандарты харнеса

| Вопрос / Контракт | Решение | Источник правды |
|---|---|---|
| Программы внутри `.doc/` | Только `.doc/web/`. Все остальные скрипты выносятся в `.agents/skills/` | `project.md_Constraints_harness_scripts_in_skills` |
| Оформление переноса | Каждый инструмент упаковывается как скил (`SKILL.md`, `README.md`, `skill.json`, `scripts/`, `tests/`, `assets/`, `references/`) + MCP-правило + MCP-док | `project.md_Decisions_migration_artifacts_as_harness` |
| Оркестратор харнеса | Корневой скил `harness-router` с детьми в `children/` | `ref22.md`, `skill-format.md` S06 |
| Оркестратор задач | Корневой скил `task-router` с дочерними адаптерами трекеров | `ref22.md`, `project.md_Decisions_task_tracker_scope` |
| Единый список сред | `harness-router/assets/environments.json` (один источник правды) | R1 `ref22.md` |
| Единый список kit | `harness-router/assets/kit.json` (копирование, исключения, состояние) | R2 `ref22.md` |
| Общая библиотека | `harness-router/scripts/lib/` (импорт по полному пути от корня) | R3 `ref22.md`, `skill-format.md` B07 |
| CLI для человека и агента | `harness_cli.py` (`doctor`, `setup`, `sync`, `export`, `verify`, `mcp-audit`) | R4 `ref22.md` |
| Отчетность в трекер | Скил `jira-report` переименовывается в трекеро-независимый `task-report` | `corrections.md_Corrections_jira_report_skill_name` |
| Адаптер Kaiten | Дочерний docs-only скил `task-router/children/kaiten` без скриптов до API-клиента | `project.md_Decisions_task_tracker_scope` |
| Состояние и кеши | Выносятся в `.doc/skil_data/` и `~/.local/state/harness/`; в скилы не попадают | `skill-format.md` S08 |
| Валидатор `.doc` | Отдельный постоянный сканер не создаётся; структура упорядочивается однократно | решение пользователя от 2026-11-04 |
| Запуск под Windows | Через `wsl.exe`; нативный UNC-запуск PowerShell не гарантируется | `new-project` spec |

---

## 2. Аудит директории `.doc/` и сканирование компонентов

По результатам сканирования 32 каталогов внутри `.doc/` выявлено распределение файлов:

```
Каталог .doc/               Всего     Код     MD     Прочее  Назначение / Действие
------------------------------------------------------------------------------------------------------
.content-extractor          5195    1725     23       3447  Код в skill:page-content, venv удалить
.xml-river                  6315    4540     22       1753  Код в skill:xmlriver, venv в .state
.mcpyandexscreen             163       1      1        162  Скрипт в skill:yadisk-screenshot, imd/ удалить
.jira                         20      14      2          4  Код в skill:task-router/children/jira
.seoq                        124      26      3         95  Код в новый skill:seoq
serpanalise                  383      49     12        322  Код в skill:serpanalise-report
buisnes_analis               304      21      1        282  Код в skill:business-analyst, данные в .state
codeception                 3370    2948    139        283  Скрипты в skill:test-task / browser-verify, vendor удалить
docscripts                    24      20      0          4  Скрипты в skill:project-doc / doc-verify
jsondoc_scripts            27463      83   2591      24789  Код в skill:task-doc, runs/work в .state
leantime                      22       2      6         14  Скрипты в skill:task-router/children/leantime
qa                           153      28     26         99  Скрипты в skill:test-task, docs в references/
synh_harnes                   30      14      3         13  Код в skill:harness-router
task-analytics               139      11      3        125  Код в skill:task-router/children/analytics
testanalyze                  642       2    153        487  Скрипты в skill:test-task, данные в .state
rebase_project*.ps1 (корень)   2       2      0          0  Скрипты в skill:harness-router/children/new-project
------------------------------------------------------------------------------------------------------
web                           70      16      4         50  ОСТАЕТСЯ В .doc/web (единственная программа)
harnes                       286       0    284          2  ОСТАЕТСЯ В .doc/harnes (документация харнеса)
architecture                 511       0     81        430  ОСТАЕТСЯ В .doc/architecture (документация домена)
tasks                      15010      69   1207      13734  ОСТАЕТСЯ В .doc/tasks (документация и задачи)
kaiten                         1       0      1          0  ОСТАЕТСЯ В .doc/kaiten (описание, данные)
optimizeform                   9       0      9          0  ОСТАЕТСЯ В .doc/optimizeform (документы формы)
plan                           2       0      2          0  ОСТАЕТСЯ В .doc/plan (история планов)
d2, d8, d9                     8       0      0          8  ОСТАЕТСЯ В .doc/ (статические диаграммы)
------------------------------------------------------------------------------------------------------
.rebase-mcp-backup             -       -      -          -  Перенести в .doc/skil_data/rebase-mcp-backup
.jdocmunch                    23       0      0         23  Индекс; хранить в ~/.doc-index или .state
.backup                      967       6      1        960  УДАЛИТЬ (старые дампы панели)
_backup_harness                2       0      0          2  УДАЛИТЬ (устаревший бэкап)
.bitbucket                    11       7      1          3  УДАЛИТЬ / архив (legacy трекер)
temp                        3913    1818    726       1369  УДАЛИТЬ (временные бенчмарки и тесты)
tmp                            0       0      0          0  УДАЛИТЬ
```

### 2.1. Итоги инспекции harness-mirror и линтера

Запуск `harness-mirror lint` выявил критические структурные дефекты:
1. `unreferenced_script`: 24 скрипта лежат в `.cursor/scripts/` и `.agents/skills/*/scripts/`, но не имеют декларации в `skill.json` или правил вызова.
2. `bad_relation`: ссылки вида `.cursor/skills/...` вместо канонического пути `.agents/skills/...` нарушают переносимость между клиентами.
3. `isolated`: 8 скилов не имеют входящих и исходящих связей с другими компонентами харнеса.
4. Отсутствие источников правды (`no_sources`) в мета-блоках правил.
5. `node_id collision`: вложенные дочерние скилы `children/<name>` давали тот же `doc:` и `config:` id, что и родительский README и `skill.json`. Сканер `harness_mirror.py` исправлен: slug для файлов внутри `children/` включает путь `children/<name>`. После исправления `scan --include-mirrors` и `check` проходят, 928 узлов, 0 ошибок.

Рефакторинг решает эти дефекты: каждый исполняемый файл связывается со скилом, регистрируется в его манифесте и отражается в графе `harness-mirror`.

---

## 3. Целевая архитектура скилов и пакетов

### 3.1. Иерархия управления харнесом (`harness-router`)

```
.agents/skills/harness-router/
├── SKILL.md                          # Оркестратор управления харнесом
├── README.md                         # 4 обязательных раздела (R01-R06)
├── skill.json                        # kind: orchestrator, children [...]
├── scripts/
│   ├── harness_cli.py                # Единый CLI (doctor, setup, sync, export, verify)
│   ├── lib/                          # Общая библиотека (импорт из всех дочерних скилов)
│   │   ├── __init__.py
│   │   ├── config.py                 # Валидация и загрузка environments.json / kit.json
│   │   ├── manifest.py               # Манифесты, хеширование, сравнение деревьев
│   │   ├── ports.py                  # Выбор свободных портов, определение владельцев
│   │   ├── mcp.py                    # Нормализация и трансформация конфигураций MCP
│   │   ├── report.py                 # Пошаговая отчетность, тайминги, сводки
│   │   └── paths.py                  # Разрешение абсолютных и относительных путей
│   └── adapters/                     # Модули сред (правила, скилы, MCP)
│       ├── __init__.py
│       ├── base.py                   # Интерфейс BaseAdapter
│       ├── cursor.py
│       ├── codex.py
│       ├── kilo.py
│       ├── qoder.py
│       ├── qwen.py
│       └── agents.py
├── assets/
│   ├── environments.json             # Реестр сред (канон)
│   └── kit.json                      # Реестр переносимых директорий kit
├── references/
│   ├── environments.md
│   ├── kit.md
│   └── cli.md
├── tests/
│   ├── test_config.py
│   ├── test_manifest.py
│   ├── test_ports.py
│   ├── test_mcp.py
│   └── test_cli.py
└── children/
    ├── project-setup/                # Настройка проекта после миграции (бывший project-setup)
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── skill.json
    │   ├── scripts/
    │   │   └── onboard-project.py
    │   └── references/onboarding.md
    ├── new-project/                  # Перенос kit в новый проект (бывший new-project)
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── skill.json
    │   ├── scripts/
    │   │   ├── rebase_project.ps1
    │   │   ├── rebase_project_gi.ps1
    │   │   └── copy-dsh-kit.ps1
    │   └── references/export.md
    ├── environment-sync/             # Синхронизация проекций по environments.json
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── skill.json
    │   ├── scripts/
    │   │   └── sync-agent-views.sh   # Обертка над harness_cli.py sync
    │   └── references/sync.md
    ├── mcp-audit/                    # Аудит, проверка статусов и инвентаризация MCP
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── skill.json
    │   ├── scripts/
    │   │   ├── test-mcp-servers.mjs
    │   │   ├── verify_mcp_views.py
    │   │   └── scan-usage.py
    │   └── references/mcp-map.md
    ├── mirror/                       # Зеркало харнеса и просмотрщик связей
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── skill.json
    │   ├── scripts/harness_mirror.py
    │   └── references/
    └── index/                        # Индекс харнеса и смысловой аудит
        ├── SKILL.md
        ├── README.md
        ├── skill.json
        └── references/
```

### 3.2. Иерархия управления задачами (`task-router`)

```
.agents/skills/task-router/
├── SKILL.md                          # Оркестратор работы с задачами и источниками
├── README.md                         # Человеческое описание
├── skill.json                        # kind: orchestrator
├── references/
│   ├── sources.md                    # Инварианты task_id (Jira vs 0_N)
│   └── workflow.md                   # Жизненный цикл задачи
└── children/
    ├── jira/                         # Адаптер трекера Jira
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── skill.json
    │   ├── scripts/
    │   │   ├── server.php            # MCP-сервер jira-task
    │   │   ├── export_task.py        # Экспорт task.md
    │   │   ├── test-dual-export.php
    │   │   └── diag-auth.php
    │   └── references/jira-config.md
    ├── leantime/                     # Адаптер локального PM Leantime
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── skill.json
    │   ├── scripts/
    │   │   ├── rpc.sh
    │   │   └── launch.sh             # MCP-сервер leantime
    │   └── references/leantime.md
    ├── kaiten/                       # Docs-only адаптер трекера Kaiten
    │   ├── SKILL.md
    │   ├── README.md
    │   ├── skill.json
    │   └── references/kaiten-contract.md
    ├── gototask/                     # Переход к задаче
    ├── task-diff/                    # Diff задачи
    ├── task-doc/                     # Документация задачи
    ├── task-intake/                  # Заведение задачи
    ├── task-code-review/             # Проверка кода задачи
    ├── task-change-report/           # HTML-отчет
    ├── task-report/                  # Краткий отчет в трекер
    ├── prepare-task-test/            # Подготовка браузерного теста
    ├── test-task/                    # Проверка задачи тестами
    ├── git-task-blame/               # История изменений задачи
    └── analytics/                    # Метрики задач и аналитика
        ├── SKILL.md
        ├── README.md
        ├── skill.json
        ├── scripts/
        │   ├── render.py
        │   ├── facts.py
        │   ├── metrics.py
        │   ├── slices.py
        │   └── compliance.py
        └── references/metrics.md
```

### 3.3. Реестр остальных скилов-инструментов

| Скил | Тип | Исходный каталог в `.doc/` | Переносимый код | MCP-сервер |
|---|---|---|---|---|
| `task-report` | leaf | `jira-report/` (переименование) | Генерация краткого отчета в любой трекер | - |
| `page-content` | leaf | `.doc/skil_data/page-content/` | `src/`, `tests/`, фикстуры | - |
| `xmlriver` | leaf | `.doc/skil_data/xmlriver/` | `src/`, `scripts/build_*.py`, assets | `xmlriver`, `xmlriver-ws` |
| `yadisk-screenshot`| leaf | `.doc/skil_data/yadisk-screenshot/` | `yadisk-fetch.ps1` | - |
| `serpanalise-report`| leaf | `.doc/skil_data/serpanalise-report/` | `lib/*.py`, `tests/` | - |
| `business-analyst` | leaf | `.doc/skil_data/business-analyst/` | `scripts/*.py`, `tests/` | - |
| `project-doc` | leaf | `.doc/docscripts/` (часть) | `map-project.ps1`, `audit-docs.ps1`, `sync-docs.ps1` | - |
| `doc-verify` | leaf | `.doc/docscripts/` (часть) | `get-verify-batch.ps1`, `mark-verify-done.ps1` | - |
| `task-doc` | leaf | `.doc/skil_data/task-doc/` | `jsondoc.py`, `jsondoc/*.py`, `tests/` | - |
| `test-task` | leaf | `.doc/qa/scripts/`, `.doc/skil_data/test-task/testanalyze/` | `task-test.sh`, `gates.py`, `build-testanalyze.py` | - |
| `browser-verify` | leaf | `.tools/codeception/scripts/` | `start-chromedriver-wsl.sh`, `chromedriver-host-relay.py` | `playwright` |
| `seoq` | leaf | `.doc/skil_data/seoq/` (новый скил) | `sigmaplaza/*.py`, `*.ps1` | - |

---

## 4. Конфигурационные схемы канона

### 4.1. `harness-router/assets/environments.json`

```json
{
  "schema": 1,
  "environments": [
    {
      "id": "cursor",
      "enabled": true,
      "adapter": "cursor",
      "rules": {"source": ".cursor/rules", "target": ".cursor/rules", "format": "mdc"},
      "skills": {"mode": "native", "target": ".agents/skills"},
      "mcp": {"source": ".cursor/mcp.json", "target": ".cursor/mcp.json"},
      "instructions": {"target": "AGENTS.md"}
    },
    {
      "id": "codex",
      "enabled": true,
      "adapter": "codex",
      "rules": {"source": ".cursor/rules", "target": ".codex/rules", "format": "flat_md"},
      "skills": {"mode": "mirror", "target": ".codex/skills"},
      "mcp": {"source": ".cursor/mcp.json", "target": ".codex/config.toml"}
    },
    {
      "id": "kilo",
      "enabled": true,
      "adapter": "kilo",
      "rules": {"source": ".cursor/rules", "target": ".kilo/rules", "format": "flat_md"},
      "skills": {"mode": "native", "target": ".agents/skills"},
      "mcp": {"source": ".cursor/mcp.json", "target": ".kilo/kilo.jsonc"}
    },
    {
      "id": "qoder",
      "enabled": true,
      "adapter": "qoder",
      "rules": {"source": ".cursor/rules", "target": ".qoder/rules", "format": "trigger"},
      "skills": {"mode": "mirror", "target": ".qoder/skills"},
      "mcp": {"source": ".cursor/mcp.json", "target": ".qoder/settings.json"}
    },
    {
      "id": "qwen",
      "enabled": true,
      "adapter": "qwen",
      "rules": {"source": ".cursor/rules", "target": ".qwen/rules", "format": "paths"},
      "skills": {"mode": "native", "target": ".agents/skills"},
      "mcp": {"source": ".cursor/mcp.json", "target": ".qwen/settings.json"}
    },
    {
      "id": "agents",
      "enabled": true,
      "adapter": "agents",
      "rules": {"source": ".cursor/rules", "target": ".agents/rules", "format": "trigger"},
      "skills": {"mode": "native", "target": ".agents/skills"},
      "mcp": {"source": ".cursor/mcp.json", "target": ".agents/mcp.json"}
    }
  ]
}
```

### 4.2. `harness-router/assets/kit.json`

```json
{
  "schema": 1,
  "copy": [
    ".cursor",
    ".codex",
    ".agents",
    ".kilo",
    ".qoder",
    ".qwen",
    ".dsh",
    ".serena",
    ".doc/harnes",
    ".doc/web",
    ".doc/qa",
    ".tools/codeception"
  ],
  "rootFiles": [
    "AGENTS.md",
    "mcp.index.md",
    ".codeprism.toml",
    ".cbmignore"
  ],
  "skipDirs": [
    "node_modules",
    "vendor",
    "__pycache__",
    ".venv",
    ".venv-linux",
    ".venv-win",
    "cache",
    "runs",
    "work",
    "state",
    "reports",
    "test-runs"
  ],
  "skipFiles": [
    "mcp.env",
    ".env",
    "config.env",
    "*.log",
    "*.token",
    "*.pyc",
    "*.fail.png",
    "*.fail.html"
  ],
  "stateDirs": [
    ".doc/skil_data",
    ".doc/temp",
    ".doc/tmp",
    ".doc/skil_data/jdocmunch"
  ]
}
```

---

## 5. Спецификация CLI (`harness_cli.py`)

Точка входа: `.agents/skills/harness-router/children/harness-core/scripts/harness_cli.py`.

### 5.1. Команды

| Команда | Назначение | Ключевые флаги |
|---|---|---|
| `doctor` | Диагностика готовности среды, MCP, портов, git | `--root`, `--json` |
| `setup` | Мастер настройки проекта (MCP, MySQL, порты, git) | `--root`, `--yes`, `--php-container`, `--mysql`, `--serena-port`, `--web-port` |
| `sync` | Синхронизация проекций по `environments.json` | `--root`, `--dry-run`, `--yes`, `--mirror`, `--env <id>` |
| `export` | Перенос kit в целевой проект с этапом 0 | `--target`, `--profile`, `--yes`, `--skip-preflight`, `--include-docs` |
| `verify` | Проверка инвариантов паритета и манифестов | `--root`, `--check-freshness` |
| `mcp-audit` | Инвентаризация серверов, использования и портов | `--root`, `--check-listeners` |

### 5.2. Контракт кодов возврата
- `0`: успех, операция завершена, проверки пройдены.
- `1`: отказ пользователя (отмена перезаписи на этапе 0), проверка не прошла, предупреждения линтера в строгом режиме.
- `2`: ошибка конфигурации (невалидный JSON, отсутствующий путь, неизвестная среда).

---

## 6. Пакеты работ (Work Packages WP0–WP10)

### WP0. Заморозка контрактов и создание каркаса скилов
- **Цель:** подготовить структуру каталогов и файлов манифестов без нарушения существующего пайплайна.
- **Действия:**
  1. Создать `.agents/skills/harness-router/` со всеми подкаталогами (`scripts/lib`, `scripts/adapters`, `assets`, `references`, `tests`, `children`).
  2. Записать `assets/environments.json` и `assets/kit.json`.
  3. Создать каркасы дочерних скилов `project-setup`, `new-project`, `environment-sync`, `mcp-audit`, `mirror`, `index`.
  4. Создать `.agents/skills/task-router/` с дочерними `jira`, `leantime`, `kaiten`, `analytics`.
  5. Проверить `validate_skills.py`.
- **Зависимости:** нет.
- **Приемка:** 0 ошибок в `validate_skills.py`, структура видна в `harness-mirror`.

### WP1. Разработка общей библиотеки `scripts/lib/`
- **Цель:** изолировать общую логику путей, портов, манифестов и MCP.
- **Действия:**
  1. `lib/config.py`: функции `load_environments()`, `load_kit()`, `validate()`.
  2. `lib/manifest.py`: функции `build_manifest()`, `compare_manifests()`, вычисление SHA256 и быстрая сверка по mtime/size.
  3. `lib/ports.py`: функции `port_free()`, `first_free()`, `serena_owner()`, `sibling_ports()`.
  4. `lib/mcp.py`: загрузка канона, нормализация `alwaysAllow`/`trust`, парсинг env, маскирование токенов.
  5. `lib/report.py`: унифицированные тайминги, шаги, статусы `OK/WARN`.
  6. Написать unit-тесты в `tests/test_*.py`.
- **Зависимости:** WP0.
- **Приемка:** 100% прохождение unit-тестов `pytest` / `unittest`.

### WP2. Реализация адаптеров сред и команды `sync`
- **Цель:** заменить скрипты `generate-*.py` на модульные адаптеры `adapters/*.py`.
- **Действия:**
  1. `adapters/cursor.py`: генерация `.cursor/rules/*.mdc` и `.cursor/mcp.json`.
  2. `adapters/codex.py`: генерация `.codex/rules/*.md`, зеркалирование `.codex/skills`, генерация `.codex/config.toml`.
  3. `adapters/kilo.py`: генерация `.kilo/rules/*.md`, генерация `.kilo/kilo.jsonc`.
  4. `adapters/qoder.py`: генерация `.qoder/rules/*.md` с триггерами, зеркалирование `.qoder/skills`, генерация `.qoder/settings.json`.
  5. `adapters/qwen.py`: генерация `.qwen/rules/*.md` с `paths:`, выделение model-decision правил в `rule-*` скилы, генерация `.qwen/settings.json`.
  6. `adapters/agents.py`: генерация `.agents/rules/*.md`.
  7. Реализовать `harness_cli.py sync` с поддержкой `--dry-run` (вывод детального списка заменяемых и добавляемых файлов), подтверждением и флагом `--yes`.
  8. Заменить тело `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` на вызов `python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py sync "$@"`.
- **Зависимости:** WP1.
- **Приемка:** побайтовый паритет со старыми генераторами; `sync --dry-run` ничего не меняет; синк идемпотентен.

### WP3. Реализация команды `export` (перенос в проект)
- **Цель:** перенести PowerShell-логику ребейза в единый контур управления.
- **Действия:**
  1. Перенести `rebase_project.ps1`, `rebase_project_gi.ps1`, `copy-dsh-kit.ps1` в `harness-router/children/new-project/scripts/`.
  2. Связать этап 0 с манифестом из `lib/manifest.py` (вывод 30 первых перезаписываемых файлов, запрос `y/N`, флаг `-Yes`).
  3. Связать выбор порта Serena с `lib/ports.py`.
  4. Обеспечить чтение исключений и копируемых путей из `assets/kit.json`.
  5. Реализовать `harness_cli.py export` как обертку над PowerShell-движком с единым интерфейсом.
  6. Оставить в `.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1` совместимый forwarder.
- **Зависимости:** WP1, WP2.
- **Приемка:** успешный тестовый экспорт в пустой каталог и в каталог с существующим проектом; проверка отказа по `N`.

### WP4. Реализация `setup` и `doctor` (настройка проекта)
- **Цель:** перенести логику онбординга в скил `harness-router/children/project-setup`.
- **Действия:**
  1. Переместить `onboard-project.py` в `children/project-setup/scripts/`.
  2. Реализовать `harness_cli.py doctor` (проверка MCP, индексов, портов, git-исключений).
  3. Реализовать `harness_cli.py setup` (диалоговый мастер с флагами `--php-container`, `--mysql`, `--serena-port`, `--web-port`).
  4. Оставить в `.agents/skills/harness-router/children/project-setup/scripts/onboard-project.py` forwarder.
- **Зависимости:** WP1, WP2.
- **Приемка:** `harness_cli.py doctor` корректно рапортует состояние; `setup --yes` выполняет полную настройку без зависаний.

### WP5. Реализация подсистемы `mcp-audit`
- **Цель:** перенести скрипты проверки и аудита MCP серверов в `children/mcp-audit`.
- **Действия:**
  1. Перенести `test-mcp-servers.mjs` из `.cursor/scripts/` в `children/mcp-audit/scripts/`.
  2. Перенести `verify_mcp_views.py` из `.doc/skil_data/harness-core/` в `children/mcp-audit/scripts/`.
  3. Написать `scan-usage.py`: статический поиск упоминаний серверов в конфигах, правилах `.cursor/rules/mcp/*.mdc`, скилах и документации.
  4. Интегрировать команду `harness_cli.py mcp-audit`.
- **Зависимости:** WP1.
- **Приемка:** команда `mcp-audit` выводит полную матрицу активности MCP-серверов по всем 6 средам.

### WP6. Управление задачами (`task-router`) и переименование `task-report`
- **Цель:** перенести скрипты трекеров задач из `.doc/` и завершить ребрендинг отчета.
- **Действия:**
  1. Перенести код из `.doc/skil_data/jira/` (`server.php`, `export_task.py`, `diag-auth.php`) в `.agents/skills/task-router/children/jira/scripts/`.
  2. Обновить вызов сервера `jira-task` в `.cursor/mcp.json` на новый путь скрипта.
  3. Перенести скрипты Leantime из `.doc/skil_data/leantime/` (`rpc.sh`, `launch.sh`) в `task-router/children/leantime/scripts/`.
  4. Перенести код аналитики задач из `.doc/skil_data/analytics/lib/*.py` в `task-router/children/analytics/scripts/`.
  5. Переименовать скил `.agents/skills/jira-report` в `.agents/skills/task-router/children/reporting-router/children/task-report`:
     - обновить `name: task-report` в `SKILL.md`;
     - сохранить старый триггер `jira-report` в `description` на 1 релиз;
     - обновить `skill.json` и `README.md`;
     - обновить ссылки в `bitbucket-tasks.mdc`, `task-doc.mdc`, `text-style.mdc`.
  6. Обновить пути вызовов в `gototask`, `task-diff`, `task-intake`, `task-doc`.
- **Зависимости:** WP1, WP2.
- **Приемка:** `export_task.py` и MCP `jira-task` функционируют; `task-report` вызывается по обоим триггерам; тесты скилов зеленые.

### WP7. Миграция инструментов из `.doc/` в независимые скилы
- **Цель:** перенести все оставшиеся скрипты из `.doc/` в соответствующие скилы.
- **Действия:**
  1. **page-content:** перенести код, фикстуры и тесты из `.doc/skil_data/page-content/` в `.agents/skills/page-content/{scripts,tests,assets}/`.
  2. **xmlriver:** перенести код и утилиты из `.doc/skil_data/xmlriver/` в `.agents/skills/xmlriver/{scripts,assets}/`. Обновить пути запуска MCP `xmlriver` и `xmlriver-ws`.
  3. **yadisk-screenshot:** перенести `yadisk-fetch.ps1` из `.doc/skil_data/yadisk-screenshot/` в `.agents/skills/yadisk-screenshot/scripts/`. Удалить локальный кеш картинок `imd/`.
  4. **serpanalise-report:** перенести библиотеки и раннеры из `.doc/skil_data/serpanalise-report/` в `.agents/skills/serpanalise-report/{scripts,tests}/`.
  5. **business-analyst:** перенести скрипты из `.doc/skil_data/business-analyst/scripts/` и тесты в `.agents/skills/business-analyst/{scripts,tests}/`.
  6. **project-doc & doc-verify:** распределить скрипты из `.doc/docscripts/`:
     - в `project-doc/scripts/`: `map-project.ps1`, `build-tasks-index.ps1`, `validate-docs.ps1`, `audit-docs.ps1`, `sync-docs.ps1`, `task-identity.py`.
     - в `doc-verify/scripts/`: `get-verify-batch.ps1`, `mark-verify-done.ps1`, `find-related-tasks.ps1`.
  7. **task-doc:** перенести `jsondoc.py` и модули из `.doc/skil_data/task-doc/` в `.agents/skills/documentation-router/children/task-doc/scripts/`.
  8. **test-task & browser-verify:**
     - перенести скрипты из `.doc/qa/scripts/` (`task-test.sh`, `gates.py`, `lib.sh`) в `test-task/scripts/`.
     - перенести скрипты из `.tools/codeception/scripts/` (`start-chromedriver-wsl.sh`, `chromedriver-host-relay.py`, `dev-*.php`) в `browser-verify/scripts/`.
     - перенести `build-testanalyze.*` из `.doc/skil_data/test-task/testanalyze/` в `test-task/scripts/`.
  9. **seoq (новый скил):** создать скил `.agents/skills/seoq/`, перенести скрипты из `.doc/skil_data/seoq/`.
  10. Оставить forwarder-файлы в `.doc/` на 1 релиз.
- **Зависимости:** WP0, WP1.
- **Приемка:** все скрипты перенесены; в манифестах скилов `skill.json` заполнены секции `scripts` и `tests`; запуск тестов по каждому скилу успешен.

### WP8. Документация, правила и перелинковка
- **Цель:** синхронизировать текстовые документы, архитектурные гайды и правила агентов с новой топологией.
- **Действия:**
  1. Обновить `.doc/harnes/index.md`, `.agents/skills/`, `AGENTS.md`.
  2. Обновить правила `.cursor/rules/*.mdc` (убрать старые пути `.doc/...` и `.cursor/scripts/...`, заменить на `.agents/skills/...`).
  3. Обновить документы серверов `.doc/harnes/mcp/*.md`.
  4. Обновить документацию по переносу `.doc/harnes/state/13-agent-migration.md`, `14-project-migration.md`, `15-mcp-stack.md`.
  5. Запустить `check-links.py`, `validate_rules.py`, `validate_docs.py`.
- **Зависимости:** WP2–WP7.
- **Приемка:** 0 битых ссылок; 0 ошибок валидации правил.

### WP9. Очистка устаревших артефактов и изоляция состояния
- **Цель:** удалить legacy и мусор из `.doc/`.
- **Действия:**
  1. Удалить мусорные каталоги: `.doc/temp`, `.doc/tmp`, `.doc/_backup_harness`, `.doc/.backup`.
  2. Удалить legacy-сервер `.doc/.bitbucket` (функционал заменен на Jira / GitVerse).
  3. Создать каталог `.doc/skil_data/` и переместить туда служебные файлы:
     - `.doc/skil_data/rebase-mcp-backup/`
     - `.doc/skil_data/parity-report.json`
     - `.doc/skil_data/onboard-report.json`
     - `.doc/skil_data/onboard-report.md`
  4. Проверить, что в `.doc/` из программных компонентов присутствует исключительно `.doc/web/`.
- **Зависимости:** WP7, WP8.
- **Приемка:** объем `.doc/` уменьшился; в `.doc/` нет сторонних `.py`/`.ps1`/`.sh` файлов.

### WP10. Финальная верификация и стабилизация
- **Цель:** сквозной контроль качества системы.
- **Действия:**
  1. Выполнить `harness_cli.py doctor`.
  2. Выполнить `harness_cli.py sync --dry-run` и `sync --yes`.
  3. Выполнить экспорт во временный каталог `/tmp/test-harness-v2` с проверкой этапа 0.
  4. В целевом каталоге выполнить `harness_cli.py setup --yes` и проверить запуск MCP.
  5. Удалить временные forwarder-шимы.
  6. Собрать граф харнеса: `python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py scan && harness_mirror.py check`.
- **Зависимости:** WP0–WP9.
- **Приемка:** граф валиден, инварианты соблюдены, синк зеленый во всех 6 средах.

---

## 6.4. Статус реализации на 2026-11-04

| WP | Статус | Что сделано |
|---|---|---|
| WP0 | готово | созданы `harness-router`, `task-router`, `documentation-router`, менеджеры тестов и отчетов, конфиги |
| WP1 | готово | библиотека `scripts/lib`, 6 unit-тестов |
| WP2 | частично | `harness_cli.py` и `sync --dry-run`; синк пока вызывает старый `sync-agent-views.sh` |
| WP3 | готово | `rebase_project.ps1`, `rebase_project_gi.ps1`, `copy-dsh-kit.ps1` перенесены в `children/new-project/scripts`; старые пути - forwarder |
| WP4 | готово | `onboard-project.py` в `children/project-setup/scripts` |
| WP5 | готово | `test-mcp-servers.mjs`, `verify_mcp_views.py`, `scan-usage.py` в `children/mcp-audit/scripts` |
| WP6 | готово | `jira-report` переименован в `task-report`; Jira, Leantime и analytics перенесены, `kaiten` docs-only |
| WP7 | готово | все инструменты перенесены в скилы; в `.doc` остались только веб-панель и продуктовые тесты Codeception |
| WP8 | готово | активные правила, скилы и документация переписаны на новые пути; ссылки проверены |
| WP9 | готово | удалены `.temp`, `.backup`, `_backup_harness`, `.bitbucket` и старые шимы |
| WP10 | готово | синк, skill-валидация, doctor, линтер графа и тесты проходят |

Проверки: 16 корневых скилов, 0 ошибок; `test_sync_views.py` 11/11; синк PASS по шести гейтам; `harness_mirror.py check` PASS, 1389 узлов; `harness_cli.py doctor` PASS; экспорт через новый движок PASS.

---

## 7. Порядок исполнения и контрольные точки

```
[WP0] Создание структуры и схем JSON
  ↓
[WP1] Библиотека lib/*.py + unit-тесты
  ↓
[WP2] Адаптеры сред + CLI sync
  ↓
[WP5] Подсистема mcp-audit (контроль MCP перед переносом кода)
  ↓
[WP3] Экспорт kit в new-project
  ↓
[WP4] Настройка проекта project-setup
  ↓
[WP6] task-router (Jira, Leantime, Analytics, task-report)
  ↓
[WP7] Перенос инструментов (page-content, xmlriver, test-task, docscripts и др.)
  ↓
[WP8] Документация, правила, перелинковка
  ↓
[WP9] Очистка мусора и изоляция .doc/skil_data/
  ↓
[WP10] Финальная приемка и сборка графа
```

---

## 8. Детальная карта миграции файлов из `.doc/`

| Исходный путь в `.doc/` | Целевой путь в `.agents/skills/` | Дополнительные действия по стандартам харнеса |
|---|---|---|
| `.content-extractor/` | `page-content/` | Скрипты в `scripts/`, тесты в `tests/`, html-фикстуры в `assets/`. Venv удалить |
| `.xml-river/` | `xmlriver/` | Скрипты генерации конфигов и пакетных запросов в `scripts/`. Конфиги регионов в `assets/`. MCP-серверы `xmlriver` и `xmlriver-ws` направить на новый путь |
| `.mcpyandexscreen/yadisk-fetch.ps1` | `yadisk-screenshot/scripts/` | Исключить кеш `imd/`. Скрипт вызывается из `SKILL.md` полным путем |
| `.jira/` (`server.php`, `export_task.py`) | `task-router/children/jira/scripts/` | MCP-сервер `jira-task` в `.cursor/mcp.json` перенаправить на `task-router/children/jira/scripts/server.php` |
| `.seoq/sigmaplaza/*.py` | `seoq/scripts/` | Новый скил `seoq` для комплексного анализа доменов и поисковой выдачи |
| `serpanalise/lib/*.py` | `serpanalise-report/scripts/` | Скрипты генерации отчетов репутации. Тесты в `tests/`. Входные CSV не переносить |
| `buisnes_analis/scripts/*.py` | `business-analyst/scripts/` | Скрипты извлечения правил. Тесты в `tests/`. `registry.json` и `work/` оставить в данных `.doc/` |
| `codeception/scripts/*.{sh,php,py}` | `browser-verify/scripts/` и `test-task/scripts/` | Chromedriver relay и запуск headless/headed браузера. Vendor и логи удалить |
| `docscripts/map-project.ps1` | `project-doc/scripts/` | Скрипты построения карты проекта, аудита и валидации структуры документов |
| `docscripts/get-verify-batch.ps1` | `doc-verify/scripts/` | Скрипты пакетной сверки документации с кодовой базой |
| `jsondoc_scripts/jsondoc.py` | `task-doc/scripts/` | Ядро JSONdoc. Модули `contract`, `store`, `review` перенести в `scripts/jsondoc/`. `runs/` в `.state/` |
| `leantime/rpc.sh`, `launch.sh` | `task-router/children/leantime/scripts/` | Скрипты вызова RPC и старта MCP-сервера Leantime |
| `qa/scripts/gates.py`, `task-test.sh` | `test-task/scripts/` | Машинные гейты G1–G15 и раннер тестов задачи. Флоу `qa/flows/` перенести в `references/` |
| `synh_harnes/*.py`, `*.sh` | `harness-router/scripts/` | Генераторы и адаптеры сред. Тесты перенести в `harness-router/tests/` |
| `task-analytics/lib/*.py` | `task-router/children/analytics/scripts/` | Скрипты аналитики и compliance задач. Шаблоны отчетов в `assets/` |
| `testanalyze/scripts/*.{py,sh}` | `test-task/scripts/` | Утилиты анализа покрытия тестами |
| `rebase_project.ps1` | `harness-router/children/new-project/scripts/` | Движок экспорта kit в новые проекты |
| `rebase_project_gi.ps1` | `harness-router/children/new-project/scripts/` | Модуль инъекции безопасных git-исключений |

---

## 9. План тестирования

1. **Unit-тестирование библиотеки (`pytest`):**
   - парсинг и валидация схем `environments.json` и `kit.json`;
   - корректность генерации списков портов и обнаружения владельцев процессов через `/proc`;
   - нормализация MCP-серверов (обработка `envFile`, `httpUrl`, `disabledTools`, `trust`).
2. **Snapshot-тестирование адаптеров:**
   - генерация проекций для Cursor, Codex, Kilo, Qoder, Qwen, Agents;
   - проверка побайтового совпадения (body parity) с эталонными снимками.
3. **CLI интеграционное тестирование:**
   - проверка кодов возврата `0`, `1`, `2` для всех подкоманд;
   - проверка работы флагов `--dry-run` (гарантия отсутствия записи на диск) и `--yes`.
4. **End-to-End тестирование экспорта:**
   - прогон экспорта во временный каталог с этапом 0 и эмуляцией ответа `N` (отмена);
   - прогон с флагом `-Yes`; проверка выполнения must-check аудита.
5. **Сквозная валидация структуры скилов:**
   - `python3 .agents/skills/harness-router/children/improvement/scripts/validate_skills.py` (0 ошибок);
   - `python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py` (0 ошибок);
   - сборка и проверка графа `harness-mirror`: `harness_mirror.py check`.

---

## 10. Критерии приёмки (Definition of Done)

- [ ] Все пакеты WP0–WP10 выполнены в строгом порядке зависимостей.
- [ ] Добавление новой среды разработки осуществляется редактированием исключительно `environments.json` без вмешательства в код других скриптов.
- [ ] Добавление или исключение каталога kit осуществляется редактированием исключительно `kit.json`.
- [ ] В каталоге `.doc/` из исполняемых программ присутствует **только `.doc/web/`**.
- [ ] Все служебные утилиты перенесены в соответствующие скилы и задекларированы в их манифестах `skill.json`.
- [ ] Нет скриптов-сирот: каждый исполняемый файл имеет скил-владелец и документацию.
- [ ] Команда `harness_cli.py sync --dry-run` наглядно выводит дельту изменений без мутации файлов.
- [ ] Команда `harness_cli.py export` перед копированием проводит аудит целевой папки на этапе 0 и требует явного подтверждения.
- [ ] Скил `jira-report` переименован в `task-report`, сохранен триггер обратной совместимости.
- [ ] Локальное состояние, кеши картинок, venv и временные дампы не попадают в git и kit-экспорт.
- [ ] Проверки `validate_skills.py`, `check-links.py` и `harness_mirror.py check` завершаются со статусом `passed`.

---

## 11. Риски и план отката

| Риск | Вероятность | Влияние | Превентивная мера | План отката |
|---|---|---|---|---|
| Поломка путей вызова MCP при перемещении скриптов | Средняя | Высокое | Тестирование `mcp-audit` и smoke-тестов на каждом WP | Временное сохранение forwarder-файлов на старых путях в `.doc/` |
| Сбой сборки проекций для нестандартных сред (Qwen, Qoder) | Низкая | Высокое | Тестирование через `verify_mcp_views.py` и parity тесты | Откат коммита соответствующего адаптера |
| Случайное удаление пользовательских данных при очистке `.doc/` | Низкая | Критическое | Четкое разделение в `kit.json`: состояние/задачи/архитектура изолированы | Восстановление из `.doc/skil_data/` и git-истории |
| Рассинхронизация ссылок в правилах `.cursor/rules/*.mdc` | Средняя | Среднее | Пакет WP8 автоматизирует поиск и замену ссылок | Прогон `validate_rules.py` перед мержем каждого WP |

---

## 12. Связи

- [Миграция между агентами](../state/13-agent-migration.md) — канон сред, текущий порядок синхронизации.
- [Миграция между проектами](../state/14-project-migration.md) — правила и инварианты экспорта kit.
- [Формат скила](../skill-format.md) — стандарт структуры скилов, frontmatter и `skill.json`.
- [Канон скилов (.agents/skills/)](../../agents/skills/) — README.md в каждом скиле
- [Единый стандарт документации](../doc_rules.md) — регламент оформления `.doc/`.

---

## 13. Известные проблемы и ограничения

### П-1: Размазанные списки сред и путей
- Симптом: подключение среды (Qoder, Qwen) требует изменений в 4–5 независимых скриптах.
- Причина: отсутствие декларативного манифеста конфигурации.
- Решение: внедрение `environments.json` и `kit.json` в WP0–WP2.

### П-2: Смешение исполняемого кода, данных и состояния
- Симптом: раздутый размер репозитория (240Мб в `jsondoc_scripts`, 116Мб в `codeception`), засорение `.doc/`.
- Причина: историческое размещение служебных утилит в `.doc/`.
- Решение: перемещение скриптов в скилы (WP7), изоляция состояния в `.doc/skil_data/` (WP9).

### П-3: Дублирование ответственности в отчетах трекера
- Симптом: путаница между экспортом задач, формированием комментария и генерацией HTML-отчета.
- Причина: имя `jira-report` ассоциировалось только с одним трекером.
- Решение: переименование в `task-report` (WP6), экспорт закреплен за `task-router/children/jira`.

### П-4: Node id collision у дочерних скилов в harness-mirror
- Симптом: `doc:harness-router-readme` и `config:harness-router-skill` совпадали у родителя и ребенка.
- Причина: `slug_of` не учитывал путь `children/<name>` для README и `skill.json`.
- Решение: slug для файлов внутри `children/` включает `children/<name>`; проверка `harness_mirror.py check` проходит.

---

## 14. История изменений

- 2026-11-04: создан документ требований ref22 для рефакторинга миграции и настройки харнеса.
- 2026-11-04: добавлен аудит `.doc`; все скрипты выносятся в скилы, кроме панели `.doc/web/`.
- 2026-11-04: зафиксирована иерархия `harness-router` и `task-router`, добавлены схемы и контракты.
- 2026-11-04: `jira-report` переименован в `task-report`; `kaiten` переведен в статус docs-only дочернего скила.
- 2026-11-04: исключен постоянный валидатор `.doc`; структура организуется однократно при рефакторинге.
- 2026-11-04: документ переработан в исчерпывающий детальный архитектурный план: добавлены WP0–WP10, результаты сканирования всех 32 каталогов `.doc/`, инвентаризация 24 сирот по линтеру `harness-mirror`, пофайловая карта миграции и критерии готовности (DoD).
- 2026-11-04: при реализации WP0 исправлен `harness_mirror.py`: node id дочерних скилов теперь включает `children/<name>`; `scan --include-mirrors` и `check` проходят.
- 2026-11-04: реализованы WP0-WP5 и часть WP6: каркас скилов, библиотека, CLI, onboarding, mcp-audit, движок экспорта, Jira и Leantime; WP7-WP10 остаются.
- 2026-11-04: WP6 закрыт, WP7 частично: перенесены Jira, Leantime, analytics, seoq; остальные инструменты ещё в `.doc`.
- 2026-11-04: WP7 продвинут: task-analytics, seoq, testanalyze перенесены; остались крупные каталоги `.content-extractor`, `.xml-river`, `jsondoc_scripts`, `codeception`, `qa`, `serpanalise`, `buisnes_analis`, `docscripts`.
- 2026-11-04: `docscripts` перенесены в `project-doc` и `doc-verify`, старые пути оставлены forwarder-шимами; активные скилы переведены на новые пути.
- 2026-11-04: перенесены `synh_harnes`, `docscripts`, `qa`, `codeception/scripts`, `jsondoc_scripts`, `buisnes_analis`; осталось три крупных data-heavy инструмента: `.content-extractor`, `.xml-river`, `serpanalise`.
- 2026-11-04: очищены скриншоты `.content-extractor/src/content_extractor/screen`: удалено 354 PNG, освобождено около 644 МБ; код и venv пока остаются из-за editable-установки.
- 2026-11-04: удалены forwarder-шимы и старые скилы `harness-setup`/`harness-migration`; ссылки в правилах, скилах и документации переписаны на новые пути; `validate_skills`, синк и mirror проходят.
- 2026-11-04: завершены WP7-WP10: перенесены `.content-extractor`, `.xml-river`, `serpanalise`; удалены legacy и шимы; активные пути обновлены; синк, skill-валидация, doctor, mirror и docs-links проходят.
- 2026-11-04: остаточные данные и venv перенесены в `.doc/skil_data/*`; в корне `.doc` остались только документация, `.doc/web`, `.doc/qa`, `.doc/codeception` и `.doc/tasks`.
- 2026-11-04: данные скилов перенесены в `.doc/skil_data/{skill}/`; правило S11 и D10 добавлены в документацию харнеса.
- 2026-11-04: сгенерированы документы для 312 скриптов и карточки всех скилов; `validate_docs.py` проходит с 0 ошибок.
- 2026-11-04: данные скилов перенесены в `.doc/skil_data/{skill}/`; закреплены S11 в `skill-format.md` и D10/7.1 в `component-docs.md`.
- 2026-11-04: Jira MCP восстановлен после restart контейнера; page-content тесты 31/31 в Linux venv; архитектурные документы пересобраны с новыми путями.
- 2026-11-04: исправлены probe-проверки MCP: codegraph больше не требует `app/`, serena проверяет `OrderService`; полный MCP smoke завершается с exit 0.
- 2026-11-04: `harness-mirror` и `harness-index` перенесены в `harness-router/children` как `mirror` и `index`; пустые дубли удалены, родитель использует существующие скилы.
- 2026-11-04: документы скриптов уточнены из исходников, MCP smoke exit 0, данные скилов лежат в `.doc/skil_data`.
- 2026-11-04: task-скилы перенесены в `task-router/children`: gototask, task-diff, task-doc, task-intake, task-code-review, task-change-report, task-report, prepare-task-test, test-task, git-task-blame; родитель маршрутизирует их по запросам.
- 2026-11-04: в план добавлены task-скилы `gototask`, `task-diff`, `task-doc`, `task-intake`, `task-code-review`, `task-change-report`, `task-report`, `prepare-task-test`, `test-task`, `git-task-blame`; правило глубины снято, маршрутизация родителя обязательна.
- 2026-11-04: добавлены менеджеры `testing-router` и `reporting-router` под `task-router`, `documentation-router` в корень; `harness-improvement` стал дочерним `improvement` у `harness-router`.
