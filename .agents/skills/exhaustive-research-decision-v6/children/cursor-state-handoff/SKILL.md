---
name: cursor-state-handoff
description: Управляет возобновляемым состоянием, корректными ссылками на промежуточные файлы, чекпоинтами, compaction и handoff. Использовать перед стартом/возобновлением и после каждой волны. Не собирает факты и не выбирает решение.
---

# cursor-state-handoff

## 1. Старт / resume

Прочитать строго по путям:

```text
00-brief.md
00-state.md
99-handoff.md
task-spec.md
research-protocol.md
criteria.csv
gates.json
```

Не полагаться на историю чата. Не переспрашивать уже записанные вопросы. Продолжить ровно с `next_action`.

## 2. 00-state.md

```yaml
task_id: ...
phase: criteria-synthesis
wave: 2
freedom_profile: frontier | balanced | regulated
model_class: frontier | standard | small
risk_class: low | medium | high | critical
active_subagents: [...]
open_gates: [...]
last_checkpoint: 2026-11-10T14:20:00+07:00
next_action: "дозаполнить 7 ячеек feature-evidence.csv; см. gaps.csv"
residual_unknowns: [...]
loaded_files:
  - path: criteria.csv
    hash: sha256:...
  - path: feature-evidence.csv
    hash: sha256:...
files_changed_since_checkpoint: [...]
```

Ссылки — **path + hash + stable_id**, а не «§2 чата» и не «как помнится».

## 3. 99-handoff.md

```markdown
1. Прочитать: 00-brief.md, 00-state.md, task-spec.md, research-protocol.md, criteria.csv, gates.json.
2. НЕ читать историю чата как источник истины.
3. Проверить open_gates и loaded_files hash.
4. Субагенту передавать task_id + input_files[] + output_file + stop_condition.
5. После волны обновить 00-state.md, context-budget.md, 99-handoff.md, gates.json.
6. При исчерпании бюджета: INCOMPLETE + незакрытые гейты.
```

## 4. context-budget.md

```yaml
max_root_tokens: 6000
max_wave_tokens: 24000
max_loaded_files_per_wave: 3
subagent_summary_tokens: 2000
forbidden_in_context: ["весь unified doc", "история чата", "исходный код при clean-room rebuild"]
compaction_log: ...
```

Для `frontier` профиля `subagent_summary_tokens` и `max_loaded_files_per_wave` являются heuristic и могут быть изменены через `deviation-request.md`.

## 5. После волны

- обновить `loaded_files` с новыми hash;
- записать compaction: что сохранено, что удалено;
- обновить `open_gates` и `next_action`;
- запустить `check_v6()`;
- переписать `gates.json`.

## 6. Stop

`CONTEXT_BUDGET` = PASS только если state/handoff/budget обновлены, все loaded paths существуют, hash не пустые, `next_action` не placeholder.

## Запрещено

- Ссылаться на секции чата вместо файлов.
- Обновлять state «по памяти».
- Оставлять расхождение между `open_gates` и `gates.json`.
