# Короткие примеры

## Очередь

```bash
tqueue init site --root .
ttask new «Проверить» --type fix --queue site
```

Первая команда создаёт registry entry и пустой queue index. Вторая создаёт
`T-001`, папку `data/T-001-fix/` и строку индекса.

## Формулировка и закрытие

```bash
ttask set T-001 --problem «ошибка» --change-kind fix \
  --acceptance «дефект воспроизводится в тесте» \
  --acceptance «регрессия зелёная» --by lead
ttask status T-001 --status ready --by lead
ttask claim T-001 --by developer
ttask evidence T-001 --kind tests --path artifacts/test.log \
  --note «полный прогон» --by tester
ttask report-skeleton T-001 --by developer
ttask close T-001 --report report.json --verdict met --by developer
```

## Поток

```bash
ttask flow start --flow jira-fix --from T-001 --by lead
ttask flow state T-001 --flow jira-fix
ttask flow next T-002
```

Создаются черновики шагов; человек сам публикует их в `ready`.

## Зеркало

```bash
tcheck import jira --file jira.json --queue site --by importer
```

Raw остаётся дословно, revision увеличивается при повторном импорте. Печатаются
команды дочерних `intake`, но дочерние записи автоматически не создаются.
