# Связи скила prepare-plan

Пути даны от корня проекта. Они не дублируются в `SKILL.md`, чтобы главный файл
оставался портируемым и без переходов вверх по дереву.

| Скил | Файл | Роль |
|---|---|---|
| audit-plan | `.agents/skills/task-router/children/audit-plan/SKILL.md` | независимый аудит, правки плана и журнал проходов |
| git-task-blame | `.agents/skills/task-router/children/git-task-blame/SKILL.md` | история строк и прежние задачи, P0.5b |
| gototask | `.agents/skills/task-router/children/gototask/SKILL.md` | переход к ветке и экспорт `task.md` |
| jdocmunch | `.agents/skills/jdocmunch/SKILL.md` | поиск документации по корпусам |
| ponytail | `.agents/skills/ponytail/SKILL.md` | лестница минимальной полной правки, P4.0 |
| test-task | `.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md` | исполнение сценариев после реализации |
| task-diff | `.agents/skills/task-router/children/task-diff/SKILL.md` | обновление диффа задачи для stage2 |
| task-doc | `.agents/skills/documentation-router/children/task-doc/SKILL.md` | документация задачи после реализации |

Критерии готовности, формат меток и журнала принадлежат `audit-plan`
(`references/criteria.md` и `references/workflow.md`). Этот скил их не копирует.

Правило-триггер автора плана: `.cursor/rules/prepare-plan.mdc`.
Правило-триггер аудита: `.cursor/rules/audit-plan.mdc`.
