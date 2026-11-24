<!-- generated from architecture:deepseek-harness-05-skripty by doc_render.py; do not edit -->

# Скрипты, оболочка и MCP

task unknown - status unknown - branch unknown - release unknown

# Скрипты, оболочка и MCP
<a id="скрипты,-оболочка-и-mcp"></a>
<!-- meta
type: config
status: actual
updated: 2026-10-31
tags: [deepseek, scripts, mcp]
-->

---

## Суть
<a id="суть"></a>
Скрипты канона не копируются, а вызываются по каноническому пути. Python, git и
bash идут напрямую: агент уже внутри WSL. PowerShell-скрипты идут только через
шим `.dsh/scripts/run-ps1.sh`, который выбирает движок PowerShell и запускает
скрипт с нативным git. MCP-серверы подключаются патчем, имена инструментов
`mcp__<serverName>__<tool>`.

> **AI:** читай этот doc, чтобы правильно запускать скрипты и MCP из DSH.
> **Сначала:** [03-workflow.md](./deepseek-harness-03-workflow.md) - где какой скрипт вызывается.
> **Не читай целиком:** команды бери из `.dsh/adapters/shell.md` по мере надобности.
> **См. также:** [../harnes/state/05-scripts.md../state/05-scripts.md) - реестр скриптов канона.

---

## Оболочка (факты)
<a id="оболочка-(факты)"></a>
| Инструмент | Где | Версия |
|---|---|---|
| python3 | WSL | 3.14.4 |
| git | WSL | 2.53.0 |
| bash | WSL | есть |
| node | WSL, nvm | v24.17.0 |
| pwsh | WSL, `~/.local/pwsh/pwsh` | 7.4.6 (нужен invariant-режим) |
| powershell.exe | Windows, полный путь | 5.1, в PATH отсутствует |

### Правила вызова
<a id="правила-вызова"></a>
```
py:  python3 <repo-relative-path> <args>
git: git <args>
sh:  bash <repo-relative-path> <args>
ps1: bash .dsh/scripts/run-ps1.sh <repo-relative-path> <args>
```

`wsl -e` не нужен: команды выполняются внутри WSL.

---

## Шим run-ps1.sh
<a id="шим-run-ps1.sh"></a>
Порядок выбора движка: `pwsh` в PATH, `~/.local/pwsh/pwsh`, затем
`powershell.exe` с конвертацией пути через `wslpath -w`.

Замеры на этой машине:

| Способ | Операция | Время |
|---|---|---|
| powershell.exe + UNC | `git status --short` | ~50 с |
| powershell.exe + UNC | `gototask inspect` | больше 180 с |
| pwsh в WSL | `gototask inspect` | ~6 с |
| pwsh в WSL | `task-diff inspect` | ~2 с |

Причина разницы: под `powershell.exe` каждый `git` это Windows-git по
`\\wsl.localhost`. Поэтому `powershell.exe` оставлен только как fallback.

---

## Скрипты канона (не копируются)
<a id="скрипты-канона-(не-копируются)"></a>
```
.agents/skills/*/scripts/   32 scripts (скилы)
.cursor/scripts/            multi-exec.sh, multi-search.sh, php-docker и др.
.agents/skills/project-doc/scripts/            find-related-tasks, build-tasks-index и др.
.agents/skills/test-task/scripts/            gates.py, task-test.sh, check-tests.sh
.doc/skil_data/task-doc/       jsondoc.py (plan write/verify/template)
.agents/skills/harness-management/children/environment-sync/scripts/           sync-agent-views.sh, generate-dsh-config.py, copy-dsh-kit.ps1
```

Ключевые вызовы:

```bash

# переход к задаче
<a id="переход-к-задаче"></a>
bash .dsh/scripts/run-ps1.sh .agents/skills/gototask/scripts/gototask.ps1 \
  -TaskNumber N -Action inspect

# diff задачи
<a id="diff-задачи"></a>
bash .dsh/scripts/run-ps1.sh .agents/skills/task-diff/scripts/task-diff.ps1 \
  -TaskNumber N -Action generate

# план
<a id="план"></a>
python3 .doc/skil_data/task-doc/jsondoc.py --root . plan verify --task N --require-syntax

# тест
<a id="тест"></a>
bash .agents/skills/test-task/scripts/task-test.sh N
python3 .agents/skills/test-task/scripts/gates.py N
```

---

## DSH kit и миграция
<a id="dsh-kit-и-миграция"></a>
DSH kit не хранится в git. При переносе проекта его копирует
`.agents/skills/harness-management/children/new-project/scripts/copy-dsh-kit.ps1`:

- `.dsh/skills`, `.dsh/adapters`, `.dsh/scripts`, `.dsh/tests`,
  `.dsh/models.overlay.json`;
- не копирует `.dsh/project.patch.yml`, `DSH-RULES.md`, `__pycache__`, бэкапы overlay.

Сгенерированные файлы создает `sync-agent-views.sh`. После генерации синк выполняет
`generate-dsh-config.py --check` и падает при расхождении.

Проверки:

```bash
python3 .agents/skills/harness-management/children/environment-sync/scripts/test_dsh_config.py
python3 .agents/skills/harness-management/children/environment-sync/scripts/test_dsh_kit.py
bash .dsh/scripts/smoke.sh
```

`smoke.sh` проверяет kit, динамическое число скилов и валидность
`models.overlay.json`.

## Шим smoke.sh
<a id="шим-smoke.sh"></a>
```bash
bash .dsh/scripts/smoke.sh              # статические проверки
bash .dsh/scripts/smoke.sh --task 2622  # плюс gototask и task-diff
bash .dsh/scripts/smoke.sh --mcp        # напоминание про живые MCP
```

Exit 0 - всё зелёное, exit 1 - есть падения с причиной.

---

## MCP: имена и диагностика
<a id="mcp:-имена-и-диагностика"></a>
12 серверов в патче. Имя инструмента `mcp__<serverName>__<tool>`.

| serverName | DSH prefix |
|---|---|
| codebase-memory-mcp | `mcp__codebase-memory-mcp__` |
| sourcegraph | `mcp__sourcegraph__` |
| mysql | `mcp__mysql__` |
| serena | `mcp__serena__` |
| playwright | `mcp__playwright__` |
| context7 | `mcp__context7__` |
| phpstan-mcp | `mcp__phpstan-mcp__` |
| semgrep | `mcp__semgrep__` |
| git | `mcp__git__` |
| graphify | `mcp__graphify__` |
| php-deps-mcp | `mcp__php-deps-mcp__` |
| jira-task | `mcp__jira-task__` |

Выключены: deepwiki, bitbucket-task (disabled в каноне), xdebug (порт 9003).

### Диагностика (кеш)
<a id="диагностика-(кеш)"></a>
Статус сервера стабилен в пределах сессии. Кеш в `.doc/tasks/{N}/mcp-status.json`:

```json
{"servers": {"codebase-memory-mcp": {"status": "green", "checked_at": "..."},
             "sourcegraph": {"status": "red", "fallback": "grep", "checked_at": "..."}}}
```

### Fallback при red
<a id="fallback-при-red"></a>
```
CBM red         -> sourcegraph -> serena -> grep/read
sourcegraph red -> grep по коду
mysql red       -> факты БД не выдумывать
playwright red  -> Codeception через CLI
```

---

## Адаптеры
<a id="адаптеры"></a>
| Файл | Что содержит |
|---|---|
| `.dsh/adapters/shell.md` | правила оболочки, факты, замеры, установка pwsh |
| `.dsh/adapters/mcp-names.md` | serverName -> prefix, fallback |
| `.dsh/adapters/models.md` | модели, включение `llm-pi-ai` |
| `.dsh/adapters/prepare-plan-digest.md` | сжатый чеклист P0-P7 |

---

## Связи
<a id="связи"></a>
- [Workflow](./deepseek-harness-03-workflow.md) - где вызываются скрипты
- [Устройство](./deepseek-harness-01-ustroystvo.md) - состав
- [Скрипты канона../state/05-scripts.md) - полный реестр

---

## Известные проблемы и ограничения
<a id="известные-проблемы-и-ограничения"></a>
- Симптом: `command not found`.
- Причина: PATH агентской оболочки без `/mnt/c`.
- Решение: только через `run-ps1.sh`.


- Симптом: `project.patch.yml` содержит токены и пароли в `env`.
- Причина: генератор инлайнит `mcp.env`.
- Решение: файл вне git, значения не копировать в документы и чат.


- Раньше писали "node нет". Сейчас v24.17.0, npx-серверы MCP работают.

---

## История изменений
<a id="история-изменений"></a>
- 2026-10-20: создан
- 2026-10-20: исправлены факты оболочки, добавлен шим, MCP 14 серверов
- 2026-10-29: MCP 15 серверов (в патч добавлен graphify)

#deepseek #scripts #mcp
- 2026-10-31: добавлены copy-dsh-kit.ps1, DSH-гейт в синке и smoke-проверки kit
