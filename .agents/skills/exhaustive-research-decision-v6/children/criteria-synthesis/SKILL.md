---
name: criteria-synthesis
description: Строит единый реестр критериев из четырёх источников и полную матрицу признаков. Использовать когда найдены кандидаты и нужно получить один канонический criteria.csv, объединить характеристики разных решений, дозаполнить пропуски вторым проходом и отделить синтетические проектные метрики от фактов.
---

# criteria-synthesis

Вход: `00-brief.md`, `task-spec.md`, `research-protocol.md`, `candidates.csv`, `sources.csv`, domain adapters.  
Выход: `feature-dictionary.csv`, `feature-evidence.csv`, `criteria.csv`, `synthetic-scores.csv`, `gaps.csv`.

## 1. Четыре источника критериев

| origin | Откуда | Пример |
|---|---|---|
| `brief` | цели/ограничения/DoD из брифа | `budget <= X`, `RPO <= 15 min` |
| `domain_standard` | доменный adapter/стандарт | IICRC S700, GRADE, NIST AI RMF, OpenSSF Scorecard |
| `candidate_union` | объединение характеристик кандидатов | `vector_search_support`, `tensor_core_gen`, `streaming_api` |
| `synthetic` | формула поверх первых трёх | `speed_score_parrots`, `budget_fit_pct`, `project_fit_pct` |

## 2. Двухпроходный union

Пример: по Framework A собрали 50 характеристик, по Framework B — 30.

1. **Pass 1:** нормализовать алиасы, единицы, версии; построить union уникальных `feature_id`.
2. **Pass 2:** для каждого кандидата дозаполнить отсутствующие ячейки. Отсутствие признака — это `not_supported` или `n/a`, а не `0` и не пустота.
3. `unknown` идёт в `gaps.csv` и блокирует итоговую оценку, если критерий `decision_critical: yes`.

## 3. feature-dictionary.csv

```csv
feature_id,canonical_name,aliases,definition,unit,direction,source_ids,method_ids,version_scope
FTR001,vector_search_support,"semantic search; ANN",наличие нативного/расширяемого векторного поиска,enum,maximize,S001;S002,M010;M017,2026-11-10
```

## 4. feature-evidence.csv

```csv
candidate_id,feature_id,value,normalized_value,status,source_ids,excerpt,location,date,version,contradiction_ids,method_ids
C001,FTR001,native,2,verified,S001,"native HNSW with filters",docs §4,2026-11-10,2.4,—,M010
C002,FTR001,extension,1,verified,S002,"via plugin",docs §7,2026-11-10,1.9,—,M010
```

Допустимые `status`: `verified | provisional | disputed | unknown | not_supported | n/a`. Для `n/a` и `not_supported` обязательны `notes`/`gap_id`.

## 5. criteria.csv — один канонический реестр

```csv
criterion_id,name,origin,type,unit,direction,applies_to_all,na_policy,formula,input_feature_ids,weight,hard_gate,source_ids,method_ids,decision_critical,synthetic,owner,status
K001,budget_fit_pct,brief,synthetic,percent,maximize,yes,not_applicable_only,"clamp(1-(TCO-budget)/budget,0,1)",FTR010;FTR011,0.20,no,S001,M015;M030,yes,yes,user,verified
```

Правила:

- `type = factual | hard_gate | weighted | synthetic`;
- `synthetic = yes` требует `formula`, `input_feature_ids`, `method_ids`, `sensitivity_status`;
- `applies_to_all = yes` означает строку в `decision-matrix.csv` для каждого кандидата;
- `na_policy` объясняет, когда `n/a` допустим;
- `hard_gate` проверяется до весов.

## 6. synthetic-scores.csv

```csv
score_id,criterion_id,formula,input_feature_ids,normalization,method_ids,sensitivity_status,status
SYN001,K001,"clamp(1-(TCO-budget)/budget,0,1)",FTR010;FTR011,minmax_0_1,M015;M030,PASS,verified
```

Синтетика не маскируется под факт. «Попугаи», «процент подхода», «риск-скор» всегда имеют формулу, входы, нормализацию и проверку чувствительности.

## 7. gaps.csv

```csv
gap_id,link_type,link_id,owner,status,evidence
G001,feature_cell,C003-FTR007,feature-gap-scout,closed,S014
```

## 8. Stop

`UNION_COMPLETE`, `GAP_FILLING`, `CRITERIA_TRANSPARENCY`, `SYNTHETIC_TRANSPARENCY` = PASS только если:

- словарь признаков закрыт;
- у каждого `candidate × feature` есть строка;
- нет `unknown` по decision-critical ячейкам;
- у каждого синтетического критерия есть formula/inputs/sensitivity;
- `criteria.csv` — единственный реестр критериев.

## Запрещено

- Сравнивать кандидатов по разным наборам критериев.
- Превращать `unknown` в `0`.
- Считать «процент подхода» фактом.
- Позволять маркетинговым названиям создавать дубли признаков.
- Скрывать формулу синтетической оценки.
