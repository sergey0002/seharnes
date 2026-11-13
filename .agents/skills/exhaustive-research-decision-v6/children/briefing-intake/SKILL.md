---
name: briefing-intake
description: Формализует сырую мысль пользователя в одобренную задачу и исследовательский протокол до запуска поиска. Использовать когда пришла новая размытая задача, выбор, сравнение, разработка стандарта или восстановление продукта. Не ищет кандидаты и не считает критерии.
---

# briefing-intake

Вход: сырой текст, `00-state.md` при resume, доступные файлы проекта, доменные стандарты.  
Выход: только `00-brief.md`, `task-spec.md`, `research-protocol.md`. В чат возвращать `status`, `brief_hash`, `open_blocking_questions`, `next_action`.

## 1. Один версионируемый файл, а не россыпь

`00-brief.md` содержит четыре явно помеченные секции:

```markdown
---
status: draft | clarified | approved | frozen
brief_hash: sha256:...
freedom_profile: frontier | balanced | regulated
model_class: frontier | standard | small
risk_class: low | medium | high | critical
approved_by: user | delegate
open_blocking_questions: 0
---

## Raw
<дословно, опечатки сохраняем>

## Pre-brief research
| known_id | statement | source_ids | method_ids | confidence |
| unknown_id | gap | why_cannot_infer | candidate_question_ids |
| assumption_id | statement | owner | risk_if_wrong |

## Clarified
goal: ...
why_now: ...
current_state: ...
target_state: ...
problems_to_solve: [...]
stakeholders: [...]
constraints: [...]
success_metrics: [...]
definition_of_done: ...
out_of_scope: [...]
acceptance_authority: ...
assumptions: [...]
open_unknowns: [...]
review_triggers: [...]

## Approval + freeze
approved_at: ...
approval_evidence: ...
amendment_policy: ...
```

## 2. Вопросы без искусственного лимита

- `brief-questions.csv` допустим как дополнительный view, но не как второй источник истины.
- Вопрос задаётся только если ответ меняет цель, требование, риск, метод, границу или критерий принятия.
- Pre-brief research сначала находит ответы в файлах/стандартах; пользователя не спрашивают о том, что уже выводимо.
- Использовать `ask questions tool`, clarifying questions Plan Mode и front-loaded интервью Kiro.
- Останов по sufficiency, а не по N: 5W1H/ISQ закрыты, цели измеримы, `definition_of_done` проверяемо, нет `open-blocking`, пользователь одобрил, критик подписал.
- Для `frontier` профиля число раундов можно сжать через `deviation-request.md`, но одобрение и freeze обязательны.

## 3. task-spec.md

Одна «идеальная операционная задача»: формулировка, границы, измеримые цели, DoD, residual unknowns, `brief_hash`, ссылки на `00-brief.md`.

```yaml
goal: ...
current_state: ...
target_state: ...
problems_to_solve: [...]
in_scope: [...]
out_of_scope: [...]
definition_of_done: ...
residual_unknowns: [...]
brief_hash: sha256:...
```

## 4. research-protocol.md

Это **не SDD**. Это аналог PRISMA-P / OSF preregistration для исследования и принятия решения:

```markdown
question_format: PICO | PCC | 5W1H | free
eligibility: [...]
exclusion: [...]
information_sources: [...]
search_plan: ...
synthesis_plan: ...
analysis_plan: ...
criteria_plan: "brief -> domain -> candidate_union -> synthetic"
reuse_policy: "adopt/adapt/extend/compose до build"
amendment_log: []
protocol_registered_at: ...
registration_id: local:<task-id>
```

Любое изменение после freeze = поправка в `amendment_log` с датой, причиной и влиянием на `criteria.csv` / `research-assignments.csv`.

## 5. Stop

`BRIEF = PASS` только если `status: frozen`, `open_blocking_questions: 0`, `brief_hash` заполнен, `task-spec.md` и `research-protocol.md` exist, `approval_evidence` не placeholder. Иначе `INCOMPLETE`.

## Запрещено

- Начинать поиск кандидатов до freeze.
- Переписывать Raw «красивее» без diff.
- Ограничивать вопросы числом.
- Спрашивать о фактах, уже выведенных из источников.
- Давать диагноз/назначение/разрешение работ на этапе брифинга.
