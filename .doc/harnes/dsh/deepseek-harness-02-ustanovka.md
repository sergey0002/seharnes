<!-- generated from architecture:deepseek-harness-02-ustanovka by doc_render.py; do not edit -->

# Установка и перенос на сервер

task unknown - status unknown - branch unknown - release unknown

# Установка и перенос на сервер
<a id="установка-и-перенос-на-сервер"></a>
<!-- meta
type: config
status: actual
updated: 2026-10-31
tags: [deepseek, deploy, setup]
-->

---

## Суть
<a id="суть"></a>
Порядок развёртывания харнеса DSH на новой машине или сервере. Харнес это
каталог `.dsh/`, файл `DSH-RULES.md` в корне репозитория и генератор
`.agents/skills/harness-management/children/environment-sync/scripts/generate-dsh-config.py`. В git это не попадает.

Переносимая часть `.dsh` копируется `copy-dsh-kit.ps1`. Файлы
`.dsh/project.patch.yml` и `DSH-RULES.md` генерируются из `.cursor` на целевой
машине.

> **AI:** читай этот doc при переносе харнеса или новой установке.
> **Сначала:** [01-устройство.md](./deepseek-harness-01-ustroystvo.md) - состав.
> **Не читай целиком:** шаги выполняй по одному, проверяй `smoke.sh`.
> **См. также:** [../harnes/state/09-transfer.md../state/09-transfer.md) - перенос проекта.

## Предусловия на сервере
<a id="предусловия-на-сервере"></a>
| Компонент | Требование |
|---|---|
| DeepSeek Harness | установлен, `dsh` в PATH (проверено на 0.2.1-rc.2) |
| WSL | репозиторий и агент внутри WSL |
| python3 | 3.9+ |
| git | любой свежий |
| node | 20+ (нужен самому dsh и npx-серверам MCP) |
| PowerShell 7 | портативный pwsh в `~/.local/pwsh/pwsh` |
| API-ключи | зависят от модели: deepseek-account через UI, либо `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY` |
| MCP-серверы | Docker `copytrust-dev-php-apache-1`, Sourcegraph `127.0.0.1:7080`, mysql `127.0.0.1:8031` |

---

## Шаг 1 - поставить портативный pwsh
<a id="шаг-1---поставить-портативный-pwsh"></a>
Без него PowerShell-скрипты канона уходят в `powershell.exe` и работают
в 30-80 раз медленнее (замеры в [05-скрипты.md](./deepseek-harness-05-skripty.md)).

```bash
mkdir -p ~/.local/pwsh
curl -sSL -o /tmp/pwsh.tar.gz \
  https://github.com/PowerShell/PowerShell/releases/download/v7.4.6/powershell-7.4.6-linux-x64.tar.gz
tar -xzf /tmp/pwsh.tar.gz -C ~/.local/pwsh
chmod +x ~/.local/pwsh/pwsh
DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1 ~/.local/pwsh/pwsh -NoProfile -Command '$PSVersionTable.PSVersion.ToString()'
```

Ожидаемо: `7.4.6`. Флаг `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` нужен, потому
что в WSL нет `libicu`. Шим ставит его сам, руками запоминать не надо.

---

## Шаг 2 - перенести файлы харнеса
<a id="шаг-2---перенести-файлы-харнеса"></a>
Переносимая часть kit:

```
.dsh/
  skills/dsh-router/SKILL.md
  adapters/            (8 файлов)
  scripts/             (run-ps1.sh, smoke.sh, stage-artifacts.py, usage-metrics.py, jdocmunch-mcp.sh)
  tests/               (3 файла)
  models.overlay.json
```

Перенос в новый проект:

```bash
pwsh -NoProfile -File .agents/skills/harness-management/children/new-project/scripts/copy-dsh-kit.ps1 -Source <образец> -Target <новый>
pwsh -NoProfile -File .agents/skills/harness-management/children/new-project/scripts/copy-dsh-kit.ps1 -Source <образец> -Target <новый> -Check
```

Скрипт не копирует `.dsh/project.patch.yml`, `DSH-RULES.md`, `__pycache__` и
бэкапы `models.overlay.json`.

Плюс генератор с флагами:

```
.agents/skills/harness-management/children/environment-sync/scripts/generate-dsh-config.py  (--no-llm, --no-model-selection)
```

На новом сервере `.git/info/exclude` создаётся заново. Добавить:

```
/.dsh/
/DSH-RULES.md
```

## Шаг 2a - перенести kit в новый проект
<a id="шаг-2a---перенести-kit-в-новый-проект"></a>
Когда DSH kit нужен в другом проекте, не копируйте `.dsh` целиком. Используйте
`copy-dsh-kit.ps1`.

| Копируется | Создается заново |
|---|---|
| `.dsh/skills/` | `.dsh/project.patch.yml` |
| `.dsh/adapters/` | `DSH-RULES.md` |
| `.dsh/scripts/` | `__pycache__`, `.pytest_cache` |
| `.dsh/tests/` | `models.overlay.json.bak-*` |
| `.dsh/models.overlay.json` | - |

Проверка полноты:

```bash
pwsh -NoProfile -File .agents/skills/harness-management/children/new-project/scripts/copy-dsh-kit.ps1 -Source <образец> -Target <новый> -Check
```

`rebase_project.ps1` вызывает скрипт автоматически и добавляет `.dsh` пути в
must-check.

## Шаг 3 - сгенерировать патч и правила
<a id="шаг-3---сгенерировать-патч-и-правила"></a>
```bash
python3 .agents/skills/harness-management/children/environment-sync/scripts/generate-dsh-config.py --root . --no-llm --no-model-selection
```

Флаги обязательны на этой машине:

- `--no-llm` - не добавлять `llm-pi-ai`, пока роутинг моделей не нужен;
- `--no-model-selection` - ставить `modelSelectionSettings: false`, иначе
  строка настроек ругается при старте вне preset-контекста.

Ожидаемый вывод: `"mcp_servers"` содержит 14 имён, `"entries": 15`,
`"overlay_entries": 3` (model_selection, subagent, workflow; `llm-pi-ai` отброшен),
`"skipped"` перечисляет xdebug, deepwiki, bitbucket-task.

---

## Шаг 4 - секреты
<a id="шаг-4---секреты"></a>
`.dsh/project.patch.yml` содержит живые значения в `env` (SOURCEGRAPH_MCP_TOKEN,
MYSQL_PASSWORD). Файл вне git, обращаться как с `.cursor/mcp.env`.
Генератор инлайнит значения из `.cursor/mcp.env`.

---

## Шаг 5 - запуск
<a id="шаг-5---запуск"></a>
```bash
dsh --patch .dsh/project.patch.yml web --no-open
```

Без `--patch` MCP-инструменты и overlay не поднимутся.

---

## Шаг 6 - проверка
<a id="шаг-6---проверка"></a>
```bash
bash .dsh/scripts/smoke.sh --task 2622
```

Ожидаемо: `SMOKE: passed`. Что проверяется:

| Проверка | Ожидание |
|---|---|
| движок PowerShell | портативный pwsh 7.4.6 |
| python3, git, node | версии печатаются |
| генератор | `DSH-RULES.md` и патч совпадают с выходом генератора, `--check` |
| патч | MCP-клиентов 14, `llm-pi-ai` нет, `modelSelectionSettings: false` |
| скилы | 23 канона, 23 зеркала, dsh-router, корректный frontmatter |
| правила | по 16 в `.codex`, `.kilo`, `.agents`, `.antigravity`, `.gemini` |
| DSH kit | `.dsh/skills`, `adapters`, `scripts`, `tests`, `models.overlay.json` |
| скрипты | `jsondoc plan` |
| тесты | `test_dsh_config.py`, `test_dsh_kit.py` |
| задача | `gototask inspect` и `task-diff inspect` отдают JSON |

MCP-инструменты из bash не проверить: открыть сессию и убедиться, что в
tool-каталоге есть `mcp__codebase-memory-mcp__*`, `mcp__sourcegraph__*`,
`mcp__git__*`, `mcp__mysql__*`, `mcp__serena__*`.

## Если что-то не поднялось
<a id="если-что-то-не-поднялось"></a>
| Симптом | Причина | Действие |
|---|---|---|
| `pwsh: couldn't find ICU` | нет libicu | запускать с `DOTNET_SYSTEM_GLOBALIZATION_INVARIANT=1` (шим делает сам) |
| `powershell.exe: not found` | PATH без `/mnt/c` | не вызывать напрямую, только через `run-ps1.sh` |
| `warning: 1 entry did not activate` (`modelSelectionSettings`) | строка настроек вне preset | `--no-model-selection` |
| `no LLM providers` | `llm-pi-ai` выключен | это норма для текущего профиля, см. [04-модели.md](./deepseek-harness-04-modeli.md) |
| нет `mcp__*` | запуск без `--patch` | перезапуск с `--patch .dsh/project.patch.yml` |

---

## Связи
<a id="связи"></a>
- [Устройство](./deepseek-harness-01-ustroystvo.md) - состав
- [Модели](./deepseek-harness-04-modeli.md) - включение тяжёлых моделей
- [Скрипты](./deepseek-harness-05-skripty.md) - оболочка
- [Перенос проекта../state/09-transfer.md) - общий перенос CopyTrust

---

## Известные проблемы и ограничения
<a id="известные-проблемы-и-ограничения"></a>
- Симптом: после клонирования `.dsh/` в untracked.
- Причина: exclude локальный, не коммитится.
- Решение: вручную добавить `/.dsh/` и `/DSH-RULES.md`.


- Симптом: после `generate-dsh-config.py --root .` появляются `llm-pi-ai` и
  `modelSelectionSettings: true`, старт даёт warning.
- Причина: флаги не переданы.
- Решение: всегда `--no-llm --no-model-selection` на этой машине.

---

## История изменений
<a id="история-изменений"></a>
- 2026-10-20: создан
- 2026-10-20: добавлены шаг установки pwsh, флаги генератора, `smoke.sh`,
  таблица разбора сбоев

#deepseek #deploy #setup
- 2026-10-31: добавлен шаг 2a, перенос kit через copy-dsh-kit.ps1, обновлены проверки smoke: 23 скила, DSH kit, тесты
