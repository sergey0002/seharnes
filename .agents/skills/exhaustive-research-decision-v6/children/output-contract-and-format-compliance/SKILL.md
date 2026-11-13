---
name: output-contract-and-format-compliance
description: Сопоставляет выходной пакет с принятыми спецификациями и machine-checkable схемами. Использовать перед финальным PASS. Не подменяет доменную верификацию и reuse decision.
---

# output-contract-and-format-compliance

Вход: все канонические артефакты, `assets/schemas/*.json`, `method-registry.md`, `gates.json`.  
Выход: `compliance-matrix.csv`, финальный `gates.json`, `final-report.md` через корневой скилл.

## 1. Гибридная природа выхода

Единого стандарта для «AI research decision dossier» нет. Соответствие оценивается по семействам:

| Семейство | Артефакт |
|---|---|
| PRISMA-P / OSF preregistration | `research-protocol.md`, amendments |
| PRISMA 2020 / SWiM | `sources.csv`, synthesis, contradictions |
| GRADE EtD | только клиника, через domain adapter |
| ISO 29148 / EARS / Volere / Gherkin | `task-spec.md`, `criteria.csv`, `verification.md` |
| ISPOR MCDA | `criteria.csv`, `decision-matrix.csv`, `synthetic-scores.csv` |
| Spec Kit / Kiro / OpenSpec / Reversa | `reuse-decision.md`, `research-assignments.csv`, deltas |
| AGENTS.md / llms.txt / Agent Skills | `00-brief.md`, `00-state.md`, `context-budget.md` |
| Structured Outputs / JSON Schema | `assets/schemas/*.json`, `gates.json` |

## 2. compliance-matrix.csv

```csv
standard_id,requirement,artifact,status,score,gap,owner,method_ids
STD-01,"protocol before search",research-protocol.md,compliant,9,—,orchestrator,M020
STD-07,"weights and uncertainty reported",synthetic-scores.csv,partial,8,"stakeholder validation не проведена",user,M015
```

Допустимые `status`: `compliant | partial | missing | n/a`. `missing` без `gap/owner` = blocking. `partial` переносится в `residual_unknowns`.

## 3. Schemas

`assets/schemas/*.schema.json` проверяют `criteria.csv`-подобные структуры, `gates.json`, assignments и candidate records. Все объекты имеют `additionalProperties: false` и явный `required`; валидатор не требует внешних зависимостей.

## 4. Профили свободы

- `frontier`: можно сократить число отчётных артефактов через deviation, но `compliance-matrix.csv`, `gates.json` и `residual_unknowns` обязательны.
- `balanced`: полный набор по умолчанию.
- `regulated`: добавляются подписи, audit trail и неизменяемыеchemas.

## 5. Stop

`OUTPUT_CONTRACT`, `NO_FAKE_PASS` = PASS только если manifest полон, схемы валидируют ключевые JSON, compliance matrix закрыта, `gates.json` записан `scripts/check_gates.py`, а не вручную.

## Запрещено

- Выдавать PASS без валидатора.
- Скрывать `partial`/`missing`.
- Называть гибрид «сертифицированным стандартом».
- Копировать `gates.json` из прошлого прогона.
