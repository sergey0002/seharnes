# Portable MCP kit для Cursor

Скопируйте всю папку **`.cursor`** в корень проекта. Серверы из `mcp.json` подключаются **на уровне проекта**; глобальные — из `%USERPROFILE%\.cursor\mcp.json`. Cursor **объединяет** оба списка; при совпадении **имени** сервера побеждает конфиг **проекта**.

Краткий старт в корне репозитория: [`README-MCP-SETUP.md`](./README-MCP-SETUP.md).

Рекомендации для агента на большом legacy **PHP + Vue.js**: [`recommendations.md`](recommendations.md) (можно подключить как Cursor Rule).

Подробная инструкция по **codebase-memory-mcp** (индекс, UI-граф, чат, CLI): правило [`rules/mcp/codebase-memory-mcp.mdc`](rules/mcp/codebase-memory-mcp.mdc) и [документация сервера](../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md).

Карта MCP: [`rules/mcp.mdc`](rules/mcp.mdc) - назначение, порядок вызова и ссылки на правило и документ каждого сервера.

**Работа с задачами Jira** (ветки, `task.md`, diff, скилы): Cursor Rule [`.cursor/rules/bitbucket-tasks.mdc`](rules/bitbucket-tasks.mdc) и раздел [Задачи Jira](#задачи-jira) ниже.

**Документация проекта** перед задачей: [`.doc/architecture/index.md`](../.doc/architecture/index.md).

---

## Задачи Jira

Документация для агента: экспорт из Jira, git-ветки на GitVerse (`origin`), скилы **gototask** / **task-diff**.

### Структура каталогов

```
.doc/
├── architecture/            # документация проекта для агента (начать с index.md)
│   └── index.md
├── .jira/                   # экспорт задач из Jira REST API
│   ├── server.php           # CLI + MCP stdio (jira-task)
│   ├── config.env           # credentials (не в git)
│   └── README.md            # настройка экспорта
├── .bitbucket/              # legacy Bitbucket Issues (не использовать)
└── tasks/
    └── {N}/                 # N = номер задачи, напр. 1612
        ├── task.md          # описание + комментарии из Jira
        ├── diff.md          # полный diff по задаче (git)
        └── diff.files.md    # только список изменённых путей
```

**Путь к задаче:** `.doc/tasks/{N}/` (от корня репозитория).

**Именование папки:** только цифры номера задачи (`1612`, не `#1612`).

---

### Файлы задачи — что за что отвечает

| Файл | Источник | Назначение | Когда читать агенту |
|------|----------|------------|-------------------|
| `task.md` | Jira REST API | Заголовок, метаданные, описание, **комментарии** и changelog | Контекст бага/требований, договорённости в комментариях |
| `diff.files.md` | git (скрипт task-diff) | **Плоский список путей** + разбивка по коммитам | **Первым** — понять какие файлы трогать, без чтения diff |
| `diff.md` | git (скрипт task-diff) | Diff по коммитам задачи: id, дата, автор, patch | Когда нужны детали изменений по строкам |

**Порядок чтения (экономия токенов):**

1. `diff.files.md` — какие файлы
2. `task.md` — что нужно сделать / что уже обсуждали
3. `diff.md` — только если нужен построчный diff
4. Исходники в репо — через Serena / Read

---

### Формат `task.md`

Генерируется автоматически (`.agents/skills/task-router/children/jira/scripts/server.php`). Руками не править — перезаписывается при обновлении.

```markdown
# Issue #2538: заголовок задачи

**Jira:** <https://copytrust-team.atlassian.net/browse/CT-2538>

| Field | Value |
| --- | --- |
| State | Backlog |
| Kind | Баг |
| Priority | Medium |
| ... | ... |

## Description

Текст описания.

## Comments

**Автор** · 30.03.2026 06:46 UTC

Текст комментария.

---

**Другой автор** · ...

*Changed:* State: `new` → `open`
```

**Полезные поля для агента:**

- `Kind`: `Баг` / `bug` → ветка `bugfixes/#N`; «доработка» в заголовке → `features/#N`
- `Description` — воспроизведение, ожидаемое поведение
- `Comments` — решения, стенды (d1, d4), связанные задачи (#1579, #1581)

---

### Формат `diff.files.md`

Компактный индекс для агента (~3 KB). UTF-8 with BOM.

```markdown
# Files Issue #1612

| Field | Value |
| Unique files | 19 |

## All files

lib/Objects/Client/ClientService.php
scripts/module/item/components/step5.js
...

## By commit

### `785d721f0` | 23.05.2026 04:30:22 +0700 | Сергей О

lib/Objects/Account/AccountController.php
...
```

---

### Формат `diff.md`

Полный diff. UTF-8 with BOM. Только коммиты, у которых **subject начинается** с `{N}` или `#{N}`.

Секции:

- метаданные (ветка, релиз-база, merge-base)
- **Commits (index)** — краткий список
- **Committed changes** — по каждому коммиту: id, author, date, message, stat, ` ```diff `

Незакоммиченные правки (если есть) — секция **Uncommitted changes**.

---

### Git: ветки задач и релизы

**Remote:** `origin` → `git@gitverse.ru:realant/copytrust.ru.git` (GitVerse). Запасной: `bitbucket` → `git@bitbucket.org:copytrust/copytrust.ru.git`. См. [cicd.md §6a](../.doc/architecture/cicd.md#6a-локальный-git-push).

#### Именование веток задач

| Тип в заголовке | Префикс | Пример |
|-----------------|---------|--------|
| «доработка» | `features` | `features/#1612` |
| «ошибка» | `bugfixes` | `bugfixes/#1612` |

Шаблон: `{prefix}/#{номер}`.

**Бэкпорт в другой релиз** (одна задача в нескольких релизах):

```
bugfixes/#1612           ← основная ветка
bugfixes/#1612_for5606   ← бэкпорт для release/5.6.0.6
bugfixes/#1638_for_5.6.0.6
```

Суффикс `_for5606` / `_for_5.6.0.6` → скрипты подставляют соответствующую релизную ветку.

#### Релизные ветки

База для **новых** веток задач — актуальная релизная ветка в проде.

| Шаблон | Пример |
|--------|--------|
| `release/{X.Y.Z.W}` | `release/5.6.0.6` |
| `releases/{X.Y.Z.W}` | `releases/5.6.1` |

Конфиг: [`.cursor/skills/task-router/children/gototask/config.json`](skills/task-router/children/gototask/config.json):

```json
{
  "releaseBranch": "release/5.6.0.6",
  "releaseBranchFallbacks": ["releases/5.6.0.6"]
}
```

Обновлять при смене релиза в проде.

#### Сообщения коммитов

**Начинать subject с номера задачи** — иначе diff не попадёт в `diff.md`:

```
1612 правки по результатам тестов
1612 - Правки ошибки синхронизации...
#1612 fix something
```

Плохо (не попадёт в task-diff): `fix 1612`, `WIP for task 1612`.

---

### Скилы Cursor (агент)

| Скил | Триггер в чате | Скрипт |
|------|----------------|--------|
| **gototask** | «перейди к задаче 1612», `gototask` | `.cursor/skills/task-router/children/gototask/scripts/gototask.ps1` |
| **task-intake** | «заведи задачу», «догнать документацию задачи» | `.cursor/skills/task-router/children/task-intake/scripts/intake_orchestrator.py` |
| **task-diff** | «обнови диф задачи 1612» | `.cursor/skills/task-router/children/task-diff/scripts/task-diff.ps1` |
| **project-doc** | «задокументируй проект» / «задокументируй раздел [name]» | `.cursor/skills/documentation-router/children/project-doc/SKILL.md` (инструкция) |
| **task-doc** | «задокументируй задачу» / «document task» | `.cursor/skills/documentation-router/children/task-doc/SKILL.md` (инструкция) |
| **prepare-plan** | «подготовь план», «составь план», «проведи аудит плана» | `.cursor/skills/prepare-plan/SKILL.md` — blast-radius ladder (P1), git-task-blame (P0.5b/P7.4a), per-шаг тест-сценарий, SOLID/DRY-гейт (P4.1), аудит P7 только код; **аудит = тот же скил (режим P7.4a), не отдельный** |
| **git-task-blame** | «кто менял этот код», «какие задачи трогали этот файл» | `.cursor/skills/task-router/children/git-task-blame/SKILL.md` — git log -L/blame → номера задач → export-task, обязателен внутри prepare-plan |
| **test-task** | «тестируй задачу», «тестируй задачу 2606» | `.cursor/skills/task-router/children/testing-router/children/test-task/SKILL.md` — оркестратор: prepare-task-test (если нет Cest) → browser-verify → test-runs по `.doc/tests.md` |
| **prepare-task-test** | «подготовь тест задачи N» | `.cursor/skills/task-router/children/testing-router/children/prepare-task-test/SKILL.md` — конструктор Cest + test.md |
| **browser-verify** | «проверь через браузер», e2e, регрессия UI | `.cursor/skills/task-router/children/testing-router/children/browser-verify/SKILL.md` — Codeception → Playwright, отчёт §8 |
| **login-as-user** | «войди как клиент N» | `.cursor/skills/login-as-user/SKILL.md` — имперсонация на dev |
| **task-code-review** | review task diff, аудит коммитов задачи | `.cursor/skills/task-router/children/task-code-review/SKILL.md` (инструкция) |
| **send-to-git** | «отправь в гит», «закоммить и запушь» | `.cursor/skills/send-to-git/SKILL.md` — согласование commit/push, выполнение после «да» |
| **yadisk-screenshot** | «загрузи скрин с яндекса», ссылка на Яндекс.Диск | `.cursor/skills/yadisk-screenshot/SKILL.md` (инструкция) |
| **jira-report** | «напиши отчет для жиры», отчёт в Jira | `.cursor/skills/task-router/children/reporting-router/children/task-report/SKILL.md` — короткий комментарий + пути скринов |

Подробности: [`skills/task-router/children/gototask/SKILL.md`](skills/task-router/children/gototask/SKILL.md), [`skills/task-router/children/task-diff/SKILL.md`](skills/task-router/children/task-diff/SKILL.md).

**Правило:** использовать PS1-скрипты, **не** дублировать git-команды и **не** вызывать MCP `jira-task` вручную (скрипты сами вызывают `.agents/skills/task-router/children/jira/scripts/server.php` через PHP/Docker).

---

### Как обновлять файлы задачи

#### 1. Перейти к задаче (ветка + task.md)

**Чат:** `перейди к задаче 1612`

**Консоль:**

```powershell
cd C:\projects\copytrust\testdeploydocker

# inspect — состояние веток, JSON
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 1612 -Action inspect

# checkout существующей ветки
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 1612 -Action checkout -TaskBranch "bugfixes/#1612" -LocalChanges keep

# создать ветку от релиза (только после подтверждения пользователя!)
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 1612 -Action create-branch -ReleaseBranch "release/5.6.0.6" -TaskBranch "bugfixes/#1612" -ConfirmCreateBranch

# вмержить релиз в ветку задачи (после подтверждения)
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 1612 -Action merge-release -ReleaseBranch "release/5.6.0.6" -TaskBranch "bugfixes/#1612"
```

`gototask` автоматически обновляет `task.md` (PHP или Docker `copytrust-dev-php-apache-1`).
При открытом вопросе из `needsUserInput` apply требует `-ConfirmCreateBranch`,
`-ConfirmMerge` или `-ConfirmDiscard`, иначе возвращает exit 3. После apply
best-effort запускается `codegraph sync` (поле `codegraphIndex`).

#### 2. Обновить task.md отдельно

```powershell
php .agents/skills/task-router/children/jira/scripts/server.php 2538
# или
docker exec copytrust-dev-php-apache-1 php /var/www/html/.agents/skills/task-router/children/jira/scripts/server.php 2538
```

Настройка: [`.doc/skil_data/jira/README.md`](../.doc/skil_data/jira/README.md).

#### 3. Обновить diff.md + diff.files.md

**Чат:** `обнови диф задачи 1612`

**Консоль:**

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/skills/task-router/children/task-diff/scripts/task-diff.ps1 -TaskNumber 1612
```

С явными ветками:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/skills/task-router/children/task-diff/scripts/task-diff.ps1 -TaskNumber 1612 -TaskBranch "bugfixes/#1612" -ReleaseBranch "release/5.6.0.6"
```

Лучше запускать **на ветке задачи** — тогда в diff попадут незакоммиченные правки.

---

### Workflow агента по задаче

```
1. gototask inspect / перейди к задаче {N}
   → ветка, свежий task.md

2. Прочитать .doc/architecture/index.md
   → архитектура и домены проекта

3. Прочитать task.md
   → требования, комментарии, связанные задачи

4. Прочитать diff.files.md (или сгенерировать task-diff)
   → список файлов

5. diff.md — при необходимости построчного контекста

6. Правки в коде (Serena / Read)
   → коммиты с префиксом "{N} " в subject

7. task-diff — обновить diff.md + diff.files.md

8. push / PR — только по запросу пользователя
```

**Обязательно спрашивать пользователя (AskQuestion):**

- какую релизную ветку использовать
- создавать ли новую ветку
- мержить ли релиз в ветку задачи
- затереть / stash локальные правки
- push, commit merge-конфликтов

---

### Файлы kit (дополнение)

```
.cursor/
  skills/
    gototask/
      SKILL.md
      config.json           # текущая релизная ветка
      scripts/gototask.ps1
    task-diff/
      SKILL.md
      scripts/task-diff.ps1
.doc/
  .jira/                    # экспорт Jira → task.md
  .bitbucket/               # legacy Bitbucket Issues
  tasks/{N}/
    task.md
    diff.md
    diff.files.md
```

---

## Быстрый старт

```powershell
# 1. Скопировать .cursor в корень целевого проекта
# 2. Один раз в проекте:
.\.cursor\setup.ps1

# 3. Заполнить секреты (не коммитить):
#    .cursor\mcp.env  ← из mcp.env.example

# 4. (Опционально) Глобально установить codebase-memory-mcp UI — см. раздел ниже

# 5. Полностью перезапустить Cursor → Settings → MCP → все серверы зелёные
```

**Требования:** Node.js (`npx`), [uv](https://docs.astral.sh/uv/) (`uvx`), PHP + Composer (для PHPStan/phpda), локальный MySQL (для mysql MCP), Semgrep (через `uvx semgrep mcp`).

---

## Где лежат конфиги

| Уровень | Путь (Windows) | Назначение |
|--------|----------------|------------|
| **Глобально** | `%USERPROFILE%\.cursor\mcp.json` | Серверы во **всех** workspace (например `codebase-memory-mcp`) |
| **Проект (kit)** | `<repo>\.cursor\mcp.json` | Portable набор: Playwright, Serena, MySQL, PHP toolchain, … |
| **Секреты проекта** | `<repo>\.cursor\mcp.env` | `MYSQL_*`, `PHP_BIN` — **в .gitignore** |
| **Артефакты PHP** | `<repo>\.cursor\artifacts\` | callgraph SVG и т.п. |
| **CLI PHP (kit)** | `<repo>\.cursor\tools\vendor\` | PHPStan/phpda только для MCP, не путать с `vendor/` проекта |
| **Индекс CBM** | `%USERPROFILE%\.cache\codebase-memory-mcp\` (Windows) / `~/.cache/codebase-memory-mcp/` (WSL) | SQLite-графы всех проиндексированных репозиториев |

### Подстановки в `mcp.json`

Cursor разрешает в `command`, `args`, `env`, `url`:

- `${workspaceFolder}` — корень проекта (где лежит `.cursor/mcp.json`)
- `${workspaceFolderBasename}` — имя папки проекта
- `${userHome}` — домашний каталог
- `${env:VAR}` — переменная окружения
- `${pathSeparator}` / `${/}` — разделитель пути ОС

---

## codebase-memory-mcp (глобальный + в kit)

[Репозиторий](https://github.com/DeusData/codebase-memory-mcp) — граф знаний по коду (tree-sitter, 155 языков), 17 MCP-инструментов, локально, без API-ключей.

**Правило для агента:** [`rules/mcp/codebase-memory-mcp.mdc`](rules/mcp/codebase-memory-mcp.mdc) (методы, аргументы, когда брать). **Эксплуатация:** [документация сервера](../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md) (установка, индексация, UI на :9749, CLI, troubleshooting).

### Установка

**Windows (UI):** `%LOCALAPPDATA%\Programs\codebase-memory-mcp\codebase-memory-mcp.exe` — см. [документацию CBM](../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md).

**WSL / Linux (UI):** `~/.local/bin/codebase-memory-mcp` — архив `codebase-memory-mcp-ui-linux-amd64` с [Releases](https://github.com/DeusData/codebase-memory-mcp/releases). Нужен **tmux** для автозапуска UI.

### Подключение в portable kit (`mcp.json`)

```json
"codebase-memory-mcp": {
  "type": "stdio",
  "command": "bash",
  "args": [
    "${workspaceFolder}/.agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-launch.sh",
    "--ui=false"
  ]
}
```

Лаунчер [`scripts/codebase-memory-mcp-launch.sh`](scripts/codebase-memory-mcp-launch.sh): кроссплатформенный поиск бинарника; на WSL при старте MCP поднимает UI в tmux (`cbm-ui`, порт 9749).

**3D-граф:** [http://localhost:9749](http://localhost:9749) — после открытия проекта в Cursor (MCP зелёный). Ручной запуск: `bash .agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-ui.sh`.

### Автоиндексация и наблюдатель

```bash
codebase-memory-mcp config list
```

В этом проекте `auto_index=false`: параллельная полная переиндексация от нескольких клиентов запрещена. Наблюдатель файлов при этом включён (`auto_watch`, `watcher_enabled`), но он не гарантирует свежесть. Перед `git push` граф обновляется вручную: `index_repository` с абсолютным `repo_path` и `mode=fast`. Подробности: [документация сервера](../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md), правило [`rules/cbm-index-before-push.mdc`](rules/cbm-index-before-push.mdc).

### Инструменты codebase-memory-mcp

| Инструмент | Назначение |
|------------|------------|
| `index_repository` | Построить/обновить граф. Режимы: `full`, `moderate`, `fast`, `cross-repo-intelligence`. `persistence: true` → артефакт `.codebase-memory/graph.db.zst` для команды |
| `index_status` | Статус индексации проекта |
| `list_projects` | Список проиндексированных репозиториев |
| `delete_project` | Удалить проект из индекса |
| `search_graph` | Поиск по графу: BM25 (`query`), regex (`name_pattern`), семантика (`semantic_query` — **массив** строк). Вместо слепого grep по всему репо |
| `search_code` | Grep только по **проиндексированным** файлам + обогащение из графа |
| `trace_path` | Цепочки вызовов / data flow по графу |
| `query_graph` | Cypher-подмножество (MATCH/WHERE/RETURN) |
| `get_graph_schema` | Схема графа — **вызывать первым** при незнакомом проекте |
| `get_code_snippet` | Исходник по qualified name (сначала `search_graph`) |
| `get_architecture` | Обзор: языки, пакеты, routes, hotspots, кластеры |
| `detect_changes` | Git diff → затронутые символы и blast radius |
| `manage_adr` | Architecture Decision Records |
| `ingest_traces` | Уточнение HTTP/асинхронных рёбер по runtime-трейсам |

**auto-allow в kit** (без лишних кликов): read-only обзорные инструменты; `index_repository` / `delete_project` — с подтверждением.

### Дублирование global vs project

Если в `%USERPROFILE%\.cursor\mcp.json` и в `.cursor/mcp.json` одно имя `codebase-memory-mcp`, действует **проектный** блок. На Windows без лаунчера — `.exe` в `%LOCALAPPDATA%\Programs\...`; в WSL — бинарник в `~/.local/bin/` + лаунчер из kit.

---

## Серверы portable kit (`mcp.json`)

### playwright — E2E / ручная проверка UI

`npx -y @playwright/mcp@0.0.38`

| Инструмент | Описание |
|------------|----------|
| `browser_navigate` | Открыть URL |
| `browser_snapshot` | A11y-снимок страницы (предпочтительнее скриншота для действий) |
| `browser_click` | Клик |
| `browser_type` | Ввод в поле |
| `browser_fill_form` | Несколько полей формы |
| `browser_evaluate` | JS на странице |
| `browser_take_screenshot` | Скриншот |
| `browser_wait_for` | Ожидание текста/времени |
| `browser_console_messages` | Логи консоли |
| `browser_network_requests` | Сетевые запросы |
| `browser_close` | Закрыть страницу |
| `browser_install` | Установить браузер Playwright |

**auto-allow:** navigate, snapshot, click, type, fill_form, evaluate, screenshot.

**disabledTools:** tabs, drag, hover, select_option, navigate_back, press_key — меньше шума в legacy UI.

**Требование проекта:** тестирование всегда с видимым браузером (headed) - `@playwright/mcp` по умолчанию headed (`--headless` не задан в `mcp.json`, не добавлять).

**Chrome на WSL (пути, chromedriver, env MCP):** [`.doc/qa/browser-setup.md`](../.doc/qa/browser-setup.md).
В `mcp.json` заданы `PLAYWRIGHT_MCP_EXECUTABLE_PATH` / `CHROME_PATH` /
`LD_LIBRARY_PATH` на Chrome for Testing; нужен также `/opt/google/chrome/chrome`.
После смены env - Reload MCP.

---

### serena — PHP-редактирование по символам (LSP)

`uvx` + `serena start-mcp-server --context desktop-app --project ${workspaceFolder}`

Перед правками: `get_symbols_overview` / `find_symbol` → потом `replace_symbol_body` / `insert_*`.

| Группа | Инструменты |
|--------|-------------|
| Обзор | `get_symbols_overview`, `find_symbol`, `find_file`, `list_dir`, `search_for_pattern` |
| Навигация | `find_declaration`, `find_implementations`, `find_referencing_symbols`, `get_type_hierarchy` (если включён) |
| Правки | `replace_symbol_body`, `insert_before_symbol`, `insert_after_symbol`, `replace_content`, `rename_symbol`, `safe_delete_symbol`, `create_text_file`, `read_file` |
| Диагностика | `get_diagnostics_for_file` |
| Память сессий | `write_memory`, `read_memory`, `list_memories`, `edit_memory`, `delete_memory`, `rename_memory` |
| Прочее | `activate_project`, `get_current_config`, `onboarding`, `initial_instructions`, `execute_shell_command` |

**auto-allow:** list_dir, find_symbol, get_symbols_overview, find_file, search_for_pattern, replace_content, read_file, get_type_hierarchy.

**Роль:** точечные правки PHP; для **структуры всего репо** — codebase-memory-mcp; для **полнотекста** — sourcegraph; для **текста без символов** — обычный grep/Read.

---

### sourcegraph — полнотекстовый поиск (локальный, после CBM)

HTTP MCP → `http://127.0.0.1:7080/.api/mcp/v1` (см. [`.cursor/mcp.json`](mcp.json)).

| Инструмент | Описание |
|------------|----------|
| `sg_keyword_search` | Точный поиск с `repo:^src-serve-git-3434/repos/testdeploydocker$` |
| `sg_nls_search` | Семантический/размытый поиск по модулю |
| `sg_list_repos` / `sg_list_files` | Репозиторий и каталоги |
| `sg_read_file` | Фрагмент файла (если CBM snippet мало) |

**Порядок:** CBM (`search_graph`, `trace_path`) → Sourcegraph (`sg_*`) → Serena.  
**Не для:** `.doc/` (Read). **Синхронизация:** `sourcegraph-local/sync-mirror.sh`.  

---

### context7 — актуальная документация библиотек

`npx -y @upstash/context7-mcp@3.2.2`

| Инструмент | Описание |
|------------|----------|
| `resolve-library-id` | Имя пакета → Context7 library ID (**сначала**) |
| `query-docs` | Запрос к доке/примерам по library ID |

Использовать для Laravel, Vue, Vite, PHPUnit и т.д., когда версия/API неочевидны.

---

### mysql — схема и данные dev-БД

`npx -y @f4ww4z/mcp-mysql-server` + `envFile: .cursor/mcp.env`

| Инструмент | Описание | Подтверждение |
|------------|----------|----------------|
| `connect_db` | Подключение | auto |
| `list_tables` | Список таблиц | auto |
| `describe_table` | DDL/колонки | auto |
| `query` | SELECT | auto |
| `execute` | INSERT/UPDATE/DELETE | **требует OK** |

**Правило kit:** схему БД узнавать **только** через mysql MCP, не выдумывать колонки.

Переменные в `mcp.env`: `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER`, `MYSQL_PASSWORD`, `MYSQL_DATABASE`.

---

### git — история и диффы

`uvx mcp-server-git --repository ${workspaceFolder}`

| Инструмент | Описание | auto |
|------------|----------|------|
| `git_status` | Working tree | да |
| `git_log` | История коммитов | да |
| `git_diff` | Дифф | да |
| `git_show` | Объект/коммит | да |
| `git_blame` | Blame по файлу | да |

Дополнительно к `detect_changes` в CBM — git MCP ближе к «что изменилось в git», CBM — к «какой код затронут в графе».

---

### semgrep — SAST

`uvx semgrep mcp`

| Инструмент | Описание |
|------------|----------|
| `semgrep_scan` | Локальный скан по правилам Semgrep |
| `semgrep_scan_with_custom_rule` | Скан с кастомным правилом |
| `semgrep_scan_supply_chain` | Supply chain / зависимости |
| `semgrep_findings` | Findings из Semgrep AppSec (если настроено) |
| `get_abstract_syntax_tree` | AST файла |
| `get_supported_languages` | Поддерживаемые языки |
| `semgrep_rule_schema` | Схема правила |

---

### xdebug — отладка PHP

`npx -y xdebug-mcp`

Инструменты зависят от версии пакета (breakpoints, evaluate, stack). Нужен настроенный Xdebug в `php.ini` проекта. Включать, когда задача — «почему в рантайме», а не статический анализ.

---

### phpstan-mcp — статический анализ PHP

Локальный Node-сервер: `.tools/mcp-servers/php-toolchain/server.js`, режим `phpstan`.

| Инструмент | Описание |
|------------|----------|
| `phpstan_analyze` | `phpstan analyze` (JSON). Пути и `level` опционально. Ищет `vendor/bin/phpstan` **проекта**, иначе `.cursor/tools/vendor/bin/phpstan` |

**auto-allow:** `phpstan_analyze`.

---

### php-deps-mcp — граф зависимостей PHP

Тот же `server.js`, режим `php-deps`.

| Инструмент | Описание |
|------------|----------|
| `phpcallgraph_generate` | Call graph (SVG/PNG) в `.cursor/artifacts/` |
| `phpda_analyze` | php-dependency-analysis (`phpda.xml` в корне или `.cursor/tools/phpda.yml`) |

**auto-allow:** оба инструмента.

---

### deepwiki — выключен

`disabled: true` в `mcp.json`. Включать только при явной необходимости.

---

## Сводная таблица: что когда использовать

| Задача | Первый выбор | Запасной |
|--------|--------------|----------|
| «Где определён X / кто вызывает Y» | CBM `search_graph` + `trace_path` | Sourcegraph `sg_keyword_search`; Serena `find_symbol` |
| Строки в .js/.tpl, regex по репо | Sourcegraph `sg_keyword_search` | CBM `search_code` |
| Правка метода/класса PHP | Serena | Read + ручная правка |
| Схема таблицы / пример данных | mysql `describe_table` + `query` | — |
| Дока Laravel/Vue/NPM | context7 | — |
| Регрессия UI (Vue), уже покрыто тестом | Codeception Acceptance (`browser-verify`) | — |
| Регрессия UI, новая логика без покрытия | playwright | — |
| Сломанный рантайм PHP | xdebug | логи |
| Типы/мертвый код PHP | phpstan-mcp | CBM `search_graph` + dead code через граф |
| Слои/циклы зависимостей PHP | phpda + CBM `get_architecture` | phpcallgraph |
| Уязвимости / антипаттерны | semgrep | — |
| Что в git изменилось | git + CBM `detect_changes` | — |
| Обзор монолита с нуля | CBM `get_architecture` + `get_graph_schema` | Serena onboarding |

---

## Файлы kit

```
.cursor/
  mcp.json              # MCP-серверы проекта
  mcp.env.example       # шаблон секретов
  mcp.env               # локально (не в git)
  setup.ps1             # npm/composer для toolchain
  README.md             # этот файл (MCP + задачи Jira)
  recommendations.md    # принципы для агента (PHP+Vue legacy)
  scripts/
    codebase-memory-mcp-launch.sh   # MCP + автозапуск UI (WSL)
    codebase-memory-mcp-ui.sh       # ручной UI :9749
    node-mcp.sh                     # Node для phpstan/php-deps MCP
  skills/               # gototask, task-diff, prepare-plan, task-doc, …
  tools/                # composer.json → PHPStan, phpda
  artifacts/            # вывод phpcallgraph
.tools/
  mcp-servers/php-toolchain/   # phpstan + php-deps MCP (локальный, вне git)
.doc/
  .jira/                # экспорт задач Jira (MCP jira-task)
  .bitbucket/           # legacy Bitbucket Issues
  tasks/{N}/            # task.md, diff.md, diff.files.md
```

---

## Устранение неполадок

| Симптом | Действие |
|---------|----------|
| MCP красный в Settings | Проверить `npx`/`uvx`/`node` в PATH; перезапуск Cursor |
| mysql не коннектится | `mcp.env`, сервис MySQL, `MYSQL_DATABASE` |
| PHPStan not found | `.\.cursor\setup.ps1` или `composer install` в `.cursor/tools` |
| CBM «binary not found» | Windows: UI `.exe` в `%LOCALAPPDATA%\Programs\...`; WSL: `~/.local/bin/codebase-memory-mcp` (UI-архив) + лаунчер в `mcp.json` |
| UI 9749 не открывается | UI-бинарник (не standard); WSL: `tmux`; Refresh MCP; `bash .agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-ui.sh` |
| Два CBM в списке | Убрать дубликат из global или project (одинаковое имя — побеждает project) |
| Playwright «browser not installed» | `browser_install` |

---

## Обновления

```powershell
# codebase-memory-mcp
codebase-memory-mcp update

# Playwright MCP — версия в mcp.json (@0.0.38)
# Остальное — @latest в npx при перезапуске Cursor
```

## JSONdoc (с 26.09.2026)

Документация задач и архитектуры - JSON-first: канон `task.json`/`{имя}.json`, MD - generated view. Инструмент: `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py` (get/search/related/batch/apply/render/ingest/plan write/plan verify - машинный аудит P7). Спецификация: `.doc/harnes/jsondoc.md` (канон движка). Состояние и этапы J00-J17: `.doc/harnes/state/06-jsondoc.md`.
