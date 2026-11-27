# Аудит дерева скилов, связей, контроля и веб-панелей harness

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** аудит системы скилов harness — дерево скилов, система связей, система контроля, и веб-панели (`web` — v1, `web2` — v2, на которую плавно мигрируется функционал).

---

## 1. Введение

Harness строится как **дерево скилов** (skill tree): роутеры-оркестраторы группируют узкие скилы-children. Связи между скилами — через `skill.json` (`children` + `dependencies`). Контроль — валидация, аудит, rebuild-роутеров, mirror-граф. Веб-панель — PHP-сервис для просмотра задач/документации/аналитики и **просмотрщика харнеса**; есть две версии: `web` (v1, архив) и `web2` (v2, миграционный target).

---

## 2. Дерево скилов (skill tree)

### 2.1 Состав
- **Уровень 0 (top-level):** **27** скилов в `.agents/skills/`.
- **Уровень 1 (children):** 6 каталогов `children/` у роутеров.
- **Всего:** **77** `SKILL.md` + 77 `skill.json`.

### 2.2 Роутеры-оркестраторы (kind=orchestrator)

| Роутер | Children (каталог) | Число |
|--------|---------------------|-------|
| `harness-router` | `children/` | 16 (add-skill, copy-project, doc-mcp, doc-script, doc-skill, environment-sync, harness-core, improvement, index, mcp-audit, migration-review, mirror, new-project, project-setup, remove-skill, skill-authoring) |
| `task-router` | `children/` | 13 (analytics, audit-plan, git-task-blame, gototask, jira, kaiten, reporting-router, task-code-review, task-core, task-diff, task-intake, task-spec, testing-router) |
| `documentation-router` | `children/` | 3 (doc-verify, project-doc, task-doc) |
| `prepare-plan` | (standalone, без children-каталога) | 0 — orchestrator с assets/references |

### 2.3 Вложенные роутеры (level 2)
- `task-router/children/reporting-router/children/` — 2 (task-change-report, task-report).
- `task-router/children/testing-router/children/` — 3 (browser-verify, prepare-task-test, test-task).

### 2.4 Листовые скилы (kind=leaf, top-level)
skill-auditor, skill-creator, todone, codeprism, graphiti, codegraph, serena, jdocmunch, mysql, phpstan-mcp, php-deps-mcp, playwright, semgrep, context7, codebase-memory-mcp, git, yadisk-screenshot, ponytail, send-to-git, copytrust, neiroslop, exhaustive-research-decision-v6 (orchestrator), code.

**Архитектура:** роутеры содержат **только маршрутизацию**; полезная нагрузка — в дочерних скилах. Это паттерн **routing-only router**: клиент читает router-SKILL.md, выбирает один child по таблице, читает его SKILL.md по полному пути.

---

## 3. Система связей (links)

Связи задаются в `skill.json` двумя способами:

### 3.1 `children` — родитель → дочерние скилы
- Список `children/<name>` (относительно скилла).
- **Заполняется автоматически** `add_skill.py:update_parent_router()` — при добавлении child appendится `children/<name>` в родительский `skill.json`.
- **Используется** `rebuild-routers.py:children_of()` для построения routing-таблиц router-SKILL.md.

### 3.2 `dependencies` — скил → зависимые скилы и проектные файлы
Формат:
```json
"dependencies": {
  "skills":   [ {"name": "...", "required": bool, "reason": "..."} ],
  "project":  [ {"path": "...", "owner": "...", "required": bool, "reason": "..."} ]
}
```
- **`skills`** — ссылки на другие скилы (например, `prepare-plan → jdocmunch, ponytail, task-router`).
- **`project`** — ссылки на проектные файлы/скрипты (например, `gototask → task-analytics.py, server.php`, `task-intake → jsondoc.py, task-identity.py`).
- **16** непустых наборов связей (dependencies/children) по дереву.
- **`reason`** и `required` — явная семантика зависимости (обязательно/необязательно, зачем).

**Качество:** связи явные, с пояснениями; позволяют валидаторам проверять наличие зависимостей (`audit_skill.py` проверяет dependencies).

---

## 4. Система контроля (control)

| Инструмент | Роль |
|------------|------|
| `validate_skills.py` | валидация скилов по `skill-format.yaml` (структура, metadata) |
| `validate_docs.py` | валидация документации по `component-docs.yaml` |
| `validate_registry.py` | валидация `component_registry.json` |
| `validate_rules.py` | статическая валидация правил и скилов |
| `validate_structure.py` | валидация раскладки каталогов по `canon-paths.yaml` (`layout`) |
| `audit_skill.py` | **аудит одного/всех скилов**: структура, frontmatter, README, skill.json, scripts, tests, docs, индексы, registry, родительский router, dependencies |
| `rebuild-routers.py` | **перестройка router-SKILL.md** из дерева (children + triggers) |
| `harness_mirror.py` | semantic-mirror канона: scan/lint/review/audit (граф узлов) |
| `gates.py` (task) | гейты тестирования задач |

**Контрольное звено:** валидация (format/structure) + аудит (per-skill) + rebuild (router-синхронизация) + mirror (semantic). Это многоуровневая система проверки дерева.

---

## 5. Веб-панель — `web` (v1) и `web2` (v2)

### 5.1 Общая суть (обе версии)
- Сервис `copytrust-tools` (legacy-название): единая панель задач, документации, аналитики диалогов и **просмотрщика харнеса**.
- Один PHP-процесс на `127.0.0.1:8077`, **без БД, без ИИ**.
- Читает JSON/MD из `.doc` и `.cursor/.state`; изменяющие действия — только через разрешённый список скриптов.
- Вкладки: Задачи, Страница задачи, Документация, Аналитика диалогов, Диалоги задачи, Лента активности, Бизнес-аналитика, фильтры (релиз, ответственный, проект диалогов).

### 5.2 `web` (v1) — `.doc/web/` — АРХИВ
- README начинается с примечания: **«Архив (2026-11-13): PowerShell-экспорт удалён. Активный механизм `harness_transfer.py`…»**.
- Содержит: `src/` (слойная архитектура: `App.php`, `Core/`, `Domain/`, `Http/`, `Support/`, `View/`), `app/` (`harness.php`, `harness_admin.php`, `jobs.php`, `lib.php`, `pricing.php`, `providers.php`), `bin/`, `config/`, `ADAPTERS.local.md` (локальные адаптера, gitignored).
- **Просмотрщик харнеса** (`app/harness.php`): read-only статический viewer + API; читает **mirror-граф** `graph.json` из `.doc/skil_data/mirror` (data_dir из `config/service.json`).

### 5.3 `web2` (v2) — `.doc/web2/` — МИГРАЦИОННЫЙ TARGET
- Чистый README (без примечания-архива).
- Содержит: `app/` (`harness.php`, `jobs.php`, `lib.php`, `pricing.php`, `providers.php`), `bin/`, `config/` (`actions.json`, `actions.schema.json`, `prices.json`, `prices.local.example.json`, `service.json`).
- **Не содержит:** `src/` (слойная архитектура), `app/harness_admin.php`, `ADAPTERS.local.md`.

### 5.4 Миграция web → web2 (плавный перенос)
| Состав | web (v1) | web2 (v2) |
|--------|----------|-----------|
| `app/` слой (harness, jobs, lib, pricing, providers) | ✅ | ✅ (перенесён) |
| `bin/build-actions.py` | ✅ | ✅ (перенесён) |
| `config/actions.json` | 191 л. | 123 л. (сокращён — часть действий не мигрирована) |
| `src/` слой (App.php, Core/Domain/Http/Support/View) | ✅ | ❌ **не перенесён** |
| `app/harness_admin.php` | ✅ | ❌ **не перенесён** |
| `ADAPTERS.local.md` | ✅ | ❌ (локальные адаптера) |

**Вывод по миграции:** перенесена **базовая `app/`-площадка** (data-слой + jobs + harness-viewer), но **слойная архитектура `src/`**, admin-модуль и локальные адаптера — **ещё в v1**, не мигрированы в web2. Миграция **частичная, в процессе**.

---

## 6. Нахождения (findings)

### Ф-ДЕРЕВО-1. **Дрейф роутеров: `skill.json.children` пусто, routing-таблицы есть**
- `rebuild-routers.py --check` → **`routers=5 changed=5`** (harness-router, task-router, documentation-router, reporting-router, testing-router).
- У всех 5 роутеров `skill.json.children = []`, но router-SKILL.md содержит routing-таблицы: harness-router=16, task-router=18, documentation-router=3, reporting-router=2, testing-router=3.
- `add_skill.py:update_parent_router()` **заполняет** `children`, но роутеры не updated (children добавлялись иначе/раньше).
- **Последствия:** `rebuild-routers.py --write` **опустит** routing-таблицы (children_of вернёт []).
- **Класс:** дрейф/несогласованность (контроль detect). **Лечение:** заполнить `children` у роутеров (как делает add_skill) или пересобрать.

### Ф-ДЕРЕВО-2. **Связи partial: 16/77 скилов имеют непустые dependencies**
- Большинство скилов имеет `dependencies: {skills: [], project: []}`. Заполнены связи у связных скилов (prepare-plan, audit-plan, gototask, task-intake, browser-verify, test-task, send-to-git…).
- **Класс:** не дефект — скилы без зависимостей корректно пустые. Но формально большинство дерева не перечислено в dependencies (или они действительно независимы).

### Ф-ДЕРЕВО-3. **`prepare-plan` — orchestrator без children-каталога**
- kind=orchestrator, но нет `children/`; routing-нагрузка в assets/references. **Класс:** архитектурный выброс (не все orchestrator одинаково организованы).

### Ф-WEB-1. **Миграция web → web2 частична**
- `src/`-слой, `harness_admin.php`, `ADAPTERS.local.md` — только в web v1, не мигрированы в web2.
- `actions.json` сокращён (191 → 123 л.) — часть действий/функций не перенесена.
- **Класс:** процесс миграции (не дефект). Важно учитывать при плавном переносе.

### Ф-WEB-2. **web v1 — архив, но «копичные» сервисы и naming**
- README web содержит примечание-архив (2026-11-13). web2 — чистый target.
- README обеих версий содержит **4 упоминания `copytrust`** («copytrust-tools») — legacy-остаток (согласуется с задачей переименования, код в frozen-зоне).
- **Класс:** legacy-branding (к ренему), архив-состояние.

### Ф-WEB-3. **Просмотрщик харнеса читает mirror-граф (state)**
- `harness.php` читает `graph.json` из `.doc/skil_data/mirror` — панель показывает mirror-граф, а не читает дерево напрямую.
- **Класс:** зависимость от generated-state (mirror должен быть построен `harness_mirror.py build`).

---

## 7. Вердикт

**Дерево скилов — зрелая, хорошо структурированная система.**

**Сильные стороны:**
- **Routing-only router-паттерн** — роутеры только маршрутизируют, нагрузка в children; клиент читает один конкретный SKILL.md.
- **Явные связи** через `skill.json.children` + `dependencies` (skills + project, с `required`/`reason`).
- **Многоуровневый контроль**: validate (format/structure/docs/registry) + audit_skill + rebuild-routers + mirror.
- **Автоматическое обновление родителя** при добавлении скила (`update_parent_router`).
- Веб-панель — без БД/ИИ, read-mostly, действия через разрешённый список; просмотрщик харнеса на mirror-графе.

**Неровности:**
- **Ф-ДЕРЕВО-1 (дрейф роутеров)** — главная контрольная находка: `children` пусто, routing-таблицы есть, `rebuild --check` фиксирует changed=5.
- **Ф-WEB-1 (частичная миграция web→web2)** — `src/`-слой и admin ещё в v1.
- **Ф-ДЕРЕВО-3, Ф-WEB-2, Ф-WEB-3** — архитектурные выбросы и legacy-остатки.

**Общая оценка: 8 из 10.** Дерево и связей — высокого качества; контроль работоспособен (найшёл реальный дрейф роутеров). Веб-панель в стадии плавной миграции v1→v2.

---

## 8. Рекомендации

1. **Ф-ДЕРЕВО-1 (приоритет):** синхронизировать роутеры — заполнить `skill.json.children` у 5 роутеров (как делает `add_skill.py`) и/или перезапустить `rebuild-routers.py --write`, чтобы routing-таблицы соответствовали дереву. Добавить `rebuild-routers --check` в контроль (pre-commit/CI).
2. **Ф-WEB-1:** фиксировать перенос `src/`-слоя, `harness_admin.php`, `ADAPTERS.local.md` из web в web2 как следующий этап плавной миграции; сверить `actions.json` (191→123).
3. **Ф-ДЕРЕВО-3:** либо сделать `prepare-plan` соответствующим routing-контракту (children), либо задокументировать как exception.
4. **Ф-WEB-2:** по завершении миграции web2 стать активной панелью; `copytrust`-название погасить в рамках задачи переименования.
5. **Ф-WEB-3:** для просмотрщика харнеса в web2 учитывать зависимость от `harness_mirror.py build` (mirror-граф).

---

## 9. Связи

- Аудит скилов/переноса: `.doc/arena/research/audit-harness-transfer-quality.md`, `audit-python-scripts-deep.md`.
- Аудит environment-sync: `.doc/arena/research/audit-environment-sync.md`.
- CLI-справочник: `.doc/arena/research/cli-reference-all-commands.md`.
- Конфиги: `.doc/arena/research/reference-all-system-configs.md`.
- mirror-граф: `harness_mirror.py` (scan/build → `.doc/skil_data/mirror/graph.json`).

*Аудит выполнен по структурному анализу дерева скилов, чтению skill.json/SKILL.md, проверке rebuild-routers и сравнению веб-панелей web/web2.*
