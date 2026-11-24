# Исполнить и закрыть

1. Выбрать: `tqueue next` или `tqueue board`.
2. Взять: `ttask claim <id> --by <имя>`.
3. Прочитать: `ttask show <id> --mode full` или `ttask pack <id>`.
4. Править поля: `ttask set`, статус — `ttask status`.
5. Оставить refs/artifacts/evidence:
   `ttask evidence <id> --kind tests --path artifacts/test.log --by <имя>`.
6. Создать отчёт: `ttask report-skeleton <id> --by <имя>`.
7. Заполнить `report.json` и закрыть:
   `ttask close <id> --report report.json --verdict met --by <имя>`.
8. Проверить `tcheck validate <id> --strict`.

Типовые красные гейты: `NO_TESTS`, `NO_HANDOFF`, `NO_REFS`, documentation,
verdict и acceptance status. Красный гейт не меняет status. Массовые правки
делай через `ttask batch <file> --dry-run`, затем повтори без dry-run.
