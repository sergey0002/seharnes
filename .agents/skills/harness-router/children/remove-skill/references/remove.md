# Удаление скила и очистка ссылок

## Почему нельзя удалить только канон

Синхронизация работает как merge: она обновляет свои файлы и не удаляет чужие.
Если удалить только `.agents/skills/{name}`, копии в `.codex/skills`,
`.qoder/skills`, `.qwen/skills` и `.kilo/skills` останутся. Следующий скан
покажет их как локальные скилы.

Поэтому удаление выполняется по всем средам сразу.

## Порядок

1. Найти скил по имени или относительному пути.
2. Собрать ссылки в каноне, правилах, документации, реестре и MCP-конфигах.
3. Сделать бэкап.
4. Удалить канон и копии в зеркалах.
5. Удалить карточку `.doc/harnes/skills/{name}.md`.
6. Удалить строки из `skills/README.md`, `index.md`, `state/02-skills.md`.
7. Удалить запись из `component_registry.json`.
8. Удалить `children/{name}` из родительского `skill.json` и пересобрать роутеры.
9. Запустить синхронизацию и проверки.
10. Показать ссылки, которые требуют ручной правки.

## Категории ссылок

| Категория | Пример | Действие |
|---|---|---|
| `router` | строка таблицы в `SKILL.md` родителя | удаляется пересборкой роутера |
| `docs` | карточка скила | удаляется файлом |
| `state` | строка в `state/02-skills.md` | удаляется строкой |
| `registry` | запись в `component_registry.json` | удаляется ключом |
| `mcp` | сервер или лаунчер в `.cursor/mcp.json` | ручное решение |
| `rule` | упоминание в `.cursor/rules` | ручная правка текста |
| `other` | текст в документации или скрипте | ручная правка текста |

Скрипт не вырезает произвольные абзацы. Он показывает путь, строку и текст.
Так нельзя случайно сломать смысл правила.

## Зависимости

Перед удалением проверить `dependencies.skills` у других манифестов и ссылки в
`component_registry.json`. Если удаляемый скил указан как зависимость, сначала
обновить зависимый скил. Скрипт отказывает в удалении при найденной зависимости и
требует `--force`. Флаг `--force` разрешает удаление, но зависимые скилы нужно
исправить вручную.

## Откат

Бэкап лежит в:

```text
.doc/skil_data/harness-core/removed/{timestamp}/{env}/{id}
```

Для отката вернуть каталог в канон, восстановить строки документации из истории
изменений или из бэкапа, вернуть запись реестра и пересобрать роутеры.

## Проверки после удаления

```bash
python3 .agents/skills/harness-router/children/improvement/scripts/validate_skills.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_docs.py
python3 .agents/skills/harness-router/children/harness-core/scripts/rebuild-routers.py --root . --check
python3 .agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py --root .
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
```

Если скан снова показывает удаленный скил, значит копия осталась в одной из
сред или в манифесте пакета. Это нужно разобрать до завершения удаления.
