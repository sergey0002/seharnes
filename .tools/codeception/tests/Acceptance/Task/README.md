# Task/ — тесты уровня задачи

Cest-файлы конкретных задач (не глобальный регресс, не библиотека фрагментов).

**Конвенция имени:** `{N}_{Slug}Cest.php`, где `{N}` — номер задачи Jira
(`CT-{N}`), `{Slug}` — короткое английское название задачи в PascalCase.
Пример: `1612_FixOrderCancelCest.php`.

**Обязательно:**
- `@group task-{N}` на каждом методе (или на классе, если весь файл — одна задача)
- Собирается из фрагментов `AcceptanceTester` (см. `.doc/qa/fragments.md`),
  не пишется с нуля
- `checkpoint($label)` после каждого значимого шага, не только в конце
- Парный документ `.doc/tasks/{N}/test.md` — что проверяется, какие фрагменты
  и флоу использованы, ссылка на этот файл

Создаётся и обновляется скилом `prepare-task-test`
([Cursor](../../../../../.cursor/skills/prepare-task-test/SKILL.md) /
[Codex](../../../../../.codex/skills/prepare-task-test/SKILL.md)).

Не путать с:
- `.doc/codeception/tests/Acceptance/*Cest.php` (без подпапки) — тесты
  флоу/фрагментов, переживают конкретную задачу (`ItemDraftCest`, `ClientCest`)
- `DepositionFullCest.php` (план, не реализован) — глобальный регресс,
  `@group global`, не привязан к задаче

См. [`.doc/tests.md`](../../../../harnes/tests.md) §3, §5.
