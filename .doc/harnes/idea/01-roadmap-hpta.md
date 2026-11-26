# Roadmap H/P/T/A: не внедрено (проверено кодом 2026-10-02)

<!-- meta
type: plan
status: draft
updated: 2026-10-02
related: [../index.md, ./02-pending-proposals.md, ./03-plan-audit-x3.md, ./04-planx-improvements.md]
tags: [harness, roadmap, pending]
-->

---

## Суть

Исполняемый план улучшений, НЕ внедрен. Статус каждого пункта проверен по коду
2026-10-02 (см. раздел 0): из 21 пунктов не внедрен ни один. Порядок и приемка
актуальны как есть. Это единственный источник roadmap, дубликатов нет.

---

## 0. Статус внедрения (проверка кодом 2026-10-02)

| Пункт | Проверка | Результат |
|---|---|---|
| H-01 | `git add -- path1 path2` без кавычек в send-to-git SKILL.md:85 | не внедрено |
| H-02 | нет Invoke-GitWithTimeout/FetchTimeoutSec в task-diff.ps1 | не внедрено |
| H-04/H-05 | нет iter_errors/Draft202012/--init в generate_report.py | не внедрено |
| H-06 | нет .doc/docscripts/resolve-task-artifact.py | не внедрено |
| H-07 | нет scope_errors/out_of_scope в task-test.sh, qa-lint.py | не внедрено |
| H-08 | нет run_precheck infra / status blocked в task-test.sh | не внедрено |
| P-01..P-05 | нет гейтов unverified user decision / test stub / shared IN/OUT / reuse inventory в validate_plan.py (git-history и IN/OUT на open branch из F5 уже есть, это другое) | не внедрено |
| P-06 | нет .doc/docscripts/plan-audit-x3.py и .cursor/plan-audit-x3.json | не внедрено |
| T-02..T-04 | нет harness-metrics.py, нет watchlist-фикстур в test_validate_plan.py | не внедрено |
| A-01..A-03 | нет task-state.py, verify-evidence.py, harness-adapters.json | не внедрено |

Частичные пересечения с внедренным (не считать готовым): SKILL-текст T3-сверки
и гейты jsondoc plan verify (ledger_missing, test_stub_patch, SOURCE_STALE,
before_not_unique) существуют со внедрения F5-F7 (см. state/08, state/10).
Roadmap-пункты требуют отдельной реализации в validate_plan.py и скриптах.

---

## 0.1. Контекст исходника

Источник: план `harnesaudit.md` (2026-09-30, исполняемый для внедрения агентом).
База на момент написания: 24 пары аудитов (60 incidents, 46 recommendations,
35 proposed и 11 implemented), 177 задач в `.doc/tasks/`, 22 скила. Каждый пункт
содержит файлы, якоря кода, точную правку, команды проверки и критерии приемки.
Волны: 0 разблокировка, 1 gates prepare-plan, 2 throughput, 3 архитектура.

Правила внедрения для всех пунктов: править только канон `.cursor/` и `.doc/`
скрипты. Зеркала `.codex`, `.kilo`, `.agents`, `.antigravity`, `.gemini` не трогать
руками, только через `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`. Перед правкой компонента
История компонента: History планов и `doc.md` задач. После
правки соответствующий тест плюс verify_parity.py плюс синк. Статус implemented
только с evidence. Стиль текстов по text-style.mdc: дефис вместо длинного тире,
обычные кавычки, без эмодзи.

---

## 0. Карта якорей кода (прочитано 2026-09-30)

| Компонент | Файл | Якорь |
|---|---|---|
| prepare-plan adapters | `.agents/skills/prepare-plan/ADAPTERS.local.md` | 74 строки, таблица Adapter и Value, секция BLAST_RADIUS_LADDER Tier 0-8, секция Timeouts P6. |
| prepare-plan validator | `.agents/skills/prepare-plan/scripts/validate_plan.py` | 237 строк. validate_json_view строки 34-73 (делегация в jsondoc plan verify, timeout 120). validate строки 76-178 (ledger, blame, research_complete). validate_ledger строки 195-220 |
| task-diff | `.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1` | 734 строки. Sync-Origin строки 128-168: `Invoke-GitRaw fetch origin` строка 146 без таймаута, `ls-remote --heads origin` строка 157 без таймаута. Get-RemoteHeads строки 86-92. Get-RemoteBranchSha строки 205-212 |
| send-to-git | `.agents/skills/send-to-git/SKILL.md` | 178 строк. Шаг 3 строки 83-87: `git add -- path1 path2` без кавычек. Шаг 4 строка 96: ветка в кавычках, пути без |
| task-change-report generator | `.agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/generate_report.py` | 1145 строк. `jsonschema.validate(model, ...)` строка 927, catch ValidationError строка 928 с текстом только первой ошибки строка 929. Jira validate строки 1053-1055 аналогично. `validate_mermaid_diagram` строки 40-88 |
| workflow contract | `.agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/workflow_contract.py` | 278 строк. `_validate` строки 28-59 собирает все ошибки в список. preflight строки 132-245 возвращает все errors сразу. main строки 248-274. Контракт уже multi-error, генератор нет |
| schemas | `.agents/skills/task-router/children/reporting-router/children/task-change-report/templates/report-model.schema.json` | 66 строк, schema_version const 2.0, required 11 полей. workflow-context.schema.json 65 строк, version integer enum 1, input_hash pattern hex 64 |
| qa-lint | `.agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-lint.py` | 199 строк. changed_files строки 17-30 (git status porcelain). `--task` строки 102-113: добавляет `tasks/{N}/tests/**/*.php`, Support только при `--with-support`. Patch фильтр строки 138-166 через `static-on-diff.filter_to_patch` с `slack=0` |
| task-test.sh | `.agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh` | 236 строк. run_precheck строки 63-82: static, phpunit, branch-audit non-blocking, остальные ставят PRECHECK_CODE 1. Пречеки строки 91-104. PRECHECK_CODE не 0 блокирует browser строки 121-128 и 161-164 |
| branch-audit | `.agents/skills/task-router/children/testing-router/children/test-task/scripts/branch-audit.py` | 133 строки. iter_plan_sources строки 22-58 уже умеет task.json artifacts плюс `stage*/plan.md` плюс plan.md. Проблема не в поиске плана, а в отсутствии scope-фильтра и в вызове без resolver |
| static-on-diff | `.agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py` | `filter_to_patch(errors, patch, slack)` строки 284-294, slack 0 после blame строка 299, changed_lines строка 153 |
| component registry | `.agents/skills/harness-router/children/improvement/scripts/component_registry.json` | ключи version, components, 28 компонентов |

---

## Волна 0: разблокировка (H-01 - H-08)

### H-01. Квотирование путей в send-to-git и task-diff

Проблема: путь `templates/payments/include/js_&_css.tpl` сломал `git add` в задаче 2555.
Bash воспринял `&` как фон. Evidence: `audit-54b39f6d` I1, R-01 proposed P2.

Файлы: `.agents/skills/send-to-git/SKILL.md` строки 83-87 и 96;
`.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1` места сборки git add (найти по `git add`).

Правка send-to-git: Before строка 85 `git add -- path1 path2`; After
`git add -- "path1" "path2"`; добавить в Жесткие правила пункт каждый путь в git add
в двойных кавычках, пример с `&` в пути; в шаге 4 уточнить выполнять add массивом
quoted путей, не конкатенацией. Правка task-diff.ps1: найти все места
`Invoke-Git ... @("add", ...)` и обернуть каждый путь в кавычки либо передавать
массивом без ручной склейки строк.

Проверка: `touch "test_&_file.tmp" && git add -- "test_&_file.tmp" && rm "test_&_file.tmp"`,
`powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/task-router/children/task-diff/scripts/task-diff.ps1 -TaskNumber 2555 -Action inspect`.
AC: команда из SKILL с путем содержащим `&`, пробел, `#` выполняется с первого раза;
inspect для 2555 завершается exit 0. Приоритет P1. Объем small. Риск низкий.

### H-02. Таймаут сетевого git в task-diff.ps1

Проблема: Sync-Origin висит до 120 секунд при медленном origin, задача 2427 осталась
без diff.md. Evidence: `audit-2060f499` I3 и R-02 proposed P2.

Файл: `.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1` строки 128-168. Текущее:
строка 146 `$fetch = Invoke-GitRaw $Repo @("fetch", "origin")` без таймаута; строка 157
`$headsProbe = Invoke-GitRaw $Repo @("ls-remote", "--heads", "origin")` без таймаута;
строка 206 `Invoke-GitRaw ls-remote origin refs/heads/$Branch` без таймаута.

Правка: добавить функцию `Invoke-GitWithTimeout($Repo, $GitArgs, $TimeoutSec=30)`
на базе `Start-Job` плюс `Wait-Job -Timeout 30` плюс `Stop-Job`; в Sync-Origin заменить
прямые вызовы fetch и ls-remote на вызов с таймаутом 30; при таймауте
`$state.mode = "local-fallback"`, `$state.error = "timeout after 30s: fetch origin"`,
продолжить на Get-LocalHeads; добавить параметр `[int]$FetchTimeoutSec = 30` в param
блок строки 1-16; в Get-RemoteBranchSha аналогично обернуть ls-remote таймаутом 30,
при таймауте бросать понятное `origin ls-remote timeout after 30s`.

Проверка: `task-diff.ps1 -TaskNumber 2427 -Action generate -SkipFetch`, затем
с недоступным origin должен завершиться менее чем за 60 секунд с originSync local-fallback.
AC: при заблокированном origin скрипт завершается за меньше 60 секунд; diff.files.md
содержит `originSync: local-fallback`; diff.md создается из локальных коммитов.
Приоритет P1. Объем small. Риск средний (PowerShell jobs на Linux и WSL проверить).

### H-04. Все ошибки валидатора генератора отчета за один прогон

Проблема: generate_report.py показывает одну ошибку схемы, агент делает до 9 итераций.
Evidence: `audit-2060f499` I1 и I2 и R-01, `audit-b6712d84` R4, `audit-f97b29ba` R-03.

Файл: `.agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/generate_report.py` строки 920-929
и 1053-1055. Текущее строки 927-929: `jsonschema.validate(model, ...)`, catch
ValidationError с текстом только первой ошибки. Правка: заменить на сбор всех ошибок
(Draft202012Validator, iter_errors, сортировка по path, details с at, message, expected
до 200 символов, raise ValueError с count и JSON details до 4000 символов). Аналогично
для jira блока строки 1053-1055 собрать iter_errors для jira подсхемы. Формат ошибки
обязан содержать count плюс список at и message, не только первую.

Проверка: построить bad-model (schema_version `1.0`, убрать `task.full_text`),
запустить генератор, первые 20 строк вывода. AC: модель с 3 ошибками возвращает все 3
за один запуск; сообщение содержит `3 errors` и пути полей. Приоритет P1. Объем small.
Риск низкий. Зависимость: установленный jsonschema (уже импортируется).

### H-05. Команда init и эталонный пример модели отчета

Проблема: агент угадывает 20 обязательных полей и regex. Связана с H-04. Evidence те же.

Файлы: generate_report.py (добавить subcommand init), task-change-report SKILL.md
(добавить пример), шаблоны report-model.schema.json и workflow-context.schema.json
как источник полей. Правка: добавить в generate_report.py режим
`--init --task {N} --out dir`: читает обе схемы, строит минимальный JSON со всеми
required полями, плейсхолдеры вида `TODO: ...`; для report-model.json schema_version
2.0, task id, title, stage, full_text, summary 4 поля, logic before, after, delta
с source, changes 1, diagrams 2 с `flowchart TD`, tests, timeline, risks, evidence,
jira с text оканчивающимся на `релиз X.Y.Z`, limitations пусто; для workflow-context.json
version 1, scope kind task и stage, allowed_steps diff, documentation, html, jira,
sources 1 с sha256 заглушкой, facts 1, steps 4 ключа со status pending. В SKILL.md после
раздела Запуск вставить полный минимальный пример обоих JSON (взять из init вывода,
не выдумывать поля).

Проверка: `generate_report.py --init --task 2556 --out /tmp/init-2556`,
затем генерация из init модели. AC: init создает два валидных по структуре JSON;
второй запуск не падает на схеме (может упасть на stale hash, нормально).
Приоритет P1. Объем medium. Риск средний (не выдумывать поля, только из схем).

### H-06. Resolver артефактов multi-stage задач

Проблема: при stage2 и stage3 неясно где актуальный plan, diff, матрица, verdict,
report. Задачи 2548 (5 stage), 2602, 2605, 2427.

Новый файл: `.doc/docscripts/resolve-task-artifact.py`. Спецификация: CLI
`resolve-task-artifact.py {N} --type {plan|diff|test-matrix|verdict|report|all} [--json]`.
Логика plan: читать `.doc/tasks/{N}/task.json` artifacts role plan по приоритету
(как branch-audit.py строки 27-46), затем `stage*/plan.md` с Decomposition по убыванию
номера stage, затем корневой plan.md, вернуть один путь. Логика diff: корневой diff.md
плюс diff.files.md как полные, `stage*/diff.md` как partial если есть. Логика
test-matrix: test.md плюс `stage*/ac-matrix.json` если есть. Логика verdict: последний
по mtime `.doc/tasks/{N}/test-runs/*/verdict.json`. Логика report:
`reports/change-report/report.html`, fallback `stage*-change-report/report.html`.
`--type all` возвращает JSON со всеми пятью ключами. Exit 0 плюс путь и JSON. Exit 2
если артефакт не найден, с текстом что именно отсутствует.

Интеграция: branch-audit.py уже умеет iter_plan_sources, оставить как есть,
но task-test.sh и SKILL task-change-report, prepare-plan должны вызывать resolver
перед чтением. Документировать в task-doc SKILL.md режим A: сначала resolver,
затем чтение.

Проверка: `resolve-task-artifact.py 2548 --type plan`,
`resolve-task-artifact.py 2548 --type all --json`,
`resolve-task-artifact.py 2427 --type diff`. AC: для 2548 plan возвращает
`stage4/plan.md`, не корневой; для 2427 diff сообщает отсутствие diff.md exit 2;
для 2605 verdict возвращает последний по mtime. Приоритет P1. Объем medium. Риск низкий.

### H-07. Scope-aware пречеки без ложных блокировок

Проблема: task-test.sh блокирует browser при провале lint, doctor, ac-source, хотя часть
провалов вне scope задачи. qa-lint.py уже сужает JS до patch (`slack=0`), но PHP линт
и doctor идут по всем changed files.

Файлы: task-test.sh строки 63-82, 91-104, 121-128; qa-lint.py строки 17-30, 102-166;
static-on-diff.py filter_to_patch. Правка task-test.sh: разделить пречеки на blocking
(по scope) и advisory (вне scope): blocking branch-audit, ac-source, db-before,
manifest; advisory по умолчанию doctor, static, lint, phpunit фиксируются
в prechecks.jsonl, но не ставят PRECHECK_CODE 1, если ошибки только вне scope.
Реализация: каждый python пречек при `--task` обязан вернуть JSON с полями status,
scope_errors, out_of_scope_errors. Shell ставит PRECHECK_CODE 1 только если
scope_errors больше 0. Для qa-lint.py расширить patch-фильтр на PHP (сейчас только JS
строки 138-166). PHP ошибки вне patch идут в out_of_scope_errors. Для doctor.py
добавить `--task` фильтр по файлам задачи, остальное advisory.

Проверка: `qa-lint.py --task 2605 --run-dir /tmp/lint-2605`, чтение lint.json status
и errors, `task-test.sh --help`. AC: прогон 2605 с 50 чужими файлами Support
не блокируется, если patch чистый; prechecks.jsonl содержит разделение scope и
out-of-scope; Browser запускается при advisory-only провалах. Приоритет P0. Объем
medium. Риск высокий (трогает gating). Обязательно фикстуры обоих направлений.

### H-08. Явный blocked при недоступной инфраструктуре

Проблема: при мертвом стенде :8030 или chromedriver :9515 агент уходит в ручные обходы
(manual phpunit, прямой codecept, smoke). Задачи 2548, 2427, 2605.

Файлы: task-test.sh (добавить infra check перед пречеками), doctor.py (проверить формат,
дополнить), test-task SKILL.md и browser-verify SKILL.md (документация). Правка:
в task-test.sh после строки 58 добавить `run_precheck infra`: `curl -m 5` стенд
и chromedriver status; при недоступности записать verdict.json со status blocked,
reason, next_step, завершить exit 3 без запуска codecept и без предложений обхода.
В SKILL test-task и browser-verify добавить обходы запрещены, только blocked.

Проверка при остановленном стенде: `task-test.sh 2555 --phase browser`, чтение
verdict.json reason. AC: при мертвом стенде прогон возвращает blocked, не запускает
smoke; verdict содержит reason и next_step. Приоритет P1. Объем small.

---

## Волна 1: gates prepare-plan (P-01 - P-06)

### P-01. Gate user decision против brief

Проблема: решение из чата против Jira прошло P7 в 2548. Evidence: `audit-0223f270`
I1 high, R-01 proposed P1, fingerprint `554ecb3fcca0b476df5f37b705ce5c9ce2295dc8a09
2c036a9108f216082fd00`.

Файлы: prepare-plan SKILL.md раздел P7, validate_plan.py функция validate,
plan.template.md. Правка SKILL: в P7 обязательный подпункт если Sources of truth
содержит строку kind user, план обязан содержать секцию `User decisions vs brief`
с тройкой для каждого T-user (цитата чата, цитата brief, вердикт совпадает и
отличается с причиной). При расхождении без причины audit_status не может быть passed.
Правка validate_plan.py: мягкий гейт если текст содержит `kind=user` или T3
и `status: ready` или passed, требовать секцию User decisions vs brief или подстроку
T3 в Acceptance criteria out-of-scope. Отсутствие ошибка unverified user decision.
Для draft молчать. Фикстуры в test_validate_plan.py: позитив план с T3 плюс секция
проходит, негатив план ready с T3 без секции падает. AC: план 2548-v1 (решение
не фильтровать при брифе фильтровать) падает с unverified user decision.

### P-02. Gate ready требует свежий evidence

Проблема: ready без ledger, stub S, byte-broken After. Evidence: `audit-669740`
I1 high, I2 critical, I3 high.

Файл: validate_plan.py строки 147-178. Правка: усилить проверку ledger (уже есть
missing research evidence ledger строка 170, добавить проверку свежести plan_hash
уже в validate_ledger строка 200 и content_hash для каждого patch, entry, caller
строки 212-219). Добавить проверку stub: в After блоках запретить маркеры
`assertTrue(true)`, TODO, placeholder, пустые fences, найти в After тексте, ошибка
test stub patch. Добавить проверку S-покрытия: для каждого S в Decomposition требовать
упоминание в test.md либо явный manual с причиной, использовать логику branch-audit.py
как референс. Фикстуры: ready без ledger падает (уже есть, проверить), ready
со stale plan_hash падает, ready с `assertTrue(true)` в After падает. AC: fixtures
зеленые, реальный план 2427 stage3 проходит.

### P-03. Gate shared entrypoints с IN и OUT

Проблема: shared payment спланирован до reuse inventory. Evidence: `audit-a17965`
I1 critical, I2 high, R1 и R2 proposed P0.

Файлы: SKILL P1.1, validate_plan.py, component_registry.json зависимость prepare-plan
to git-task-blame уже есть. Правка SKILL P1.1: если файл имеет больше 5 inbound
(CBM trace_path или Serena references), требовать whole-file Read всех callers плюс
IN и OUT таблицу в плане (колонки Caller, Поведение до, Поведение после, Покрыто brief
да и нет, Действие opt-in и AskQuestion). Для OUT без покрытия запретить ready.
Правка validate_plan.py: если Git-история правок содержит open branch и нет IN и OUT,
уже падает строки 163-165. Расширить: если план содержит слово shared и нет секции
IN и OUT, падать с shared change without IN/OUT. AC: план shared PaymentService
без таблицы падает.

### P-04. Gate reuse inventory до патчей

Проблема: research после дизайна патчей. Evidence: `audit-6f3401` I2, `audit-a17965`
I2, R2 proposed P0.

Правка SKILL P2.7: перед Правки по файлам требовать frozen inventory (список
проверенных существующих методов domain с вердиктом reuse и not-found, зафиксированный
в research-ledger.json entries с role reuse). Новое правило: новый класс
в Decomposition без записи reuse-search в ledger блокирует ready. Правка
validate_plan.py validate_ledger: если в плане есть новый файл или new class, искать
в ledger entry с role reuse и именем domain. Отсутствие ошибка reuse inventory missing
for new code. AC: план с новым TaxCalculator без reuse записи падает.

### P-05. Gate open branch conflict

Проблема: history после claims. Evidence: `audit-a17965` I4 high, R4 proposed P1.

Файл: validate_plan.py строки 153-165 уже проверяют blame покрытие и IN и OUT
при open branch. Усилить: требовать в blame таблице для каждого patch файла колонки
last task, last commit, open branches, diff vs HEAD (empty и non-empty). Если open
branch найден и нет согласован, accepted, решен, падать (уже есть, проверить на живых
планах 2555 и 2556). В SKILL P0.5b добавить проверять не только имя ветки через
ls-remote, но и `git diff HEAD...origin/branch -- path` для диапазона. AC: фейковая
ветка с правками в том же файле ловится аудитом.

### P-06. Adversarial pass для medium и large (пилот)

Проблема: самопроверка пропускает семантику. Evidence: 8 high плюс 5 critical
за 24 пары. База: plan_audit.md 377 строк (draft, отдельный SKILL запрещен, только
оркестратор).

Правка: не создавать новый SKILL. Создать оркестратор `.doc/docscripts/plan-audit-x3.py`
(вход task N, scope, plan path, config `.cursor/plan-audit-x3.json` создать по образцу
из plan_audit.md раздел 4.1; считает sha256 плана как plan_sha256; запускает три
аудитора параллельно subagent или последовательные вызовы validate плюс jsondoc verify
плюс git-task-blame; aggregator собирает summary.json; exit 0 только если все три
passed). Порог только min_scope_size medium и выше. Trivial и small идут одиночным P7.
AC: план с T3-conflict ловится хотя бы одним из трех проходов. Приоритет P1,
после P-01 - P-05. Объем large. Риск токены x3, только для medium плюс.

---

## Волна 2: throughput (T-02 - T-04)

### T-02. Отклонить или отложить P2 и P3 с причиной

Каждую proposed старше 2 недель: implemented, deferred с условием живого кейса,
rejected с причиной. Формат как в audit2-report.md раздел Не внедрено. Метрика:
proposed старше 2 недель 0.

### T-03. Метрики харнеса

Новый скрипт `.doc/docscripts/harness-metrics.py`: вход `.doc/tasks`; выход `.doc/harness-dashboard.json` с ключами full_cycle_rate,
manual_bypass_count, blocked_infra_rate, avg_validator_iterations, missing_diff_rate,
missing_report_rate, stale_artifact_count, proposed_age_buckets, incidents_by_component,
incidents_by_cause. Эвристики: manual bypass искать по manual в test-runs путях
и smoke в test.md; stale verdict mtime больше 7 дней; missing diff по отсутствию diff.md.
Запуск еженедельно, результат в dashboard. Цели через 3 месяца: full cycle 68 в 85
процентов, ручные обходы 30 в 5, blocked 15 в 5, итерации JSON 5-9 в 1-2, без diff 23
в 10, без report 20 в 10, proposed 35 в 5, prepare-plan incidents 48 в 20 процентов.

## Волна 3: архитектура (A-01 - A-03)

### A-01. State machine задачи

Новый скрипт `.doc/docscripts/task-state.py`: `task-state.py {N} --status` читает
артефакты через resolver H-06 и выводит 9 переходов (resolved, scope, artifacts,
plan-verified, implemented, tested и blocked, reported, diff-current, documented,
audited). Каждый переход проверяется машиной: файл существует, hash свежий, verify
exit 0. State хранится в `.doc/tasks/{N}/state.json`, обновляется skills после каждого
шага. Skills проверяют входной state перед работой, отказываются при неготовом входе.

### A-02. Канонический evidence

Каждый skill пишет `.doc/tasks/{N}/_evidence/{step}.json` (пример: step plan-verified,
timestamp, tool `jsondoc.py plan verify`, input_hash, output status passed checks 10,
artifacts `_jsondoc/plan-verifications/20260930/`, next_step implementation-checked).
Скрипт verify-evidence.py проверяет цепочку hash. За месяц перевести 5 skills:
prepare-plan, test-task, browser-verify, task-change-report.

### A-03. Унификация адаптеров

Новый `.doc/harness-adapters.json` с ключами DOCS_ROOT, TASK_DIR, BLAST_RADIUS_LADDER, TIMEOUTS. Генераторы synh_harnes разносят в форматы 5 сред.
ADAPTERS.local.md становится рендером этого JSON, не ручным файлом.

---

## Порядок внедрения агентом (12 шагов)

1. H-01 кавычки send-to-git плюс
фикстура с `&`. 3. H-04 multi-error генератора плюс проверка на 3 ошибках. 4. H-02
таймаут task-diff плюс проверка fallback. 5. H-05 init команда плюс пример в SKILL.
6. H-08 infra blocked плюс verdict blocked. 7. H-06 resolver плюс проверки
на 2548, 2427, 2605. 8. H-07 scope-aware пречеки плюс фикстуры обоих направлений.
9. P-01 user против brief gate плюс фикстуры. 10. P-02 ready evidence gate плюс
фикстуры. 11. P-03 - P-05 остальные gates по одному за проход. 12. T-02 - T-04
throughput параллельно с волной 1. После каждого шага: тест компонента,
verify_parity.py, sync-agent-views.sh.

## Риски

1. Ложные блокировки при новых gates: каждый gate с позитивной и негативной фикстурой.
2. Рассинхрон 5 сред: только канон, затем синк, проверка parity. 3. Токены x3
при adversarial: только medium плюс. 4. PowerShell jobs на Linux: проверить Start-Job
на WSL перед H-02. 5. jsonschema версия: использовать Draft202012Validator как в схемах.

---

## Связи

- [Точка входа](../index.md) - карта каталога и список на удаление
- [Предложения P1-P15](./02-pending-proposals.md) - предложения audit2
- [Анализ prepare-plan](./03-plan-audit-x3.md) - разбор контура и оркестратор x3
- [Индекс задач](../../tasks/index.md) - 177 задач

---

## История изменений

- 2026-10-02: создан переносом harnesaudit.md без потерь, статусы проверены кодом
