# Existing-solutions-first

## Принцип

Никакого нового формата/методики/движка до `reuse-decision.md`. Сначала ищутся готовые решения с подтверждённым опытом успешного применения.

## candidate_type

```text
oss | commercial | saas | managed | hardware | standard | methodology | process |
framework | library | model | vendor | hybrid | internal_legacy
```

Open source — пример, а не ограничение. Для задачи подбора видеокарты кандидатами будут hardware + driver stack + framework + managed inference; для документирования софта — Reversa, OpenSpec, Spec Kit, Kiro, AGENTS.md/llms.txt, внутренние standards; для клиники — валидированные рекомендации и EtD-фреймворки; для пожара — S700 и локальные протоколы.

## adoption evidence

| Тип | Что даёт |
|---|---|
| production case study | реальное внедрение |
| independent benchmark | сравнение без vendor bias |
| standard/spec | формальная норма |
| changelog/docs | версия и границы применимости |
| post-mortem | скрытые failure modes |
| community/maintenance | живучесть и exit strategy |

## Reuse ladder

```text
ADOPT → ADAPT → EXTEND → COMPOSE → BUILD
```

`COMPOSE` особенно важен: часто оптимально не «одно готовое», а 2–3 готовых решения с явным `compose_map`. `BUILD` разрешён только при `gap_proven: yes`.

## Anti-bicycle gates

- `REUSE_FIRST`;
- `CANDIDATE_ADOPTION`;
- `BUILD_JUSTIFICATION`;
- `NO_REINVENTION`;
- `reuse-critic` проверяет, что новое решение не повторяет существующее.
