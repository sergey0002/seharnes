---
status: frozen
brief_hash: sha256:00219514a9dc6a5687b6d60a93f9b1b7ad2b277562bccb5a61c6d3020a208fba
freedom_profile: balanced
model_class: standard
risk_class: low
approved_by: demo-owner
open_blocking_questions: 0
human_gate: no
---

## Raw
Выбрать готовую методику документирования для агентной rebuild-среды; сначала проверить proven successful use.

## Pre-brief research
| known_id | statement | source_ids | method_ids | confidence |
|---|---|---|---|---|
| K001 | Нужна rebuild-совместимая спецификация | S001 | M010 | high |
| K002 | Готовые решения должны иметь proven use | S002 | M050 | high |

| unknown_id | gap | why_cannot_infer | candidate_question_ids |
|---|---|---|---|
| U001 | Версия C002 native client | нет в исходном запросе | Q1 |

## Clarified
goal: выбрать готовый профиль документирования с подтверждённым применением
why_now: требуется воспроизвести логику после удаления исходника
current_state: исходник недоступен, есть только сырая мысль
target_state: adopt-решение с полной матрицей критериев
problems_to_solve: [reuse_first, complete_criteria, synthetic_transparency]
stakeholders: [demo-owner, rebuild-agent]
constraints: [не изобретать новую методику]
success_metrics: [PASS гейтов, 0 open gaps]
definition_of_done: PASS валидатора и подписанный reuse-decision
out_of_scope: [pixel-perfect UI]
acceptance_authority: demo-owner
assumptions: [C001 и C002 доступны в текущих версиях]
open_unknowns: [C002 native client parity after v2.4]
review_triggers: [смена версии C002]

## Approval + freeze
approved_at: 2026-11-10T12:00:00+07:00
approval_evidence: explicit demo approval
amendment_policy: re-open G-A
