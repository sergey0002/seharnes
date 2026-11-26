# new-project

Назначение.
Переносит или обновляет kit харнеса в другом проекте. Не копирует Git-снимок
приложения в новую папку; для этого предназначен `copy-project`.

Как работает.
Точка входа одна: `export_kit.py`. Состав kit задаёт `kit.json`, включённость
сред задаёт `environments.json`, и её читает только шаг развёртывания
представлений в Target. Профили называются `core`, `developer` и `project`;
legacy `Full` в `harness_cli.py export` отображается в `developer`.

Режимы: `install` (первый перенос, существующие файлы не перезаписываются),
`update` (обновление kit поверх установленного харнеса) и `mirror` (точный kit
с удалением файлов, которых нет в источнике). `mcp.json` и `AGENTS.md`
сливаются структурно, серверы Target сохраняются.

Отдельный движок `harness_transfer.py` работает с явно выбранными путями:
`plan` → `approve` → `apply` → `verify`/`rollback`, плюс `render` и `compact`.
Его команда `export` вызывает тот же `export_kit.py`.

Что нужно.
Путь Source и Target, профиль `core`/`developer`/`project`, режим
`install`/`update`/`mirror`.

Чего не делает.
Не заменяет sync сред `environment-sync` и перенос приложения `copy-project`.
Локальные CopyTrust workspace-скрипты вынесены из переносимого скила.
DSH не входит в kit. Серверное окружение, Docker и Windows-native входы в
текущую область не входят.
