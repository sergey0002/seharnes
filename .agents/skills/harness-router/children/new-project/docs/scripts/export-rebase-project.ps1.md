# Скрипт: `.agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, export-rebase-project]
-->

## Суть
Обратная совместимость: делегирует выполнение в `rebase_project.ps1` (канон рядом с `rebase_project.md`). Принимает те же параметры и передаёт их через `@PSBoundParameters`. Используется для совместимости со старыми вызовами и документацией, ссылающейся на `export-rebase-project.ps1`.

## Когда запускать
- При вызове старого имени скрипта (legacy).
- Не вызывать напрямую для новых задач — используйте `rebase_project.ps1`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Target |  | string | да |  | Каталог нового проекта |
| -Source |  | string | нет | '' | Корень образца (по умолчанию родитель .doc/) |
| -Profile |  | string | нет | 'Full' | Full (с Jira/gototask/qa) или Core |
| -Mode |  | string | нет | 'migrate' | migrate / clean / update |
| -ProjectName |  | string | нет | '' | Имя для .serena/project.yml |
| -IncludeKilo |  | switch | нет |  | Копировать .kilo / kilo.json |
| -SkipTools |  | switch | нет |  | Не копировать инфраструктурные `.tools`; источники MCP-серверов копируются всегда |
| -SkipRuntimeDeps |  | switch | нет |  | Не копировать `node_modules` в `.tools/mcp-servers/php-toolchain` и `tools/vendor` |
| -SkipGitInit |  | switch | нет |  | Не делать git init |
| -SkipExclude |  | switch | нет |  | Не писать .git/info/exclude |
| -RunSetup |  | switch | нет |  | Запустить .cursor\setup.ps1 и .codex\setup.ps1 |
| -SkipMcpMerge |  | switch | нет |  | Не мержить Target-only MCP |
| -SkipSiblingConfig |  | switch | нет |  | Не создавать sibling ..\.config |
| -SkipBackup |  | switch | нет |  | Не сохранять бэкап перезаписываемых файлов |
| -SkipReview |  | switch | нет |  | Не запускать анализ локальных компонентов |
| -MirrorKit |  | switch | нет |  | Точное зеркало (удалить лишнее в Target) |
| -Yes |  | switch | нет |  | Не спрашивать подтверждение |

## Коды выхода
Наследует коды выхода `rebase_project.ps1`.

## Что читает и что пишет
Делегирует в `rebase_project.ps1`.

## Побочные эффекты
Делегирует в `rebase_project.ps1`.

## Окружение и зависимости
- `rebase_project.ps1` в той же директории.

## Примеры
```powershell
# Через старый скрипт (делегирует в rebase_project.ps1)
pwsh -NoProfile -File .agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1 -Target "C:\laragon\www\test"
```

## Ограничения
- Просто обёртка; все параметры и логика в `rebase_project.ps1`.
- Не добавляет своей логики.

## Связи
- Вызывается: legacy-вызовы, старые инструкции
- Зависит от: `rebase_project.ps1`
- Результат использует: `rebase_project.ps1`

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)