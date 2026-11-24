# Роли, capabilities и агенты

Роль проекта в `<root>/.todone/roles.json` связывает логическое имя с tier,
mode, tools и concrete models. Тип хранит роль/уровень, но не model id.

```bash
tcheck roles list
tcheck roles show developer
tcheck roles set developer --tier balanced --mode subagent \
  --models model-id --by lead
tcheck tools list
tcheck tools bind git --command 'git' --by lead
```

Тип объявляет capability (`git`, `test-runner`, `docs-store` и т. д.), проект
привязывает команду. Нет привязки — `CAPABILITY_UNBOUND` и fallback из
`instruction.md`.

AGENT-1 лежит в `types/<type>/agents/<name>.json`. `ttask pack` собирает sealed
packet: общий бриф, instruction, task body, выбранную ленту, refs/artifacts и
`return_contract` (`fields`, `shape`, `persist`, `pointer`). Субагент не получает
чат родителя, другие записи или скрытый контекст; большой ответ пишет файлом.
