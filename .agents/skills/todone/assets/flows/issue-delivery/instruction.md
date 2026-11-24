# Поток `issue-delivery`

## Назначение

Универсальный preset для изменения в существующем проекте. Jira, файл, чат или другая система могут быть источником `mirror`; сам маршрут не знает происхождение входа.

## Фактический маршрут preset

```text
intake → research → test-prep → planning → plan-audit
       → implementation fan-out → documentation → test-fix → final-testing
```

В отличие от `jira-fix` и `jira-feature`, здесь план не может быть создан до закрытых research и test-prep. `planning.input_from` явно содержит оба шага, а все зависимости последовательны.

## План и аудит

`planning` — самостоятельная запись только потому, что этому preset нужны отдельный результат, refs, handoff и статус. Большой результат является artifact и по умолчанию может лежать как `artifacts/plan.md`; путь файла не является состоянием flow.

`plan-audit` — read-only запись. В `extra.verdict` обязателен один из вариантов:

Ветвление объявлено как `DECISION-TREE-1` в `flow.json`, а не как свободная логика исполнителя. Корневой узел читает `extra.verdict` закрытого аудита и ведёт только по объявленным маршрутам:

- `approved` — `implementation` может быть создан;
- `changes_required` — движок создаёт новую обычную запись `planning` с `flow_revision: 2` (или следующим номером), затем повторный `plan-audit`;
- `blocked` — реализация не создаётся и требуется решение человека.

`routes` остаётся compatibility-полем для старых FLOW-2 preset; если на шаге объявлен `decision_tree`, runtime использует дерево первым. Маршрут revision не меняет status автоматически. Человек по-прежнему закрывает план и аудит обычными командами; движок только материализует объявленный следующий экземпляр и проверяет `requires`.

## Implementation slices

`planning.extra.slice_list` — массив элементов с `slice_id`, `type`, `title`, `scope`, `depends_on`, `ac`, `tests` и `done_when`. `implementation.fan_out` создаёт по одному обычному `task.json` на элемент, записывает его `flow_item` в строку `index.json` и уважает `max_batch`. Повторный `flow start` создаёт только ещё не материализованные элементы.

`fan_out.join: all_closed` означает, что `documentation` и последующие шаги не создаются, пока все slices текущей revision не закрыты. Это fan-in в логическом flow, а не отдельная очередь: родитель/depends_on остаются обычными полями записей, а `flow_run`, `flow_item` и `flow_revision` — производные поля индекса.

## Документация: вопрос и глобальная policy

`documentation` в этом preset опциональна (`required: false`, `enforcement: advisory`). На входе шага runtime задаёт объявленный FLOW-DOC вопрос: `document_now`, `skip_once`, `switch_to_manual` или `cancel`. Ответ пользователя сохраняется в append-only ledger; исполнителю нельзя молча выбрать ветку за пользователя.

Глобальная policy рабочего пространства задаётся отдельно через `tcheck docs policy set` и имеет приоритет над default потока. Важные режимы:

- `ask` — задать вопрос шага;
- `manual` — не создавать шаг автоматически, но разрешить явный запуск документации;
- `disabled` — автоматически пропустить необязательный documentation с причиной; обязательный шаг даст `DOC_POLICY_CONFLICT`.

Порядок effective policy: workspace → flow/preset → step `documentation` → impact/explicit override → scoped decision для run/task. Это не меняет `flow.json` и не смешивает глобальную настройку с одноразовым ответом на вопрос.

## Выходы и handoff

Каждый закрытый prerequisite должен оставить заявленные `output`: поля `extra`, refs, artifacts или handoff. Результаты не копируются в родителя. `final-testing` принимает только фактическое evidence с командами, кодами возврата и verdict по исходным `AC-N`; подготовленные тесты сами по себе зелёным результатом не считаются.

## Запуск

```bash
tcheck flows show issue-delivery
ttask flow start --flow issue-delivery --from T-001 --by lead
ttask flow state T-001 --flow issue-delivery
ttask flow next T-002
```

Поток создаёт только черновики порцией `max_batch: 5`. Работу переводит в `ready` человек. Состояние запуска живёт в строках `flow`/`flow_step`/`flow_run`/`flow_item`/`flow_revision` производного `index.json`; отдельной очереди процесса нет.

<!-- AUTODOC:BEGIN diagram=flow:issue-delivery source_digest=sha256:63ef367c27f0fd5946d49d155dc1fa74817e9032fbd585408ebf536c456a48a5 projection_digest=sha256:a006bf0a64c1e3d6620157f990f6cd262cf04cb7949c9de31d3e0607bdba20da spec_digest=sha256:1d76fa6e40b07c19b3cb76382c471f547628177b08992785fcf1e8a54cfe6531 -->
```mermaid
%% AUTODOC-DIAGRAM: flow:issue-delivery
%%{init: {"theme":"base","themeVariables":{"background":"#f5f9fd","fontFamily":"Arial, sans-serif","fontSize":"14px","primaryColor":"#eaf3fc","primaryTextColor":"#132a42","primaryBorderColor":"#4b7697","lineColor":"#58758e","secondaryColor":"#e7f7f1","tertiaryColor":"#f0e9ff","edgeLabelBackground":"#eef4f8"},"flowchart":{"htmlLabels":false,"wrappingWidth":260,"nodeSpacing":55,"rankSpacing":60,"padding":16}}}%%
flowchart TB
accTitle: Исследование, аудит плана и реализация изменения
accDescr: Офлайн Mermaid-диаграмма «Исследование, аудит плана и реализация изменения»: 10 узлов и 12 переходов.
classDef normal fill:#eaf3fc,stroke:#4b7697,color:#132a42,stroke-width:1.5px,font-size:14px;
classDef optional fill:#eaf7ff,stroke:#2e86ab,color:#11384b,stroke-width:2px,font-size:14px;
classDef parallel fill:#e7f7f1,stroke:#2b8a72,color:#123c32,stroke-width:2px,font-size:14px;
classDef gate fill:#f0e9ff,stroke:#7651a6,color:#2c1d47,stroke-width:2px,font-size:14px;
classDef problem fill:#ffe8ec,stroke:#b84458,color:#54121e,stroke-width:2px,font-size:14px;
classDef muted fill:#edf2f6,stroke:#8391a0,color:#43505d,stroke-dasharray:4 3,font-size:14px;
  n_issue_delivery_intake_edcbf38f_0["intake · gate"]:::gate
  n_issue_delivery_research_ca3a47e9_1["research · gate"]:::gate
  n_issue_delivery_test_prep_d83024e0_2["test-prep · gate"]:::gate
  n_issue_delivery_planning_15a3736f_3["planning · gate"]:::gate
  n_issue_delivery_plan_audit_a0ace22e_4["plan-audit · gate"]:::gate
  n_issue_delivery_human_decision_b69b1ef6_5["Решение человека · terminal"]:::normal
  n_issue_delivery_implementation_3b5eaad5_6["implementation · fan-out / gate"]:::parallel
  n_issue_delivery_documentation_18654d87_7["documentation · gate"]:::gate
  n_issue_delivery_test_fix_28a02218_8["test-fix · gate"]:::gate
  n_issue_delivery_final_testing_48ec4ece_9["final-testing · gate"]:::gate
  n_issue_delivery_documentation_18654d87_7 -->|после| n_issue_delivery_test_fix_28a02218_8
  n_issue_delivery_implementation_3b5eaad5_6 -->|после| n_issue_delivery_documentation_18654d87_7
  n_issue_delivery_intake_edcbf38f_0 -->|после| n_issue_delivery_research_ca3a47e9_1
  n_issue_delivery_plan_audit_a0ace22e_4 -->|после| n_issue_delivery_implementation_3b5eaad5_6
  n_issue_delivery_planning_15a3736f_3 -->|после| n_issue_delivery_plan_audit_a0ace22e_4
  n_issue_delivery_research_ca3a47e9_1 -->|после| n_issue_delivery_planning_15a3736f_3
  n_issue_delivery_research_ca3a47e9_1 -->|после| n_issue_delivery_test_prep_d83024e0_2
  n_issue_delivery_plan_audit_a0ace22e_4 -->|verdict=approved| n_issue_delivery_implementation_3b5eaad5_6
  n_issue_delivery_plan_audit_a0ace22e_4 -->|verdict=blocked| n_issue_delivery_human_decision_b69b1ef6_5
  n_issue_delivery_plan_audit_a0ace22e_4 -->|verdict=changes_required| n_issue_delivery_planning_15a3736f_3
  n_issue_delivery_test_fix_28a02218_8 -->|после| n_issue_delivery_final_testing_48ec4ece_9
  n_issue_delivery_test_prep_d83024e0_2 -->|после| n_issue_delivery_planning_15a3736f_3
  click n_issue_delivery_intake_edcbf38f_0 href "#step-issue-delivery-intake" "Открыть описание шага"
  click n_issue_delivery_research_ca3a47e9_1 href "#step-issue-delivery-research" "Открыть описание шага"
  click n_issue_delivery_test_prep_d83024e0_2 href "#step-issue-delivery-test-prep" "Открыть описание шага"
  click n_issue_delivery_planning_15a3736f_3 href "#step-issue-delivery-planning" "Открыть описание шага"
  click n_issue_delivery_plan_audit_a0ace22e_4 href "#step-issue-delivery-plan-audit" "Открыть описание шага"
  click n_issue_delivery_implementation_3b5eaad5_6 href "#step-issue-delivery-implementation" "Открыть описание шага"
  click n_issue_delivery_documentation_18654d87_7 href "#step-issue-delivery-documentation" "Открыть описание шага"
  click n_issue_delivery_test_fix_28a02218_8 href "#step-issue-delivery-test-fix" "Открыть описание шага"
  click n_issue_delivery_final_testing_48ec4ece_9 href "#step-issue-delivery-final-testing" "Открыть описание шага"
```
<!-- AUTODOC:END diagram=flow:issue-delivery -->
