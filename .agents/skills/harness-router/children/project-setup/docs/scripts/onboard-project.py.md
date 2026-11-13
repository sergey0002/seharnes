# Скрипт: `.agents/skills/harness-router/children/project-setup/scripts/onboard-project.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, onboard-project]
-->

## Суть
Единая точка входа для онбординга проекта после экспорта харнеса (`rebase_project.ps1`). Идемпотентен, не удаляет файлы проекта, не коммитит. Выполняет: детект PHP контейнера (docker) и docroot; rewrite Jira/bitbucket контейнера в `.cursor/mcp.json` и `.codex/mcp.json`; настройка/отключение MySQL MCP (`MYSQL_*` в env файлах); выбор свободного Serena порта (учитывает sibling проекты через `.doc/web/.env` и `.cursor/mcp.json`) и порта веб-панели (8077-8099); установка `CODEPRISM_TARGET` и создание venv для CodePrism; построение индексов: codegraph (init), CBM (async fast), jdocmunch, CodePrism venv; опционально запуск медленного doc-index (`.dsh/scripts/doc-index.sh`); управление `.git/info/exclude` (harness/docs исключения); опционально staging безопасных harness путей (`--add-harness-to-git`). Выводит JSON-отчёт и Markdown-отчёт в `.doc/onboard-report.{json,md}` с вопросами для ручного донастройки.

## Когда запускать
- Сразу после `rebase_project.ps1` в новом проекте.
- При команде «настрой проект», «onboard проект», «догони конфигурацию».
- В CI/CD для верификации конфигурации нового проекта.
- Агент запускает с `--check` для отчёта о состоянии, без `--check` для применения.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --project-name |  | string | нет | (имя папки) | Имя проекта для репо jdocmunch |
| --php-container |  | string | нет | (автодетект) | Имя PHP docker контейнера |
| --mysql |  | string | нет | keep | keep / disable / set |
| --mysql-database |  | string | нет |  | Имя БД для MySQL MCP |
| --mysql-port |  | string | нет |  | Порт MySQL |
| --serena-port |  | int | нет | 0 | Порт Serena (0 = авто) |
| --web-port |  | int | нет | 0 | Порт веб-панели (0 = авто) |
| --jdoc-repo |  | string | нет | local/{name} | Репо для jdocmunch |
| --add-harness-to-git |  | flag | нет |  | Застейджить безопасные harness пути (без коммита) |
| --include-harness |  | flag | нет |  | Убрать harness из .git/info/exclude |
| --exclude-docs |  | flag | нет |  | Добавить /.doc/ в exclude |
| --include-docs |  | flag | нет |  | Убрать /.doc/ из exclude |
| --add-docs-to-git |  | flag | нет |  | Застейджить project docs (architecture, tasks, manifest, archviz) |
| --skip-indexes |  | flag | нет |  | Пропустить построение индексов |
| --reindex-project-docs |  | flag | нет |  | Запустить .dsh/scripts/doc-index.sh rebuild-arch/rebuild-manifest (15-20 мин) |
| --check |  | flag | нет |  | Только отчёт о состоянии, без изменений |
| --yes |  | flag | нет |  | Без промптов (для неинтерактивного) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (включая --check) | Продолжить работу |
| 1 | Ошибка выполнения (подпроцесс failed) | Проверить вывод, исправить |

## Что читает и что пишет
**Читает:**
- `.cursor/mcp.json`, `.codex/mcp.json`, `.codex/config.toml` — MCP конфиги
- `.cursor/mcp.env`, `.codex/mcp.env`, `.kilo/mcp.env` — env файлы
- `.doc/web/.env` / `.doc/web/.env.example` — веб-панель порт
- `.dsh/scripts/php-docker.sh`, `.dsh/AGENTS.md`, `README.md` — детект PHP контейнера
- `.doc/architecture/`, `.doc/tasks/`, `.doc/harnes/state/` — docroot детект
- `.serena/project.yml` — Serena project_name
- `codegraph`, `codebase-memory-mcp`, `jdocmunch-mcp.sh` — CLI инструменты

**Пишет:**
- `.cursor/mcp.json` — rewrite container, MySQL enabled/disabled/env, Serena url, CODEPRISM_TARGET
- `.codex/mcp.json` / `.codex/config.toml` — то же
- `.cursor/mcp.env` / `.codex/mcp.env` / `.kilo/mcp.env` — MYSQL_DATABASE, MYSQL_PORT
- `.doc/web/.env` — WEB_PANEL_PORT
- `.codeprism.toml` — конфиг CodePrism (если не было)
- `.cursor/tools/codeprism-ai/venv/` — venv (uv venv + pip install codeprism-ai==0.1.11)
- `.git/info/exclude` — managed block (harness/docs исключения)
- `git add -f` — безопасные harness пути / project docs (при флагах)
- `.doc/onboard-report.json` + `.md` — отчёт с вопросами

## Побочные эффекты
- Меняет MCP конфиги, env файлы, git exclude/index.
- Создаёт venv для CodePrism (uv).
- Спавнит подпроцессы: codegraph init, CBM index_repository --async, jdocmunch --index, uv venv/pip.
- Запускает канонический `environment-sync/scripts/sync-agent-views.sh` (если есть); ошибка синхронизации даёт код выхода 1.

## Окружение и зависимости
- Python 3.7+ (argparse, json, os, re, shutil, socket, subprocess, sys, pathlib).
- `uv` — для CodePrism venv (опционально, если нет — пропускает).
- `codegraph` CLI — для индексации (опционально).
- `codebase-memory-mcp` CLI — для CBM (опционально).
- `bash` + `jdocmunch-mcp.sh` — для jdocmunch (опционально).
- `git` — для exclude, add.
- `docker` — для PHP контейнера (только детект).

## Примеры
```bash
# Только проверка (read-only)
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --check

# Полный онбординг с автодетектом
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --yes

# С явными параметрами
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --yes \
  --php-container my-web-1 --mysql disable --serena-port 9124 --web-port 8079

# С индексацией проектных доков (медленно)
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --yes --reindex-project-docs
```

Пример JSON-вывода:
```json
{
  "root": "/home/user/project",
  "project": "myproject",
  "check": false,
  "steps": {
    "php-container": {"value": "my-web-1", "files": 2},
    "mysql": {"state": "configured"},
    "serena": {"port": 9124, "notes": ["serena port 9124 is free; register with add-serena.sh"]},
    "codeprism": {"target": "/home/user/project", "config": true, "present": true, "exit": 0, "tail": "..."},
    "web-panel": {"port": 8079, "env": "/home/user/project/.doc/web/.env", "start": "WEB_PANEL_PORT=8079 bash .doc/web/start.sh"},
    "git": {"exclude_path": "/home/user/project/.git/info/exclude", "harness_excluded": true, "docs_excluded": true, "changed": true, "staged": ["AGENTS.md", ".cursor/rules", "..."], "harness_committed": false},
    "indexes": {
      "codegraph": {"fileCount": 1245, "nodeCount": 8902, "state": "ready"},
      "jdocmunch": {"repo": "local/myproject", "docroot": "/home/user/project/.doc"},
      "codebase-memory-mcp": {"requested": true, "tail": "..."},
      "project-doc-index": {"state": "available", "command": "bash .dsh/scripts/doc-index.sh rebuild-arch", "note": "slow: multilingual mpnet, 15-20 min"}
    },
    "sync": {"exit": 0, "tail": "..."}
  },
  "questions": [
    "MySQL MCP включён. Отключить: --mysql disable; задать БД: --mysql set --mysql-database <db>.",
    "Serena порт выбран 9124; проверьте, что он свободен и закреплён за проектом.",
    "Харнес исключён из git. Добавить: --add-harness-to-git (стейджинг без коммита).",
    "Документация .doc исключена из git. Включить: --include-docs; добавить: --add-docs-to-git."
  ]
}
```

## Ограничения
- Не коммитит изменения — только ставит exclude и staging.
- Не настраивает Jira/Kaiten credentials — требует ручного заполнения `.cursor/mcp.env`.
- CodePrism venv требует `uv` и сеть (PyPI).
- CBM async индексация — фоновая, не дожидается завершения.
- jdocmunch требует `.doc/` структуру; без docroot — пропускается.
- Serena порт проверяется на свободность, но регистрация в Serena требует отдельного `add-serena.sh`.

## Связи
- Вызывается: `rebase_project.ps1` (опционально через -RunSetup), агент по команде «настрой проект», `project-setup` скил
- Зависит от: `rebase_project.ps1` артефактов, CLI инструментов (codegraph, CBM, jdocmunch, uv)
- Результат использует: настроенный проект, готовый к работе агентами

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)
