# HANDOFF

1. Прочитать: 00-brief.md, 00-state.md, task-spec.md, research-protocol.md, criteria.csv, gates.json.
2. НЕ полагаться на историю чата.
3. Проверить open_gates, loaded_files hash, next_action.
4. Субагенту передавать task_id + input_files[] + output_file + stop_condition.
5. После волны обновить 00-state.md, context-budget.md, 99-handoff.md, gates.json.
6. При исчерпании бюджета: INCOMPLETE и список незакрытых гейтов.
