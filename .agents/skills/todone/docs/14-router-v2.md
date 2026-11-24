# Маршрутизатор и прогрессивное чтение

`SKILL.md` — короткий маршрутизатор, а не второй справочник. Он отвечает на
вопрос «куда идти с намерением» и передаёт управление одной процедуре.
Подробности живут в `docs/`, `child-skills/` и `references/`.

## Как выбрать документ

| Намерение | Сначала | Затем |
|---|---|---|
| не знаю, какую очередь выбрать | `child-skills/01-resolve-queue.md` | `docs/08-queues.md` |
| создать очередь | `child-skills/02-create-queue.md` | `docs/03-data-model.md` |
| создать/формализовать запись | `child-skills/03-formulate-task.md` | `docs/09-types-and-stages.md` |
| прочитать большой контекст | `child-skills/06-read-and-report.md` | `docs/03-data-model.md` |
| согласовать вопрос/предложение | `child-skills/05-agree-and-clarify.md` | `child-skills/12-comment-thread.md` |
| выполнить и закрыть | `child-skills/07-execute-and-close.md` | `docs/05-validation.md` |
| разложить потоком | `child-skills/04-decompose-and-order.md` | `docs/02-lifecycle.md` |
| передать субагенту | `child-skills/11-subagent-dispatch.md` | `docs/10-roles-and-subagents.md` |
| добавить ссылку/файл | `child-skills/08-file-operations.md` | `docs/03-data-model.md` |
| понять общий CLI-контракт | `child-skills/09-cli-protocol.md` | `docs/04-cli.md` |
| посмотреть тип/роль/capability | `child-skills/10-types-stages-roles.md` | `docs/09-` и `docs/10-` |
| явно сказать «задокументируй» | `docs/04-cli.md` | `docs/18-aggregation.md`; команда `ttask document` |
| создать/проверить docs workspace | `docs/00-quick-start.md` | `docs/04-cli.md`, `docs/17-project-folders.md` |
| понять catalog/resolver и границу aggregate | `docs/18-aggregation.md` | `docs/04-cli.md` |
| проверить сбой | `docs/12-doctor.md` | `docs/05-validation.md` |

## Почему так

Контекст — ограниченный ресурс. Агенту не нужно читать все 125 live-файлов поставки,
чтобы выполнить `tqueue next`: достаточно маршрута очереди и общего CLI-контракта.
Но при изменении схемы нужно перейти к полному data model и file map.

## Правило единственного дома

Каждая инструкция отвечает только за своё:

- маршрутизатор говорит, **куда**;
- процедура говорит, **в каком порядке**;
- reference говорит, **какой формат**;
- код говорит, **что реально выполнится**;
- doctor проверяет, **не разошлись ли они**.

Если правило уже есть в `references/schema.md`, не дублируй другую версию в
каждой процедуре: дай короткий указатель. Если поведение изменилось, сначала
исправь код и затем все ссылки на него.

## Остановка вместо догадки

При отсутствии входа, неразрешённой очереди, красном гейте, readonly-зеркале,
неполном пакете или неизвестном шаге процедура обязана остановиться, назвать
код и передать готовую команду. Нельзя добавлять «временную» сущность, копировать
факт в родителя или считать capability доступной без `tools.json`.
