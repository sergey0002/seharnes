# Файлы, указатели и артефакты

`refs` — адрес внешнего факта; `artifacts` — файл результата/доказательства.
Текст в `task.json` не копируется. Путь artifact относителен папки записи и не
может содержать абсолютный путь или `..`.

```bash
ttask ref add T-001 --kind file --path src/a.py \
  --note «основная функция» --by lead
ttask artifact add T-001 --kind report --path artifacts/report.json \
  --note «полный отчёт» --by lead
ttask evidence T-001 --kind tests --path artifacts/test.log \
  --note «stdout тестов» --by tester
ttask ref rename T-001 --old src/a.py --new src/core.py \
  --note «перенос» --by lead
```

Пояснение обязательно. `artifact add` проверяет существование файла; переименование
оставляет human-readable след в ленте. `tcheck doctor` ловит отсутствующий файл,
битую связь и stale digest. Зеркало не принимает эти операции.
