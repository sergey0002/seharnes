# Аудит CLI-скриптов: дублирование функционала и кода

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** **все CLI-скрипты** — поиск дублирования функционала и кода. Ориентир — справочник `.doc/arena/research/cli-reference-all-commands.md`.
**Метод:** инвентаризация входов, кластеризация по смыслу, **кодовый скан дубликатов** (Jaccard по нормированным строкам, сравнение подкоманд, поиск перекрывающего функционала).

---

## 0. Размер «зоопарка»

| Показатель | Число |
|---|---|
| Python-скриптов с argparse (CLI-входы) | **72** |
| PowerShell-скриптов (doc/task/yadisk) | **14** |
| Адаптеров `harness-core/scripts/adapters/` | **10** |
| Скриптов в `todone/scripts/` | **5** (+ `tdcore/cli.py`) |
| Скриптов generate/verify/render в environment-sync | **14** |
| Пар с кодовым сходством Jaccard > 0.30 | **54** (в т.ч. 20+ с > 0.75) |

**Суть:** для ряда задач действительно рождено **по 5–14 инструментов**, перекрывающих один и тот же функционал. Концепция унифицирована, исполнение — дублировано.

---

## 1. Кластер A — environment-sync: **14 скриптов для одной задачи «render canon → agent view»** (CRITICAL)

**Суть.** Все скрипты `environment-sync/scripts/generate-*.py` и `render/compact` делают одну и ту же вещь: **читают канон (Cursor `.cursor/rules`, `.agents/skills`) и рендерят вид для конкретного агента** (mcp, codex, dsh, omp, opencode, qoder, qwen, antigravity). Это — самая явная «10 инструментов для одной задачи».

**Вход:**
- `generate-agent-configs.py` (682 Л) — **мастер-генератор**: уже создает native Codex/Kilo-views, discovery-файлы (`skills.json`, `.dsh/skills`, `.qwen/skills`), bootstrap.
- `generate-codex-mcp.py` (336 Л) — только Codex MCP-настройки.
- `generate-mcp-config.py` (261 Л) — MCP-вид.
- `generate-omp-config.py` (236 Л), `generate-opencode-config.py` (396 Л), `generate-qoder-config.py` (507 Л), `generate-qwen-config.py` (450 Л) — по одному виду на агент.
- `generate-dsh-config.py` (644 Л), `generate-antigravity-rules.py` (133 Л).
- `render_agent_views.py` (139 Л), `compact_agent_views.py` (295 Л) — оба управляют уже сгенерированными видами.
- `verify_parity.py` (379 Л), `verify_rule_triggers.py` (252 Л), `verify_generated_copies.py` (72 Л) — три verify-скрипта проверяют одни и те же виды/правила.

**Дублирование (доказано):**
- `generate-qoder-config.py` ↔ `generate-qwen-config.py`: **Jaccard 0.46** — почти копии одного renderer-шаблона (различие — только формат строк `rule-<name>`).
- `generate-agent-configs.py` **логически перекрывает** `generate-codex-mcp.py` (Codex-вид), discovery для `.dsh/skills`/`.qwen/skills` — то, что отдельные `generate-*-config.py` делают заново.
- Три verify-скрипта проверяют один canon-вид: parity / rule-triggers / generated-copies — разные ракурсы одной проверки.

**Почему криво:** один renderer-ядро + таблица агентов было бы в 10× меньше кода. Сейчас каждый новый агент = новый 200–600-строчный скрипт, который заново реализует парсинг canon, атомарную запись и валидацию. Это главный источник расползания.

---

## 2. Кластер B — todone: **5–6 CLI для управления задачами** (HIGH)

**Суть.** `todone/scripts/` содержит несколько параллельных входов, и **часть из них дублирует подкоманды друг друга**.

**Вход:**
- `tcheck.py` — диагностика скилла/очередей: `doctor, validate, schema, selftest, types, flows, docs, **aggregate**, **autodoc**, roles, tools, import`.
- `todone-aggregate.py` — оба: `tcheck aggregate` (scan/status/list/show/diff/rebuild/verify/export) **и отдельный скрипт** — один и тот же функционал дважды.
- `todone-autodoc.py` — `tcheck autodoc` (discover/bundle/render/diagram/audit/verify/reconstruct/generate) **и отдельный скрипт** — дублирование.
- `tqueue.py` — очередь: find/init/list/next/summary/done/sort/gantt/board/index-rebuild.
- `ttask.py` — задача: new/show/pack/set/status/report-skeleton/close/reopen/claim/unclaim/comment/ref.
- `tdcore/cli.py` — библиотека-CLI (относительные импорты, не запускается как скрипт).

**Дублирование (доказано):**
- `tcheck.py` ↔ `todone-aggregate.py`: **Jaccard 0.80** — близкие к копии.
- `tcheck` ↔ `ttask` / `tqueue`: **Jaccard 0.60** — общий фундамент обработки записей.
- **`tcheck.py` уже содержит подкоманды `aggregate` и `autodoc`, а отдельные `todone-aggregate.py` и `todone-autodoc.py` существуют как отдельные точки входа** — прямое дублирование входа.

**Почему криво:** `tcheck` — единый управляющий CLI, но `todone-aggregate`/`todone-autodoc` — его дублирующие wrapperы. Два пути в одну команду; обновление один раз — в другом забыть.

---

## 3. Кластер C — создание скиллов: **две параллельные системы** (HIGH)

**Суть.** Создание/упаковка/регистрация скилла представлено **двумя независимыми кластерами** с разным упором, но одной задачей.

**Вход:**
- **`skill-creator/`** (standalone, «17 агентов»):
  - `scaffold_skill.py` (489 Л) — «Deterministic **17-agent** skill scaffolder».
  - `package_and_verify.py` (484 Л) — «Deterministic **.skill packager and 17-agent preflight verifier**».
- **`harness-router/children/skill-authoring/`**:
  - `create_skill.py` (216 Л) — «Create a new harness skill scaffold and register it».
  - `audit_skill.py` (314 Л) — «Audit one or all harness skills against the project rules».
- **`harness-router/children/add-skill/`**:
  - `add_skill.py` (502 Л) — «Install a local skill into the harness canon with documentation» (обновляет родительский роутер).

**Дублирование:**
- **scaffold**: `scaffold_skill.py` (skill-creator) vs `create_skill.py` (skill-authoring) — оба «создать каркас скилла».
- **package/verify**: `package_and_verify.py` (skill-creator) vs `add_skill.py` (add-skill) — оба упаковывают/регистрируют скилл в canon.
- **audit**: `audit_skill.py` (skill-authoring) — параллельно к `skill-auditor/` (см. кластер F).

**Почему криво:** две системы — `skill-creator` (упор на 17 агентов, standalone) и `skill-authoring/add-skill` (интеграция в харнес) — перекрываются по смыслу, но живут раздельно. Кто что выбирает — неочевидно; правки дублируются.

---

## 4. Кластер D — new-project / перенос кита: **8 входов, перекрывающих transfer/export/onboard** (MEDIUM-HIGH)

**Суть.** Migration-инструменты раздроблены на множество скриптов с перекрывающимися функциями.

**Вход:**
- `harness_transfer.py` (1161 Л) — engine переноса (inventory/fetch/plan/verify/approve/apply/rollback/render/compact/export/adopt).
- `export_kit.py` (607 Л) — «Kit export engine: one walker, three modes, no per-adapter copy lists».
- `harness_wizard.py` (143 Л) — интерактивный мастер-превью transfer.
- `onboard-project.py` (619 Л) — «Onboard a project after the harness migration».
- `profile_manifest.py` (124 Л) — карта путей из `kit.json` (без записи).
- `release_manifest.py` (225 Л) — derived release-manifest из одного commit.
- `release-repo-check.py` (82 Л) — проверка видимости файлов в релиз-репозитории.
- `git-preview.py` (103 Л) — превью путей из bare store.

**Дублирование:**
- `harness_transfer.py` и `export_kit.py` — **оба engine экспорта/переноса кита**, один walks, другой export-engine; `harness_transfer.export` vs `export_kit` — перекрытие.
- `harness_wizard.py` — wrapper над `harness_transfer` (перекрытие функционала превизу).
- `profile_manifest` / `release_manifest` / `git-preview` — три разных «превью путей/manifest», перекрывающих inventory.

**Почему криво:** два parallel-engine (`harness_transfer` + `export_kit`) + wrapper + три preview — концептуально единый «перенести/показать» pipeline, разбросанный по 8 скриптам.

---

## 5. Кластер E — валидаторы: **5+ проверяльщиков одной «структуры»** (MEDIUM)

**Суть.** Неколико validator-скриптов проверяют структуру/документацию, часто с общим шаблоном (`--json`, `--warn-only`).

**Вход:**
- `improvement/scripts/validate_docs.py` — покрытие doc харнеса + D07 links.
- `improvement/scripts/validate_registry.py` — реестр скиллов.
- `improvement/scripts/validate_rules.py` — правила (rules-dir/skills-dir).
- `improvement/scripts/validate_skills.py` — скилы.
- `improvement/scripts/validate_structure.py` — структура харнеса.
- `doc-router/.../check-links.py` — ссылки (отдельно).
- `doc-router/.../check-doc-text.py` — текст доков (отдельно).
- `exhaustive-research-.../check_gates.py` — проверка гейтов.

**Дублирование:**
- **5 validator-скриптов в одном каталоге** с общей философией (`--json/--warn-only/exit`) — единый «validate-X» could be one CLI with subcommands (как `harness_cli.py`/`tcheck.py` уже делают).
- `check-links.py` дублирует логику D07 в `validate_docs.py` (validate_docs **вызывает** check-links, но doc-router имеет свой ключ).
- `check-doc-text.py` перекрывает часть validate_docs.

**Почему криво:** 5 маленьких validator-скриптов вместо одного `validate --what {docs,registry,rules,skills,structure,links}`. Даже `tcheck.py` уже группирует validate/selftest — но харнес-валидаторы нет.

---

## 6. Кластер F — аудит: **4 ревью-инструмента** (MEDIUM)

**Суть.** Аудит скиллов/харнеса/миграции распределён по нескольким большим скриптам.

**Вход:**
- `skill-auditor/scripts/static_audit.py` (2648 Л) — статический аудит скиллов.
- `skill-auditor/scripts/eval_runner.py` (408 Л) — запуск eval.
- `skill-auditor/scripts/score_aggregator.py` (866 Л) — сводка score.
- `skill-authoring/scripts/audit_skill.py` (314 Л) — аудит скиллов по правилам проекта.
- `mirror/scripts/harness_mirror.py` (2713 Л) — mirror-граф + viewer.
- `migration-review/scripts/review_migration.py` (534 Л) — ревью миграции.

**Дублирование:**
- **`static_audit.py` (2648 Л) vs `audit_skill.py` (314 Л)** — оба «аудит скиллов». Different depth, same intent.
- `harness_mirror.py` — огромный граф, но он **не покрывает** audit_skill/static_audit; три разных «аудиторского» входа.
- `review_migration.py` — параллельно `harness_transfer.verify` (проверка после миграции).

**Почему криво:** для одной «проверить скилл/харнес/миграцию» — четыре входа разной глубины и один enormous mirror; неочевидно, какой вызывать.

---

## 7. Кластер G — документация: **3 doc-генераторов** (LOW-MEDIUM)

**Вход:**
- `doc-skill/scripts/doc_skill.py` (108 Л) — документация скилла (README).
- `doc-script/scripts/doc_script.py` (1744 Л) — документация скриптов внутри скилла.
- `doc-mcp/scripts/doc_mcp.py` (235 Л) — один док на MCP-сервер.

**Дублирование:** три doc-генераторов с общей целью «документировать харнес-компонент»; `doc_script.py` (1744 Л) — самый крупный, дублирует логику doc_skill/doc_mcp на более глубоком уровне.

---

## 8. Кластер H — адаптера-склады: **10 тонких файлов Jaccard 1.00** (LOW, но системно)

**Вход:** `harness-core/scripts/adapters/{agents,codex,cursor,kilo,omp,opencode,qoder,qwen,base,dsh}.py` — каждый **14 Л**, класс `Adapter(BaseAdapter)` с `name = "..."` и пустым `check()`.

**Дублирование:** после нормирования все **взаимно Jaccard 1.00** — это **унифицированный boilerplate**, а не разный код. Это не «зоопарк», но это **10 файлов, один из которых** (registry-driven) заменил бы всю стойку.

**Оценка:** LOW вред (маленькие, единообразные), но **системная гигиена** — один data-driven `ADAPTERS` registry + цикл.

---

## 9. Кластер I — web/web2: **точные дубликаты** (MEDIUM)

**Вход:** `.doc/web/bin/selfcheck.py` ↔ `.doc/web2/bin/selfcheck.py` (**Jaccard 1.00**), `.doc/web/bin/build-actions.py` ↔ `.doc/web2/bin/build-actions.py` (**Jaccard 1.00**).

**Дублирование:** копии web-v1 в web-v2 без синхронизации. **Миграция web→web2 частична** (см. предыдущий аудит веб-панелей) — дубли подтверждают это.

---

## 10. Кластер J — анализ задач: **3 аналитика задач** (LOW-MEDIUM)

**Вход:** `task-router/.../task-analytics.py` (аналитика задач), `todone/.../todone-aggregate.py` (aggregate записей), `task-router/.../intake_analysis.py` (каркас diff-анализа).

**Дублирование:** три аналитика задач/записей с перекрывающимися метриками; `task-analytics.py` (знание задач) vs `todone-aggregate.py` (aggregate тоделов) vs `intake_analysis.py`.

---

## 11. Сводка по дублированию (по серьёзности)

| Кластер | Объект | Степень дублирования | Вред |
|---|---|---|---|
| **A** environment-sync | 14 render/verify | CRITICAL — одна задача, 14 скриптов, Jaccard 0.46+ | Очень высокий |
| **B** todone | 5–6 CLI, tcheck уже содержит дубли подкоманд | HIGH — дублирующие входы | Высокий |
| **C** skill-creation | 2 параллельные системы | HIGH | Высокий |
| **D** new-project | 8 transfer/export/onboard | MEDIUM-HIGH — 2 engine | Высокий |
| **E** validators | 5+ validator-скриптов | MEDIUM — единый шаблон | Средний |
| **F** audit | 4 ревью-инструмента | MEDIUM | Средний |
| **G** doc-generation | 3 doc-генератора | LOW-MEDIUM | Низкий |
| **H** adapters | 10 Jaccard-1.00 файлов | LOW (boilerplate) | Низкий |
| **I** web/web2 | 2 точных дублика | MEDIUM | Средний |
| **J** task-analytics | 3 аналитика | LOW-MEDIUM | Низкий |

**Чёткая картина «зоопарка»:**
- **One-task-many-tools** (A, B, C, D, E): по одной задаче — 5–14 входов.
- **Parallel systems** (C, D, F): по две-три системы на одну функцию.
- **Copy-duplication** (H, I, B): точные/почти точные копии.

---

## 12. Рекомендации по упорядочению (по приоритету)

### Сlevel 1 — дедупликация входа (быстрые, безопасные)
1. **B (todone):** адаптировать `todone-aggregate.py` и `todone-autodoc.py` как thin wrapper-ы **над `tcheck aggregate`/`tcheck autodoc`** (или убрать как отдельные входы). Исключить дублирование подкоманд.
2. **I (web/web2):** синхронизировать `selfcheck.py`/`build-actions.py` (или сделать one canonical + link).
3. **H (adapters):** заменить 10-файловую стойку на **registry** (`ADAPTERS = {name: ...}`) + цикл; либо явно задокументировать как «задуманный boilerplate».

### Сlevel 2 — консолидация engine (согласование + план)
4. **A (environment-sync):** выделить **единое render-ядро** (parse canon → render view) + **таблицу агентов**; 14 скриптов → `generate-views --agent X`. `generate-agent-configs.py` — как мастер. Это самый крупный выигрыш.
5. **D (new-project):** согласовать единый engine (`harness_transfer` как canonical) + thin wrapperы (wizard, git-preview); `export_kit` — либо merged, либо явно дифференцирован от transfer.
6. **C (skill-creation):** определить **canonical path** (skill-authoring/add-skill) и либо merge `skill-creator`, либо дифференцировать по «17 агентов, standalone».

### Сlevel 3 — группировка валидаторов/аудитов
7. **E (validators):** один `validate` CLI с подкомандами `{docs,registry,rules,skills,structure,links}` (как `harness_cli`/`tcheck` уже делают).
8. **F (audit):** определить roles: `harness_mirror` (graph), `audit_skill`/`static_audit` (rules), `review_migration` (post-migration). Документировать矩阵.

### Сlevel 4 — глобальный контроль
9. **Контроль дубликатов:** добавить в audit/CI скан дубликатов (Jaccard/структурный) как gate — чтобы новые скиллы не дублировали существующие CLI.
10. **Единый описатель:** справочник `cli-reference-all-commands.md` расширить колонкой «замена/дублирует» — так выбор инструмента будет очевиден.

**Важно:** код не правился — это аудит. Дедупликация требует **согласования плана** и замены дублирующих входов wrapper-ами/ядром; это деликатная миграция.

---

## 13. Связи
- Справочник: `.doc/arena/research/cli-reference-all-commands.md`
- Аудит CLI-скриптов (глубина): `.doc/arena/research/audit-python-scripts-deep.md`
- Аудит environment-sync: `.doc/arena/research/audit-environment-sync.md`
- Аудит скилов/панелей: `.doc/arena/research/audit-skill-tree-and-web-panels.md`
- Аудит системы задач: `.doc/arena/research/audit-task-system.md`
- Аудит системы документации: `.doc/arena/research/audit-documentation-system-defects.md`

*Аудит выполнен по структурной инвентаризации 72 Python-CLI + 14 PS1-скриптов, кластеризации по смыслу и кодовому сканированию дубликатов (Jaccard по нормированным строкам).*
