# Criteria and synthetic scores

## Четыре источника критериев

1. `brief` — цели, ограничения, DoD.
2. `domain_standard` — адаптер домена.
3. `candidate_union` — объединение характеристик всех кандидатов.
4. `synthetic` — проектные метрики поверх первых трёх.

## Union / two-pass

```text
Pass 1: candidate A 50 features, candidate B 30 features -> union 58 normalized features
Pass 2: fill missing cells for every candidate
Result: candidate × feature matrix without holes
```

Значения:

```text
verified | provisional | disputed | unknown | not_supported | n/a
```

`unknown` блокирует decision-critical оценку. `not_supported` и `n/a` требуют обоснования и `gap_id`. `0` — только численное значение.

## Пример vector search

Критерий `vector_search_support` применяется ко всем:

| Кандидат | Значение |
|---|---|
| A | `native`, HNSW + filters |
| B | `extension`, plugin |
| C | `unknown`, нужен gap-scout |
| D | `not_applicable`, не storage-движок |

Нельзя сравнивать только «у кого есть». Колонка общая для всех.

## Synthetic scores

| Метрика | Формула | Оговорка |
|---|---|---|
| `speed_score_parrots` | normalized tokens/s + p95 + throughput | калибровка на representative benchmark |
| `budget_fit_pct` | `clamp(1-(TCO-budget)/budget,0,1)` | штраф и вес утверждает пользователь |
| `project_fit_pct` | weighted sum/TOPSIS по `criteria.csv` | воспроизводимый расчёт, не «ощущение» |
| `risk_adjusted_utility` | utility − penalty(harm, uncertainty) | sensitivity обязательна |

Каждая синтетика: `formula`, `input_feature_ids`, `normalization`, `method_ids`, `sensitivity_status`, `owner`. Синтетика никогда не записывается в `sources.csv` как факт.

## Hard gates до весов

Лицензия, регуляция, safety, RPO/RTO, совместимость, юрисдикция — veto. Взвешивание не перебивает провал hard gate.
