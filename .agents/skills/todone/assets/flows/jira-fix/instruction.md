# Поток `jira-fix`

## Назначение

Маршрут для внешнего Jira-дефекта с воспроизведением, минимальным исправлением
и регрессионным прогоном.

## Порядок шагов

```text
intake → (research ∥ planning ∥ test-prep) → fix → (code-review?) → testing
```

`research` ищет причину и подтверждает воспроизведение, `planning` фиксирует
границы и способ исправления, `test-prep` готовит регрессионные проверки,
`fix` меняет код, optional `code-review` проверяет дифф, `testing` оставляет
фактическое evidence и verdict.

Точные `input_from`, `output`, executor, parallel/optional и `gate_out` читаются
из `flow.json`.

## Как запускать

```bash
tcheck flows show jira-fix
ttask flow start --flow jira-fix --from T-001 --by lead
ttask flow state T-001 --flow jira-fix
ttask flow next T-002
```

Порция ограничена `max_batch: 5`; создаются только черновики. Работу публикует
человек: `ttask status <id> --status ready --by <имя>`. После закрытия входных
шагов повтори `flow start`, чтобы создать оставшиеся.

## Границы

Зеркало только читается импортом; служебные уточнения — в дочерней `intake`.
Результат шага не вставляется в родителя. Если заявленный output отсутствует,
следующий шаг возвращает `FLOW_OUTPUT_MISSING`; если индекс и flow.json
расходятся — `FLOW_STATE_MISMATCH`.

<!-- AUTODOC:BEGIN diagram=flow:jira-fix source_digest=sha256:0738ca42b9228ffc7b38b1fd6ff84ec352c02a8ff500d5ec24d9e84cb6eb5567 projection_digest=sha256:46683c72daceaa6bb14bd2a086b6cc0da373d1e57f291a392bca8954f36c54fe spec_digest=sha256:29b4688e8c0ada70d43ddcf052b97e28bc3fb32753735b8955cf0335452957b1 -->
```mermaid
%% AUTODOC-DIAGRAM: flow:jira-fix
%%{init: {"theme":"base","themeVariables":{"background":"#f5f9fd","fontFamily":"Arial, sans-serif","fontSize":"14px","primaryColor":"#eaf3fc","primaryTextColor":"#132a42","primaryBorderColor":"#4b7697","lineColor":"#58758e","secondaryColor":"#e7f7f1","tertiaryColor":"#f0e9ff","edgeLabelBackground":"#eef4f8"},"flowchart":{"htmlLabels":false,"wrappingWidth":260,"nodeSpacing":55,"rankSpacing":60,"padding":16}}}%%
flowchart TB
accTitle: Задача из Jira: дефект
accDescr: Офлайн Mermaid-диаграмма «Задача из Jira: дефект»: 7 узлов и 8 переходов.
classDef normal fill:#eaf3fc,stroke:#4b7697,color:#132a42,stroke-width:1.5px,font-size:14px;
classDef optional fill:#eaf7ff,stroke:#2e86ab,color:#11384b,stroke-width:2px,font-size:14px;
classDef parallel fill:#e7f7f1,stroke:#2b8a72,color:#123c32,stroke-width:2px,font-size:14px;
classDef gate fill:#f0e9ff,stroke:#7651a6,color:#2c1d47,stroke-width:2px,font-size:14px;
classDef problem fill:#ffe8ec,stroke:#b84458,color:#54121e,stroke-width:2px,font-size:14px;
classDef muted fill:#edf2f6,stroke:#8391a0,color:#43505d,stroke-dasharray:4 3,font-size:14px;
  n_jira_fix_intake_f8da8be0_0["intake · gate"]:::gate
  n_jira_fix_research_c3a0b2f8_1["research · parallel / gate"]:::parallel
  n_jira_fix_planning_c3759896_2["planning · parallel / gate"]:::parallel
  n_jira_fix_test_prep_52c02179_3["test-prep · parallel / gate"]:::parallel
  n_jira_fix_fix_d0b03e1b_4["fix · gate"]:::gate
  n_jira_fix_code_review_e057d849_5["code-review · optional / gate"]:::optional
  n_jira_fix_testing_8722515b_6["testing · gate"]:::gate
  n_jira_fix_fix_d0b03e1b_4 -->|после| n_jira_fix_code_review_e057d849_5
  n_jira_fix_fix_d0b03e1b_4 -->|после| n_jira_fix_testing_8722515b_6
  n_jira_fix_intake_f8da8be0_0 -->|после| n_jira_fix_planning_c3759896_2
  n_jira_fix_intake_f8da8be0_0 -->|после| n_jira_fix_research_c3a0b2f8_1
  n_jira_fix_intake_f8da8be0_0 -->|после| n_jira_fix_test_prep_52c02179_3
  n_jira_fix_planning_c3759896_2 -->|после| n_jira_fix_fix_d0b03e1b_4
  n_jira_fix_research_c3a0b2f8_1 -->|после| n_jira_fix_fix_d0b03e1b_4
  n_jira_fix_test_prep_52c02179_3 -->|после| n_jira_fix_fix_d0b03e1b_4
  click n_jira_fix_intake_f8da8be0_0 href "#step-jira-fix-intake" "Открыть описание шага"
  click n_jira_fix_research_c3a0b2f8_1 href "#step-jira-fix-research" "Открыть описание шага"
  click n_jira_fix_planning_c3759896_2 href "#step-jira-fix-planning" "Открыть описание шага"
  click n_jira_fix_test_prep_52c02179_3 href "#step-jira-fix-test-prep" "Открыть описание шага"
  click n_jira_fix_fix_d0b03e1b_4 href "#step-jira-fix-fix" "Открыть описание шага"
  click n_jira_fix_code_review_e057d849_5 href "#step-jira-fix-code-review" "Открыть описание шага"
  click n_jira_fix_testing_8722515b_6 href "#step-jira-fix-testing" "Открыть описание шага"
```
<!-- AUTODOC:END diagram=flow:jira-fix -->
