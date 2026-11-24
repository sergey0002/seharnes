# Поток `jira-feature`

## Назначение

Маршрут для внешней задачи Jira о новой возможности. Входом служит обычная
запись `mirror` или другая запись, от которой человек запускает поток.

## Порядок шагов

```text
intake → (research ∥ planning ∥ test-prep) → feature → (code-review?) → testing
```

- `intake` формализует сырой вход и оставляет `handoff`;
- `research` и `planning` читают общий вход параллельно;
- `test-prep` связывает будущий прогон с критериями;
- `feature` реализует утверждённый план;
- optional `code-review` разбирает дифф;
- `testing` обязан оставить verdict и evidence.

Точные типы, выходы, исполнители и гейты находятся в `flow.json`; этот файл не
дублирует состояние конкретной задачи.

## Как запускать

```bash
tcheck flows show jira-feature
ttask flow start --flow jira-feature --from T-001 --batch 5 --by lead
ttask flow state T-001 --flow jira-feature
ttask flow next T-002
```

`max_batch` равен 5. `flow start` создаёт доступные шаги как `draft`, не делает
их `ready` и не берёт их в работу. Следующий вызов создаёт оставшиеся шаги.
Человек публикует каждый черновик через `ttask status <id> --status ready`.

## Границы

Поток не редактирует зеркало и не создаёт state-файл. `flow` и `flow_step` живут
в строках индекса, а факты — в обычных `task.json`. Не копируй факты между
шагами: оставляй `refs(kind=queue)` и артефакты. Если закрытый входной шаг не
оставил объявленный выход, остановись с `FLOW_OUTPUT_MISSING`.

<!-- AUTODOC:BEGIN diagram=flow:jira-feature source_digest=sha256:99d9fa0625e4db3bb7280cc5791befce16b4ce1be9ebb9dd341356218cbafd23 projection_digest=sha256:d9e047febb5b70cf96e912996db43410bbbe55da579e2ce3fb93dc1557357448 spec_digest=sha256:9d73b60ae5169c3b5c61e9b593f4df0b8d633b965192d015af41388ea4116218 -->
```mermaid
%% AUTODOC-DIAGRAM: flow:jira-feature
%%{init: {"theme":"base","themeVariables":{"background":"#f5f9fd","fontFamily":"Arial, sans-serif","fontSize":"14px","primaryColor":"#eaf3fc","primaryTextColor":"#132a42","primaryBorderColor":"#4b7697","lineColor":"#58758e","secondaryColor":"#e7f7f1","tertiaryColor":"#f0e9ff","edgeLabelBackground":"#eef4f8"},"flowchart":{"htmlLabels":false,"wrappingWidth":260,"nodeSpacing":55,"rankSpacing":60,"padding":16}}}%%
flowchart TB
accTitle: Задача из Jira: возможность
accDescr: Офлайн Mermaid-диаграмма «Задача из Jira: возможность»: 7 узлов и 8 переходов.
classDef normal fill:#eaf3fc,stroke:#4b7697,color:#132a42,stroke-width:1.5px,font-size:14px;
classDef optional fill:#eaf7ff,stroke:#2e86ab,color:#11384b,stroke-width:2px,font-size:14px;
classDef parallel fill:#e7f7f1,stroke:#2b8a72,color:#123c32,stroke-width:2px,font-size:14px;
classDef gate fill:#f0e9ff,stroke:#7651a6,color:#2c1d47,stroke-width:2px,font-size:14px;
classDef problem fill:#ffe8ec,stroke:#b84458,color:#54121e,stroke-width:2px,font-size:14px;
classDef muted fill:#edf2f6,stroke:#8391a0,color:#43505d,stroke-dasharray:4 3,font-size:14px;
  n_jira_feature_intake_7bca20e6_0["intake · gate"]:::gate
  n_jira_feature_research_747dd746_1["research · parallel / gate"]:::parallel
  n_jira_feature_planning_88feed45_2["planning · parallel / gate"]:::parallel
  n_jira_feature_test_prep_2ef4e6bc_3["test-prep · parallel / gate"]:::parallel
  n_jira_feature_feature_f7154916_4["feature · gate"]:::gate
  n_jira_feature_code_review_e99d026f_5["code-review · optional / gate"]:::optional
  n_jira_feature_testing_88c4375b_6["testing · gate"]:::gate
  n_jira_feature_feature_f7154916_4 -->|после| n_jira_feature_code_review_e99d026f_5
  n_jira_feature_feature_f7154916_4 -->|после| n_jira_feature_testing_88c4375b_6
  n_jira_feature_intake_7bca20e6_0 -->|после| n_jira_feature_planning_88feed45_2
  n_jira_feature_intake_7bca20e6_0 -->|после| n_jira_feature_research_747dd746_1
  n_jira_feature_intake_7bca20e6_0 -->|после| n_jira_feature_test_prep_2ef4e6bc_3
  n_jira_feature_planning_88feed45_2 -->|после| n_jira_feature_feature_f7154916_4
  n_jira_feature_research_747dd746_1 -->|после| n_jira_feature_feature_f7154916_4
  n_jira_feature_test_prep_2ef4e6bc_3 -->|после| n_jira_feature_feature_f7154916_4
  click n_jira_feature_intake_7bca20e6_0 href "#step-jira-feature-intake" "Открыть описание шага"
  click n_jira_feature_research_747dd746_1 href "#step-jira-feature-research" "Открыть описание шага"
  click n_jira_feature_planning_88feed45_2 href "#step-jira-feature-planning" "Открыть описание шага"
  click n_jira_feature_test_prep_2ef4e6bc_3 href "#step-jira-feature-test-prep" "Открыть описание шага"
  click n_jira_feature_feature_f7154916_4 href "#step-jira-feature-feature" "Открыть описание шага"
  click n_jira_feature_code_review_e99d026f_5 href "#step-jira-feature-code-review" "Открыть описание шага"
  click n_jira_feature_testing_88c4375b_6 href "#step-jira-feature-testing" "Открыть описание шага"
```
<!-- AUTODOC:END diagram=flow:jira-feature -->
