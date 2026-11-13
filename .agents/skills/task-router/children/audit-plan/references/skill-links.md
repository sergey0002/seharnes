# Связи скила audit-plan

Пути даны от корня проекта. Они не дублируются в `SKILL.md`, чтобы главный файл
оставался портируемым.

| Скил | Файл | Роль в аудите |
|---|---|---|
| prepare-plan | `.agents/skills/prepare-plan/SKILL.md` | автор плана, источник Patches и сценариев |
| git-task-blame | `.agents/skills/task-router/children/git-task-blame/SKILL.md` | история диапазона, прежние задачи и ветки |
| task-code-review | `.agents/skills/task-router/children/task-code-review/SKILL.md` | принадлежность хунков задаче, не заменяет аудит плана |
| jdocmunch | `.agents/skills/jdocmunch/SKILL.md` | поиск доменных документов перед пересборкой радиуса |
| test-task | `.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md` | исполнение сценариев после реализации, не часть аудита |

Правило-триггер аудита: `.cursor/rules/audit-plan.mdc`.
Правило-триггер автора плана: `.cursor/rules/prepare-plan.mdc`.

Контракт критериев принадлежит этому скилу. `prepare-plan` ссылается на
`references/criteria.md` по имени и не копирует текст.
