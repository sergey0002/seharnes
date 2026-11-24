# Оркестратор параллельного аудита плана x3 (не внедрен)

<!-- meta
type: plan
status: draft
updated: 2026-10-02
related: [../index.md, ./01-roadmap-hpta.md, ./04-planx-improvements.md, ../state/08-plan-contour.md]
tags: [harness, prepare-plan, plan-audit, x3, subagent, pending]
-->

---

## Суть

План внедрения параллельного аудита плана тремя моделями-субагентами
(аудит 2026-09-28). НЕ внедрен: нет `.cursor/plan-audit-x3.json`, нет оберток
`plan-auditor-*`, нет `.doc/docscripts/plan-audit-x3.py` (проверено 2026-10-02).
Связан с roadmap P-06 (его реализация). Отдельный скил аудита запрещен,
только оркестратор поверх prepare-plan в режиме audit-only.

---

Один план пишет одна модель через prepare-plan. Три разные модели параллельно аудируют
замороженный plan.md в режиме audit-only (P7.4a steps 1-17), не меняя план. Четвертый
проход-агрегатор собирает три JSON в summary.json и проводит adversarial-ревью,
только после этого план правится и проходит один финальный P7. Модель задается
не в SKILL.md, а в конфиге оркестратора и в тонких обертках вызова. Схема переносима:
канон инструкций не меняется, меняются только адаптеры. Плановый вход оркестратора
привязан к механическому гейту канона P7.0 (`jsondoc.py plan verify`), а не
к legacy-префлайту validate_plan.py: у JSON-first плана служебный plan_sha256 берется
из модели jsondoc, у legacy MD-плана считается по plan.md.

Отдельный скил аудита запрещен: канон prepare-plan SKILL единственный источник,
аудит тот же скил в режиме audit-only (P7.4a), детали в references modes.md,
чеклист audit-gate-p7.md (17 шагов rebuild, shallow re-tick невалиден), реестр
фиксирует 22 скила без отдельного plan-audit. Новый файл plan-audit и SKILL.md запрещен,
создаст рассинхрон канона и зеркал. Добавляется только оркестратор поверх скила.

Роли и единственный писатель: Planner одна модель полный P0-P7 пишет plan.md.
Auditor A, B, C три модели только audit-only читают замороженный план, пишут только
свой `audits/audit-*.json`, план read-only. Aggregator одна модель-арбитр читает три
JSON, пишет summary.json плюс summary.md, предлагает правки. Final P7 одна модель
(обычно planner или aggregator) полный P7.4a, пишет plan.md, выставляет audit_status
и History. Параллельность: три аудитора субагентами. В Kilo три вызова Task параллельно
или три Agent Manager worktree на одном коммите. В Cursor три subagent с разным model
picker. В Codex три роли и профиля с разным model. В Antigravity три запуска с разным
tier. Аудиторы не видят друг друга, гонок нет. Запреты аудиторам: не править plan.md,
stageN и plan.md, audit_status, task_closure; не коммитить, не пушить, не менять ветку;
не переиспользовать stale blast radius и stale git-task-blame, прогнать заново;
результат без plan_sha256 отбрасывается.

Раскладка: `.doc/tasks/{N}/` task.md, plan.md, `audits/` audit-a.json, audit-b.json,
audit-c.json, summary.json, summary.md. plan.md единственный вход. Перед аудитами
считается sha256 plan.md как plan_sha256, фиксируется git sha рабочей копии и task ID
из task.md (не из имени ветки). Каждый аудитор пишет ровно один файл. Имя файла
привязано к слоту конфига (a, b, c), не к имени модели. summary.json пишет только
агрегатор. summary.md человекочитаемый рендер той же модели. Каталог `audits/`
локальный, как остальной `.doc/tasks/`.

Канонический конфиг (пример имени `.cursor/plan-audit-x3.json`, единственный
редактируемый конфиг, зеркала строит генератор): version 1, skill prepare-plan,
mode audit-only, min_scope_size medium, slots a, b, c (model provider и model, tier
pro и flash, out `audits/audit-*.json`), aggregator slot arbiter, finalP7 by arbiter.
Поля: model точный ID для Cursor, Codex, Kilo; tier переносимый уровень (pro, flash)
для Antigravity, оркестратор маппит tier на доступную модель, значение для Antigravity
не проверено по источнику в репо, помечено unverified до подтверждения реальным
tier-полем среды; out фиксированный путь; min_scope_size порог включения x3,
оркестратор пропускает веер для trivial и small без High и Critical и запускает
одиночный аудит, чтобы не умножать токены втрое; замена модели правка одной строки
конфига. Пресет Antigravity: слот a tier pro, слоты b и c tier flash, только один
pro-аудит. В средах с точными ID три конкретных model, в Antigravity один pro и два flash.

Маппинг по средам: Cursor `.cursor/agents/plan-auditor-*.md` frontmatter model
(SKILL.md без поля model, модель на обертке). Codex роль `[agents.plan-auditor-x]`
плюс файл роли с model, либо профиль и `codex --profile` (роль сужает права, аудиторам
только read плюс запись своего JSON). Kilo `.kilo/agent/plan-auditor-*.md` поле model
mode subagent, либо Task-вызов с model, Agent Manager сессии с явной моделью.
Antigravity `.agents/agents/plan-auditor-*.md` frontmatter model и tier плюс skills
prepare-plan (нет точного ID, только tier pro и flash unverified). Во всех средах скил
модель-агностик, модель крепится к обертке вызова, не к SKILL.md. Тонкие обертки:
имя, модель и tier из конфига, запрет записи плана, ссылка на канон, путь выхода.
Три обертки отличаются только слотом и моделью, тело промпта общее, дублирование
логики запрещено.

Общий бриф аудитора (один текст на три слота): режим prepare-plan audit-only P7.4a
steps 1-17; канон SKILL.md; чеклист audit-gate-p7.md; задача task.md; план plan.md;
plan_sha256; ревизия кода git sha; выход `audits/audit-<slot>.json`; требования:
шаг 0 механический гейт P7.0 до ручных проверок (`jsondoc.py plan verify --task N`,
exit code в JSON; legacy MD-план через validate_plan.py как префлайт, но вердикт дает
jsondoc verify, не legacy-префлайт); Read whole для каждого файла из Patches
(файлы до 300 строк целиком, крупные по size policy P2.2); перестроить blast radius
по P1.1 с указанием какой tier что нашел, заново git-task-blame по каждому
Patches-файлу, P7.9 на свежем брифе; проверить P3.5 scope_size, P7.8 zero-ambiguity
(Before grep ровно 1, After pasteable), Sources of truth T-id, AC-ID против Coverage;
после прохода с установкой найди баг не подтверждай план провести adversarial-проход,
находка инвалидирует passed; не править plan.md, audit_status, task_closure; каждый
finding обязан иметь evidence вида file и line плюс цитата из this-session Read,
finding без evidence не писать. Оркестратор подставляет N, hash, git sha, slot
и раздает один текст трем слотам.

Формат результата: auditor a, model, plan_sha256, plan_source_sha256, task_id,
code_rev git sha, verify (tool `jsondoc plan verify` или validate_plan.py, exit_code
обязателен), status passed или failed, findings (id F-001, severity high, location
`app/Service/Order.php:120`, check P7.4a-5, problem, evidence file и line плюс цитата
Read, recommendation). Правила: verify механический гейт P7.0, exit_code не 0
при JSON-first вердикт SOURCE_STALE и ambiguous и status failed до ручных проверок;
plan_sha256 hash планового входа оркестратора (для JSON-first совпадает с plan_sha256
модели jsondoc, plan_source_sha256 source_sha256 из research-ledger свежесть файлов;
для legacy MD plan_sha256 равно sha256 plan.md, plan_source_sha256 пуст, оба поля
обязательны к проверке в приемке); status passed или failed (любой незакрытый finding
high или critical требует failed, как ненулевой exit_code); check номер шага P7.4a
или P7.0, P7.8, P7.9, P3.5 (без привязки к чеку finding уходит в needs-review);
severity critical, high, medium, low; status passed при пустом findings допустим
(сигнал, не доказательство).

Алгоритм оркестратора. Шаг 0 префлайт: проверить plan.md существует; определить режим
JSON-first (есть task.json с моделью) или legacy MD (для JSON-first прогнать
`jsondoc.py plan verify --task N` и зафиксировать exit code, для legacy validate_plan.py
как префлайт механика не вердикт); зафиксировать plan_sha256 (из модели jsondoc
для JSON-first, иначе sha256 plan.md), source_sha256, git sha и task ID из task.md
(не из имени ветки); прочитать min_scope_size из конфига (если scope_size ниже порога
trivial и small без High и Critical, пропустить веер и запустить одиночный аудит
слота a, файлы audit-b и audit-c не создавать, в summary.json отметить single_pass true);
создать каталог `audits/`. Шаг 1 веер: прочитать слоты из конфига (количество N
произвольно 2, 3, 5, N), запустить все слоты параллельно с одним брифом, каждый пишет
`audits/audit-{slot}.json`, таймаут общий, ретрай только упавшего слота с тем же входом
максимум 2 ретрая, ошибка слота (таймаут, падение, невалидный JSON, несовпадение хеша
после ретраев) не останавливает веер, слот помечается error. Шаг 2 приемка: проверить
файлы существуют и валидный JSON (отсутствующий или битый слот error); проверить
plan_sha256 в каждом принятом совпадает с замороженным, plan_source_sha256 совпадает
с зафиксированным (несовпадение после ретраев слот error, файл отбрасывается);
проверить task_id и code_rev совпадают; проверить verify.exit_code зафиксирован
(ненулевой у JSON-first слот failed до агрегации); кворум минимум 2 принятых слота
(один принятый single_pass, веер несостоявшийся, решение арбитр с пометкой degraded;
ноль принятых abort, план не правится, веер перезапускается). Шаг 3 агрегация
(модель-арбитр, отдельный adversarial-проход): нормализовать каждый finding
в fingerprint (norm location плюс check плюс norm problem, нижний регистр, схлопнуть
пробелы, убрать кавычки-дефисы-вариации); сгруппировать по числу слотов N (consensus_N_N
найден всеми принятыми, partial найден частью с указанием каких, unique найден одним
пометить needs-review не удалять, conflict один утверждает passed по чеку другой дает
high и critical по тому же location плюс check вывести обе evidence-строки рядом);
слоты error в голосовании не участвуют, отсутствие не голос passed; группа consensus
только по принятым, в summary.json поле quorum accepted и total обязательно;
отсутствие finding не доказательство; вес голоса consensus выше partial, unique требует
ручной проверки; после сборки арбитр проводит adversarial-проход (найди баг не
подтверждай план), независимо перечитывает модель и код по точкам расхождения,
собственная находка в conflict и unique с пометкой arbiter, находка инвалидирует passed;
записать summary.json (plan_sha256, task_id, quorum `2/3`, inputs, errors
`audits/audit-c.json: timeout after 2 retries`, groups consensus, partial, unique,
conflict, decision accept и fix-plan и replan, fix_list); рендер summary.md (таблица
слот, status, count, затем группы с location и evidence, затем fix_list); decision
accept (править нечего), fix-plan (есть что править), replan (план неверен в корне).
Шаг 4 синтез: только агрегатор предлагает правки plan.md по fix_list; после правок
пересчитать plan_sha256 (новый hash), прогнать один финальный prepare-plan P7 тем же
каноном (полный P7.4a steps 1-17 плюс механический гейт P7.0); финальный проход
выставляет audit_status passed и failed, task_closure, History; History обязан записать
не только fingerprints, но и расхождения трех моделей (какие finding какой слот
пропустил и нашел первым, какие conflict и unique покрыты правкой, какие переведены
в accepted debt с причиной), сохраняет ценность multi-model и не дает финальному
проходу молча переписать вердикт слотов; параллельные JSON неизменяемые исторические
снимки, не переписывать под новый hash. Шаг 5 отчет: в чат слоты, модели, статусы,
counts, exit code гейта, группы consensus, partial, unique, conflict, adversarial-находки
арбитра, решение, путь summary.md, финальный audit_status; в History какие fingerprints
от каких слотов и как закрыты расхождения.

Интеграция с генератором и parity: generate-agent-configs.py строит только rules,
skills, scripts и MCP, каталогов агентов и команд нет ни у Codex ни у Kilo ни у
Antigravity, ручная правка запрещена, канон правее зеркала. Внедрение: канон добавить
`.cursor/plan-audit-x3.json` и `.cursor/agents/plan-auditor-*.md` (тонкие обертки);
генератор расширить чтобы строить Codex роли из оберток, Kilo agent из тех же оберток
с полем model, Agents agents с tier для Antigravity; паритет расширить проверкой
оберток, иначе отчет снова зеленый при разъехавшихся зеркалах. Правка harness вести
по harness-improvement SKILL: сначала история компонента по History планов и doc.md,
затем минимальная переносимая правка, затем проверка parity. Сам
prepare-plan SKILL.md и зеркала при этом не меняются.

Запуск по средам. Kilo основной нативно: вариант Task три параллельных вызова
с одинаковым prompt, разный model, subagent_type general, затем четвертый
вызов-агрегатор; вариант Agent Manager три worktree на одном коммите, каждой задаче
своя модель из конфига, merge обратно только `audits/audit-*.json`, plan.md в worktree
read-only; именованные аудиторы `.kilo/agent/plan-auditor-*.md` с mode subagent
и model из конфига. Cursor: три subagent с одним брифом, модель в model picker,
скил как prepare-plan или Custom Mode, поле model в SKILL.md отсутствует по дизайну
Cursor, пин модели в `.cursor/agents/` обертке. Codex: три роли `[agents.plan-auditor-*]`
с файлами ролей каждая со своим model, либо три профиля и параллельные
`codex exec --profile`, инструкции из `.codex/AGENTS.md` и Codex SKILL, роль сужает права
до read плюс запись своего JSON. Antigravity: три запуска с маппингом tier (слот a pro,
слоты b и c flash), только один pro-аудит, при недоступности параллельных агентов
допустим последовательный прогон тем же брифом, схема файлов не меняется.
Универсальный fallback любая IDE: внешний скрипт plan-audit-x3.py читает конфиг,
считает plan_sha256, вызывает три провайдера с одним системным промптом (SKILL.md плюс
audit-gate-p7.md плюс бриф), раскладывает ответы в `audits/`, запускает агрегацию.
Модель в скиле не хранится ни в одном варианте.

Переносимость rebase checklist: скопировать prepare-plan SKILL.md плюс references
плюс scripts validate_plan.py, новый plan-audit-x3.json, три обертки, скрипт
оркестратора, патч генератора; заполнить Project adapters (DOCS_ROOT, DOCS_INDEX,
TASK_DIR, ROUTER, MCP_CONFIG, TASK_EXPORT), без этого P0 и P7.9 не соберутся;
в конфиге заменить только model и tier на доступные, логику не трогать; прогнать
sync-agent-views.sh и verify_parity.py, убедиться обертки есть во всех вью;
продуктовые имена в скил и оркестратор не вшивать, пути к задаче из адаптеров,
не хардкодить `.doc/tasks`; проверить что find-related-tasks, git-task-blame
либо портированы, либо явно помечены N/A с причиной в плане,
молчаливый пропуск запрещен.

Валидация внедрения: `jsondoc.py plan verify --task N` (JSON-first) и validate_plan.py
(legacy) проходят на тестовом плане до и после; три тестовых аудита на одном
замороженном плане дают три JSON с одним plan_sha256 и одинаковыми verify.exit_code;
подмена plan.md между веером и приемкой детектится несовпадением хеша, устаревший
источник несовпадением plan_source_sha256; арбитр проводит adversarial-проход,
находка в summary.json и инвалидирует passed; план ниже min_scope_size не запускает
веер, в summary.json single_pass true; verify_parity.py видит обертки во всех вью,
parity-report.json без stale passed; замена одной модели в конфиге не требует правки
скила и промптов; Antigravity-пресет (pro плюс flash плюс flash) собирается тем же
оркестратором без отдельной ветки кода, но tier-поле подтверждено до внедрения.

Известные ограничения: Antigravity не дает точный ID модели, только tier, конфиг хранит
оба поля, оркестратор читает tier, конкретное tier-поле не подтверждено источником
в репо, помечено unverified. Двойной валидатор: `jsondoc plan verify` (канон P7.0,
JSON-first) и validate_plan.py (legacy MD), оркестратор привязан к jsondoc plan verify,
validate_plan.py только префлайт для legacy, чтобы три аудитора не гоняли разные гейты.
Параллельные аудиторы умножают расход токенов втрое. Порог min_scope_size medium
включает x3 только для medium и large и High и Critical, ниже одиночный аудит.
Ledger research-ledger.json workspace-local и не переносится, на другой машине P7.4a
перечитывает все, plan_source_sha256 помечается n/a. parity-report.json ранее врал
stale passed, после оберток parity обязан проверять их. Kilo-адаптер ранее терял
sourcegraph (Tier 3) и ломал php-toolchain, до внедрения x3 генератор чинится.

История: 2026-09-28 создан как план внедрения x3 (отдельный скил отклонен, модель
в конфиг и обертки, Antigravity-пресет pro плюс flash плюс flash). Правка по аудиту
документа: оркестратор привязан к P7.0, добавлены plan_source_sha256 и verify.exit_code,
adversarial-роль арбитра, порог min_scope_size, tier помечен unverified. Обобщено
на N слотов, политика ошибок слота (2 ретрая, статус error), кворум 2 и N, поле quorum
и errors в summary.json.

---

## Связи

- [Точка входа](../index.md) - карта каталога
- [Roadmap](./01-roadmap-hpta.md) - P-06 реализует этот план
- [Доработки prepare-plan](./04-planx-improvements.md) - смежный план
- [Контур планирования](../state/08-plan-contour.md) - фактическое состояние скила

---

## История изменений

- 2026-10-02: создан переносом plan_audit.md (раздел 12 старого 15-plan-audit.md) без потерь
