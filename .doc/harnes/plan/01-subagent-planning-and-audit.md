# Поэтапное планирование, независимые аудиты и исполнение на субагентах

<!-- meta
type: plan
status: draft
updated: 2026-11-06
related: [../plan.md, ./deepseek.md, ./02-project-index-and-business-knowledge.md, ./03-web-testing-system.md, ./04-knowledge-store-and-queue.md, ./05-bug-hunt-and-modernization.md]
tags: [harness, planning, audit, subagents, testing, portability]
-->

## Суть

Цель: исследовать проблему один раз, передать квалифицированным субагентам небольшие проверяемые задания и принимать результат по доказательствам. Главный чат не должен сам выполнять все исследование, планирование и повторные аудиты.

**Planner тоже работает на субагенте.** Для закрытого локального этапа используется самая дешевая модель, прошедшая профильную квалификацию. Неопределенность, shared design и новые доменные решения вызывают эскалацию. Старшая роль означает требуемую квалификацию, а не обязательную дорогую модель на каждом шаге.

Это детализация разделов 9-11 и WP5-WP9 [общего плана](../plan.md). Индексы, источники бизнес-правил и их актуальность описаны в [документе 02](./02-project-index-and-business-knowledge.md). Тестовые контракты, browser providers и стенды описаны в [документе 03](./03-web-testing-system.md).

Документ предлагает новые интерфейсы. Показанные команды, модели конфигурации и leaf-компоненты не объявляются существующими. В этом проходе меняется только документация, не код, глобальные настройки, продуктовые тесты или CI/CD.

Ни план, ни несколько аудиторов не гарантируют отсутствие ошибок. Система обязана обнаруживать известные классы отказов, показывать непроверенное и не превращать отсутствие инструмента в passed.

> **Обновление 2026-11-10.** Замороженные хеши плана и источников в текущем
> каноне не используются. `audit-plan` правит `plan.md` на месте, помечает каждую
> правку номером прохода и датой, ведет журнал `## Аудит плана`, а версия плана
> задается целым `plan_rev`. Требования `plan_hash`, `snapshot_hash` и отдельного
> `plan-audit.json` ниже читать как исторический проект.

## 2. Что сохранить и что заменить

| Сейчас | Сохранить | Изменить |
|---|---|---|
| `prepare-plan`: T/AC/R/S и Before/After | Трассировку требования до операции и проверки | Planner получает ограниченный evidence capsule; не весь чат |
| Аудит внутри P7.4a | Механические проверки исходника и полноты | Независимый audit leaf, общий verifier, compatibility alias |
| `git-task-blame` | Историю точного диапазона и прежние инварианты | Скрипт собирает факты; reviewer оценивает только релевантный риск |
| `test-task` и browser skills | Runner, Page/Step, сценарии и артефакты | Исполнимые проверки до patch; точные case/run IDs |
| JSONdoc и research ledger | Каноническую модель, hashes, generated views | Строгие схемы, stage DAG, provenance и единый reducer |

Проверенные причины изменения: `prepare-plan/SKILL.md:23` обещает нулевой шанс ошибки слабого исполнителя, а строка 66 запрещает отдельный audit skill. Эти утверждения заменить проверяемой квалификацией и разделением ролей. В `jsondoc/plan_verify.py:149-153` hash проверяется лишь при наличии; для исполнимого packet обязательны все preconditions. Пустой ready и неразобранный ledger уже воспроизведены в findings F02/F03 [общего плана](../plan.md#41-проверки-планов-и-тестов).

## 3. Основной цикл

```text
intent -> WorkContext -> bounded research tasks -> evidence capsules
       -> scope/test contract -> stage planners -> plan integrator
       -> mechanical verify -> independent audits -> global coverage audit
       -> materialize tests -> test/oracle fidelity -> baseline/expected RED
       -> executable stage -> packet executor -> GREEN + impacted invariants
       -> implementation audit -> next eligible stage
       -> global integration/regression/browser -> docs -> complete
```

Это граф зависимостей, а не требование писать все разделы для каждого вопроса. Простой вопрос заканчивается ответом с источниками. Маленькая правка получает один stage и минимальный набор проверок. Наличие Jira, ветки или номера задачи не является условием работы.

У каждого запуска есть `work_id`, `project_id`, `worktree_id`, `scope`, `baseline_ref` и contract version. Внешняя задача является опциональным `task_ref={provider,project,external_id}`, как в общем WorkContext. Обнаружение другого проекта или рабочего дерева останавливает запуск.

## 4. Роли и ленивые leaf skills

Предлагаемое логическое дерево указано относительно `SKILLS_ROOT` установленного профиля. Генератор переводит component IDs в разрешенные пути конкретной среды; абсолютные пути и чужие mirror roots в инструкции не попадают.

```text
task-router/
  children/planning-router/
    SKILL.md                         # только выбор роли
    children/research-scope/SKILL.md  # ограниченное исследование
    children/plan-stage/SKILL.md      # локальный planner-субагент
    children/integrate-plan/SKILL.md  # один владелец общей модели
    children/audit-plan/
      SKILL.md                       # risk-based маршрутизация аудита
      children/audit-business/SKILL.md
      children/audit-security/SKILL.md
      children/audit-history-regression/SKILL.md
      children/audit-test-oracle/SKILL.md
      children/audit-global-coverage/SKILL.md
  children/implementation-router/
    SKILL.md
    children/implement-stage/SKILL.md
    children/audit-implementation/SKILL.md
  children/testing-router/            # существующий роутер
    children/design-test-scenarios/   # новый leaf
    children/prepare-task-test/       # существующий, portable facade
    children/test-task/               # существующий, verify-work facade
    children/browser-verify/          # существующий browser provider
prepare-plan/SKILL.md                 # совместимый вход в planning-router
```

Новые листья не создавать заранее пустыми. Сначала shared schema/runner и тесты, затем минимальные entry contracts. Existing `prepare-plan` и audit-only alias временно переводят запросы в новые компоненты без дублирования процедур.

| Роль | Вход и выход | Разрешения и предел |
|---|---|---|
| Coordinator | WorkContext, policy -> задания и состояние | Не утверждает смысл вместо профильного reviewer; не порождает дерево без лимита |
| Research worker | Вопрос, seeds, budget -> capsule | Read-only; расширение scope только запросом coordinator |
| Stage planner | Capsule, AC, interfaces -> stage proposal | Не пишет продукт; не меняет глобальные AC и oracle |
| Plan integrator | Stage proposals -> canonical plan/DAG | Единственный writer модели; проверяет межэтапные зависимости |
| Audit workers | Frozen input -> typed findings/coverage | Read-only; не исправляют проверяемый план |
| Test author | Approved scenario -> test sources | Не меняет expected ради green; пишет только tests write-set |
| Stage executor | Executable packet -> operation/check receipts | Закрытые команды; scope expansion и неизвестная ошибка останавливают шаг |
| Implementation reviewer | Approved operation, actual diff, results -> findings | Не подменяет отсутствующие проверки рассуждением |

Integrator и coordinator могут быть одним процессом, если остаются разные обязанности и единственный владелец записи. Они не становятся независимыми аудиторами собственного решения.

### 4.1. Почему дерево не означает лишний контекст

- Parent содержит краткую таблицу детей, условия выбора и negative triggers.
- В runtime видны только необходимые роли либо компактный flattened registry, если нативного lazy discovery нет.
- Вызов конкретного leaf не требует читать все родители, соседей и их references.
- Skill body, evidence и tool schemas загружаются только для текущей роли.
- Runtime smoke измеряет фактически загруженные descriptions и bodies; вложенная папка сама по себе не гарантирует ленивую загрузку.

### 4.2. Четыре разных механизма

| Механизм | Что хранит | Чего не делает |
|---|---|---|
| Portable role manifest | Роль, proof obligations, input/output schema, model alias и capability needs | Не запускает процесс и не назначает реальные permissions |
| Native actor config | Подтвержденный mapping роли в subagent/fresh-session конкретного runtime | Не заменяет skill и не гарантирует фактическую модель при fallback |
| Role SKILL и references | Ленивую предметную инструкцию: business/security/history/oracle/execution | Сам по себе не создает новый контекст, не переключает модель и не изолирует запись |
| Deterministic runner | Queue/deadlines, artifact validation, model/qualification checks, операции и reducer | Не придумывает бизнес-смысл вместо planner/reviewer |

Каждый audit leaf задает свой набор proof obligations с IDs. Выход содержит `obligation_id -> evidence_ref -> done/unresolved/not_applicable(reason)` и проверенный coverage subset. Один общий passed без этих строк не закрывает роль. Discovery adapter публикует только parent или краткие child metadata без двойного каталога.

## 5. Ограниченное исследование до планирования

Coordinator создает задания по вопросам, а не по произвольным папкам. Примеры: кто меняет состояние заявки; где проверяется владелец; какие старые задачи добавили защиту повторов; чем подтверждается schema. Независимые read-only задания исполняются параллельно.

Задание содержит `question_id`, relevant AC/risk, known symbols, allowed corpus, capabilities, limits, expected evidence и stop conditions. Бюджет задается на время, tokens, число расширений и общий fan-out; модель не может его увеличить самостоятельно.

Research capsule содержит:

```text
capsule_id + question_id + work/scope
claims: факт, source ref, source hash, symbol/range, limitation
entry/caller/state/schema links + observed graph coverage
related decisions/history invariants + applicability
unknowns/conflicts + next discriminating check
read_set + index generation + policy/adapter versions
```

Код, комментарии, Jira, документация и tool outputs внутри capsule являются evidence-only данными. Они не могут изменить role policy, command registry, write-set, approvals и источник полномочий oracle. Найденная фраза с просьбой отключить проверку или отправить `.env` не выполняется как инструкция. Trusted role/system policy и пользовательское разрешение передаются отдельно от извлеченного текста.

Индекс дает кандидатов, исходник подтверждает факты, runtime проверяет наблюдаемое поведение. Пустая выдача неполного графа не доказывает отсутствие caller. Обязательное неизвестное состояние не скрывается сокращенной сводкой.

Останавливать поиск, когда обязательные вопросы закрыты evidence или явно blocked, все изменяемые состояния и OUT consumers учтены и дополнительное чтение не изменяет решение. Не требовать чтения всего файла только ради числа строк, но расширять контекст при shared state, implicit flow и динамических вызовах.

## 6. Planner-субагенты и глобальная полнота

### 6.1. Легкий stage planner

Planner получает capsule, связанный AC, утвержденные интерфейсы и бюджет. Если задача закрыта, он формирует patch или строгую операцию, test cases, read/write-set, dependencies, invariants и recovery. Главное условие допуска: профильный eval, а не название модели.

Planner эскалирует при конфликте требований/истории, недостаточном evidence, изменении общего контракта, новой транзакционной границе, неопределенном oracle, невозможности сохранить OUT поведение и превышении контекста. Он возвращает конкретный нерешенный вопрос, а не увеличивает исследование бесконечно.

### 6.2. Интегратор и stage DAG

Plan integrator проверяет полный набор AC и соединяет proposals в DAG. Каждый stage имеет stable ID, цель, входы/выходы, зависимости, write-set, exposed interfaces, test contract и risk. Нельзя объявлять этап независимым, если он читает файл или state, изменяемый соседним этапом.

Глобальная матрица содержит `AC -> rule/source -> stage -> scenario -> case -> required result`. У AC может быть несколько этапов; локальный stage pass не означает закрытие AC, пока не подтвержден их общий результат.

Проверки до публикации:

1. Нет циклов, потерянных AC, orphan stages и несовместимых versions/interfaces.
2. Общие записи имеют порядок либо явный merge owner; разные files не доказывают независимость через БД/events.
3. Cross-stage happy/error/cancel/retry paths имеют сценарии; сохраняемые OUT callers не исчезают из матрицы.
4. Recovery определен для частично примененного шага; no-op является отдельным обоснованным outcome.
5. Общий архитектурный выбор сделан до локальных patches; stage planner не решает его случайно.

### 6.3. Сквозной пример

`BR-PUBLISH-001 v1`: владелец отправляет новую заявку на публикацию; повтор запроса не создает дубликат, чужой пользователь не может отправить ее от имени владельца. Это иллюстрация контракта, не утверждение о текущем CopyTrust.

| Stage | Результат | Проверки по `SC-PUBLISH-001` |
|---|---|---|
| ST-01 | Проверка owner и допустимого состояния на сервере | `CASE-OWNER-NEW`, `CASE-FOREIGN-DENIED` |
| ST-02, зависит от ST-01 | Идемпотентное сохранение/ответ и согласованная транзакция | `CASE-OWNER-NEW`, `CASE-OWNER-REPLAY`, parallel replay при соответствующем риске |
| ST-03, зависит от ST-02 | UI action связан с серверным результатом | Реальная роль/route, один пользовательский результат, отказ без чужого side effect |

Business review проверяет смысл owner/replay. Security review пытается обойти авторизацию. History review сверяет прежние исключения. Oracle review проверяет, что тесты различают дубликат и повторный ответ. Global review ловит пример, когда все локальные stages passed, но UI отправляет новый ключ на каждый retry и нарушает ST-02.

## 7. Независимые аудиты

### 7.1. Разные вопросы, не одинаковые три прохода

| Аудит | Что обязан проверить | Когда требуется |
|---|---|---|
| Business | AC, действующие rule versions, state transitions, OUT поведение, конфликты intent/observed | Изменение поведения; краткий scoped pass для low risk |
| Security | Trust boundaries, ownership/tenant, injection, секреты, опасные side effects, abuse/replay | Auth/data mutation/external input; иначе policy `not_required` с причиной |
| History/regression | Применимые прежние решения, точный git range, shared callers, соседние инварианты | Существующий shared код, regression/hotfix, legacy branches |
| Test oracle | Независимый expected, различение RED/infra, negative cases, meaningful assertions | Изменение поведения; усиленный pass для high/critical |
| Global coverage | Все AC, interfaces, combined state/flows, совместимость stage DAG | Любой multi-stage план и финальная интеграция |

Для low-risk role checks можно объединить в один независимый запуск с явной coverage rubric. Разделение компетенций не требует пять моделей на любую строку. Для high/critical business/security/oracle не закрываются авторской самопроверкой.

### 7.2. Frozen input

```text
review_id + review_role + work/scope + stage_or_global
canonical_plan_hash + stage_DAG_hash + requirements/decisions_hash
test_contract_hash + oracle/source refs + business_rule_versions
source/read_set hashes + expected transition chain
schema/config/index fingerprints + policy/adapter version
requested_model_alias + qualification_ref + allowed capabilities
```

Auditor получает исходные требования и доступ к исходникам, не только вывод planner. Его initial pass не содержит findings других аудиторов. Форк полного чата маркируется shared-context review и не выдается за независимую fresh-session проверку.

### 7.3. Typed findings и решение

Finding содержит `id`, `role`, `stage/AC/rule refs`, `location+source_hash`, проверяемое утверждение, контрпример, ущерб, способ проверки, severity и `blocking`. Evidence отсутствует -> `needs_evidence`, а не автоматически подтвержденный дефект.

Coordinator валидирует schema/hash и передает разногласия adjudicator. Тот сверяет counterexample, не считает голоса. **Одна подтвержденная блокирующая находка блокирует переход, даже если остальные reviewers написали passed.** Timeout, missing reviewer и invalid JSON не становятся положительным голосом.

Решение finding: `confirmed`, `refuted_with_evidence`, `needs_evidence`, `accepted_nonblocking_risk`. Непроверенная существенная находка оставляет review incomplete. Снять blocker можно исправлением с перепроверкой либо доказательным опровержением; подписать его как debt ради green запрещено.

Author исправляет proposal через единственного integrator. Новая версия не переписывает старые audit receipts. Измененная стратегия, AC или high-risk interface требуют нового общего аудита; локальная правка проверяется по dependency invalidation.

Design-audited не означает runtime-verified. Если разрешено, runner может наложить patches в изолированный snapshot и исполнить проверки: результат получает отдельный simulation/test receipt с runtime identity. Он не подменяет будущую проверку реального integrated tree и не объявляется продуктовым результатом только по LLM review.

### 7.4. Ограничение циклов

Config задает fan-out, deadline, token budget, число retries технической ошибки и число design iterations. После повторения нерешенного counterexample выдавать `needs_design_review` с evidence, а не автоматически размножать reviewers. Для пилота: не более двух design iterations по одному blocker, затем явная эскалация; значение проверяется экспериментом.

### 7.5. Пошаговый аудит каждого stage

| Шаг | Исполнитель | Обязательный результат до продолжения |
|---|---|---|
| A0. Назначение | Policy runner | Stage risk, обязательные audit roles и proof obligations определены до review; planner не снимает неудобного аудитора |
| A1. Механика | Скрипты | Schema, AC/case links, anchors, read/write-set и зависимости корректны; source scope разрешен |
| A2. Профильные проверки | Независимые role workers | Каждый обязательный reviewer проверил свои obligations на одной frozen версии stage |
| A3. Контрпримеры | Adjudicator с targeted evidence | Подтвержденные blockers исправлены и перепроверены; существенные unresolved не потеряны |
| A4. Межэтапный контракт | Global coverage reviewer | Stage не нарушает интерфейсы соседей, общие AC и сохраненные инварианты |
| A5. Тестовая исполнимость | Test author, fidelity reviewer и runner | Test source соответствует oracle; baseline/expected RED классифицированы; hashes фактических tests связаны с contract |
| A6. Разрешение | Детерминированный reducer | Stage certificate связывает design audit, actual test hashes, expected transitions и допустимый packet |
| A7. После исполнения | Runner и implementation reviewer | Actual diff, GREEN и immediate impacted checks соответствуют сертификату; следующий stage использует подтвержденный postimage |

A2 можно выполнять параллельно, потому что reviewers не меняют вход. Переходы A0-A7 последовательны по зависимостям. Для каждого stage сохраняется собственная матрица role/obligation/evidence; один общий audit всей задачи не заменяет ее. Global audit дополнительно проверяет взаимодействие stages и итоговый бизнес-процесс.

Reuse receipt допустим, если obligation относится к неизмененному read-set и ожидаемому переходу; scope и основание reuse записываются. Изменение актуальных требований, незапланированного source или test oracle возвращает только затронутые stages на нужный audit шаг. Утвержденный переход H0/H1/H2 сам по себе не запускает весь audit заново.

## 8. Выбор моделей и квалификация

### 8.1. Роли не равны ценовым уровням

| Роль | Дешевый профиль допускается | Эскалация |
|---|---|---|
| Research | Точный symbol/history/doc вопрос, bounded read-set | Неоднозначный flow, индексные gaps, противоречивые источники |
| Stage planner | Закрытые AC/interfaces и достаточный capsule | Shared redesign, неопределенные side effects, новый алгоритм вне qualification |
| Semantic auditor | Профильный независимый eval нужной категории риска | Пропущенные blockers, недостаточный контекст/инструменты |
| Test author | Утвержденные oracle/fixtures, шаблонный runner | Неясная проверяемость или test fidelity |
| Executor | Одобренный patch/операция и контролируемые commands | Генеративная задача, неожиданный diff, незнакомая ошибка |
| Integrator | Eval cross-stage coverage и conflict resolution | Несовместимые proposals или global architectural uncertainty |

Qwen/DeepSeek и другие семейства не получают постоянный статус пригодности. Название, параметры, цена и self-confidence не подтверждают квалификацию. Qualification привязана к model/version, runtime/tool profile, context budget, роли, языку и классу риска.

Практичный начальный набор кандидатов: `qwen28b_4k` для closed-patch executor и узкого локального planner, `deepseek_flash` для bounded research/planner/test author, `reasoning_auditor` для сложной интеграции и независимых смысловых проверок. Это aliases пользовательских кандидатов, не подтвержденные provider IDs и не готовый допуск. `reasoning_auditor` тоже может оказаться недорогой моделью после eval. В конкретном проекте допускается один кандидат на несколько ролей, но квалификация и независимые сессии остаются раздельными.

### 8.2. Минимальный eval

Использовать versioned development/holdout cases: корректный локальный stage, ложный capsule, missed OUT caller, changed requirements, oracle tautology, idempotency, owner bypass, stage interface mismatch, stale hashes, tool timeout и переполнение окна. Planner оценивается не только форматом JSON, но правильностью решения и эскалации.

Допуск задается policy: обязательные safety/false-green fixtures не пропускаются ни разу в тестовом наборе; качество решений и recall blockers сопоставляются с reference rubric; стоимость считается с retries и ручными исправлениями. Конкретные пороги и число повторов выбрать до holdout. Конечный eval не гарантирует будущую безошибочность.

Qualification receipt хранит case set hash, настройки, metrics, known limits и срок/условия повторной оценки. Замена модели, quantization, prompt, tools, контекста или parser может инвалидировать допуск. Отсутствие допущенного дешевого профиля -> доступный квалифицированный либо `unsupported`, не скрытое понижение требований.

### 8.3. Нейтральная конфигурация

Следующий YAML является **проектируемой общей схемой**, не native syntax Codex/Cursor/Antigravity. Adapter валидирует mapping и создает поддерживаемый профиль установленной версии.

```yaml
schema_version: 1
orchestration:
  mode: auto
  fallback_order: [native_subagents, sequential_fresh_sessions]
  single_chat: self_review_only
role_models:
  research: bounded-reader
  stage_planner: scoped-planner
  integrator: cross-stage-designer
  test_designer: scenario-designer
  test_author: test-writer
  audit_business: domain-reviewer
  audit_security: security-reviewer
  audit_history_regression: regression-reviewer
  audit_test_oracle: oracle-reviewer
  audit_global_coverage: cross-stage-reviewer
  audit_implementation: implementation-reviewer
  executor: packet-runner
model_aliases:
  bounded-reader:
    candidate_aliases: [deepseek_flash, qwen28b_4k]
    qualification: qualification://bounded-research/v1
  scoped-planner:
    candidate_aliases: [deepseek_flash, qwen28b_4k]
    qualification: qualification://planning-local/v1
    fallback_alias: cross-stage-designer
  packet-runner:
    candidate_aliases: [qwen28b_4k, deepseek_flash]
    qualification: qualification://closed-patch-execution/v1
    total_context_limit: 4096
  cross-stage-designer:
    candidate_aliases: [reasoning_auditor]
    qualification: qualification://cross-stage-design/v1
  scenario-designer:
    candidate_aliases: [deepseek_flash, reasoning_auditor]
    qualification: qualification://test-scenario-design/v1
  test-writer:
    candidate_aliases: [deepseek_flash, qwen28b_4k]
    qualification: qualification://test-code-generation/v1
  domain-reviewer:
    candidate_aliases: [deepseek_flash, reasoning_auditor]
    qualification: qualification://business-audit/v1
  security-reviewer:
    candidate_aliases: [reasoning_auditor]
    qualification: qualification://security-audit/v1
  regression-reviewer:
    candidate_aliases: [deepseek_flash, reasoning_auditor]
    qualification: qualification://history-regression-audit/v1
  oracle-reviewer:
    candidate_aliases: [reasoning_auditor]
    qualification: qualification://test-oracle-audit/v1
  cross-stage-reviewer:
    candidate_aliases: [reasoning_auditor]
    qualification: qualification://global-coverage-audit/v1
  implementation-reviewer:
    candidate_aliases: [deepseek_flash, reasoning_auditor]
    qualification: qualification://implementation-audit/v1
environment_mapping:
  codex:
    scoped-planner: {binding: native-role, model_id_ref: local/planner}
    packet-runner: {binding: native-role, model_id_ref: local/executor}
  cursor:
    scoped-planner: {binding: native-subagent, model_id_ref: local/planner}
    packet-runner: {binding: native-subagent, model_id_ref: local/executor}
  antigravity:
    scoped-planner: {binding: fresh-session, model_id_ref: local/available}
    packet-runner: {binding: fresh-session, model_id_ref: local/available}
  standalone:
    scoped-planner: {binding: provider-api, model_id_ref: local/planner}
    packet-runner: {binding: provider-api, model_id_ref: local/executor}
limits: {max_concurrent: 3, max_spawn_depth: 1, design_iterations: 2}
```

Все role aliases определены в примере. `environment_mapping` показывает только два binding для краткости; generator требует mapping каждой активной роли либо явный disabled/unsupported. Для каждого `local/*` профиль требует `provider_id`, `model_id`, `model_revision_or_unknown`, `context_limit`, `sampling/effort`, `discovery_evidence_ref` и `qualification_ref`. Пока ID отсутствует после discovery, binding disabled, не строка-заглушка реального API-запроса. API credentials остаются в отдельном разрешенном secret store. Модель из provider API не считается доступной внутри IDE автоматически.

Runner сравнивает requested alias и фактически наблюдаемую model/version с qualification. Mismatch требует явно допустимого qualified fallback либо reject/escalation; unknown observed model не считается подтвержденной. Учет provider/model disclosure ограничен возможностями runtime, поэтому среда без нужного подтверждения не проходит strict qualification profile.

### 8.4. Что подтверждено официальными источниками

- [Claude Code subagents](https://code.claude.com/docs/en/sub-agents): доступны настройки модели и возможностей субагента; adapter должен учитывать реальный precedence и версию клиента.
- [Codex subagents](https://developers.openai.com/codex/subagents): поддерживаются custom roles/model settings. Permissions наследуются от parent; инструкция read-only сама не создает отдельную sandbox. Схему адаптировать к установленной версии, не копировать старый TOML из idea.
- [Cursor subagents](https://cursor.com/docs/subagents): отдельные contexts и настройка модели поддерживаются, но ограничения аккаунта/администратора могут изменить фактический выбор. Запрошенный model ID не равен доказанному фактически использованному.
- [Anthropic, Building effective agents](https://www.anthropic.com/research/building-effective-agents): простые composable workflow являются обоснованной отправной точкой; из этого не следует обязательность дорогой модели или постоянного x3 fan-out.

Для Antigravity/DSH/local provider native model switching здесь не подтвержден. До runtime contract test они используют explicit fresh-session/API adapter либо показывают `model_binding_unverified`. Не выдумывать tier fields и нативный синтаксис. Источники проверены 2026-11-06; перед реализацией сверить установленный клиент.

### 8.5. Разрешение на передачу данных модели

Qualification модели не является разрешением отправить ей закрытый исходник. WorkContext и role input содержат `data_policy_ref`, classification, allowed provider/model endpoints, допустимые region/retention условия и redaction profile. Перед каждым dispatch, включая cheap fallback, runner проверяет именно этот target и состав capsule. Установка API credentials также не дает согласия на передачу всех данных проекта.

Если требуемая политика не подтверждена, запрос блокируется до отправки в сеть. Допустим разрешенный локальный provider или безопасный сокращенный capsule, который все еще достаточен для решения. Нельзя удалить существенное evidence ради экономии/анонимизации и сохранить прежнюю отметку полноты. Receipt хранит policy decision и redaction refs без секретов.

## 9. Packet executor с общим окном 4k

Общий бюджет включает system/developer, skill metadata, schemas, packet, tool results, reasoning/output по правилам backend и reserve. Пилотный пример на 4096: 650 instructions + 250 schemas + 1400 packet/evidence + 650 results + 650 output + 496 reserve. Это гипотеза бюджета, не измеренный факт.

Если стартовые инструкции runtime занимают все окно, planner не может исправить это коротким планом. Нужен минимальный executor profile или модель с большим окном. Compiler использует tokenizer/backend accounting выбранного профиля и отказывается обрезать обязательные preconditions/invariants.

Минимальные tools: получить packet/status, применить approved operation, запустить command ID, прочитать bounded error, записать result through runner. Произвольный shell/write к исходникам и receipts не нужен для закрытого patch. Доступ ограничивается runtime/OS, не только промптом.

Packet включает work/stage/step, plan+audit refs, qualification, dependencies, expected preimages/postimages, write-set, invariants, case/command IDs, allowed side effects, stop conditions и recovery. Ссылки не заменяют обязательный смысл: runner детерминированно получает артефакт и проверяет его hash.

Command ID привязан к command registry hash, версии/доступному fingerprint runner provider, разрешенной форме argv/env и environment identity. Перед исполнением runner сверяет эту привязку, а не разрешает любую новую команду под старым ID. Измененный helper script или подмененный target требует переоценки соответствующего packet; разрешение на тест не разрешает произвольный shell.

**Approved patch:** planner подготовил конкретные bytes; runner проверяет источник, уникальность, scope, применяет patch, сверяет postimage/diff. Малая модель не перепечатывает код. Никакого fuzzy patch после stale source.

**Generative work:** результат нельзя предсказать заранее. Квалифицированный worker создает candidate diff в изолированном write-set; новый diff проходит audit/test fidelity и freeze. Только затем пересчитываются зависимые snapshots и выдается новое разрешение. Такой шаг не маскируется как approved deterministic packet.

## 10. Промежуточные hashes и receipts

### 10.1. Собственные изменения не должны делать следующий этап stale

Compiler моделирует детерминированные переходы `H0 -> H1 -> H2` и связывает каждый с operation hash. ST-02 ожидает H1, а не H0. Receipt ST-01 подтверждает разрешенный переход. Неожиданное состояние дает `needs_replan`, а не обновление hashes на глаз.

Для параллельных ветвей нужны disjoint write-sets, неизменные общие dependencies и проверяемый join. При пересечении либо shared state использовать serialization/единый интеграционный шаг. Случайный порядок завершения workers не определяет итоговый snapshot.

Design audit привязан к test contract. Материализация test sources является разрешенным отдельным переходом; executable receipt включает фактические test hashes, fidelity review и baseline. Для high/critical fidelity проверяет независимый reviewer. Изменение expected возвращает контракт на аудит.

### 10.2. Записи и доверие

```text
receipt_id + kind + work/stage/step + attempt + producer
input_contract_hashes + expected_snapshot + observed_snapshot
operation/command_digest + test/fixture/runtime fingerprints
executed_case_ids + result_assertions + exit + artifact_refs
qualification_ref + requested/observed_model + isolation_mode
coverage + limitations + status + supersedes_ref
```

Receipts immutable: исправление создает новую запись. Runner валидирует exact IDs, schema version и hashes; timestamps дают порядок наблюдений, не свежесть кода. Полный transcript и исходные tool outputs лежат в artifact storage; чат получает bounded summary и refs.

Нужны CAS/locks единственного writer, operation IDs и recovery после timeout. При неизвестном результате записи сначала reconcile actual file state; blind retry может применить patch дважды. Shared worktree dirty изменения пользователя не удаляются и не принимаются как собственный approved diff.

Hash не доказывает честность автора receipt. Если агент может произвольно писать receipts или выполнять shell, защита только от случайной ошибки. Для сильной provenance нужны доверенный runner, ограничения записи и изоляция; секретный signing key нельзя передавать модели.

## 11. Состояния stage и всей работы

```text
stage: proposed -> mechanically_valid -> audited -> tests_materialized
       -> baseline_valid -> executable -> applied -> verified -> accepted
work:  scoped -> plan_integrated -> globally_audited -> executing
       -> integration_verified -> documented -> complete
```

Альтернативные исходы: `needs_input`, `needs_replan`, `needs_design_review`, `blocked_infra`, `failed_check`, `no_change_needed`. Неполный draft допустим. Только reducer выводит transitions из receipts, а не выставленного моделью поля ready.

Следующий stage допускается после accepted dependencies. После shared/default/signature change сразу выполняются его cases и малый набор impacted invariants. Финальная интеграция проверяет cross-stage сценарии и browser evidence для UI; все локальные stages passed недостаточны для complete.

Expected RED нужен только тестам, различающим новое/исправленное поведение и baseline. Characterization/сохраняемый invariant может быть GREEN. Import/infra failure не полезный RED. Точные правила и fixtures находятся в [системе тестирования](./03-web-testing-system.md).

## 12. Работа без нативных субагентов

| Режим | Как исполнять те же роли | Ограничение |
|---|---|---|
| Native isolated subagents | Coordinator запускает роли с bounded input и собирает их artifacts | Проверить реальные model/tool/permission bindings |
| Последовательные fresh sessions | Сначала researcher/planner, затем отдельные audit sessions; runner передает frozen artifacts | Нет выигрыша latency от параллельности; контракт и независимость сохраняются при изоляции |
| External provider adapter | Явно разрешенные API/CLI процессы получают те же capsules | Доступ к данным и tools настроить отдельно; API call без code tools не равен аудиту исходников |
| Один продолжающий чат | Роли выполняются последовательно с явно ограниченным scope | Это self-review; high/critical independent gate остается незакрытым |

Coordinator не требует от пользователя вручную повторять контекст: экспортирует role packet и импортирует проверенный result. Если launch API недоступен, предлагает один конкретный fresh-session packet и ожидаемый output path; до возврата результата статус incomplete.

Для режима без model switching используется доступная квалифицированная модель; экономия от смены модели не заявляется. Невозможно снизить независимость или обязательные проверки, просто переименовав один процесс в несколько ролей.

## 13. Реализация по фазам

Общий код добавлять после reuse-проверки в существующий `harness-router/children/harness-core/scripts/lib/`; data storage остается у JSONdoc. Canonical root определить по WP0 [общего плана](../plan.md), зеркала не править. Компоненты ниже относятся к source owner, а не обязательно к `.codex`.

| Фаза | Существующие файлы/компоненты | Новые компоненты и результат |
|---|---|---|
| P0. Основание | `prepare-plan/scripts/validate_plan.py`, `jsondoc/plan_writer.py`, `plan_verify.py`, `test-task/scripts/check-ac-matrix.py`, result consumers | Строгие schemas и единый verification reducer; воспроизведения false-green перестают проходить |
| P1. Identity/evidence | JSONdoc store/contract, `research_ledger.py`, artifact refs, `qa-manifest.py` | `work_context`, `evidence`, `artifact_resolver`; taskless/stage/exact-run и versioned receipts |
| P2. Planner delegation | `prepare-plan/SKILL.md`, references, context/router generators, model registry | Research/stage-planner/integrator leaf; capsules, bounded fan-out, model qualification |
| P3. Audit | Prepare-plan rule/P7.4a alias, `git-task-blame`, business/test capabilities | Audit router/leaves, finding schema, frozen input assembler, global coverage reducer |
| P4. Execution | `prepare-task-test`, `test-task`, browser provider, common runner | Packet compiler, expected snapshots, test fidelity, implement-stage и implementation review |
| P5. Runtime adapters | `environment-sync`, environment registry, config generators/parity | Подтвержденные native/fresh-session mappings, safe fallback, установленные capabilities |
| P6. Pilot | Harness fixture tests, usage/analytics, project profiles | Holdout по моделям/рискам, перенос на другой стек, flags и rollback |

Последовательность: P0 -> P1 -> P2/P3 contracts -> P4 -> P5 runtime smoke -> P6. Минимальный single-session adapter для тестов существует с P1; реальные native integrations вводятся только после проверки установленной схемы. P2/P3 не требуют заранее работающих пяти дорогих моделей.

Каждая фаза: negative fixture -> изменение owner -> unit/contract test -> generate/verify adapters -> targeted runtime smoke -> receipt. Изменение schema требует совместимого importer; неизвестная версия не интерпретируется молча. Бизнес-энциклопедия не блокирует запуск: пока используются доступные подтвержденные sources с явными gaps.

## 14. Приемочные отрицательные сценарии

| ID | Контрпример | Обязательный результат |
|---|---|---|
| N01 | Пустые AC/R/S или malformed ledger при ready | Mechanical reject до LLM review |
| N02 | Метод существует в другом классе; case не запускался | Нет AC coverage/pass |
| N03 | Два stages passed, но один AC потерян при join | Global audit blocks complete |
| N04 | Цикл DAG, пересекающиеся writes, shared state без зависимости | Plan reject/serialization, не случайный merge |
| N05 | Owner допускается, FOREIGN меняет чужие данные | Security/business blocker даже при других passed |
| N06 | REPLAY возвращает тот же UI, но создает вторую запись | Oracle/integration обнаруживает side effect |
| N07 | Planner убрал прежний invariant из history | History review finding; relevant regression обязательна |
| N08 | Reviewer timeout, нет tools или подменен input hash | Incomplete/blocked; не quorum passed |
| N09 | Findings коллег переданы до first pass | Independence mode не independent |
| N10 | ST-01 одобрен и меняет файл для ST-02 | ST-02 принимает expected H1, но отклоняет произвольный H1' |
| N11 | Тестовый author ослабил expected/fixture ради green | Fidelity reject, contract audit повторно |
| N12 | Packet больше общего окна или tool output усечен | Compile reject/explicit continuation, не молчаливый truncate |
| N13 | Runtime заменил model либо qualification не подходит роли | Requalification/fallback по policy, факт модели не выдумывается |
| N14 | Timeout после patch, до receipt | Reconcile state; повтор operation ID не дублирует запись |
| N15 | Local stages green, browser wiring сломан | Integration/browser fail, complete запрещен |
| N16 | Нет native subagents и доступен лишь прежний чат | Self-review label; independent high-risk gate не закрыт |
| N17 | Qualified cheap fallback отправляет private capsule неразрешенному provider | Dispatch blocked до сети; допустимый локальный fallback выбирается отдельно |
| N18 | Источник evidence содержит команду отключить auth или отправить `.env` | Команда не появляется в capabilities/write-set; authority policy неизменна |
| N19 | Command ID прежний, но registry/helper/target подменены после audit | Preconditions reject; тестовое разрешение не применяется к новой операции |

Позитивные пары проверяют допустимый draft, no-op, сохраненный invariant GREEN, разрешенный переход H0/H1/H2 и одинаковые contracts native/sequential режимов. Tests выполняются в изолированных fixtures; production auth, реальные платежи и deployment не являются harness fixtures.

## 15. Пилот, метрики и откат

Сравнить старый workflow и кандидат на одинаковых snapshots, моделях, budgets и fixtures. Сначала development cases, затем неизменяемый holdout; число повторов и пороги утвердить до просмотра holdout. Отдельно сравнить cheap planner + qualified escalation и постоянно более дорогой planner.

Измерять полную стоимость всех subagents/retries, startup/schema tokens, долю полезных findings, false blockers, missed seeded blockers, global AC gaps, частоту эскалации, время до evidence и accepted result. Число tool calls не заменяет токены, деньги и качество. Missing usage обозначается proxy, не измеренной экономией.

Включать по flags: strict evidence -> delegated planning -> independent audit -> packet execution -> role-specific model selection. Rollback сохраняет artifacts/schema readers и отключает новый orchestration; нельзя возвращать false-green или unsafe writes ради прежней скорости. Пользовательские source changes не откатываются.

## Известные проблемы и ограничения

- Native runtime API и model availability меняются. Проверка официальной страницы не заменяет smoke установленной версии и аккаунта.
- Субагенты и независимые contexts уменьшают часть коррелированных ошибок, но общий неверный oracle способен обмануть всех reviewers.
- Полнота бизнес-индекса и call graph ограничена. Незакрытые gaps требуют исследования или ограничения решения, не обещания полного знания проекта.
- Конфигурация, новые skills и runner interfaces в этом документе пока не реализованы и не прошли benchmark.

## Связи

- [Общий план улучшения](../plan.md): исходные findings, архитектура, WP5-WP9.
- [Мастер-план сканирования и аудита](./deepseek.md): цели, очередь, фазы и приемка.
- [Индекс проекта и бизнес-знания](./02-project-index-and-business-knowledge.md): capsules, rule versions и актуальность.
- [Система web-тестирования](./03-web-testing-system.md): oracle, cases, browser evidence и runner receipts.
- [Хранилище знаний и очередь](./04-knowledge-store-and-queue.md): leases, generation и receipts.
- [Поиск дефектов и модернизация](./05-bug-hunt-and-modernization.md): findings и pass library.
- [Старый x3-проект](../idea/03-plan-audit-x3.md): frozen inputs сохраняются, постоянный x3 и голосование заменяются risk-based audit.

## История изменений

- 2026-11-06: создан проект системы по запросу пользователя. Planner вынесен на квалифицированного субагента; добавлены stage DAG, независимые профильные аудиты, промежуточные hashes и runtime fallbacks. Код не изменялся.
- 2026-11-06: при общей проверке согласованы task/case IDs, полный набор role aliases и явная последовательность аудита A0-A7 для каждого stage.
- 2026-11-06: независимая проверка уточнила data-egress policy при fallback, trust boundary evidence/instructions и binding command registry к packet.

#harness #planning #audit #subagents #testing #portability
