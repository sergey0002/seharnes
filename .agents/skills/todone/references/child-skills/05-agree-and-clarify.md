# Уточнить и согласовать

Модель не заполняет пробелы молча. Неизвестное заноси в `open_questions` или
поле типа, вопрос человеку — `ASK_USER`.

```bash
ttask comment add T-001 --body «Нужно уточнить срок» \
  --kind human --question --by analyst
ttask comment add T-001 --body «Предлагаю вариант B» \
  --kind proposal --by planner
ttask comment apply T-001 --comment C-4 --note «подходит по границам» --by lead
ttask comment reject T-001 --comment C-5 --note «не проходит гейт» --by lead
```

Решение меняет поля предложения и добавляет human-реплику в ту же ленту;
отдельного журнала операций нет. Комментарий внешнему зеркалу блокируется —
служебный ответ идёт в дочернюю `intake`.
