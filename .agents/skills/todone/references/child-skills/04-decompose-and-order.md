# Разложить и упорядочить работу

Поток — JSON-определение шагов, не отдельная очередь. Записи потока обычны;
`flow`/`flow_step` лежат в строках индекса.

```bash
tcheck flows list
tcheck flows show jira-fix
ttask flow start --flow jira-fix --from T-021 --by lead
ttask flow state T-021 --flow jira-fix
ttask flow next T-022
```

`flow start` создаёт только доступные черновики, не переводит их в работу и
уважает `max_batch`/`--batch`. Повторный запуск создаёт оставшиеся шаги.
Человек публикует черновик `ttask status <id> --status ready --by <имя>`.

`flow next` показывает следующий шаг, declared outputs его входов и то, что уже
оставлено. При пропаже выхода — `FLOW_OUTPUT_MISSING`; при рассинхронизации
индекса и определения — `FLOW_STATE_MISMATCH`.
