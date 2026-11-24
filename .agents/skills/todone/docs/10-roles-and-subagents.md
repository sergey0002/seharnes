# Роли, capabilities и субагенты

## Почему модель не хранится в типе

Тип знает смысл работы и требуемый уровень (`cheap`, `balanced`, `strong`), но
не знает хрупкий id конкретной модели. Проект связывает роль с реальными моделями
в `<root>/.todone/roles.json`. Так один и тот же тип переносится между проектами.

## ROLE-1

Элемент `roles` имеет:

| Ключ | Смысл |
|---|---|
| `role` | имя: `developer`, `researcher`, `tester`, `planner`, `reviewer`, `writer`… |
| `tier` | `cheap`, `balanced`, `strong` |
| `mode` | `subagent`, `inline`, `either` |
| `tools` | разрешённый набор инструментов роли |
| `models` | конкретные model id проекта; первый считается рабочим |

Команды:

```bash
tcheck roles list --root .
tcheck roles show developer --root .
tcheck roles set developer --tier balanced --mode subagent \
  --tools read,edit,bash --models project-model --by lead
tcheck roles unset developer --by lead
```

Все изменения roles требуют `--by`; сохранение атомарно с `.bak`. `roles list`
печатает слабейшую назначенную модель. На ней следует прогнать маршрут фазы:
сильная модель может скрыть недостаток брифа или неявное правило.

## Capability и TOOLS-1

Тип может объявить одну из capabilities:

```text
code-graph, memory, web-search, git, test-runner, docs-store
```

Проект привязывает её к команде/серверу:

```bash
tcheck tools list --root .
tcheck tools bind test-runner --command 'python3 -m unittest' \
  --note «запуск из корня проекта» --by lead
tcheck tools unbind test-runner --by lead
```

Нет привязки — это не успех и не разрешение придумать результат. `doctor` даёт
`CAPABILITY_UNBOUND`; инструкция типа должна содержать запасной путь («читать
исходники», «запустить вручную», «зафиксировать ограничение»).

## AGENT-1 и папка типа

Объявление субагента лежит в `assets/types/<type>/agents/<name>.json`:

```json
{
  "name": "developer",
  "role": "developer",
  "tools": ["read", "edit", "bash"],
  "boundaries": ["не менять чужую запись"],
  "return_contract": {
    "fields": ["files_changed", "commands_run", "evidence", "verdict"],
    "shape": "json: …",
    "persist": "artifacts/report.json",
    "pointer": "ttask artifact add <id> --kind report --path artifacts/report.json --note <что> --by <кто>"
  },
  "brief": "_shared/subagent-brief.md"
}
```

`return_contract` обязан иметь `fields`, `shape`, `persist`, `pointer`. Большой
результат не возвращается простынёй: он сохраняется в файл и наружу приходит
указатель.

## Запечатанный пакет

```bash
ttask pack T-002 --queue site
ttask pack T-002 --mode handoff --last 3 --agent developer
```

Пакет содержит:

1. общий `assets/types/_shared/subagent-brief.md`;
2. `assets/types/<kind>/instruction.md`;
3. тело записи целиком;
4. выбранную ленту (`handoff`, `digest`, `comments` или `full`);
5. refs и artifacts;
6. контракт возврата и границы агента.

Субагент не наследует историю диалога, память, результаты инструментов родителя
или другие записи. Режим `handoff` отдаёт последние K реплик плюс все `handoff`;
тексты выбранных реплик не режутся. Пакет откажется с `PACK_INCOMPLETE`, если
нет инструкции, общего брифа или обязательных ключей контракта.

## Границы исполнителя

- тип и id нельзя менять; смена формы — дочерняя запись;
- чужие факты не копируются; возвращается `REF(kind=queue)`;
- зеркало не редактируется;
- правки данных проходят через CLI;
- нет разрешённой capability — не изображать выполненный результат;
- при красном гейте или неполном входе вернуть код и готовое действие;
- глубина делегирования — один пакет; субагент не порождает новый пакет сам.

## Что делает родитель

Родитель сверяет результат с `AC-N`, кладёт большой ответ в artifact, добавляет
handoff-реплику, заполняет evidence/verification отчёта и закрывает запись
обычным `ttask close`. Сам факт делегирования не снимает гейты записи.
