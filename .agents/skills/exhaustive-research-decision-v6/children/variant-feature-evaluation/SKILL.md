---
name: variant-feature-evaluation
description: Оценивает кандидаты по единому criteria.csv, строит полную decision-matrix.csv, проверяет hard gates, веса, sensitivity и rank reversal. Использовать когда варианты/технологии/продукты уже найдены и criteria-synthesis закрыл словарь признаков. Не создаёт второй словарь фич и не подменяет reuse decision.
---

# variant-feature-evaluation

Вход: `criteria.csv`, `feature-dictionary.csv`, `feature-evidence.csv`, `synthetic-scores.csv`, `candidates.csv`, `method-registry.md`.  
Выход: `decision-matrix.csv`, обновлённый `synthetic-scores.csv` по sensitivity.

## 1. Не дублировать критерии

Этот скилл **не создаёт** новый `feature-dictionary.csv` и не переопределяет `criteria.csv`. Он потребляет канонические файлы `criteria-synthesis`. Если критерий отсутствует, создаётся `gap_id`, а не локальная таблица.

## 2. Полная матрица

Для каждого `candidate_id` и каждого `criterion_id` с `applies_to_all: yes` должна быть строка:

```csv
candidate_id,criterion_id,raw_value,normalized,score,source_ids,method_ids,status,notes
C001,K001,120000,0.82,0.164,S001;S002,M015;M030,verified,"TCO из двух источников"
C002,K001,not_supported,0,0,S003,M015,n/a,"нет managed-режима; обоснование в gaps.csv"
```

Правила:

- `unknown` запрещён в финальной матрице; сначала `gaps.csv` и второй проход.
- `n/a` и `not_supported` требуют `notes` и `gap_id`.
- `0` — численное значение, а не «нет данных».
- `hard_gate: yes` проверяется до взвешивания; балл не перебивает veto.

## 3. Веса и ранг

- AHP/MAVT/TOPSIS/ELECTRE/Pugh выбираются из `method-registry.md`.
- Веса фиксируются с `method_ids` и `rationale`.
- Обязательны sensitivity, Monte Carlo или сценарный анализ, `rank_reversal_at`.
- Синтетические критерии проходят повторный пересчёт при изменении нормализации.

## 4. Исключения

Исключённые кандидаты не удаляются молча: причина, `source_ids`, дата/версия и негативный результат пишутся в `notes` или отдельный `exclusions.md`, если он создан через deviation. `reuse-decision.md` ссылается на эти причины.

## 5. Stop

`MATRIX_COMPLETE`, `SENSITIVITY` = PASS только если все ячейки заполнены, все hard gates проверены, веса согласованы, rank reversal исследован, синтетика пересчитана. Иначе `INCOMPLETE`.

## Запрещено

- Сравнивать кандидатов по разным наборам критериев.
- Закрывать противоречие весом.
- Превращать unknown в средний балл.
- Скрывать исключённые семейства.
