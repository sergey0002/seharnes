# Поток `release-testing`

## Назначение

Короткий маршрут проверки релиза из текстового входа: сначала подготовить тесты,
затем выполнить прогон и по желанию обновить документацию.

## Порядок шагов

```text
test-prep → testing → (doc?)
```

- `test-prep` формулирует набор проверок и передаёт `handoff`;
- `testing` запускает команды, сохраняет evidence и verdict по AC-N;
- optional `doc` проверяет/обновляет документацию, проходя docs-гейт.

Точные поля `output`, роли и гейты находятся в `flow.json`.

## Как запускать

```bash
tcheck flows show release-testing
ttask flow start --flow release-testing --from T-001 --by lead
ttask flow state T-001 --flow release-testing
ttask flow next T-002
```

`max_batch: 3`. Сначала создаются draft, затем человек переводит их в `ready` и
исполнители оставляют evidence/handoff. Optional шаг не означает, что его выход
можно выдумать: если шаг выбран, он обязан пройти свой gate.

## Границы

Поток — маршрут обычных записей. Он не хранит копию отчёта, не создаёт отдельную
очередь состояния и не изменяет внешний mirror. При отсутствии объявленного
выхода — `FLOW_OUTPUT_MISSING`.

<!-- AUTODOC:BEGIN diagram=flow:release-testing source_digest=sha256:9a5268461d60ee7ce7f8132a8619f49679c8722c809d111a0a7ba102d0b47ecf projection_digest=sha256:7063199b933410b89d3e51af4760f12e38cf1437773ccd0f2ed73130215bccfc spec_digest=sha256:4b89d82033a87455fe0d551a34869c22a5924644aefa39e201639be228054fc6 -->
```mermaid
%% AUTODOC-DIAGRAM: flow:release-testing
%%{init: {"theme":"base","themeVariables":{"background":"#f5f9fd","fontFamily":"Arial, sans-serif","fontSize":"14px","primaryColor":"#eaf3fc","primaryTextColor":"#132a42","primaryBorderColor":"#4b7697","lineColor":"#58758e","secondaryColor":"#e7f7f1","tertiaryColor":"#f0e9ff","edgeLabelBackground":"#eef4f8"},"flowchart":{"htmlLabels":false,"wrappingWidth":260,"nodeSpacing":55,"rankSpacing":60,"padding":16}}}%%
flowchart TB
accTitle: Проверка релиза
accDescr: Офлайн Mermaid-диаграмма «Проверка релиза»: 3 узлов и 2 переходов.
classDef normal fill:#eaf3fc,stroke:#4b7697,color:#132a42,stroke-width:1.5px,font-size:14px;
classDef optional fill:#eaf7ff,stroke:#2e86ab,color:#11384b,stroke-width:2px,font-size:14px;
classDef parallel fill:#e7f7f1,stroke:#2b8a72,color:#123c32,stroke-width:2px,font-size:14px;
classDef gate fill:#f0e9ff,stroke:#7651a6,color:#2c1d47,stroke-width:2px,font-size:14px;
classDef problem fill:#ffe8ec,stroke:#b84458,color:#54121e,stroke-width:2px,font-size:14px;
classDef muted fill:#edf2f6,stroke:#8391a0,color:#43505d,stroke-dasharray:4 3,font-size:14px;
  n_release_testing_test_prep_00e1bf56_0["test-prep · gate"]:::gate
  n_release_testing_testing_39fa4d06_1["testing · gate"]:::gate
  n_release_testing_doc_0fb98a3f_2["doc · optional / gate"]:::optional
  n_release_testing_test_prep_00e1bf56_0 -->|после| n_release_testing_testing_39fa4d06_1
  n_release_testing_testing_39fa4d06_1 -->|после| n_release_testing_doc_0fb98a3f_2
  click n_release_testing_test_prep_00e1bf56_0 href "#step-release-testing-test-prep" "Открыть описание шага"
  click n_release_testing_testing_39fa4d06_1 href "#step-release-testing-testing" "Открыть описание шага"
  click n_release_testing_doc_0fb98a3f_2 href "#step-release-testing-doc" "Открыть описание шага"
```
<!-- AUTODOC:END diagram=flow:release-testing -->
