<!-- generated from architecture:deepseek-harness-01-ustroystvo by doc_render.py; do not edit -->

# Устройство харнеса DeepSeek Harness

task unknown - status unknown - branch unknown - release unknown

# Устройство харнеса DeepSeek Harness
<a id="устройство-харнеса-deepseek-harness"></a>
<!-- meta
type: architecture
status: actual
updated: 2026-10-31
tags: [deepseek, harness, structure]
-->

---

## Суть
<a id="суть"></a>
Харнес DeepSeek Harness - тонкий слой поверх канона `.cursor/`, который
адаптирует скилы, правила и MCP к модели конфигурации DSH. У DSH нет движка
always-правил и он не читает `.cursor/rules/*.mdc` напрямую: правила
подключаются файлом `DSH-RULES.md`, скилы читаются из проектных корней, MCP
живёт отдельными инстансами `dsh-mcp-client`, PowerShell-скрипты запускаются
через шим.

Харнес не копирует канон. Единственный источник скилов и правил - `.cursor/`.
DSH-слой маршрутизирует: какой скил читать, какой скрипт запускать, как
называются MCP-инструменты и что реально доступно в этой среде.

> **AI:** читай этот doc, чтобы понять состав и границы харнеса DSH перед правкой.
> **Сначала:** [02-установка.md](./deepseek-harness-02-ustanovka.md) для развёртывания.
> **Не читай целиком:** файлы `.dsh/adapters/*.md` открывай по мере необходимости.

---

## Состав файлов
<a id="состав-файлов"></a>
```
.dsh/
├── project.patch.yml              MCP + overlay, генерируется, загружается через --patch
├── models.overlay.json            маршрутизация моделей (руками)
├── project.patch.yml.bak-*        старые снимки патча, не для запуска
├── scripts/
│   ├── run-ps1.sh                 шим запуска PowerShell-скриптов канона
│   └── smoke.sh                   проверка окружения и харнеса
├── skills/
│   └── dsh-router/SKILL.md        единственный проектный скил DSH (ранг 100)
└── adapters/
    ├── shell.md                   оболочка, pwsh, замеры
    ├── mcp-names.md               15 serverName -> mcp__server__tool
    ├── models.md                  модели и как включить llm-pi-ai
    ├── prepare-plan-digest.md     сжатый чеклист P0-P7
DSH-RULES.md                       always-правила инлайнены, on-demand таблицей (генерируется)
```

| Файл | Кто создаёт | Роль |
|---|---|---|
| `.dsh/project.patch.yml` | `generate-dsh-config.py` | MCP-инстансы + overlay моделей |
| `.dsh/models.overlay.json` | вручную | маршрутизация моделей, читается генератором |
| `.dsh/skills/dsh-router/SKILL.md` | вручную | маршрутизация задачи, гейты, оболочка |
| `.dsh/adapters/*.md` | вручную | справочники оболочки, MCP, моделей, команд |
| `.dsh/scripts/run-ps1.sh` | вручную | единственный способ запускать `.ps1` канона |
| `.dsh/scripts/smoke.sh` | вручную | повторяемая проверка харнеса |
| `DSH-RULES.md` | `generate-dsh-config.py` | always-правила целиком, on-demand - таблица триггеров |

---

## Слои и границы
<a id="слои-и-границы"></a>

### Канон (читаем, не правим)
<a id="канон-(читаем,-не-правим)"></a>
```
.cursor/rules/*.mdc        36 правил
.agents/skills/            26 скилов
.agents/skills/*/scripts/  скрипты скилов (32 scripts в каноне)
.cursor/scripts/           общие скрипты (multi-exec, multi-search, php-docker)
.cursor/mcp.json           19 серверов, 4 выключены
.cursor/mcp.env            секреты
```

### Зеркала (генерируются)
<a id="зеркала-(генерируются)"></a>
```
.codex/ .kilo/ .agents/ .antigravity/ .gemini/
```

DSH читает скилы из `.agents/skills` (ранг 200) и `.dsh/skills` (ранг 100),
правила - только из `DSH-RULES.md` и `AGENTS.md`.

### Слой DSH (единственный редактируемый)
<a id="слой-dsh-(единственный-редактируемый)"></a>
`.dsh/`, `DSH-RULES.md`, документация `.doc/architecture/` (deepseek-harness-*).
Вне git через `.git/info/exclude`: `/.dsh/`, `/DSH-RULES.md`.

Переносимая часть `.dsh` (`skills`, `adapters`, `scripts`, `tests`, `models.overlay.json`)
копируется `copy-dsh-kit.ps1` при переносе проекта. `project.patch.yml` и
`DSH-RULES.md` генерируются из `.cursor` и в git не входят.

## 18 скилов канона и роль в DSH
<a id="18-скилов-канона-и-роль-в-dsh"></a>
Скилы читаются через tool `skill(name)`. `dsh-router` в эти 18 не входит.

| Скил | Роль в DSH-цикле |
|---|---|
| gototask | переход к задаче, ядро цикла |
| task-doc | погружение (режим A) и doc.md после push (режим B) |
| prepare-plan | план и аудит P7.4a |
| git-task-blame | история строк внутри prepare-plan |
| task-diff | diff задачи после правок |
| test-task | оркестратор теста |
| prepare-task-test | собрать Cest, если нет |
| browser-verify | прогон браузера внутри test-task |
| login-as-user | вход под клиентом |
| send-to-git | commit и push по явному "да" |
| task-change-report | HTML-отчёт после тестов |
| jira-report | текст в Jira |
| harness-improvement | правка харнеса |
| doc-verify | сверка arch и кода |
| project-doc | индексация документации |
| task-intake | завод задачи и догон документации |
| task-code-review | ревью hunk-ов |
| yadisk-screenshot | скриншот по ссылке |

`comment-triage` - правило, не скил. В цикле обязательно.

## Как DSH отличается от Cursor
<a id="как-dsh-отличается-от-cursor"></a>
| Понятие Cursor | Как в DSH |
|---|---|
| `.cursor/rules/*.mdc` с `alwaysApply` | `DSH-RULES.md`: всегда-правила инлайнены, on-demand - таблица |
| `.agents/skills/*/SKILL.md` | `.agents/skills` (зеркало) + `.dsh/skills` (наш скил) |
| `.cursor/mcp.json` + `mcp.env` | `project.patch.yml`, по одному `dsh-mcp-client` на сервер |
| AskQuestion | tool `ask_user_question` (есть, с вариантами) |
| `powershell -File script.ps1` | `bash .dsh/scripts/run-ps1.sh script.ps1` |
| автоматический apply правил | нет, правила приходят текстом в промпте |

---

## Связи
<a id="связи"></a>
- [Установка](./deepseek-harness-02-ustanovka.md) - как развернуть и проверить
- [Workflow](./deepseek-harness-03-workflow.md) - цикл задачи
- [Модели](./deepseek-harness-04-modeli.md) - что доступно и как включить остальное
- [Скрипты и MCP](./deepseek-harness-05-skripty.md) - оболочка и инструменты
- [Канон и среды../state/01-canon-envs.md) - полная картина сред

---

## Известные проблемы и ограничения
<a id="известные-проблемы-и-ограничения"></a>
- Симптом: `project.patch.yml` не совпадает с тем, что выдаёт генератор.
- Причина: раньше патч правили руками (убирали `llm-pi-ai`, ставили
  `modelSelectionSettings: false`).
- Решение: генерировать с явными флагами
  `--no-llm --no-model-selection`; `smoke.sh` сверяет результат побайтно.
- Файлы: `.dsh/project.patch.yml`, `.agents/skills/harness-management/children/environment-sync/scripts/generate-dsh-config.py`


- Симптом: `powershell.exe: command not found` в агентской оболочке.
- Причина: `PATH` не содержит `/mnt/c/...`, хотя interop включён.
- Решение: `run-ps1.sh` ищет движок сам, приоритет у pwsh в WSL.
- Файлы: `.dsh/scripts/run-ps1.sh`, `.dsh/adapters/shell.md`


- Симптом: `list_subagent_models` возвращает `no LLM providers`.
- Причина: `llm-pi-ai` не входит в патч.
- Решение и цена включения: [04-модели.md](./deepseek-harness-04-modeli.md).
- Файлы: `.dsh/models.overlay.json`, `.dsh/project.patch.yml`


- Симптом: новых `mcp__*` нет в списке инструментов.
- Причина: патч применяется при старте профиля.
- Решение: перезапуск `dsh --patch .dsh/project.patch.yml web --no-open`.

---

## История изменений
<a id="история-изменений"></a>
- 2026-10-20: создан из plan/07-dsh-final.md и plan/06b-dsh-scripts-and-testing.md
- 2026-10-20: аудит DSH; исправлены факты оболочки (node есть, powershell.exe не в PATH),
  добавлены `run-ps1.sh` и `smoke.sh`, описан реальный состав MCP (14) и моделей (1)

#deepseek #harness #structure
- 2026-10-31: зафиксирован перенос DSH kit через copy-dsh-kit.ps1 и актуальный состав 23 скилов
