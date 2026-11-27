# Аудит мусора в гит-репозитории и папках харнеса

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** **мусор в git и папках харнеса** — мёртвый/неиспользуемый код, legacy-остатки, дубли, orphan-файлы, one-off-скрипты и прочее.
**Метод:** инвентаризация, поиск markers (deprecated/legacy/stub), кодовый скан дубликатов (Jaccard), проверка вызовов, проверка активности MCP, проверка SyntaxError.

---

## 0. Содержание

| Категория | Объём | Серьёзность |
|---|---|---|
| **G1. CopyTrust-остатки** (проект переименован в seharnes) | **162 файла / 573 упоминания + стимка `.agents/skills/copytrust/`** | 🔴 CRITICAL |
| **G2. Мёртвый legacy-скрипт** (`find-task-branch.ps1`) | 1 скрипт + 3 док | 🔴 HIGH |
| **G3. SyntaxError — невыполняемый код** | 2 скрипта | 🔴 HIGH |
| **G4. One-off с хардкодом путей** | 2+ скрипта | 🟡 MEDIUM |
| **G5. Дубли в web/web2** | 2 файла (точные копии) | 🟡 MEDIUM |
| **G6. Неактивные MCP-скилы** | `neiroslop`, `ponytail` (не в mcp.json) | 🟡 MEDIUM |
| **G7. archive-директории** | `.doc/harnes/archive/` (9 файлов) | 🟢 LOW |
| **G8. Авто-доки-мироры** (docs/scripts/*.md) | 162 файла | 🟢 LOW (система) |
| **G9. Гигантские монолиты + дублирование** | см. refactoring-аудит | 🟡 MEDIUM |

**repo:** 1 617 файлов, ~29 МБ; `.git` — 6 МБ (история относительно чистая).

---

## 1. G1 — CopyTrust-остатки (CRITICAL)

**Суть.** Проект переименован в **`seharnes`**, но имя `copytrust` осталось в коде и документах. Это **наибольший мусор**.

**Доказательства (подтверждено):**
- Весь скилл-стим `.agents/skills/copytrust/`: **9 файлов, 64 КБ** — `README.md`, `SKILL.md`, `skill.json`, children `platform-browser-test`, `platform-logs`.
- **162 файла** содержат `copytrust`, **573 упоминания** во всем repo.
- В production-скриптах:
  - `.agents/skills/documentation-router/children/project-doc/scripts/audit-docs.ps1:11` — `cd C:\projects\copytrust\testdeploydocker`
  - `.agents/skills/documentation-router/children/project-doc/scripts/_restore_cicd_from_transcript.py:5` — `C:\Users\NewUser\.cursor\projects\c-projects-copytrust-testdeploydocker\...`
  - `.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1:136` — `# Индекс задач CopyTrust`
  - `.agents/skills/harness-router/children/harness-core/assets/kit.json` — copytrust-пути
  - docs: `audit-docs.ps1.md`, `build-tasks-index.ps1.md`, `references/indexing.md`
- Также `.doc/harnes/doc_rules.md` (2), `.doc/harnes/jsondoc.md` (1).

**Почему мусор:** CopyTrust — это **конкретный старый проект**, а харнес — **универсальный** (по корректировке пользователя). Имя в production-скриптах делает их непереносимыми и ложит.

**Очистка:** удалить стимку `.agents/skills/copytrust/`; заменить `copytrust`→`seharnes` во всех скриптах/доках (по **согласованному** плану; 573 упоминания — автоматический replace + проверка).

---

## 2. G2 — Мёртвый legacy-скрипт (HIGH)

**Суть.** `.agents/skills/task-router/children/gototask/scripts/find-task-branch.ps1` — **legacy, не вызывается**.

**Доказательства:**
- `gototask/SKILL.md:243`: «`scripts/find-task-branch.ps1` лежит в каталоге как **legacy и не вызывается**: поиск веток живёт в `gototask.ps1`».
- `.doc/harnes/idea/06b-dsh-scripts-and-testing.md:255`: «find-task-branch.ps1 | **не вызывается, legacy**».
- `.doc/harnes/state/02-skills.md:145`: «у `gototask` убрана ложная зависимость от `find-task-branch.ps1`».
- Но он всё ещё в `skill.json` (`scripts/find-task-branch.ps1`) и в auto-доке `docs/scripts/find-task-branch.ps1.md`.

**Почему мусор:** код, который никем не вызывает, но занимает место и создаёт путаницу (два скрипта на одну задачу).

**Очистка:** удалить `find-task-branch.ps1` + auto-док; убрать из `skill.json`.

---

## 3. G3 — SyntaxError: невыполняемый код (HIGH)

**Суть.** Два production-скрипта **не запускаются** из-за SyntaxError (f-string backslash, Python <3.12).

**Доказательства:**
- `.agents/skills/task-router/children/jira/scripts/export_task.py:280` — SyntaxError.
- `.agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/generate_report.py:540` — SyntaxError.

**Почему мусор:** это **мёртвый код** — объявлен, но не может выполниться. Either fix или убрать/заменить.

**Очистка:** исправить 2 SyntaxError (или заменить скрипты рабочими аналогами).

---

## 4. G4 — One-off-скрипты с хардкодом путей (MEDIUM)

**Суть.** Скрипты с захардкоженными чужими абсолютными путями — непереносимы.

**Доказательства:**
- `_restore_cicd_from_transcript.py` — one-off, читает `C:\Users\NewUser\...\copytrust-testdeploydocker\...jsonl` и пишет `architecture/cicd.md`.
- `audit-docs.ps1:11` — `cd C:\projects\copytrust\testdeploydocker`.
- Также hardcoded-пути в auto-доках: `mysql-mcp-proxy.mjs.md`, `php-docker.*.md`, `test-mcp-servers.mjs.md`, `phpstan-docker.sh.md`.

**Почему мусор:** скрипты работают **только на одной машине**; при переносе — ломаются. Это не паттерн, а скрипт-однорочка.

**Очистка:** удалить `_restore_cicd_from_transcript.py` (one-off); параметризовать `audit-docs.ps1` (remove hardcoded `cd`); проверить auto-доки.

---

## 5. G5 — Дубли в web/web2 (MEDIUM)

**Суть.** Миграция web→web2 частична, остались **точные копии**.

**Доказательства:**
- `.doc/web/bin/selfcheck.py` ↔ `.doc/web2/bin/selfcheck.py` — **103 = 103** (Jaccard 1.00).
- `.doc/web/bin/build-actions.py` ↔ `.doc/web2/bin/build-actions.py` — **161 = 161** (Jaccard 1.00).

**Почему мусор:** две копии одного кода; при правке одной — другая устареет.

**Очистка:** синхронизировать web2 с web (или сделать один canonical + link).

---

## 6. G6 — Неактивные MCP-скилы (MEDIUM)

**Суть.** Скилы-адаптеры MCP-серверов, не вписанные в активный `.cursor/mcp.json` — мёртвые.

**Доказательства.** Активные MCP в `.cursor/mcp.json`: bitbucket-task, codebase-memory-mcp, codegraph, codeprism, context7, deepwiki, graphiti, git, jira-task, mysql, php-deps-mcp, phpstan-mcp, playwright, semgrep, serena, sourcegraph, xdebug, jdocmunch.
- **Не активны:** `neiroslop` (7 файлов, 140 КБ) — не в mcp.json; `ponytail` (6 файлов, 40 КБ) — не в mcp.json.

**Почему мусор:** скилы без активного сервера — не используются.

**Очистка:** либо активировать (добавить в mcp.json), либо удалить/архивировать.

---

## 7. G7 — archive-директории (LOW)

**Суть.** Заархивированная документация в `.doc/harnes/archive/`.

**Доказательства:** 9 файлов:
- `.doc/harnes/archive/buisnes_analis/plan.md`
- `.doc/harnes/archive/mcp/`: README.md, bitbucket-task.md, deepwiki.md, graphify.md, rules-placement.md, sourcegraph-local.md, sourcegraph.md, xdebug.md

**Очистка:** либо перенести в `.doc/harnes/archive/` (система), либо удалить устаревшие (sourcegraph-local — gitignored target, см. D3-ссылки).

---

## 8. G8 — Авто-доки-мироры (LOW, система)

**Суть.** 162 файла `docs/scripts/*.md` — auto-генерируемая документация к скриптам.

**Оценка:** это **система документации** (doc_script), не мусор. Но:
- они **дублируют** SKILL.md/скрипты;
- содержат CopyTrust/hardcoded-пути (G1/G4);
- при рефакторинге (duplication-аудит) 162 mirrorа тяжело держать в актуальности.

**Очистка:** не удалять целиком; держать генерируемыми, но при rename/refactor — перегенерировать.

---

## 9. G9 — Гигантские монолиты и дублирование (MEDIUM)

**Суть.** См. отдельные аудиты — это тоже «мусор» в виде расползающего, дублирующего кода.

- **Гигантские монолиты:** `tdcore/autodoc.py` 5 899 Л, `harness_mirror.py` 2 713 Л, `static_audit.py` 2 648 Л.
- **Дублирование функционала:** 10 кластеров (environment-sync — 14 скриптов на одну задачу; todone — дублирующие входы; и т.д.).

**Очистка:** см. `audit-cli-duplication.md` и `audit-cli-refactoring.md`.

---

## 10. git-история

- `.git` — **6 МБ**, история относительно чистая (1 617 файлов в working tree).
- **Глубокая очистка истории** (rebase/filter-branch) — **не рекомендуется** без явного запроса: это разрушительно и репозиторий не требует (размер померяем).
- Если нужна очистка истории — отдельный согласованный план (filter-repo), но текущий объём не критичен.

---

## 11. Сводка — что почистить (приоритет)

| Приоритет | Объект | Действие | Ожидаемый выигрыш |
|---|---|---|---|
| **P1** | CopyTrust-остатки (G1) | удалить `.agents/skills/copytrust/`; rename `copytrust`→`seharnes` (573 mentions) | убрать 162 файла/573 упоминания; скрипты станут переносимыми |
| **P1** | `find-task-branch.ps1` (G2) | удалить скрипт + доки, убрать из skill.json | убрать мёртвый code |
| **P1** | 2 SyntaxError (G3) | fix `export_task.py`, `generate_report.py` | восстановить 2 нерабочие CLI |
| **P2** | One-off с хардкодом (G4) | удалить `_restore_cicd_from_transcript.py`; параметризовать `audit-docs.ps1` | убрать непереносимые скрипты |
| **P2** | web/web2 дубли (G5) | синхронизировать web2 с web | убрать дублирование |
| **P2** | Неактивные MCP-скилы (G6) | либо активировать, либо удалить `neiroslop`, `ponytail` | убрать мёртвые скилы |
| **P3** | archive (G7) | либо системно архивировать, либо удалить устаревшие | убрать захламленность |
| **P3** | Авто-доки (G8) | держать генерируемыми; перегенерировать при rename/refactor | аккуратность docs |
| **P3** | Монолиты/дубли (G9) | по refactoring-плану | убрать расползание |

**Главный мусор:** **CopyTrust** (G1) — это систематический остаток ренема; чистить первым и по согласованному плану.

---

## 12. Рекомендации

1. **G1 (P1):** заменить `copytrust`→`seharnes` по согласованному плану (grep-replace + проверка), удалить стимку `copytrust/`.
2. **G2/G3 (P1):** убрать `find-task-branch.ps1`; исправить 2 SyntaxError.
3. **G4/G5/G6 (P2):** удалить one-off; синхронизировать web2; решить с неактивными MCP-скилами.
4. **Контроль:** включить в CI скан мусора — SyntaxError, orphan-скрипты, CopyTrust, deprecated-markers — как gate, чтобы мусор не возвращался.
5. **Гигиена:** при рефакторинге (duplication-аудит) держать auto-доки перегенерированными.

**Важно:** код не правился — это аудит мусора. Очистка требует **согласования плана** (особенно G1 — массовый rename).

---

## 13. Лишние файлы вне харнеса (orphan — не относящиеся к харнесу, нигде не используемые)

**Суть.** По задаче: **не трогать скилы**, найти **лишние файлы**, не относящиеся к харнесу и нигде не используемые. Скан битов репозитория: каждый файл (вне `.agents/skills/`) проверен на входящие ссылки по имени во всех текстовых файлах repo.

**Результат:** 119 файлов с нулевыми входящими ссылками, сведены в категории. Только файлы, genuinely не относящиеся к харнесу, marked как мусор; web-панели (`.doc/web`, `.doc/web2`) — харнес-панели, не мусор (orphan-по-имени из-за PHP-классов).

### F1. `.tools/codeception/` — продуктовая e2e-стимка (88 файлов) 🔴

**Суть.** Codeception-набор **конкретного продукта** (тарифы/бронирование/клиенты), не универсальный харнес.

**Доказательства:**
- 46 файлов содержат **`ct_`-schema** (`ct_client`, `ct_order` — schema старого проекта), например `TariffDeleteCest.php`: `$I->updateInDatabase('ct_client', ['tariffId' => 7], ['id' => 1])`.
- Page-объекты продукта: `AdminOrdersPage`, `TariffShowcasePage`, `OrderBookingPage`, `CabinetBalancePage`, `SignupPage` и т.д. (~40 Page/Step).
- Это **тесты целевого продукта**, не харнес-фреймворк. HARNESS browser-verify **использует Codeception как движок**, но эта стимка — конкретный тест-корпус продукта.

**Оценка:** 🔴 **мусор/неотносящийся** — если харнес должен быть универсальным, это локальный тест-корпус конкретного проекта. Решение: либо вынести за repo (в проект-потребитель), либо gitignore.

### F2. `.cursor/mcp-stack/` — legacy MCP-toolset (10 файлов) 🟡

**Суть.** Legacy-инструменты управления MCP-стек (systemd-юниты CodePrism/Serena/Graphiti).

**Доказательства:**
- `.cursor/mcp-stack/`: `add-codeprism.py` (systemd user-unit), `add-project.sh`, `add-serena.sh`, `export.sh`, `restore.sh`, `verify.sh`, `graphiti/{config.yaml,docker-compose.yml}`, `tests/test_add_codeprism.py`, `tests/test_transfer_codeprism.py`.
- **Уже есть харнес-ответственный инструмент**: `.agents/skills/harness-router/children/mcp-audit/` (check-mcp.sh, scan-usage.py, test-mcp-servers.mjs, verify_mcp_views.py) — МКР-аудит харнеса.
- Ссылки на `mcp-stack` идут только из **auto-доков** MCP-скиллов (codeprism.md, codegraph.md и т.д.), не из логики харнеса.

**Оценка:** 🟡 **legacy/дублирующий** —superseded харнес-mcp-audit. Решение: либо удалить, либо явно задокументировать как legacy.

### F3. `EXPORT_NEXT_STEPS.md` — временный файл (1 файл) 🟡

**Суть.** Файл-заметка «шаги после экспорта», **самого себя announced как удалить**.

**Доказательства:** `EXPORT_NEXT_STEPS.md` содержит пункт «Remove `EXPORT_NEXT_STEPS.md` when the target is configured». Это **временный setup-artifact**, не часть харнеса.

**Оценка:** 🟡 **мусор (temp)**. Решение: удалить после настройки таргета (или сделать gitignored).

### F4. `.doc/harnes/dsh/*.json` — сгенерированные JSON-виды (6 файлов) 🟢

**Суть.** DSH-views JSON (попарно к `.md`). Это **порожденные артефакты**, не рукописный код.

**Оценка:** 🟢 **порожденный мусор** — либо gitignore, либо держать генерируемыми. JSON-дубликаты `.md`.

### F5. `.doc/harnes/idea/documentation-queue-migration.md` — черновик (1 файл) 🟢

**Суть.** Черновик-идея (`status: draft`, tags `idea, documentation, indexing`). Не мусор в строгом смысле, но черновик.

**Оценка:** 🟢 **черновик** — либо доработать и включить, либо архивировать.

### F6. Web-панели `.doc/web/`, `.doc/web2/` — харнес, не мусор (orphan-по-имени) ⚪

**Суть.** `.doc/web/src/**` (~50 PHP-файлов) + `.doc/web2/` — **панели харнеса** (v1/v2). orphan-по-имени из-за того, что PHP-классы не ссылаются по имени в док-текстах.

**Оценка:** ⚪ **не мусор** — это харнес-панели (архив v1 + миграционный target v2). С ними решается отдельно (см. предыдущий аудит веб-панелей). **Не удалять.**

### Итого по лишним файлам вне харнеса

| Категория | Файлов | Относится к харнесу? | Используется? | Действие |
|---|---|---|---|---|
| **F1** `.tools/codeception/` | 88 | ❌ (продукт) | частично (browser-verify) | вынести/gitignore |
| **F2** `.cursor/mcp-stack/` | 10 | ⚠️ legacy | нет (superseded) | удалить/архив |
| **F3** `EXPORT_NEXT_STEPS.md` | 1 | ❌ temp | нет | удалить |
| **F4** `.doc/harnes/dsh/*.json` | 6 | ✅ (generated) | генерируемые | gitignore |
| **F5** `.../documentation-queue-migration.md` | 1 | ✅ draft | нет | доработать/архив |
| **F6** web/web2 src | ~50 | ✅ (панели) | харнес | не трогать |

**Главный лишний блок:** **F1 `.tools/codeception/`** (88 файлов, продуктовая e2e-стимка) — это самый крупный «не-харнес» мусор.

---

## 14. Сводка очистки мусора + лишних файлов

**В харнесе (previous sections):** CopyTrust (G1), legacy find-task-branch (G2), SyntaxError (G3), one-off (G4), web/web2-дубли (G5), неактивные MCP (G6).
**Вне харнеса (orphan, this section):** продуктовая codeception-стимка (F1), legacy mcp-stack (F2), temp EXPORT_NEXT_STEPS (F3).

**План очистки (объединённый):**
1. **P1:** CopyTrust rename (G1) + удалить стимку; удалить `find-task-branch.ps1` (G2); исправить 2 SyntaxError (G3).
2. **P2:** Определить с `.tools/codeception` (F1) — вынести/gitignore; удалить `.cursor/mcp-stack` (F2); удалить `EXPORT_NEXT_STEPS.md` (F3).
3. **P3:** archive, dsh-json (gitignore), черновики, web/web2 синхронизация.
4. **Контроль:** CI-gate скан мусора (SyntaxError/orphan/CopyTrust/deprecated).

**Важно:** скилы не трогали. Очистка — по согласованному плану; F1/F2 требуют решения (вынести или оставить).

---

## 15. Связи
- Дублирование CLI: `.doc/arena/research/audit-cli-duplication.md`
- Рефакторинг-аудит: `.doc/arena/research/audit-cli-refactoring.md`
- Система документации: `.doc/arena/research/audit-documentation-system-defects.md`
- Система задач: `.doc/arena/research/audit-task-system.md`
- Ренема CopyTrust: `.doc/arena/research/rename-copytrust-to-seharnes.md`

*Аудит выполнен по инвентаризации, поиску markers, кодовому сканированию дубликатов, проверке вызовов/активности MCP, orphan-сканированию (входящие ссылки по имени) и прогону py_compile для всех папок харнеса и git-репозитория.*
