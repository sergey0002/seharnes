# Справочник JSON-схем

Схемы живут в `scripts/tdcore/schema.py` и показываются CLI:

```bash
tcheck schema TASK
tcheck schema INDEX
tcheck schema TYPE
tcheck schema
```

Команда печатает ключи/перечисления фактического кода; этот файл объясняет их
роль, но не заменяет вызов `tcheck schema`.

## Основные схемы

| Имя | Где используется | Содержание |
|---|---|---|
| `TASK` / TASK-6 | `data/*/task.json` | тело записи, мета, массивы, source, comments, extra, refs, artifacts |
| `INDEX` / INDEX-1 | queue `.todone/index.json` | строки ссылок и состояние потока |
| `TYPE` / TYPE-5 | `types/*/type.json` | форма, гейты, executor, plugin-поля |
| `FIELD` / FIELD-1 | `TYPE.fields[]` | дополнительные поля `extra` |
| `REF` / REF-1 | `task.refs[]` | адрес факта без копии текста |
| `ARTEFACT` / ARTEFACT-1 | `task.artifacts[]` | файл результата/доказательства |
| `SOURCE` (версия контракта SRC-2) | `task.source` | внешний источник и дословный raw |
| `COMMENT` / COMMENT-1 | `task.comments[]` | лента реплик и решение proposal |
| `REPORT` | `report.json` | результат закрытия и AC verdicts |
| `CHECK` / CHECK-1 | `type.checks[]` | модуль процедурной проверки |
| `CODE` / CODE-1 | `check.codes[]` | код, уровень, готовая подсказка |
| `FLOW` / FLOW-1 | `flows/*/flow.json` | вход, шаги, лимит порции |
| `STEP` / STEP-1 | `FLOW.steps[]` | тип, входы, выходы, executor, gate |
| `TOOL` / TOOLS-1 | `<root>/.todone/tools.json` | capability → команда |
| `ROLE` / ROLE-1 | `<root>/.todone/roles.json` | role → tier/mode/tools/models |
| `AGENT` / AGENT-1 | `types/*/agents/*.json` | sealed return contract |
| `SETTINGS` | queue `settings.json` | пороги адаптивного чтения |

## TASK-6

Разрешённые ключи: `id`, `title`, `priority`, `phase`, `status`, `parent`,
`depends_on`, `parallelizable`, `module`, `problem`, `goals`, `acceptance`,
`in_scope`, `out_of_scope`, `context`, `files_hint`, `steps`, `verify`,
`open_questions`, `owner`, `started_at`, `blocked_reason`, `notes`, `change_kind`,
`created_at`, `due`, `estimate_h`, `kind`, `release`, `source`, `comments`, `report`,
`extra`, `refs`, `artifacts`.

Статусы: `draft`, `ready`, `in_progress`, `blocked`, `parked`, `mirror`, `closed`,
`cancelled`. Адресуемые массивы используют префиксы `G`, `AC`, `IN`, `OUT`, `CT`,
`F`, `S`, `V`, `Q`, `N`.

## INDEX-1

Верхний объект: `schema`, `alias`, `updated_at`, `order`, `items`. Строка:
`id`, `path`, `type`, `title`, `status`, `priority`, `phase`, `release`, `owner`,
`due`, `estimate_h`, `parent`, `flow`, `flow_step`, `flow_run`, `flow_item`,
`flow_revision`, `updated_at`. Тексты записи сюда запрещены архитектурным
правилом, не только рекомендацией. `flow_item` и `flow_revision` различают
fan-out элементы и повторные route revision.

## Перечисления

- refs: `file`, `symbol`, `doc`, `url`, `queue`, `report`;
- artifacts: `spec`, `refs`, `tests`, `report`, `log`, `digest`, `other`;
- comments: `human`, `agent`, `import`, `proposal`, `handoff`;
- source systems: `jira`, `openspec`, `speckit`, `chat`, `file`;
- capabilities: `code-graph`, `memory`, `web-search`, `git`, `test-runner`, `docs-store`;
- tiers: `cheap`, `balanced`, `strong`; modes: `subagent`, `inline`, `either`;
- read modes: `body`, `full`, `comments`, `digest`, `handoff`, `comment`, `element`,
  `report`, `pack` (последний используется `ttask pack`, не `show`).

## Строгость

Неизвестный ключ — находка. Свободный текст не имеет числового лимита. Числа
`priority`, `estimate_h`, настройки и `revision` проверяются как числа; `due` и
id — по формату. Внешний raw остаётся строкой целиком.
