---
name: evidence-provenance
description: Ведёт канонический факт-слой: источники, claims, method registry, contradictions, synthesis. Использовать когда любой вывод, критерий, вес, фича или исключение должен трассироваться F/CL → S → M.
---

# evidence-provenance

Вход: все assignment outputs, `research-protocol.md`, `method-registry.md`.  
Выход: `sources.csv`, `claims.csv`, `method-registry.md`, `contradictions.csv`, `critique-log.csv`.

## 1. sources.csv

```csv
source_id,url,document_name,type,tier,date,version,location,excerpt,independence_group,claim_ids,method_ids,retrieval_date
S001,https://...,Official Docs,standard,T0,2026-11-10,2.4,§4,"native HNSW with filters",VendorA,CL001,M010;M017,2026-11-10
```

`excerpt` дословный. 50 репостов одного пресс-релиза = одна `independence_group`.

## 2. claims.csv — единственный реестр утверждений

```csv
claim_id,statement,decision_critical,source_ids,method_ids,verification_status,qualification,contradiction_ids
CL001,"FrameworkA поддерживает нативный HNSW",yes,S001;S002,M010;M017,verified,"версия 2.4; docs §4",—
```

`decision_critical: yes` без `source_ids`, `method_ids`, `excerpt`, `date/version` и `location` = blocking.

## 3. method-registry.md

Регистрируется **до поиска**. Смена после результатов = amendment.

```markdown
| MID | method | canonical_source | version | scope | applicability | limitation | pre_registered_at | amendment |
|---|---|---|---|---|---|---|---|---|
| M010 | Contract/spec extraction | https://... | 2026 | 30-contracts | machine contracts | не заменяет бизнес-логику | 2026-11-10T09:00 | — |
```

## 4. contradictions.csv

Конфликтующие значения сохраняются **обоими** атрибуциями; усреднение запрещено.

```csv
contradiction_id,claim_a,claim_b,source_a,source_b,resolution,status,method_ids
D001,CL011,CL012,S001,S003,"разные условия измерения; требуется domain critic",resolved,M017;M018
```

## 5. critique-log.csv

Три точки критики: после brief, после union/gap-filling, перед финалом. Для `frontier` можно заменить независимых критиков аргументированным self-audit через `deviation-request.md`, но blocking findings должны быть закрыты.

## 6. Stop

`PROVENANCE`, `CONTRADICTION`, `CRITIQUE` = PASS только если нет `unsupported`, нет `unresolved-blocking`, все blocking critique resolved, method registry закрыт до первой волны.

## Запрещено

- Публиковать факт без excerpt/URL/версии.
- Усреднять несовместимые источники.
- Регистрировать методику после того, как увидели результат.
- Выдавать T3-маркетинг за T0-стандарт.
