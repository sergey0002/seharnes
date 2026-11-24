# Лента реплик

`comments` — массив COMMENT-1 внутри `task.json`: `id`, `at`, `by`, `kind`,
`text` и optional внешний id/вопрос/решение. Ограничения длины текста нет.

```bash
ttask comment add T-001 --body «…» --kind human --by lead
ttask comment list T-001
ttask comment brief T-001 --last 3
ttask comment apply T-001 --comment C-2 --note «принято» --by lead
ttask comment reject T-001 --comment C-3 --note «отклонено» --by lead
```

Виды: `human`, `agent`, `import`, `proposal`, `handoff`. Handoff входит в
выбранный handoff-срез всегда; это не означает, что остальные старые реплики
потеряны — полный режим остаётся доступен. Импорт пишет `import` в зеркало;
ручной комментарий внешнему зеркалу блокируется.
