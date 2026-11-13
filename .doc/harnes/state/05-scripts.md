# Скрипты контуров

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [../index.md, ./07-workflows.md, ../doc_rules.md]
tags: [harness, scripts]
-->

---

## Суть

Карта скриптов по владельцам: системные утилиты в `.tools/scripts`, лаунчеры MCP и
инструменты в `scripts/` своих скилов, очереди документации и JSONdoc в скилах
`documentation-router`, генератор сред и его проверки в скиле `environment-sync`.
Принцип один: скрипт дает структуру, агент не сканирует файлы вручную. Здесь
назначение, входы и артефакты. Правила размещения скриптов: [dirtree.md](../dirtree.md),
раздел 6, и [26-tools.md](./26-tools.md). Текст скриптов - в самих файлах.

---

## 1. Скрипты MCP и инструментов в скилах

Лаунчер и инструмент лежат в `scripts/` скила-владельца. Документ каждого скрипта
лежит в `{skill}/docs/scripts/`, проверка - `doc_script.py --audit`.

| Скрипт | Владелец | Роль |
|---|---|---|
| `codebase-memory-mcp-launch.sh`, `.cmd`, `codebase-memory-mcp-ui.sh` | `codebase-memory-mcp` | Запуск CBM для Linux, Windows и UI-режима |
| `codegraph-mcp.sh` | `codegraph` | Запуск CodeGraph MCP: `codegraph serve --mcp --path <корень>`, поиск CLI в `PATH` и nvm |
| `codegraph-ui.sh` | `codegraph` | Локальный просмотрщик CodeGraph: `CODEGRAPH_UI=1`, `--read-only`, порт 4747, `--open` и `--port` |
| `codeprism-mcp.sh` | `codeprism` | stdio-мост к общему HTTP CodePrism; `CODEPRISM_TARGET` проверяет корень. Детали: [codeprism.md](../../../.agents/skills/codeprism/docs/mcp/codeprism.md) |
| `codeprism_serve.py` | `codeprism` | MCP-сервер с живым наблюдателем файлов: сохранение обновляет граф за 1-2 с |
| `test_codeprism_mcp.py`, `test_codeprism_serve.py` | `codeprism` | Тесты моста и обёртки, лежат в `tests/` скила |
| `graphiti-stack.sh` | `graphiti` | FalkorDB и Graphiti MCP через Docker Compose, команды `up`, `down`, `status`, `verify` |
| `jdocmunch-mcp.sh` | `jdocmunch` | Запуск jDocMunch MCP: корпус `architecture harnes tasks web`, режимы `--index`, `--repo`, `--status`. Детали: [jdocmunch.md](../../../.agents/skills/jdocmunch/docs/mcp/jdocmunch.md) |
| `serena-shared.sh` | `serena` | Запуск serena на проект: порт из хеша корня, owner-файл, `SERENA_PORT` для переопределения |
| `phpstan-docker.sh` | `phpstan-mcp` | Запуск phar PHPStan в образе dev-стенда PHP 7.4 (`PHPSTAN_DOCKER_IMAGE`) |
| `phpstan-task.sh` | `phpstan-mcp` | PHPStan только по PHP-файлам задачи из `.doc/tasks/{N}/diff.files.md` и git |

Свой MCP-сервер: `.tools/mcp-servers/php-toolchain/` (режимы phpstan и php-deps).

---

## 1a. Системные утилиты `.tools/scripts` (14 файлов)

Полный инвентарь `.tools` с окружениями, портами и правилами описан в
[26-tools.md](./26-tools.md).

| Скрипт | Роль |
|---|---|
| `mcp-shared-server.sh` | Общий HTTP-сервер из stdio MCP через `mcp-proxy` |
| `wait-for-ports.sh` | Ожидание TCP-портов для `ExecStartPre`; используется unit `dsh-web.service` |
| `node-mcp.sh`, `.cmd` | Обертка node для php-toolchain MCP |
| `php-docker.sh`, `.cmd`, `.ps1`, `.js` | Выполнение PHP внутри контейнера dev-стенда |
| `mysql-mcp-proxy.mjs` | Прокси mysql MCP: порт стенда 8031 в listen 3306 |
| `run-with-mcp-env.sh` | Подстановка `mcp.env` перед запуском команды, единая обертка Kilo и Codex |
| `multi-search.sh`, `.ps1` | Пакетный поиск N паттернов одним проходом, JSON-lines. Правило `batch-calls`. Детали: [12-batch-calls.md](./12-batch-calls.md) |
| `multi-exec.sh`, `.ps1` | Пакетный запуск N команд и чтений, JSON-lines и `content_hash`. Правило `batch-calls`. Детали: [12-batch-calls.md](./12-batch-calls.md) |

---

## 2. `.agents/skills/documentation-router/children/project-doc/scripts/` (20 скриптов)

| Скрипт | Роль | Артефакт |
|---|---|---|
| `_lib.ps1` | Общая библиотека: мета документов, реестр, заголовки | - |
| `map-project.ps1` | Карта проекта, вызывает генераторы | `_map/tree.txt`, `hot-files.txt` |
| `generate-file-registry.ps1` | Реестр всех файлов со статусами | `architecture/_map/file-registry.tsv` |
| `generate-doc-index.ps1` | TSV-индекс arch-документов | `architecture/_map/doc-index.tsv` |
| `get-indexing-batch.ps1` | Батч индексации 15 файлов (CSS/TPL/SQL до 30) с приоритетами | `current-batch.txt` |
| `mark-noise.ps1` | Пометка плагинов и минифицированных как noise | `file-registry.tsv` |
| `get-verify-batch.ps1`, `mark-verify-done.ps1` | Очередь сверки doc-verify: выдать батч, закрыть шаг | `architecture/_map/verify-registry.tsv` |
| `audit-docs.ps1` | Аудит gaps и устаревших документов, вывод в stdout | - |
| `validate-docs.ps1` | Валидация meta, секций, дат | ошибки в stdout |
| `sync-docs.ps1` | Документы, устаревшие после правок кода (git log против updated) | список |
| `build-tasks-index.ps1` | Индекс задач и файл-к-задачам, флаг `-AlsoTsv` | `tasks/index.md` плюс `_map/file-to-tasks.tsv` |
| `find-related-tasks.ps1` | Поиск задач по файлам и документам, score, флаг `-Json` | кандидаты для P0.5a и V6 |
| `check-links.py` | Проверка md-ссылок и якорей в документации | список битых ссылок |
| `task-identity.py` | Гейт личности задачи: заголовок task.md, metadata.title, ключ трекера, номер ветки | exit 0 / 2 |
| `export-rebase-project.ps1` | Обертка экспорта переноса kit | zip-профиль FULL или CORE |
| `_batch-ai-links.py` | Массовая простановка AI-блоков в arch-документы | arch `*.md` |
| `_fix_indexed_files_order.py`, `_restore_cicd_from_transcript.py` | Разовые recovery-утилиты | - |

Ключевые контракты:

- `build-tasks-index.ps1 -AlsoTsv` обязателен в конце task-doc Режим B при смене
файлов. Без свежего индекса doc-verify и поиск "кто трогал файл" устаревают.
- `find-related-tasks.ps1 -Doc {name} -Json -Limit 12`, порог score>=20 для P0.5a
и V6. Внутри fast path через `jsondoc.py related --profile legacy-v1` при наличии
arch JSON, иначе legacy скан. Скоринг не дублируется скилами.
- Очереди индексации и сверки (`current-batch.txt`, `verify-registry.tsv`) живут
в `_map`, не пересоздаются из `code_files`.

---

## 3. `.agents/skills/task-router/children/testing-router/children/test-task/scripts/` (28 файлов, без `__pycache__` и `*.pyc`)

Ядро прогона:

| Скрипт | Роль |
|---|---|
| `task-test.sh` | Оркестратор: фазы preflight, unit, browser, all, finalize |
| `gates.py` | Гейты готовности G0-G13, машинный вердикт |
| `check-tests.sh` | Реестр и селекторы, загрузка Cest |
| `preflight.sh` | Предпроверки перед прогоном |
| `run-phpunit.py` | Запуск PHPUnit |
| `make-report.py`, `make-verdict.py` | Отчет по `tests.md` 8 и `verdict.json` |
| `test-batch.sh` | Пакетный прогон нескольких задач |
| `record-history.py`, `compare-runs.py` | История прогонов и сравнение |

Остальные: `branch-audit.py` (читает task.json artifacts и stage-планы),
`check-ac-matrix.py`, `check-selectors.py`, `check-tests-load.php`,
`collect-data-test.py`, `db-isolation.py`, `disposable-db.sh`, `doctor.py`,
`harness-selftest.py`, `lib.sh`, `llm-review.py`, `migrate-task-tests.py`,
`new-task-test.py`, `qa-lint.py` (patch-фильтр, `slack=0`), `qa-manifest.py`,
`resolve-neighbors.py`, `static-on-diff.py` (`filter_to_patch`), `lib.sh`.

Канон тестирования: `tests.md` (корень harnes; чек-лист 7, отчет 8). Устройство QA: `.doc/qa/README.md`.
Ветки тестирования: `testaudit.md` (корень harnes) 9.

---

## 4. `.agents/skills/harness-router/children/environment-sync/scripts/` - генератор сред

| Файл | Роль |
|---|---|
| `sync-agent-views.sh` | Оркестратор: генераторы, копии, LF-нормализация, parity, freshness-гейт, шаг `rule-triggers` |
| `generate-agent-configs.py` | Codex и Kilo: правила, скилы, MCP, permissions fragment, `rules-index` |
| `generate-antigravity-rules.py` | Плоские правила `.agents/rules` с обязательным `trigger` |
| `generate-qoder-config.py` | `.qoder`: правила с `trigger`, скилы, `settings.json` |
| `generate-qwen-config.py` | `.qwen`: baseline и conditional правила, `rule-*` скилы, `settings.json` |
| `generate-dsh-config.py` | DSH patch и `DSH-RULES.md`, `--check` для гейта свежести |
| `generate-mcp-config.py` | MCP с раскрытием путей для Antigravity и Gemini |
| `rule_model.py` | Общий классификатор правил: `always`, `conditional`, `agent_requested`, `manual` |
| `verify_rule_triggers.py` | Гейт: сверяет вид каждого правила во всех шести средах |
| `verify_parity.py` | Сверка канона скилов, правил и MCP с представлениями сред, пишет `parity-report.json` |

Тесты лежат в `.agents/skills/harness-router/children/environment-sync/tests/`:
`test_sync_views.py`, `test_dsh_config.py`, `test_dsh_kit.py`.
Сгенерированные артефакты лежат в `.doc/skil_data/harness-core/`: `parity-report.json`,
`antigravity_mcp_config.windows-wsl.json`, `kit-manifest.json`. Нативный
`antigravity_mcp_config.json` лежит в `.doc/skil_data/harness-router/`. Артефакты
не правятся руками. `copy-dsh-kit.ps1` перенесён в
`.agents/skills/harness-router/children/new-project/scripts/`, план отчетной цепочки в
`.agents/skills/harness-router/children/environment-sync/references/report-workflow-plan.md`.

Запуск из корня репо:

```bash
./.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
```

---

## 5. Прочие контуры

| Каталог | Состав и роль |
|---|---|
| `.doc/skil_data/jira/` | `config.env` и `src/` для экспорта задач; транспорт `server.php` и скрипты лежат в `.agents/skills/task-router/children/jira/scripts/` |
| `.doc/.bitbucket/` | Legacy-аналог для Bitbucket, отключен |
| `.doc/skil_data/task-doc/` | Рабочие данные JSONdoc: `state/`, `work/`, `implementation/`. Движок `jsondoc.py`, модули и тесты лежат в `.agents/skills/documentation-router/children/task-doc/`. Детали: [06-jsondoc.md](./06-jsondoc.md) |
| `.doc/skil_data/yadisk-screenshot/` | Кеш скринов и README; скрипт перенесен в `.agents/skills/yadisk-screenshot/scripts/` |
| `.doc/task-analytics/out/` | Результаты анализа диалогов: `unassigned/`, `stats/`, `state/`. Код, конфиги и схемы лежат в `.agents/skills/task-router/children/analytics/`. Детали: [16-task-analytics.md](./16-task-analytics.md) |
| `.cursor/mcp-stack/` | `add-project.sh`, `add-serena.sh`, `verify.sh`, `export.sh`, `restore.sh` для общего MCP-стека |
| `.agents/skills/harness-router/children/improvement/scripts/` | Валидаторы и реестр: `validate_structure.py` (раскладка и хлам), `validate_docs.py`, `validate_skills.py`, `validate_rules.py`, `validate_registry.py`, `component_registry.json`. Запускаются гейтами `doctor` |
| `sourcegraph-local/` (корень репо) | Legacy SG-стек `:7080`, опционален. В каноне MCP `sourcegraph` выключен, агентский поиск идет через codegraph и `multi-search.sh` |

---

## Связи

- [Точка входа](../index.md) - карта каталога
- [JSONdoc](./06-jsondoc.md) - команды движка документации
- [Рабочие цепочки](./07-workflows.md) - где скрипты вызываются
- [Правила документации](../doc_rules.md) - очереди и реестры
- Индекс задач в проекте Target - продукт `build-tasks-index.ps1`

---

## История изменений

- 2026-11-11: каталоги `.doc/skil_data/analytics` и `.doc/skil_data/business-analyst` удалены как легаси; аналитика читается из `.agents/skills/task-router/children/analytics/` и пишет в `.doc/task-analytics/out/`; нативный MCP-артефакт Antigravity указан в `harness-router`.
- 2026-11-11: пул `.cursor/scripts` удалён. Лаунчеры MCP и инструменты перенесены в `scripts/` скилов, системные утилиты в `.tools/scripts`, `verify_parity.py` в `environment-sync`. Документы скриптов переехали в `{skill}/docs/scripts`, для `.tools` в `harness-core/docs/scripts/tools`. MCP-конфиг, sync, systemd units и реестр обновлены.
- 2026-11-11: php-toolchain перенесён в `.tools/mcp-servers`; `node-mcp.sh` запускает `server.js` по новому пути.
- 2026-11-07: уточнена роль `codeprism-mcp.sh`: мост подключается к общему серверу проекта и не запускает собственный индекс.
- 2026-11-09: список business-analyst scripts обновлён: добавлен `publish_transaction.py`, тесты перенесены в канонический `.agents/skills/business-analyst/tests/`.
- 2026-11-07: PHPStan использует образ основного стенда PHP 7.4; автосборка ограничена его локальным Dockerfile и не подменяет пользовательские теги.
- 2026-10-01: вынесено из `readmy.md` в `.doc/harnes/`
- 2026-10-02: добавлены `multi-search.sh`/`.ps1` и `multi-exec.sh`/`.ps1` (всего 16), детали в [12-batch-calls.md](./12-batch-calls.md)
- 2026-10-30: `.cursor/scripts` 21 (`mcp-shared-server.sh`, `wait-for-ports.sh`, ранее `php-docker.ps1`), добавлен `.cursor/mcp-stack/` (add-project, verify, export, restore)
- 2026-10-30: добавлен пул `.doc/skil_data/business-analyst/scripts` (14 скриптов, 9 тестов).
- 2026-10-29: factual audit: `.cursor/scripts` 18 (добавлены `graphify-mcp-serve.sh`, `serena-shared.sh`), docscripts 19 (добавлены `check-links.py`, `task-identity.py`)
- 2026-10-30: добавлен контур `.doc/skil_data/analytics/` (анализ `kilo.db`), см. [16-task-analytics.md](./16-task-analytics.md)
- 2026-11-01: `.cursor/scripts` 22, добавлен `jdocmunch-mcp.sh` (канон вместо kit в `.dsh/scripts`)
- 2026-11-02: сверка с диском: docscripts 20 файлов, business scripts 15, skills 25; счётчики в index, state/02 и state/05 приведены к факту
- 2026-11-02: `.cursor/scripts` 24, добавлены `codegraph-mcp.sh` и `codegraph-ui.sh`, скил `codegraph`
- 2026-11-02: `.cursor/scripts` 25, добавлен `codeprism-mcp.sh`, MCP `codeprism`; закрыты документы скриптов codegraph
- 2026-11-03: `.cursor/scripts` 26, добавлен `codeprism_serve.py`, живой наблюдатель индекса
- 2026-11-02: корпус `jdocmunch-mcp.sh` расширен каталогом `web`, документация панели `.doc/web/README.md` попала в индекс
- 2026-11-05: раздел генератора сред исправлен по факту: скрипты лежат в `.agents/skills/harness-router/children/environment-sync/scripts/`, добавлены `rule_model.py` и `verify_rule_triggers.py`, тесты и артефакты разнесены по каталогам, см. [23-rule-transfer-2026-11-05.md](./23-rule-transfer-2026-11-05.md)
