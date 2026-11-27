# Полный рефакторинг-аудит всех CLI-скриптов

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** **все CLI-скрипты харнеса** (без веб-панелей `.doc/web`/`.doc/web2`): структура, сложность, дублирование, тестирование, кодовые запахи, и **конкретный план рефакторинга** по каждому инструменту.
**Метод:** метрики кода (200 скриптов / 65 903 строки / 2 503 функции), кодовый скан дубликатов (Jaccard), анализ подкоманд, `py_compile`, оценка тест-покрытия.

---

## 0. Общая картина

| Показатель | Значение |
|---|---|
| CLI-скриптов (без веб) | **200** |
| Всего строк | **65 903** |
| Функций | **2 503** |
| Средняя длина скрипта | 329 строк |
| Зависимости | stdlib-only (PyYAML — опционально) |
| Прогон `py_compile` | **2 SyntaxError**: `jira/export_task.py`, `reporting/generate_report.py` |

**Тест-покрытие по кластерам:**

| Кластер | Скриптов | Тест-файлов | Оценка |
|---|---|---|---|
| documentation-router | 21 | 17 | ✅ Хорошее |
| environment-sync | 19 | 9 | ⚠️ Среднее |
| task-router | 19 | 11 | ⚠️ Среднее |
| todone | 38 | 6 | ⚠️ Модули не покрыты |
| improvement (validators) | 6 | 1 | ❌ Плохо |
| skill-auditor | 3 | 0 | ❌ Нет тестов |
| mirror | 2 | 1 | ⚠️ Немного |

**Главные проблемы (в порядке приоритета):**
1. **Дублирование функционала** (см. `audit-cli-duplication.md`) — 10 кластеров, 54 пары Jaccard>0.30.
2. **Гигантские монолитные модули** — `tdcore/autodoc.py` 5 899 Л, `harness_mirror.py` 2 713 Л, `static_audit.py` 2 648 Л.
3. **Неравномерное тестирование** — валидаторы и skill-auditor почти без тестов.
4. **2 SyntaxError** — два невыполняемых CLI.
5. **Разнородные конвенции** — argparse/envelope/exit-codes не едины.

---

## 1. Универсальные рефакторинги (apply ко всем)

### R-0.1. Вынести общие helpers в shared core
-environment-sync: 9 generatorов независимо `import argparse/json/re/pathlib/os/shutil` + `import rule_model` — **общая база есть (`rule_model.py`), но CLI-скaffolding дублируется**. Вынести общий render-ядро + argparse-скaffolding в `environment_sync/core.py`.

### R-0.2. Единые конвенции exit-codes и envelope
- Унифицировать коды выхода (`0 ok / 1 not found / 2 validation / 3 conflict / 4 recovery` — как в `jsondoc.py`, самый честный). Применить к validator-скриптам и environment-sync.

### R-0.3. Включить `py_compile` + базовые smoke-тесты в CI
- два SyntaxError (`export_task.py`, `generate_report.py`) — ни один CLI не запускается. Fix + CI gate.

---

## 2. Кластер A — environment-sync: **рефакторинг render-ядра** (ПРИОРИТЕТ 1, CRITICAL)

**Текущее состояние.** 19 скриптов, один из них — 9 `generate-*-config.py`, каждый рендерит canon→agent-view, каждый со 自己的 argparse/parse/write. `generate-agent-configs.py` (682 Л) — мастер-генератор. Три verify-скрипта.

**Проблемы:**
- 9 generatorов перекрывают общий render-ядро (Jaccard `qoder`↔`qwen` = 0.46).
- `generate-agent-configs.py` уже содержит то, что отдельные generatorы делают заново.
- Три verify (`verify_parity` 379Л, `verify_rule_triggers` 252Л, `verify_generated_copies` 72Л) — разные ракурсы одной проверки.

**Рефакторинг-план:**
1. **Создать `environment_sync/core.py`** — единый pipeline: `load_canon() → render_view(agent, canon) → write_atomic()`.
2. **Заменить 9 `generate-*-config.py`** на один `generate-views.py --agent {mcp,codex,dsh,omp,opencode,qoder,qwen,antigravity}` + **таблица агентов** (`agents.py`/registry: name → render-spec). 9 скриптов → 1 + data.
3. **Синхронизировать `generate-agent-configs.py`** как мастер-wrapper над ядром (или его заменить).
4. **Объединить три verify** в `verify-views.py --check {parity,rules,copies}`.
5. **Тесты:** довести покрытие 9→19 (table-driven: для каждого агента assert output-шаблон).

**Ожидаемый выигрыш:** ~50–60% кода в environment-sync; один источник render-логики.

---

## 3. Кластер B — todone: **уже есть правильный pattern, но нужны splits** (ПРИОРИТЕТ 2)

**Текущее состояние.** **Уже хорошо отрефакторено**: тонкие CLI-wrapper (`tcheck.py` 17Л, `tqueue.py` 17Л, `ttask.py` 17Л, `todone-aggregate.py` 14Л, `todone-autodoc.py` 25Л) → библиотека `tdcore/` (38 модулей). Это **правильная архитектура** (в отличие от environment-sync).

**Проблемы:**
- **Гигантские модули:** `tdcore/autodoc.py` **5 899 Л**, `flow.py` 1 933 Л, `task_cli.py` 1 777 Л, `check_cli.py` 1 496 Л.
- **Дублирующие входы:** `tcheck` содержит `aggregate`/`autodoc`, а есть отдельные `todone-aggregate.py`/`todone-autodoc.py`.
- **Тест-покрытие:** 6 тестов для 38 модулей.

**Рефакторинг-план:**
1. **Split `tdcore/autodoc.py`** (5 899 Л): выделить `autodoc_render.py`, `autodoc_bundle.py`, `autodoc_diagram.py`, `autodoc_audit.py` по ответственности.
2. **Split `tdcore/flow.py`** (1 933 Л): `flow_validate.py`, `flow_steps.py`.
3. **Split `tdcore/task_cli.py`** (1 777 Л) и `check_cli.py` (1 496 Л) на покомандные модули.
4. **Дедуплицировать входы:** `todone-aggregate.py`/`todone-autodoc.py` → thin wrappers над `tcheck aggregate`/`tcheck autodoc` (или удалить как отдельные точки).
5. **Тесты:** добавить модульные тесты для split-модулей.

**Ожидаемый выигрыш:** модули до 1 000–1 500 Л; убирает дублирующие входы.

---

## 4. Кластер C — skill-creation: **объединить две системы** (ПРИОРИТЕТ 2)

**Текущее состояние.** `skill-creator/` (scaffold_skill 489Л, package_and_verify 484Л, «17 агентов») vs `skill-authoring/` (create_skill 216Л, audit_skill 314Л) + `add-skill/` (add_skill 502Л).

**Проблемы:**
- Две параллельные системы на одну задачу (скaffold/package/audit).
- `scaffold_skill.py` ↔ `create_skill.py` — перекрытие; `package_and_verify.py` ↔ `add_skill.py` — перекрытие.

**Рефакторинг-план:**
1. **Определить canonical path:** либо `skill-authoring`+`add-skill` (интеграция в харнес), либо `skill-creator` (standalone, 17 агентов).
2. **Синхронизировать:** один из дублированных входов → wrapper/alias на canonical.
3. **Merge логику:** вынести общий `skill_manifest` + шаблон в shared, оба кластера использовать его.
4. **Тесты:** package_and_verify/add_skill — добавить паритетные тесты.

---

## 5. Кластер D — new-project / перенос: **объединить engine** (ПРИОРИТЕТ 3)

**Текущее состояние.** `harness_transfer.py` (1 161 Л) + `export_kit.py` (607 Л) + `harness_wizard.py` + `onboard-project.py` (619 Л) + `profile_manifest.py` + `release_manifest.py` + `release-repo-check.py` + `git-preview.py`.

**Проблемы:**
- Два engine экспорта/переноса (`harness_transfer` + `export_kit`) — перекрытие.
- Три preview (`profile_manifest`, `release_manifest`, `git-preview`) — перекрывающие inventory.

**Рефакторинг-план:**
1. **Зафиксировать canonical engine:** `harness_transfer` как единственный.
2. **`export_kit.py`** — либо merge в `harness_transfer.export`, либо дифференцировать явно (kit-export vs project-transfer) + документировать.
3. **`harness_wizard.py`** → thin wrapper над `harness_transfer`.
4. **Объединить preview:** один `preview.py --kind {profile,release,git}`.
5. **Тесты:** transfer — рендер-тесты (plan/verify).

---

## 6. Кластер E — валидаторы: **объединить в один CLI** (ПРИОРИТЕТ 3)

**Текущее состояние.** `improvement/`: validate_docs, validate_registry, validate_rules, validate_skills, validate_structure + doc-router: check-links, check-doc-text + exhaustive: check_gates.

**Проблемы:**
- 5 validator-скриптов в одном каталоге с общим шаблоном (`--json/--warn-only`).
- `check-links.py` дублирует D07-логику (validate_docs вызывает его).
- Низкое тестирование (1 тест на 6 скриптов).

**Рефакторинг-план:**
1. **Объединить в один** `harness_cli.py validate --what {docs,registry,rules,skills,structure,links}` (как `harness_cli`/`tcheck` уже делают).
2. **check-links.py** — вынести в shared `doc_links.py`, вызывать из validate_docs и doc-router.
3. **Единые exit-codes** (R-0.2).
4. **Тесты:** table-driven для каждого `--what`.

**Ожидаемый выигрыш:** 5 скриптов → 1 + data; единые конвенции.

---

## 7. Кластер F — аудит: **разграничить роли** (ПРИОРИТЕТ 3)

**Текущее состояние.** `static_audit.py` (2 648 Л) + `eval_runner.py` (408 Л) + `score_aggregator.py` (866 Л) + `audit_skill.py` (314 Л) + `harness_mirror.py` (2 713 Л) + `review_migration.py` (534 Л).

**Проблемы:**
- 4 ревью-инструмента с неочевидным разделением.
- `static_audit.py` (2 648 Л) — монолит.
- Нет тестов (0/3 в skill-auditor).

**Рефакторинг-план:**
1. **Зафиксировать矩阵 ролей:** `harness_mirror` — граф; `static_audit`/`audit_skill` — правила; `review_migration` — пост-миграционное.
2. **Split `static_audit.py`** на модули: `audit_skill_fleet`, `scan_security`, `audit_agents_md` (уже функции — вынести в модули).
3. **Merge `audit_skill.py`** в `static_audit` как подмодуль (или wrapper).
4. **Тесты:** добавить для static_audit/audit_skill.

---

## 8. Кластер G — документация: **объединить doc-генераторы** (ПРИОРИТЕТ 4)

**Текущее состояние.** `doc_skill.py` (108 Л), `doc_script.py` (1 744 Л), `doc_mcp.py` (235 Л).

**Проблемы:** `doc_script.py` (1 744 Л) — монолит; три док-генератора с общей целью.

**Рефакторинг-план:**
1. **Split `doc_script.py`** по объектам: `doc_script_parse.py`, `doc_script_render.py`, `doc_script_main.py`.
2. **Объединить** в единый `doc-gen.py --target {skill,script,mcp}` (как pattern A/E).
3. **Тесты:** doc_script — парсинг/рендер.

---

## 9. Кластер H — адаптера-склады: **registry** (ПРИОРИТЕТ 4)

**Текущее состояние.** 10 файлов `adapters/*.py`, каждый 14 Л, Jaccard 1.00.

**Рефакторинг-план:**
1. Заменить на **registry** — `ADAPTERS = {"cursor": ..., "qwen": ...}` + цикл.
2. Или задокументировать как «задуманный boilerplate» (LOW вред, не приоритет).

---

## 10. Кластер I — task-router / analytics / reporting: **split + тесты** (ПРИОРИТЕТ 3-4)

**Текущее состояние.** `task-analytics.py` (605 Л) + `lib/metrics.py` (317Л `analyze`), `generate_report.py` (1 231 Л) + SyntaxError, `task-change-report`, `workflow_contract.py`, `task_spec.py`, `intake_*`.

**Проблемы:**
- `generate_report.py` — SyntaxError (не запускается).
- `lib/metrics.py:analyze` — 317 Л.
- `task-change-report` не тестимо из-за SyntaxError.

**Рефакторинг-план:**
1. **Fix SyntaxError** в `generate_report.py:540` (f-string backslash).
2. **Split `lib/metrics.py`** (317Л analyze) на показатели.
3. **Split `generate_report.py`** по стадиям отчёта.
4. **Тесты:** добавить для analytics/reporting (task-router 11/19).

---

## 11. Кластер J — mirror / harness-core: **split giant, добавить тесты** (ПРИОРИТЕТ 4)

**Текущее состояние.** `harness_mirror.py` (2 713 Л, 1 тест), `harness_cli.py`, `rebuild-routers.py`, `render_policy_docs.py`, `canon_paths.py`.

**Проблемы:** `harness_mirror.py` — монолит 2 713 Л; низкий тест.

**Рефакторинг-план:**
1. **Split `harness_mirror.py`** на `mirror_graph.py`, `mirror_scan.py`, `mirror_audit.py`, `mirror_bundle.py`.
2. **Тесты:** добавь graph/scan unit-тесты.

---

## 12. Приоритетный план рефакторинга (phases)

### Phase 1 — безопасная ликвидация дефектов (быстрые, без изменения архитектуры)
- **P1.1** Fix 2 SyntaxError: `jira/export_task.py`, `reporting/generate_report.py`.
- **P1.2** Дедуплицировать входы: `todone-aggregate`/`todone-autodoc` → wrapperы над `tcheck`.
- **P1.3** Synchronize web/web2 selfcheck/build-actions (если без веб — опционально).
- **P1.4** Registry для `adapters/` (10 файлов → 1 + data).

### Phase 2 — общая консолидация (согласование + план)
- **P2.1** Environment-sync: render-ядро + таблица агентов (A).
- **P2.2** Валидаторы: единый `validate --what` (E).
- **P2.3** Документация: единый `doc-gen --target` (G).

### Phase 3 — split монолитов + объединение engine
- **P3.1** todone: split `autodoc.py`/`flow.py`/`task_cli.py`/`check_cli.py` (B).
- **P3.2** new-project: единый engine + preview (D).
- **P3.3** static_audit: split + role-matrix (F).
- **P3.4** harness_mirror: split (J).
- **P3.5** skill-creation: canonical path (C).

### Phase 4 — тест-покрытие + контроль
- **P4.1** Довести тест-покрытие: skill-auditor (0→), improvement validators (1→), todone split-модули.
- **P4.2** CI-gate: py_compile + smoke-тесты для всех CLI.
- **P4.3** Скан дубликатов в CI как gate.

---

## 13. Ожидаемые результаты

| Показатель | Сейчас | После рефакторинга |
|---|---|---|
| Число CLI-скриптов | 200 | ~120–140 |
| environment-sync generatorов | 9 | 1 + data |
| Валидаторов | 5+ | 1 + data |
| SyntaxError | 2 | 0 |
| Teст-покрытие | неравномерное (0–17) | table-driven по кластерам |
| Гигантские модули (>1 500 Л) | ~8 | ~0–2 |

**Главный принцип:** один CLI-вход на задачу + shared-ядро + data (registry/table). Pattern уже доказан в `todone` (wrapper + tdcore) и `jsondoc` (один вход, subcommands) — распространить его на environment-sync, validators, doc-generation.

**Важно:** код не правился — это аудит + план рефакторинга. Все изменения требуют **согласования плана**.

---

## 14. Связи
- Дублирование: `.doc/arena/research/audit-cli-duplication.md`
- Справочник: `.doc/arena/research/cli-reference-all-commands.md`
- Глубина Python-скриптов: `.doc/arena/research/audit-python-scripts-deep.md`
- environment-sync: `.doc/arena/research/audit-environment-sync.md`
- Система задач: `.doc/arena/research/audit-task-system.md`
- Система документации: `.doc/arena/research/audit-documentation-system-defects.md`

*Аудит выполнен по метрикам кода, кодовому сканированию дубликатов, анализу подкоманд, прогону py_compile и оценке тест-покрытия для всех 200 CLI-скриптов (без веб-панелей).*
