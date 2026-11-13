# Скрипт: `.agents/skills/harness-router/children/new-project/scripts/rebase_project_gi.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, rebase_project_gi]
-->

## Суть
Настраивает локальный git exclude (`.git/info/exclude`) и опционально `skip-worktree` флаги для AI-kit файлов в целевом проекте. Канон: `.doc/rebase_project.md` (секция local exclude). Пишет managed block в `.git/info/exclude` с исключением всех 7 сред агентов (`.cursor/`, `.codex/`, `.agents/`, `.kilo/`, `.qoder/`, `.qwen/`, `.antigravity/`, `.gemini/`), `.doc/`, `.serena/`, `.playwright-mcp/`, `.dsh/`, `DSH-RULES.md`, `AGENTS.md`, `php_error.log`, `.kilocode/`, `kilo.json`, `.tools/`, `sourcegraph-local/`, `graphify-out/`, `tools/docker-dev/`, `tools/codeception/`. Не коммитится — только локальные настройки репозитория. Поддерживает добавку недостающих строк к существующему блоку (не перезаписывает developer's exclude), force-перезапись, и `skip-worktree` для локальных оверрайдов (`tools/docker-dev/`, `tools/codeception/`).

## Когда запускать
- После `rebase_project.ps1` (вызывается автоматически внутри, если не -SkipExclude).
- В существующем проекте для настройки/обновления exclude.
- При команде «настрой git exclude для харнеса».
- Агент запускает при онбординге проекта (`onboard-project.py` — через manage_git).

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -RepoRoot |  | string | нет | '' | Корень репозитория (где .git); авто: родитель .doc/ или cwd |
| -Force |  | switch | нет |  | Перезаписать managed block (иначе только добавляет недостающие строки) |
| -NoSkipWorktree |  | switch | нет |  | Не ставить skip-worktree флаги |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех | Продолжить работу |

## Что читает и что пишет
**Читает:**
- `.git/info/exclude` — существующий файл (если есть)
- Наличие файлов для skip-worktree: `tools/docker-dev/compose.yaml`, `tools/docker-dev/README.md`, `tools/docker-dev/php-apache/Dockerfile`, `tools/codeception/tests/Acceptance/FirstCest.php` (или в `.tools/`)

**Пишет:**
- `.git/info/exclude` — managed block (добавляет/обновляет)
- Git index — `skip-worktree` флаги для 4 файлов (если не -NoSkipWorktree)

## Побочные эффекты
- Меняет `.git/info/exclude` (локальный, не в коммитах).
- Меняет git index (skip-worktree — локально, не пушится).

## Окружение и зависимости
- PowerShell 5+ / pwsh.
- `git` — для `check-ignore`, `ls-files`, `update-index`.
- Репозиторий должен иметь `.git`.

## Примеры
```powershell
# Авто (из корня проекта)
cd C:\laragon\www\myproject
pwsh -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project_gi.ps1

# Явный репо, force перезапись
pwsh -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project_gi.ps1 -RepoRoot "C:\laragon\www\myproject" -Force

# Без skip-worktree
pwsh -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project_gi.ps1 -NoSkipWorktree
```

Вывод:
```
==> RepoRoot: C:\laragon\www\myproject
==> .git/info/exclude
    OK: wrote C:\laragon\www\myproject\.git\info\exclude
==> skip-worktree (локальные оверрайды)
    OK: skip-worktree tools/docker-dev/compose.yaml
    OK: skip-worktree tools/docker-dev/README.md
    OK: skip-worktree tools/docker-dev/php-apache/Dockerfile
    OK: skip-worktree tools/codeception/tests/Acceptance/FirstCest.php
==> проверка
    OK: check-ignore: .cursor/mcp.json
    OK: check-ignore: .doc/harnes/doc_rules.md
    OK: check-ignore: AGENTS.md
    OK: check-ignore: sourcegraph-local/README.md

skip-worktree (ожидается S в начале):
S tools/docker-dev/compose.yaml
S tools/docker-dev/README.md
S tools/docker-dev/php-apache/Dockerfile
S tools/codeception/tests/Acceptance/FirstCest.php

REBASE_GI_DONE root=C:\laragon\www\myproject exclude_hits=4
Канон: .doc\rebase_project.md (локальный git exclude)
```

## Ограничения
- Не перезаписывает developer's exclude полностью — только managed block (между `# >>> export-rebase-project (managed block)` и `# <<< export-rebase-project`).
- Если exclude уже есть без маркеров — добавляет managed block в конец.
- `skip-worktree` работает только для отслеживаемых файлов (в index); untracked игнорируются.
- Не делает `git commit` — только локальные настройки.

## Связи
- Вызывается: `rebase_project.ps1` (внутри), `onboard-project.py` (manage_git), агент вручную
- Зависит от: `git`, структуры Target проекта
- Результат использует: Target проект — харнес не попадает в коммиты, локальные оверрайды не перезаписываются при pull

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)