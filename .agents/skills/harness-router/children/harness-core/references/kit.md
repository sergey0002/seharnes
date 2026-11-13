# Kit

`assets/kit.json` задаёт каталоги переноса, корневые файлы, исключения и состояние.

- `copy`: каталоги и файлы, которые входят в kit; `.doc/qa` в него не входит, проектные флоу переносятся отдельно с приложением.
- `rootFiles`: файлы в корне проекта.
- `skipDirs` и `skipFiles`: что не копировать; `*.phar`, `state`, vendor, node_modules, venv, секреты и примеры локальных значений различаются.
- `stateDirs`: состояние, индексы и временные данные; в Git и kit не входят.

`kit.json` пока остаётся authored adapter-файлом. `profile_manifest.py` строит по нему карту `Core`/`Developer`/`Project`; `cmd_export --dry-run` использует эту карту. Фактический PowerShell-export ещё копирует по своим спискам, поэтому полный переход на один walker и генерация `kit.json` из `canon-paths.yaml` остаются открытыми. В `canon-paths.yaml` уже есть `distribution`, но профильная карта пока берёт состав из `kit.json`.

`canon-paths.yaml` — единственный authored регламент путей. `kit.json`, `profile_manifest.py` и PowerShell-списки считаются производными или переходными, их нельзя править как второй канон.
