# Context engineering and freedom profiles

## Минимальный high-signal context

Порядок загрузки:

```text
AGENTS.md / SKILL.md -> 00-brief.md -> 00-state.md -> 99-handoff.md
-> task-spec.md -> research-protocol.md -> criteria.csv -> нужные assignment outputs
```

Полный пакет в контекст не загружается. Детали подтягиваются just-in-time по `path + hash`.

## Профили

| Профиль | Модель/риск | Строгость |
|---|---|---|
| `frontier` | сильная модель, low/medium | guardrails + outcome gates; процедуры заменяемы |
| `balanced` | default | рекомендованный чеклист |
| `regulated` | high/critical | low freedom, scripts, human signoff |

## Типы правил

```text
G guardrail  — не нарушается
C criterion  — проверяется по результату
P procedure  — можно заменить через deviation-request.md
H heuristic  — по умолчанию, можно предложить лучше
```

Официальная практика Agent Skills рекомендует calibrating degrees of freedom: high freedom для неоднозначных задач, low freedom для хрупких/необратимых операций. Избыточно директивные инструкции могут ухудшать результат сильных reasoning-моделей; поэтому v6 проверяет не «сколько шагов сделано», а закрыты ли G- guardrails и итоговые критерии.

## Compaction / notes

`00-state.md`, `99-handoff.md`, `context-budget.md` и `loaded_files[].hash` заменяют историю чата. После волны сохраняются: open_gates, next_action, brief_hash, criteria_hash, residual_unknowns; сырые tool outputs удаляются.
