# new-project

Назначение.
Переносит или обновляет kit харнеса в другом проекте. Не копирует Git-снимок
приложения в новую папку; для этого предназначен `copy-project`.

Как работает.
Основной путь: `harness_transfer.py plan` → `approve` → `apply` →
`verify`/`rollback`. Профили называются `Core`, `Developer` и `Project`;
legacy `Full` отображается в `Developer`. `plan --profile` без явных корней выбирает authored paths через `profile_manifest`, generated views исключаются. `harness_wizard.py` задаёт вопросы
мастера и вызывает тот же план. Generated views пересобираются
`render_agent_views.py` или `sync-agent-views.sh`, а `compact_agent_views.py`
убирает их перед commit.

`apply` пишет обычные файлы, `AGENTS.md` (managed block) и `.cursor/mcp.json`
(структурный merge) через backup, SQLite-журнал и проверку managed-дерева;
receipt пишется последним. Остальные adapter config и generated views в план
apply не включаются: их создаёт renderer. `apply --render` пересобирает views
после commit. `compact` удаляет generated views, `composer.phar` и preflight
backups, чтобы эталон оставался компактным.

Старые `rebase_project.ps1` и `export-rebase-project.ps1` остаются
совместимыми входами. Они не являются основным движком обновления.

Что нужно.
Путь Target, профиль `Core`/`Developer`/`Project`, источник и режим
`install`/`update`. Решения по конфликтам передаются в `approve`.

Чего не делает.
Не заменяет sync сред `environment-sync` и перенос приложения `copy-project`.
Локальные CopyTrust workspace-скрипты вынесены из переносимого скила.
Серверное окружение, Docker, supervisor, панель обновления и Windows-native
входы в текущую область не входят.
