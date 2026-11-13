# Скилы (77): карта и ссылки

<!-- meta
type: architecture
status: actual
updated: 2026-11-10
related: [./index.md, ../index.md, ../../agents/skills/, ./06-jsondoc.md, ./07-workflows.md]
tags: [harness, skills, tasks, docs, meta, external]
-->

---

## Суть

В каноне 77 скилов с `SKILL.md` и 28 верхних каталогов; остальные скилы дочерние
и вызываются через роутеры. Карта ниже перечисляет верхние маршруты по группам.
Этот документ - только карта и ссылки. Описание "зачем нужен и как работает" живет
в каноне `.agents/skills/{name}/README.md`, шаги, флаги и полные инструкции -
в каноне `.agents/skills/{name}/SKILL.md`, и здесь не дублируются. Канон
воспроизводимого тестирования - [../testaudit.md](../testaudit.md).

Канон харнеса - `.agents/skills/`; копия `.codex/skills/` нужна Codex,
Kilo читает `.agents/skills/` по умолчанию.

---

## 1. Жизненный цикл задачи (16)

| Скил | Карточка | Канон |
|---|---|---|
| task-spec | [task-spec](../../../.agents/skills/task-router/children/task-spec/README.md) | `../../../.agents/skills/task-router/children/task-spec/SKILL.md` |
| gototask | [gototask](../../../.agents/skills/task-router/children/gototask/README.md) | `../../../.agents/skills/task-router/children/gototask/SKILL.md` |
| task-intake | [task-intake](../../../.agents/skills/task-router/children/task-intake/README.md) | `../../../.agents/skills/task-router/children/task-intake/SKILL.md` |
| task-diff | [task-diff](../../../.agents/skills/task-router/children/task-diff/README.md) | `../../../.agents/skills/task-router/children/task-diff/SKILL.md` |
| task-doc | [task-doc](../../../.agents/skills/documentation-router/children/task-doc/README.md) | `../../../.agents/skills/documentation-router/children/task-doc/SKILL.md` |
| prepare-plan | [prepare-plan](../../../.agents/skills/prepare-plan/README.md) | `../../../.agents/skills/prepare-plan/SKILL.md` |
| audit-plan | [audit-plan](../../../.agents/skills/task-router/children/audit-plan/README.md) | `../../../.agents/skills/task-router/children/audit-plan/SKILL.md` |
| git-task-blame | [git-task-blame](../../../.agents/skills/task-router/children/git-task-blame/README.md) | `../../../.agents/skills/task-router/children/git-task-blame/SKILL.md` |
| prepare-task-test | [prepare-task-test](../../../.agents/skills/task-router/children/testing-router/children/prepare-task-test/README.md) | `../../../.agents/skills/task-router/children/testing-router/children/prepare-task-test/SKILL.md` |
| test-task | [test-task](../../../.agents/skills/task-router/children/testing-router/children/test-task/README.md) | `../../../.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md` |
| browser-verify | [browser-verify](../../../.agents/skills/task-router/children/testing-router/children/browser-verify/README.md) | `../../../.agents/skills/task-router/children/testing-router/children/browser-verify/SKILL.md` |
| task-code-review | [task-code-review](../../../.agents/skills/task-router/children/task-code-review/README.md) | `../../../.agents/skills/task-router/children/task-code-review/SKILL.md` |
| send-to-git | [send-to-git](../../../.agents/skills/send-to-git/README.md) | `../../../.agents/skills/send-to-git/SKILL.md` |
| task-report | [task-report](../../../.agents/skills/task-router/children/reporting-router/children/task-report/README.md) | `../../../.agents/skills/task-router/children/reporting-router/children/task-report/SKILL.md` |
| task-change-report | [task-change-report](../../../.agents/skills/task-router/children/reporting-router/children/task-change-report/README.md) | `../../../.agents/skills/task-router/children/reporting-router/children/task-change-report/SKILL.md` |
| login-as-user | [login-as-user](../../../.agents/skills/login-as-user/README.md) | `../../../.agents/skills/login-as-user/SKILL.md` |

## 2. Документация, код и бизнес-анализ (5)

| Скил | Карточка | Канон |
|---|---|---|
| project-doc | [project-doc](../../../.agents/skills/documentation-router/children/project-doc/README.md) | `../../../.agents/skills/documentation-router/children/project-doc/SKILL.md` |
| doc-verify | [doc-verify](../../../.agents/skills/documentation-router/children/doc-verify/README.md) | `../../../.agents/skills/documentation-router/children/doc-verify/SKILL.md` |
| codegraph | [codegraph](../../../.agents/skills/codegraph/README.md) | `../../../.agents/skills/codegraph/SKILL.md` |
| codeprism | [codeprism](../../../.agents/skills/codeprism/README.md) | `../../../.agents/skills/codeprism/SKILL.md` |

## 3. Мета-харнес (9)

| Скил | Карточка | Канон |
|---|---|---|
| improvement | [improvement](../../../.agents/skills/harness-router/children/improvement/README.md) | `../../../.agents/skills/harness-router/children/improvement/SKILL.md` |
| copy-project | [copy-project](../../../.agents/skills/harness-router/children/copy-project/README.md) | `../../../.agents/skills/harness-router/children/copy-project/SKILL.md` |
| add-skill | [add-skill](../../../.agents/skills/harness-router/children/add-skill/README.md) | `../../../.agents/skills/harness-router/children/add-skill/SKILL.md` |
| remove-skill | [remove-skill](../../../.agents/skills/harness-router/children/remove-skill/README.md) | `../../../.agents/skills/harness-router/children/remove-skill/SKILL.md` |
| skill-authoring | [skill-authoring](../../../.agents/skills/harness-router/children/skill-authoring/README.md) | `../../../.agents/skills/harness-router/children/skill-authoring/SKILL.md` |
| migration-review | [migration-review](../../../.agents/skills/harness-router/children/migration-review/README.md) | `../../../.agents/skills/harness-router/children/migration-review/SKILL.md` |
| mirror | [mirror](../../../.agents/skills/harness-router/children/mirror/README.md) | `../../../.agents/skills/harness-router/children/mirror/SKILL.md` |
| index | [index](../../../.agents/skills/harness-router/children/index/README.md) | `../../../.agents/skills/harness-router/children/index/SKILL.md` |
| ponytail | [ponytail](../../../.agents/skills/ponytail/README.md) | `../../../.agents/skills/ponytail/SKILL.md` |

## 4. Внешние данные и SEO (5)

| Скил | Карточка | Канон |
|---|---|---|
| yadisk-screenshot | [yadisk-screenshot](../../../.agents/skills/yadisk-screenshot/README.md) | `../../../.agents/skills/yadisk-screenshot/SKILL.md` |

---

## 5. Локальные скилы проекта

| Скил | Карточка | Канон |
|---|---|---|
| variant-feature-evaluation | [variant-feature-evaluation](../../../.agents/skills/exhaustive-research-decision-v6/children/variant-feature-evaluation/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/variant-feature-evaluation/SKILL.md` |
| triz-contradiction-resolution | [triz-contradiction-resolution](../../../.agents/skills/exhaustive-research-decision-v6/children/triz-contradiction-resolution/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/triz-contradiction-resolution/SKILL.md` |
| research-assignment | [research-assignment](../../../.agents/skills/exhaustive-research-decision-v6/children/research-assignment/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/research-assignment/SKILL.md` |
| output-contract-and-format-compliance | [output-contract-and-format-compliance](../../../.agents/skills/exhaustive-research-decision-v6/children/output-contract-and-format-compliance/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/output-contract-and-format-compliance/SKILL.md` |
| existing-solution-scouting | [existing-solution-scouting](../../../.agents/skills/exhaustive-research-decision-v6/children/existing-solution-scouting/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/existing-solution-scouting/SKILL.md` |
| evidence-provenance | [evidence-provenance](../../../.agents/skills/exhaustive-research-decision-v6/children/evidence-provenance/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/evidence-provenance/SKILL.md` |
| domain-safety-verification | [domain-safety-verification](../../../.agents/skills/exhaustive-research-decision-v6/children/domain-safety-verification/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/domain-safety-verification/SKILL.md` |
| cursor-state-handoff | [cursor-state-handoff](../../../.agents/skills/exhaustive-research-decision-v6/children/cursor-state-handoff/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/cursor-state-handoff/SKILL.md` |
| criteria-synthesis | [criteria-synthesis](../../../.agents/skills/exhaustive-research-decision-v6/children/criteria-synthesis/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/criteria-synthesis/SKILL.md` |
| briefing-intake | [briefing-intake](../../../.agents/skills/exhaustive-research-decision-v6/children/briefing-intake/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/children/briefing-intake/SKILL.md` |
| skill-creator | [skill-creator](../../../.agents/skills/skill-creator/README.md) | `../../../.agents/skills/skill-creator/SKILL.md` |
| skill-auditor | [skill-auditor](../../../.agents/skills/skill-auditor/README.md) | `../../../.agents/skills/skill-auditor/SKILL.md` |
| exhaustive-research-decision-v6 | [exhaustive-research-decision-v6](../../../.agents/skills/exhaustive-research-decision-v6/README.md) | `../../../.agents/skills/exhaustive-research-decision-v6/SKILL.md` |
| bug-cause | [bug-cause](../../../.agents/skills/code/children/bug-cause/README.md) | `../../../.agents/skills/code/children/bug-cause/SKILL.md` |
| code | [code](../../../.agents/skills/code/README.md) | `../../../.agents/skills/code/SKILL.md` |
| platform-browser-test | [platform-browser-test](../../../.agents/skills/copytrust/children/platform-browser-test/README.md) | `../../../.agents/skills/copytrust/children/platform-browser-test/SKILL.md` |
| platform-logs | [platform-logs](../../../.agents/skills/copytrust/children/platform-logs/README.md) | `../../../.agents/skills/copytrust/children/platform-logs/SKILL.md` |
| copytrust | [copytrust](../../../.agents/skills/copytrust/README.md) | `../../../.agents/skills/copytrust/SKILL.md` |
| neiroslop | [neiroslop](../../../.agents/skills/neiroslop/README.md) | `../../../.agents/skills/neiroslop/SKILL.md` |

---

## Реестр и валидаторы

Реестр: `.agents/skills/harness-router/children/improvement/scripts/component_registry.json`.
103 записи: 69 компонентов со `SKILL.md`, 32 rule-only и 2 общих. У оркестраторов поле `skill_dependencies`
(test-task, browser-verify, prepare-plan, audit-plan, harness-improvement, task-intake).

Проверки:

```bash
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py --rules-dir .cursor/rules --skills-dir .agents/skills
```

Правка любого скила - только через [harness-improvement](../../../.agents/skills/harness-router/children/improvement/README.md).

---

## Связи

- [Точка входа](../index.md) - карта каталога
- [Канон скилов (.agents/skills/)](../../../.agents/skills/) - зачем нужен и как работает (README.md в каждом скиле)
- [Рулесы](./03-rules.md) - триггеры канона
- [JSONdoc](./06-jsondoc.md) - batch доступ и ingest
- [Рабочие цепочки](./07-workflows.md) - порядок вызова
- [Контур планирования](./08-plan-contour.md) - prepare-plan подробно
- [Перенос](./09-transfer.md) - профили скилов FULL и CORE
- [Канон тестирования](../testaudit.md) - ветки логики и готовность

---

## История изменений

- 2026-11-11: сводка приведена к канону: 77 скилов с `SKILL.md` и 28 верхних каталогов; карта по группам остаётся маршрутом, а не полным перечнем дочерних скилов.
- 2026-11-11: скилы `business-analyst` и `task-business-analysis` сняты с харнеса; каталог данных `.doc/skil_data/business-analyst` удален.
- 2026-11-10: аудит плана вынесен в отдельный скил `audit-plan`; `prepare-plan` остался автором плана. Обновлены карта, счетчики и реестр.
- 2026-11-10: исправления по [аудиту процесса подготовки плана](../../auditskil777.md) затрагивают prepare-plan, business-analyst, task-business-analysis, git-task-blame и MCP-скилы. README и docs/scripts сохраняются по стандарту харнеса; ponytail исключён из изменений.
- 2026-10-02: четыре документа скилов объединены в один (задачи, документация, мета, внешние)
- 2026-10-30: `gototask` получил шаг 5b (якорь задачи)
- 2026-10-30: добавлен `business-analyst` (всего 23 скила), контур бизнес-логики в [17-business-analyst.md](./17-business-analyst.md)
- 2026-10-31: карта приведена к коду: 14/3/1/5 скилов, добавлен `task-intake`, у `gototask` убрана ложная зависимость от `find-task-branch.ps1` и описаны consent gate и хук business-analyst
- 2026-11-01: описания скилов находятся в `.agents/skills/{name}/README.md`; здесь остались карта, ссылки и реестр. Выжимка testaudit перенесена в канон [testaudit.md](../testaudit.md) по ссылке
- 2026-11-02: добавлен `codegraph`; после удаления legacy-правила graphify реестр 54 = 27 скилов и 27 rule-only компонентов
- 2026-11-02: реестр сверен с файлом: 54 компонента = 26 скилов и 28 rule-only компонентов
- 2026-11-02: добавлен `ponytail`; фактический реестр 54 = 26 скилов и 28 rule-only компонентов.
  Канон скилов в синке: `.agents/skills`; Kilo читает его напрямую, `.codex/skills`
  нужен только Codex.
- 2026-11-02: добавлен `codeprism` (импорт скила knight22-21/CodePrism под сервер
  `codeprism-ai`); 28 скилов, реестр 56 = 28 скилов и 28 rule-only компонентов.
- 2026-11-05: добавлены `add-skill` и `remove-skill` для установки локальных
  скилов и удаления с очисткой документации; 30 скилов, реестр 58.
- 2026-11-05: добавлен `skill-authoring` для создания и аудита скилов;
  31 скил, реестр 59.
- 2026-11-05: добавлен `migration-review` для разбора скилов, правил и MCP
  после переноса; 32 скила, реестр 63.
- 2026-11-05: добавлен `copytrust` с детьми `platform-logs` и
  `platform-browser-test` для логов и браузерной проверки заказов; 35 скилов,
  реестр 66.
- 2026-11-05: добавлен `code` с дочерним `bug-cause` для расследования
  истинной причины бага по дифам, задачам, документации и графу вызовов;
  37 скилов, реестр 68.
- 2026-11-06: добавлен `task-spec` для сбора требований из переписки и
  формулировки однозначного документа задачи; 38 скилов, реестр 69.
- 2026-11-06: в `add-skill`, `improvement` и `mcp-audit` закреплены обязательная
  документация и отдельный формат хранения данных компонента.
- 2026-11-09: добавлен `copy-project` для переноса Git-состояния приложения
  в новую папку без harness, без секретов и без базы; Мета-харнес 9 скилов.
- 2026-11-10: `neiroslop` приведён к формату харнеса по итогам
  `skill-auditor`: исправлены frontmatter и имя, примеры и ресёрч перенесены
  в `references/`, добавлены README, `skill.json` и evals. Скил редактирует
  русский текст и не входит в контур задач.
- 2026-11-10: `copy-project` копирует `.git` вместе с проектом, удаляет в копии
  worktree-регистрации и lock-файлы. Причина: копия осталась без репозитория,
  `git status` падал с `not a git repository`.
