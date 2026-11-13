# variant-feature-evaluation

Оценивает кандидатов по единому `criteria.csv`, строит полную
`decision-matrix.csv`, проверяет hard gates, веса, sensitivity и rank
reversal. Не создаёт второй словарь признаков и не подменяет reuse decision.

Входит в пакет `exhaustive-research-decision-v6`. Вызывается родительским
скиллом по маршрутизации запроса. Инструкция: `SKILL.md`.
