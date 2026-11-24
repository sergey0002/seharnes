# Типы, внутренние этапы, роли и capabilities

Тип — папка-плагин: `type.json`, `instruction.md`, optional `agents/`, `checks/`,
`profile.py`, `references/`. Проверить его можно командами:

```bash
tcheck types list
tcheck types show <тип>
tcheck types fields <тип>
```

Тип объявляет форму `extra`, гейты, executor и capabilities. `editor: import_only`
делает запись readonly для ручных CLI-команд.

Этапы по умолчанию — внутренний контур одной записи: подготовить, выполнить,
проверить, передать. Новая запись появляется только явным child/import/flow.

Роль `ROLE-1` лежит в `<root>/.todone/roles.json`:

```bash
tcheck roles list
tcheck roles show <роль>
tcheck roles set <роль> --tier balanced --mode subagent \
  --models <модель> --by <имя>
```

Тип требует capability, проект привязывает её в `tools.json`:

```bash
tcheck tools bind <capability> --command <команда> --by <имя>
```

Отсутствие привязки даёт `CAPABILITY_UNBOUND`; инструкция обязана описать
запасной путь.
