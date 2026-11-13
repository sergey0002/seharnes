> Актуализация 2026-11-12: проверенный контракт профилей и безопасной замены описан в [state/14-project-migration.md](harnes/state/14-project-migration.md). Перенос теперь сам запускает локальный sync в Target. Full включает документацию разработки харнеса; Core исключает authoring/task/Jira и панель. Старые указания о ручном post-export sync и .codex/skills ниже являются историческими.

# Перенос AI-kit и локальной среды разработки

<!-- meta
type: config
status: actual
updated: 2026-11-11
version: 1.29
related: [rebase_project.ps1, rebase_project_gi.ps1, mcp.index.md, harnes/doc_rules.md, harnes/readmy.md, harnes/readmy_doc.md, synh_harnes/README.md, qa/browser-setup.md, harnes/tests.md, harnes/testaudit.md, tasks/index.md, leantime/mcp.md, leantime/access.md, kaiten/doc.md, harnes/mcp/codebase-memory-mcp.md]
tags: [migration, rebase, cursor, codex, mcp, skills, rules, credentials, docker, local-env, git-exclude, export-script, windows, wsl, selenium, day0, core, leantime, ai-kit-only]
-->

---

## Суть

Исчерпывающая инструкция: как перенести из этого репозитория (`testdeploydocker` / Copytrust) в **произвольный** проект весь рабочий контур агента (Cursor, Codex, Kilo, Qoder, Qwen Code, Antigravity) **и** локальную среду разработки (Docker, креды, браузер для e2e), плюс что обязательно поправить под новый стек.

Частый запрос: на новый Win с пустым Docker перенести **только AI-kit среду** (MCP включая Sourcegraph и codebase-memory), без подъёма PHP-приложения Copytrust. Это сценарий **C** ниже и секция [AI-kit only](#сценарий-c-ai-kit-only-среда-без-app).

**Скрипт экспорта:** [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1).  
Совместимый путь: [export-rebase-project.ps1](../.agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1) (тонкий wrapper → тот же канон).

**Проверка полноты путей:** секции [Сценарий C: AI-kit only](#сценарий-c-ai-kit-only-среда-без-app), [Самодостаточность и промпт агенту](#самодостаточность-и-промпт-агенту), [Новый комп: мастер-план Day0 → green](#новый-комп-мастер-план-day0--green), [День 1: куда что прописать](#день-1-куда-что-прописать-со-старта), [MCP: индексация CBM и Sourcegraph](#mcp-индексация-cbm-и-sourcegraph), [Воссоздание контейнеров с нуля](#воссоздание-контейнеров-с-нуля), [Полная карта `.doc/`](#полная-карта-doc-факт-на-диске), [Матрица skill / rule](#матрица-skill--rule--обязательные-пути), [Экспорт скриптом](#быстрый-экспорт-скриптом-cursor), [MCP: Windows vs WSL](#mcp-windows-vs-wsl-факт-с-экрана), [Docker Desktop: контейнеры](#docker-desktop-какие-контейнеры-нужны), [Leantime (опц.)](#leantime-локальный-pm--mcp). Skills: на образце **77**; после Full-export без Copytrust-only = **76**.

> Актуальные пути: операционная карта переноса - `harnes/state/14-project-migration.md`; рабочая копия Codeception - `.tools/codeception`; `docscripts/` и `synh_harnes/` заменены скриптами скилов и `environment-sync`; `qa/browser-setup.md` и `qa/fragments.md` лежат в `.doc/qa/`. Разделы ниже сохраняют исторические имена.

Два профиля export:
| Профиль | Когда | Что берём |
|---------|-------|-----------|
| **FULL** | Jira + git-ветки + PHP/Docker + e2e | Весь kit, gototask / task-diff / jira-task, docker-dev (+ docker-test / codeception); опц. Leantime |
| **CORE** | Другой проект / только docs+MCP | Без трекера и task-skills; см. [Профиль CORE](#профиль-core); Leantime с env тоже |

Три сценария развёртывания на целевой машине: **A** тот же app, **B** другой app (Full/Core), **C** только AI-kit среда без app.

Этот файл - канон. Отдельный `migrateproject.md` удалён.

> **Sourcegraph-local исключен из миграции с 2026-11-05.** Скрипт
> `rebase_project.ps1` больше не копирует `sourcegraph-local/` и не проверяет его
> в must-check. Разделы про Sourcegraph ниже оставлены как legacy-инструкция для
> ручного развертывания на машине, если стек нужен отдельно.

**Не копировать секреты** kit (`mcp.env` Cursor/Codex, `config.env` Jira, app `.env`, живые токены SG в `mcp.json`) - из `*.example` / `*.dist`.  
**Исключение Leantime:** копировать **целиком** `.doc/skil_data/leantime/` включая `docker/.env`, `mcp/mcp.env`, `access.md`, bearer.

---

## Сценарий C: AI-kit only (среда без app)

Цель: Cursor MCP и skills **как на образце** (serena, git, CBM, Sourcegraph, playwright, phpstan/php-deps, semgrep, context7, опц. leantime). **Не** цель: сайт Copytrust, mysql MCP к app-БД, jira-task, gototask.

### Когда

- Флешка / zip с Target после export (`-Profile Core` предпочтительно).
- Новый Win, пустой Docker Desktop.
- В корне уже есть (или будет) **код другого проекта** для индексации CBM/SG - или пустой каркас; app compose Copytrust не нужен.

### Что ставить один раз на машину (не дублировать на каждый проект)

| Компонент | Сколько экземпляров | Куда |
|-----------|---------------------|------|
| Docker Desktop, Node, uv/uvx, Chrome, Cursor | 1 на машину | Host |
| codebase-memory-mcp **exe** | 1 на машину | `%LOCALAPPDATA%\Programs\codebase-memory-mcp\` |
| Sourcegraph стек `:7080` | **1 на машину** (шарить) | разворачивается вручную, миграция его не копирует |
| AI-kit `.cursor`/`.codex`/`.doc` | **1 на проект** | корень этого репо |
| CBM `index_repository` | 1 на корень проекта | MCP вызов |
| SG register репо | 1 на имя репо | `repos.conf` + sync/register |

Не поднимать второй SG и не ставить второй CBM-бинарь “на каждый проект”.

### Чеклист агента (C) - по порядку

| # | Шаг | Пропуск / внимание |
|---|-----|-------------------|
| 0 | [Host install](#day0-host-install): чего нет - поставить (winget / ссылки в таблице) | без Node/uv/CBM exe MCP не зелёные |
| 1 | Open Folder = корень Target с kit; `.doc\rebase_project_gi.ps1` если есть `.git` | не родитель `<org>/` |
| 2 | Search-replace имён под проект (`testdeploydocker`, `repo:^…`) | [Search-replace](#search-replace-copytrust--новый-проект) |
| 3 | Win Cursor: убедиться что phpstan/php-deps на `node-mcp.cmd` (export патчит) | иначе Error |
| 4 | Sourcegraph: если `:7080` уже up на машине - **не** второй стек; иначе [§5](#5-sourcegraph-7080-с-нуля) | **новый** Access token → mcp.json headers |
| 5 | `repos.conf` + sync + register **этого** корня | SG сам репо не добавит |
| 6 | CBM: exe есть → Reload MCP → `index_repository` на абсолютный путь корня | [mcp.index.md](./mcp.index.md) |
| 7 | Reload Window; зелёные: serena, git, sourcegraph, codebase-memory-mcp, playwright, context7, semgrep, phpstan, php-deps, xdebug, leantime (после `compose up`) | mysql/jira могут быть Error/disabled - для C это OK |
| 8 | Опц. Leantime: `cd .doc/skil_data/leantime/docker && docker compose up -d` | volumes БД пустые; UI/API key см. [Leantime](#leantime-локальный-pm--mcp) |
| 9 | **DoD C** ниже | - |

**Явно не делать в сценарии C:** sibling `.config`, copytrust-dev/test, selenium, Jira `config.env`, gototask smoke, копирование `tasks/{N}` / architecture-контента Copytrust.

### Definition of Done C (только среда)

| # | Проверка | OK |
|---|----------|-----|
| 1 | Host: `docker version`, `node -v`, `uvx --version`, CBM `--version` | команды есть |
| 2 | Cursor MCP: serena, git, **sourcegraph**, **codebase-memory-mcp**, playwright, phpstan, php-deps | не Error |
| 3 | `sg_list_repos` / keyword search | видно **это** репо |
| 4 | CBM `index_status` / `search_graph` | индекс этого корня |
| 5 | mysql / jira-task | могут быть disabled или Error - не блокер C |
| 6 | Нет `.doc/tasks/{N}` из Copytrust; architecture stub свой | нет чужого реестра задач |

---

## Самодостаточность и промпт агенту

### Что этот файл закрывает

- Export kit (Full/Core) и запреты копирования.
- Host install если инструментов нет.
- Подъём SG + CBM + прочих MCP.
- Один SG / один CBM-бинарь на машину vs kit на проект.
- Сценарий C без app.

### Что нельзя “положить внутрь md” (агент делает по ссылкам)

| Вне документа | Действие агента |
|---------------|-----------------|
| Инсталляторы Docker/Node/uv/Cursor/CBM | скачать по ссылкам Day0; при отсутствии прав - попросить пользователя |
| Бинарь CBM | `install.ps1 --ui` из [codebase-memory-mcp.md](harnes/mcp/codebase-memory-mcp.md) |
| Живой SG token | Site Admin → создать; вписать в mcp.json (scrub при export стирает старый) |
| Данные MySQL Leantime (docker volume) | не в kit; после up - пустая БД или перенос volume вручную |
| Код целевого приложения | clone/флешка отдельно; kit его не заменяет |

Связанные файлы (читать по месту, не дублировать сюда): `sourcegraph-local/README.md`, `sourcegraph-local/MCP.md`, `.cursor/codebase-memory-mcp.md`, `.cursor/sourcegraph-mcp.md`, `leantime/mcp.md`.

### Готовый промпт (скопировать агенту на новом компе)

```
Читай .doc/rebase_project.md целиком как канон.

Цель: сценарий C (AI-kit only) - Cursor MCP среда как на образце
(включая Sourcegraph и codebase-memory-mcp). Не поднимай Copytrust-app,
copytrust-dev, Jira/gototask, .config sibling.

1) Day0 Host install: чего нет - поставь или дай точные команды пользователю.
2) Open Folder уже = корень этого проекта с kit.
3) Не дублируй Sourcegraph и CBM-бинарь если уже есть на машине.
4) Подними/подключи SG :7080, новый token в mcp.json, repos.conf + sync/register.
5) CBM index_repository на абсолютный путь этого корня.
6) Search-replace имён Copytrust под этот проект.
7) Дойди до Definition of Done C. Не копируй tasks/{N} и architecture-контент Copytrust.
```

Для полного стенда Copytrust замени “сценарий C” на Day0→green A/B и DoD полной таблицы (с php-apache/mysql/jira).

---

## Новый комп: мастер-план Day0 → green

Один порядок, чтобы на **чистой** Windows + WSL2 машине всё развернулось и MCP/skills заработали. Детали ниже по ссылкам; здесь только последовательность.

### Что нужно ДО скрипта (иначе «только md + ps1» не хватит)

| Нужно | Зачем |
|-------|--------|
| **Источник AI-kit** | Полное дерево образца с `.cursor`/`.codex`/`.doc` (USB/zip/сеть) **или** готовый Target после export на старом ПК. Один файл `rebase_project.ps1` **без** kit-дерева ничего не скопирует. |
| **Код приложения** | Для A/B: `git clone` с `tools/docker-dev`. Для **C (AI-kit only)** - не обязателен Copytrust; нужен любой корень проекта под индекс. |
| **Host tools** | см. [§ Host install](#day0-host-install) ниже |
| **Cursor** (и опц. Codex) | Open Folder = корень с kit (+ app если A/B) |

**Три сценария:**

| | A. Тот же проект на новый ПК | B. Другой / новый проект (с app) | C. Только AI-kit среда |
|--|------------------------------|----------------------------------|-------------------------|
| 1 | `git clone` app | `git clone` app **или** код другого репо | kit на флешке; app Copytrust не нужен |
| 2 | export/копия Target | export `-Profile Core` или Full | то же, лучше **Core** |
| 3 | Sibling `<org>/.config/` | То же | **пропуск** |
| 4 | Day0→green полный | Day0→green полный | [чеклист C](#чеклист-агента-c---по-порядку) |

Нельзя (A/B): открыть пустой Target только с kit и ждать mysql/jira - без app compose контейнеров нет.  
Можно (C): kit + host tools + SG + CBM без php-apache.

### Day0 Host install

Установить на Windows (часть команд - в WSL, помечено).

| Инструмент | Зачем | Установка (ориентир) |
|------------|-------|----------------------|
| **Docker Desktop** | все контейнеры | [docker.com](https://www.docker.com/products/docker-desktop/); Settings → WSL2 backend; Start on login |
| **Git** | clone | [git-scm.com](https://git-scm.com/) или `winget install Git.Git` |
| **Node.js 20+** | npx MCP, test-mcp-servers, setup | [nodejs.org](https://nodejs.org/) или `winget install OpenJS.NodeJS.LTS` |
| **uv / uvx** | serena, semgrep, git MCP | [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| **codebase-memory-mcp** (UI) | CBM MCP | Win: см. [`harnes/mcp/codebase-memory-mcp.md`](harnes/mcp/codebase-memory-mcp.md) (`install.ps1 --ui` → `%LOCALAPPDATA%\Programs\codebase-memory-mcp\`). WSL: UI linux amd64 → `~/.local/bin` + **tmux** |
| **PowerShell** | gototask, task-diff, export | Win PS 5.1+ (встроен) или pwsh |
| **PHP 8.3+ Composer** | agent Codeception / browser-verify на хосте | Laragon / [windows.php.net](https://windows.php.net/) + Composer; **или** только через docker PHP |
| **Chrome** | Playwright MCP / e2e | обычный Chrome или Chrome for Testing - [browser-setup.md](./qa/browser-setup.md) |
| **Cursor** | IDE | cursor.com; для этого kit удобнее Open Folder **`C:\...`** (Win-лаунчеры). WSL Remote → bash+`.sh` |

Проверка host:

```powershell
docker version
node -v
npx -v
uvx --version
# CBM:
& "$env:LOCALAPPDATA\Programs\codebase-memory-mcp\codebase-memory-mcp.exe" --version
```

### Day0 → green (единый чеклист)

Делать **по порядку**. Для **сценария C** шаги 3–7, 12 и mysql/jira в DoD - **пропуск**; вместо этого [чеклист C](#чеклист-агента-c---по-порядку) и [DoD C](#definition-of-done-c-только-среда).

Шаблоны секретов можно создать заранее; MCP станет зелёным только после host tools + (для A/B) Docker app / (для всех) SG+CBM.

| # | Шаг | A/B | C |
|---|-----|-----|---|
| 0 | Host install | да | да |
| 1 | kit + (A/B: clone app); `rebase_project_gi.ps1` | да | kit; app Copytrust нет |
| 2 | Open Folder = корень; Reload | да | да |
| 3 | Sibling `.config/` | да | пропуск |
| 4 | copytrust-dev up | да | пропуск |
| 5 | `.cursor/mcp.env` + `.codex/mcp.env` MYSQL_* | да | пропуск (mysql не нужен) |
| 6 | Имя PHP в mcp.json jira-task + gototask | да | пропуск / disabled |
| 7 | `.doc/skil_data/jira/config.env` | Full | пропуск |
| 8 | Search-replace имён | да | да |
| 9 | Sourcegraph :7080 + token + repos.conf | да | да (шарить один SG) |
| 10 | CBM `index_repository` | да | да |
| 11 | Playwright paths | да | да |
| 11a | Опц. Leantime | опц. | опц. |
| 12 | Опц. e2e selenium / docker-test | опц. | пропуск |
| 13 | Codex trust | опц. | опц. |
| 14 | DoD | [полная](#definition-of-done-smoke---полный-стенд-ab) | [DoD C](#definition-of-done-c-только-среда) |

Если Target = `C:\...` и копировали **вручную** без скрипта: прогнать export ещё раз или вручную поставить `node-mcp.cmd` в mcp.json (П-12), иначе phpstan/php-deps Error.

### Definition of Done (smoke) - полный стенд A/B

| # | Проверка | OK если |
|---|----------|---------|
| 1 | `docker ps` | есть `{project}-dev-php-apache-1`, `{project}-dev-mysql-1` |
| 2 | `curl -sI http://127.0.0.1:8030/` (или свой порт) | HTTP 200/302 |
| 3 | Cursor → Settings → MCP | mysql, jira-task, sourcegraph, serena, git, phpstan, php-deps, CBM, xdebug, leantime - не Error |
| 4 | MySQL MCP `list_tables` | таблицы своей БД |
| 5 | `sg_list_repos` | видно **новое** имя репо |
| 6 | gototask / «обнови таск N» | `.doc/tasks/{N}/task.md` |
| 7 | CBM `index_status` / search_graph | проект проиндексирован |
| 8 | Опц. e2e | `curl -s http://127.0.0.1:4444/status` или chromedriver `:9515` |

Для среды без app см. [DoD C](#definition-of-done-c-только-среда).

```powershell
# опц. после Node:
node .cursor\scripts\test-mcp-servers.mjs
```

### Политики, которые раньше путали

| Тема | Как правильно |
|------|----------------|
| **AI-kit only vs app** | Сценарий C: не требовать php-apache/mysql/jira. A/B: полный DoD. |
| **Один SG / один CBM exe** | На машину один раз; в каждом проекте - token + repos.conf + index_repository. Не плодить второй стек SG. |
| **codeception vendor** | Full-скрипт **копирует** `.tools/codeception/vendor`. Ручной robocopy без vendor → потом `composer install` в `.tools/codeception`. Оба варианта ок. |
| **node_modules** | Корневой app webpack - **не** копировать. MCP: `.cursor\|codex/mcp-servers/php-toolchain/node_modules` + `tools/vendor` - **да** (скрипт Full). |
| **Sourcegraph с нуля** | Для green MCP на новом ПК рекомендуем из WSL: `./start-single.sh` (проще) **или** полный `./start.sh` + upstream (как на образце). Export **не** тащит `upstream/` - clone один раз если полный стек. Токен в Cursor - в mcp.json headers. |
| **Skills count** | Образец 22; Full-export удаляет login-as-user + serpanalise-report → **20**. |
| **`.config/prepend.php`** | Только A/B. Структура обязательна; шаблон - [§1 sibling](#1-sibling-config-обязательно-для-php-в-docker-dev). |
| **UID/GID в docker `.env`** | На Linux/WSL: `id -u` / `id -g`. На чистом Win+Docker Desktop часто хватает `1000`. |
| **Корень Open Folder** | Cursor Open Folder = git/kit root, **не** родитель `<org>/`. |
| **Leantime volumes** | Env на флешке есть; данные MySQL в named volumes - нет. После up на новом ПК БД пустая, пока не install / не перенесён volume. |
---

## Локальный git exclude разработчика (вне remote)

Это главный ответ на вопрос "почему clone пустой по AI-kit". На машине-образце работают **два** локальных механизма (оба **не** уезжают в Bitbucket):

| Механизм | Файл / команда | Коммитится? | Эффект |
|----------|----------------|-------------|--------|
| **exclude** | `.git/info/exclude` | **нет** (только на этой копии) | untracked пути не видны `git status` / не попадут в add |
| **skip-worktree** | `git update-index --skip-worktree` | флаг локальный | tracked файл есть в remote, но **локальные правки** git игнорирует |
| sibling configs | `../.config/` рядом с репо | вне репо | PHP Docker mount |

После `git clone` на новой машине: **нет** exclude, **нет** skip-worktree, **нет** kit на диске. Нужно: (1) скопировать деревья с диска, (2) **заново** прописать exclude, (3) при необходимости выставить skip-worktree.

### Полный `.git/info/exclude` образца (канон для копии)

```
# Local developer excludes (not committed; this file stays in .git/info/exclude)
/.cursor/
/.codex/
/.agents/
/.kilo/
/.qoder/
/.qwen/
/.antigravity/
/.gemini/
/.dsh/
/DSH-RULES.md
/.doc/
/.serena/
/.playwright-mcp/
/AGENTS.md
/php_error.log
.kilocode/
kilo.json

# docker-dev local overrides (task 1510)
/tools/docker-dev/README.md
/tools/docker-dev/compose.yaml
/tools/docker-dev/php-apache/Dockerfile
/tools/docker-dev/php-apache/apache/

# Sourcegraph local stack (developer machine)
/sourcegraph-local/

# Graphify code graph (generated locally)
/graphify-out/

# Local Codeception admin credentials (developer machine)
/tools/codeception/tests/Acceptance/FirstCest.php

# Kilo Code agent worktrees
.kilo/worktrees/

# Kilo Agent Manager state
.kilo/agent-manager.json

# Kilo Code worktree setup script (варианты)
.kilo/setup-script
.kilo/setup-script.sh
.kilo/setup-script.ps1
.kilo/setup-script.cmd
.kilo/setup-script.bat

# Kilo Code legacy state (.kilocode)
.kilocode/worktrees/
.kilocode/agent-manager.json
.kilocode/setup-script
.kilocode/setup-script.sh
.kilocode/setup-script.ps1
.kilocode/setup-script.cmd
.kilocode/setup-script.bat

# Local Codeception suite edits (working copy is .tools/codeception)
/tools/codeception/tests/

# Codebase-memory ignore file
/.cbmignore
.cbmignore
```

### Ценность: что переносить, что нет

Размеры на образце (ориентир; `node_modules`/`vendor`/`venv` не тащить):

| Путь exclude | ~размер | Ценность | Перенос |
|--------------|---------|----------|---------|
| `.cursor/` | ~60M+ | **критично** - MCP, rules, skills, setup | да, без живого `mcp.env`; **с** `mcp-servers/php-toolchain/node_modules` и `tools/vendor` (runtime MCP) |
| `.codex/` | ~60M+ | **критично** - зеркало Codex | да, аналогично |
| `.doc/` | до ~1.4G сырой | **критично** стандарт + инфра; tasks/architecture контент - нет | выборочно (см. карту `.doc/`); без `.venv` / `imd` / `tasks/{N}`; **с** `codeception/vendor` для тестов |
| `.serena/project.yml` | мал | **важно** - языки LSP | да; без `cache/` (~27M), `memories/`, `project.local.yml` |
| `AGENTS.md` | 1K | **важно** - вход Cursor | да (`AGENTS.md` - файл-инструкция; не путать с каталогом-зеркалом `.agents/`) |
| `sourcegraph-local/` | ~378M сырой | legacy-стек SG | **не переносится** с 2026-11-05; разворачивается вручную, если нужен |
| корневой `/node_modules` | ~277M | webpack/Vue **приложения** | **не** для MCP, **не** копировать экспортом |
| `.kilo/` / `.kilocode/` / `kilo.json` | ~120M с nm | опционально | только если нужен Kilo; без `node_modules` |
| `.agents/` | мал | **рабочее зеркало** канона (22 skills, rules, scripts, mcp.json) | опционально; регенерируется из `.cursor/` через `.agents/skills/harness-router/children/environment-sync/scripts/` - см. [Синхронизация](#синхронизация-cursor--codex--адаптеры) |
| `.playwright-mcp/` | ~4M | кеш скринов MCP | **не** копировать |
| `php_error.log` | - | мусор | не копировать |
| `.tools/docker-dev`, `.tools/docker-test`, `.tools/php74`, `.tools/php85-scan` | ~115M | локальные docker, тесты и PHP-сканеры | целиком не копируются: `.env`, `dump.sql`, `vendor`, `_output`, `__pycache__` исключены; нужные конфиги создаются на Target |
| `.tools/codeception/.../FirstCest.php` | мал | логин админа в тесте (есть пароль!) | локальные креды; **не** коммитить; на новом проекте - свой логин + skip-worktree |

### skip-worktree на образце (факт)

Сейчас **один** файл (проверка: `git ls-files -v | findstr /B "S "`):

```
S tools/docker-dev/compose.yaml
```

`compose.yaml` локально монтирует sibling `.config` - ценная правка стенда. Раньше skip-worktree стоял и на `FirstCest.php`, `README.md`, `Dockerfile` (php-apache) - эти флаги сняты; в exclude пути остались как защита от случайного `git add`.

На новом проекте после адаптации файлов:

```powershell
git update-index --skip-worktree tools/docker-dev/compose.yaml
# при локальных кредах в тесте:
git update-index --skip-worktree tools/codeception/tests/Acceptance/FirstCest.php
# проверка:
git ls-files -v | findstr /B "S "
```

### Sibling вне репо (тоже "локальное", не в exclude)

```
<org>/
  .config/          # prepend.php, .env, .secrets.env  ← mount Docker
  start.bat
  *.txt             # быстрый старт / введение (human docs)
  <project>/        # git root
```

Без `.config` PHP-контейнер не поднимется как на этом стенде. Перенести структуру (секреты заполнить заново).

### После копирования kit - сразу заблокировать снова

**Скрипт (предпочтительно):** из корня Target:

```powershell
cd C:\path\to\project
powershell -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project_gi.ps1
# перезаписать exclude: -Force
# без skip-worktree: -NoSkipWorktree
```

Канон скрипта: [rebase_project_gi.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project_gi.ps1) - пишет `.git/info/exclude` и (по умолчанию) `skip-worktree` на compose/FirstCest, если файлы tracked.

Вручную:

1. Вставить в `$Target/.git/info/exclude` блок exclude выше (пути те же; docker-dev/FirstCest строки оставить даже если файлы tracked - защита от случайного `git add` после untrack).
2. Выставить skip-worktree на файлы с локальными оверрайдами (на образце сейчас только `tools/docker-dev/compose.yaml`; плюс `FirstCest.php` если там появятся локальные креды).
3. Проверка:

```powershell
Set-Location $Target
git check-ignore -v .cursor/mcp.json .doc/harnes/doc_rules.md AGENTS.md
# ожидаются строки из .git/info/exclude
git status --short | Select-String -Pattern '^\?\? \.cursor|^\?\? \.doc|^\?\? AGENTS'
# пусто = exclude работает
```

Внутри kit дополнительно свои `.gitignore` (например `.cursor/.gitignore` игнорит `mcp.env`, `node_modules`, `tools/vendor`) - они едут вместе с папками и тоже нужны.

---

## Критично: kit не в git (кратко)

`git clone` с Bitbucket **не** принесёт AI-kit. Перенос = **filesystem copy** + recreate `.git/info/exclude` + skip-worktree. Подробности - секция выше.

| В git (origin) | Только локально (exclude / skip-worktree / sibling) |
|----------------|------------------------------------------------------|
| Код приложения; `.tools/docker-test`; часть `.tools/docker-dev` / codeception как tracked | `.cursor/`, `.codex/`, `.doc/`, `.serena/`, `AGENTS.md`, опц. Kilo |
| | Локальные оверрайды compose / FirstCest через skip-worktree |
| | Sibling `<org>/.config/` |
---

## Раскладка каталогов на машине

```
<org>/                          # например copytrust/
├── .config/                    # ВНЕ репо, mount в PHP-контейнер
│   ├── prepend.php
│   ├── .env
│   └── .secrets.env
├── start.bat                   # опционально, human bootstrap
└── <project>/                  # корень репо
    ├── AGENTS.md
    ├── .cursor/                # mcp.json (вкл. leantime), rules (16), skills (23), scripts/, setup.ps1, …
    ├── .codex/                 # config.toml, AGENTS.md, skills, go-task.ps1, task-diff.ps1, …
    ├── .agents/                # генерируемое зеркало канона (skills, rules, scripts, mcp.json)
    ├── .antigravity/, .gemini/ # генерируемые зеркала канона .cursor/
    ├── .kilo/                  # генерируемое зеркало Kilo (skills, rules, kilo.jsonc); node_modules не копировать
    ├── .serena/project.yml
    ├── .doc/
    │   ├── harnes/doc_rules.md, harnes/readmy_doc.md, harnes/tests.md, rebase_project.md (+ .ps1, _gi.ps1)
    │   ├── docscripts/         # map-project, build-tasks-index, …
    │   ├── .jira/              # server.php (+ config.env локально)
    │   ├── .content-extractor/, .xml-river/
    │   ├── .mcpyandexscreen/yadisk-fetch.ps1 + imd/
    │   ├── web/                # панель документации :8077 (PHP, без БД); export целиком
    │   ├── task-analytics/     # анализ диалогов Kilo (Python); export без out/
    │   ├── leantime/           # PM Docker :8095 + MCP; export **с** .env / mcp.env / access
    │   ├── kaiten/doc.md       # research API (не runtime)
    │   ├── qa/                 # index, fragments, browser-setup, flows/
    │   ├── codeception/        # agent suite (Full-export: с vendor)
    │   ├── architecture/       # каркас index + _map (контент с нуля; .obsidian не копировать)
    │   └── tasks/              # пусто + _map/; index.md НЕ копировать - генерировать
    ├── sourcegraph-local/      # или один инстанс на машину
    ├── tools/
    │   ├── docker-dev/         # 8030 / 8031
    │   ├── docker-test/        # 8230 / 8231 + soap
    │   └── codeception/        # продуктовый suite (git)
    ├── .htaccess
    └── .env / .env.testing
```

Compose в `tools/docker-dev` монтирует конфиги как `../../../.config` (= `<org>/.config`). Без sibling `.config` PHP-приложение в контейнере **не поднимется** как на этом стенде.

---

## Инвентарь AI-kit (актуально на 2026-09-26)

### Cursor rules (`.cursor/rules/`)

| Файл | Тип | Portable | Специфика Copytrust |
|------|-----|----------|---------------------|
| `text-style.mdc` | always | да | нет |
| `doc-rules.mdc` | always | да | ссылка на bitbucket-tasks |
| `bitbucket-tasks.mdc` | always | частично | Jira `CT-{N}`, SG filter, `release/5.6.0.6` (имя файла legacy; содержимое - Jira + git) |
| `project-doc.mdc` | agent-requestable | да | SG `testdeploydocker` |
| `project-doc-indexing.mdc` | agent-requestable | да | нет |
| `task-doc.mdc` | agent-requestable | частично | SG filter |
| `prepare-plan.mdc` | agent-requestable | частично | `CT-N`, export-task |
| `yadisk-screenshot.mdc` | agent-requestable | да | нет |
| `doc-verify.mdc` | agent-requestable | частично | SG filter |
| `harness-improvement.mdc` | agent-requestable | да | порядок безопасной правки харнеса перед изменением skill/rule/MCP |
| `test-task.mdc` | agent-requestable | частично | оркестратор тестирования, chromedriver policy, стенд Copytrust |

### Codex rules (`.codex/rules/`) - полное зеркало

Паритет полный: **11 пар** `.mdc` ↔ `.md` (состав 1:1 с таблицой Cursor выше). Неполных пар 0.

| Файл | Зеркало Cursor |
|------|----------------|
| `text-style.md` | `text-style.mdc` |
| `doc-rules.md` | `doc-rules.mdc` |
| `bitbucket-tasks.md` | `bitbucket-tasks.mdc` |
| `project-doc.md` | `project-doc.mdc` |
| `project-doc-indexing.md` | `project-doc-indexing.mdc` |
| `task-doc.md` | `task-doc.mdc` |
| `prepare-plan.md` | `prepare-plan.mdc` |
| `yadisk-screenshot.md` | `yadisk-screenshot.mdc` |
| `doc-verify.md` | `doc-verify.mdc` |
| `harness-improvement.md` | `harness-improvement.mdc` |
| `test-task.md` | `test-task.mdc` |

При правках rules синхронизировать все пары `.mdc` ↔ `.md`; зеркала остальных сред генерируются через [`.agents/skills/harness-router/children/environment-sync/scripts/`](#синхронизация-cursor--codex--адаптеры).

### Skills (зеркало `.cursor/skills/` ↔ `.codex/skills/`) - 23 = 23

Состав пополнился с 2026-07-17: добавлены **git-task-blame**, **harness-improvement**, **jira-report**, **send-to-git**, **task-change-report**, **test-task** (назначения и зависимости - [state/02-skills.md](harnes/state/02-skills.md)). Документационные: **project-doc**, **doc-verify**, **task-doc**, **prepare-plan**. Актуальные нюансы:

| Skill | Что важно при переносе (2026-07) |
|-------|----------------------------------|
| **project-doc** | Cursor SKILL полный; batch через `docscripts/` + file-registry; CBM/SG при SECTION |
| **doc-verify** | Cursor SKILL → канон **Codex** `skills/documentation-router/children/doc-verify/SKILL.md` + `reference.md` (must copy Codex tree) |
| **task-doc** | FULL; после правок - `build-tasks-index.ps1`; rule только в Cursor (`task-doc.mdc`) |
| **prepare-plan** | Codex: обязательны `assets/` + `references/`; Cursor - часто только SKILL.md |

| Skill | Триггеры | Профиль | Зависимости |
|-------|----------|---------|-------------|
| **project-doc** | задокументируй проект/раздел | CORE+FULL | `docscripts/`, architecture; SG filter |
| **doc-verify** | сверка документации | CORE+FULL | CBM + SG + serena; Codex `reference.md` |
| **prepare-plan** | подготовь план | CORE+FULL | `CT-N` / export; Codex: `assets/` + `references/` |
| **task-doc** | задокументируй задачу | FULL | `.doc/tasks/{N}/`, `docscripts/build-tasks-index.ps1` |
| **gototask** | перейди к задаче N | FULL | `.doc/skil_data/jira/`, `config.json`, `scripts/*.ps1` |
| **task-diff** | обнови диф | FULL | `skills/task-router/children/task-diff/scripts/task-diff.ps1` (+ Codex wrapper) |
| **task-code-review** | review task diff | FULL | `agents/openai.yaml` внутри skill |
| **prepare-task-test** | подготовь тест задачи | FULL | `.doc/qa/` + `.tools/codeception/` + **`.doc/harnes/tests.md`** |
| **browser-verify** | проверь через браузер | FULL+e2e | то же + `qa/browser-setup.md` + Chrome |
| **login-as-user** | войди как клиент | Copytrust-only | `qa/fragments.md` + docker-test (не переносить без переписывания) |
| **page-content** | контент URL | CORE+FULL | `.agents/skills/page-content/` + `scripts/extract-page-content.ps1` |
| **xmlriver** | SERP / Wordstat | CORE+FULL | `.doc/skil_data/xmlriver/` + `invoke-xmlriver.ps1` |
| **serp-study** | разбор выдачи | CORE+FULL | xmlriver + page-content + `study-serp.ps1` |
| **yadisk-screenshot** | скрин Я.Диска | CORE+FULL | **`.agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1`** + пустой `imd/` |
| **serpanalise-report** | отчёт репутации | опционально | `.doc/serpanalise/` + scripts skill |
| **git-task-blame** | кто менял эти строки | FULL | `git log -L`, проверка веток origin, риск конфликта |
| **harness-improvement** | улучшение харнеса | CORE+FULL | `scripts/component_registry.json` + parity-проверки |
| **jira-report** | комментарий в Jira | FULL | `scripts/collect-shots.py`, стиль Sergey0002 |
| **send-to-git** | согласование commit/push | FULL | выполнение только после явного "да" |
| **task-change-report** | HTML-отчёт задачи | CORE+FULL | `scripts/generate_report.py` + report-model.json |
| **test-task** | тестируй задачу | FULL | оркестратор: resolve → impact → Cest → browser-verify → отчёт §8 |

Скрипты skills копируются вместе с папкой skill (robocopy `skills/`). **Codex wrappers:** `.codex/go-task.ps1`, `.codex/task-diff.ps1`.

**Асимметрия деревьев (не баг переноса, учитывать):**

| Путь | Cursor | Codex |
|------|--------|-------|
| `skills/prepare-plan/assets/`, `references/` | нет (только SKILL.md) | есть (обязательны для Codex) |
| `skills/documentation-router/children/doc-verify/reference.md` | нет; Cursor SKILL ссылается на Codex | есть |
| `rules/task-doc.*` | `task-doc.mdc` | `task-doc.md` - пара есть и синхронизирована (П-8 решён) |

### Корневые инструкции

| Файл | Среда |
|------|-------|
| `AGENTS.md` | Cursor |
| `.codex/AGENTS.md` | Codex (канон + anti-loop) |
| `.codex/config.toml` | Codex MCP runtime |
| `.codex/CODEX-CONFIG-NOTES.md` | global vs project config |
| `.codex/global-trust.snippet.toml` | фрагмент для `%USERPROFILE%\.codex\config.toml` |
| `.codex/codex-sale/` | опциональный прокси desktop Codex (Windows) |

### MCP-серверы

| Сервер | Portable | Правки под проект |
|--------|----------|-------------------|
| `serena` | да | `.serena/project.yml` |
| `git` | да | workspace |
| `context7` | да | - |
| `semgrep` | да | - |
| `mysql` | да | `mcp.env` → `MYSQL_*` (порт стенда!); запуск через `scripts/run-with-mcp-env.sh` + `mysql-mcp-proxy.mjs`: релея `listen 127.0.0.1:3306` → target `MYSQL_PORT` (образец 8031) |
| `phpstan-mcp` / `php-deps-mcp` | PHP | `PHP_BIN`, `DOCKER_PHP_CONTAINER`, `setup.ps1` → composer в `.cursor/tools` / `.codex/tools` |
| `codebase-memory-mcp` | да | бинарь вне git; `index_repository` на новый корень |
| `sourcegraph` | да | токен; filter `repo:^…/{имя}$` в rules/skills |
| `playwright` | да | `PLAYWRIGHT_MCP_EXECUTABLE_PATH`, `CHROME_PATH`, `LD_LIBRARY_PATH` |
| `jira-task` | FULL | docker container + путь `/var/www/html/.agents/skills/task-router/children/jira/scripts/server.php` |
| `bitbucket-task` | legacy | `disabled: true` |
| `leantime` | опц. CORE+FULL | `bash` + `.agents/skills/task-management/children/leantime/scripts/launch.sh`; secrets в `.doc/skil_data/leantime/mcp/mcp.env` (не kit `mcp.env`); контейнер `:8095` |
| `xdebug` | опционально | свой Xdebug |
| `deepwiki` | обычно off | - |

### Скрипты kit (факт на диске)

| Cursor `.cursor/scripts/` | Codex `.codex/scripts/` |
|---------------------------|-------------------------|
| `codebase-memory-mcp-launch.sh` (+ `.cmd`) | то же |
| `codebase-memory-mcp-ui.sh` | то же |
| `node-mcp.sh` (+ `.cmd`) | то же |
| `run-with-mcp-env.sh` + `mysql-mcp-proxy.mjs` | то же |
| `php-docker.cmd`, `.js`, `.ps1`, `.sh` | `php-docker.cmd`, `.js`, `.ps1`, `.sh` |
| `test-mcp-servers.mjs` | `test-mcp-servers.mjs` |

Проверка MCP после переноса - общий `node .cursor\scripts\test-mcp-servers.mjs` (работает для обоих kit; отдельного Codex-verify скрипта нет).

Корень kit: оба `setup.ps1`; Codex ещё `go-task.ps1`, `task-diff.ps1`, `lib/kit-root.ps1`.

Также (входят в robocopy kit): `mcp-servers/php-toolchain/` (после copy: `npm install` если без `node_modules`), `tools/` (внутри `composer.json`, `phpda.yml.example`; vendor через `setup.ps1`), `composer-php-tools.json`, README*, `recommendations.md`, `sourcegraph-mcp.md`, `codebase-memory-mcp.md`. Опционально не критично: `push-test.sh`, `run-push-test.sh`.

### Документация `.doc/` - что копировать

| Копировать | Не копировать |
|------------|---------------|
| `harnes/doc_rules.md`, `harnes/readmy_doc.md`, `rebase_project.md` (+ `.ps1`, `_gi.ps1`), **`harnes/tests.md`** | `architecture/*.md` контент старого кода (кроме каркаса ниже) |
| `docscripts/` (все `.ps1` / `_lib.ps1`; см. список ниже) | содержимое `tasks/{N}/`, `tasks/index.md` со старыми задачами |
| `.content-extractor/` (без `.venv`, `out_*.json`) | `serpanalise/`, `.seoq/`, `Stagehand/`, `releases/`, `tmp/`, `backups/` |
| `.xml-river/` (без `.env`, `cache/`, `logs/`, `output/`) | корневые `5.7.*.md`, аудиты, SQL-дампы, `developer_guide.md`, … |
| `.mcpyandexscreen/` = **`yadisk-fetch.ps1` + README** + пустой `imd/` | содержимое `imd/` (кеш скринов) |
| `.jira/` без `config.env` (FULL) | `.bitbucket/` если трекер не Bitbucket |
| **`leantime/`** целиком: compose + **`docker/.env`** + **`mcp/mcp.env`** + access + bearer | - (секреты Leantime **нужны** для переноса стенда) |
| **`kaiten/doc.md`** (опц. research) | - |
| `qa/` (index, fragments, browser-setup, `flows/`) | - |
| **`codeception/`** (FULL+e2e) | Full-скрипт с vendor; иначе `composer install` | - |
| **`web/`** целиком: панель документации (PHP, без БД) | - |
| **`task-analytics/`**: код анализа диалогов (Python) | `out/` (данные проекта считаются заново), `__pycache__` |

Каркас создать пустым: `architecture/_map/`, `tasks/`, `tasks/_map/`, `qa/reports/`.

### DSH kit `.dsh/` - что копировать

DSH kit в git не хранится, как и остальные среды. Переносится копированием через
`.agents/skills/harness-router/children/new-project/scripts/copy-dsh-kit.ps1`, который вызывает `rebase_project.ps1`.

| Копировать | Не копировать, создать заново |
|------------|-------------------------------|
| `.dsh/skills/` (`dsh-router`) | `.dsh/project.patch.yml` |
| `.dsh/adapters/` | `DSH-RULES.md` |
| `.dsh/scripts/` (`run-ps1.sh`, `smoke.sh`) | `__pycache__`, `.pytest_cache` |
| `.dsh/tests/` | `models.overlay.json.bak-*` |
| `.dsh/models.overlay.json` | - |

Сгенерированные `project.patch.yml` и `DSH-RULES.md` создаёт
`sync-agent-views.sh` на Target из `.cursor/rules` и `.cursor/mcp.json`.
Проверка полноты kit после копирования:

```bash
pwsh -NoProfile -File .agents/skills/harness-router/children/new-project/scripts/copy-dsh-kit.ps1 -Source <source> -Target <target> -Check
```

`prepare-task-test` / `browser-verify` без `.tools/codeception/` **и** без `.doc/harnes/tests.md` **не работают**. `tools/codeception` - отдельный продуктовый suite (в git).

**`docscripts/` (полный список, все нужны):** `_lib.ps1`, `map-project.ps1`, `get-indexing-batch.ps1`, `mark-noise.ps1`, `validate-docs.ps1`, `sync-docs.ps1`, `audit-docs.ps1`, `generate-doc-index.ps1`, `generate-file-registry.ps1`, `get-verify-batch.ps1`, `mark-verify-done.ps1`, `find-related-tasks.ps1`, `build-tasks-index.ps1`, плюс вспомогательные `_batch-ai-links.py`, `_fix_indexed_files_order.py`, `_restore_cicd_from_transcript.py`.

---

## Полная карта `.doc/` (факт на диске)

Сверено с фактическим `ls .doc/`: каждый top-level элемент учтён. Skills: **23** в Cursor и Codex (зеркала остальных сред генерируются). Ключевое в `.doc/`: **`leantime/`** (локальный PM + MCP), **`kaiten/`** (research API), **`harnes/readmy.md`** (legacy реестр), **`synh_harnes/`** (генерация зеркал адаптеров), **`harnes/testaudit.md`** (канон тест-аудита), **`harnes/jsondoc.md`** (спецификация движка), **`harnes/tests.md`** (канон QA), **`harnes/readmy_doc.md`** (гайд документирования), **`harnes/readmy.md`** (legacy реестр).

### Каталоги

| Путь | Действие при переносе | Зачем / кто использует |
|------|----------------------|------------------------|
| `docscripts/` | **копировать** | project-doc, doc-verify, task-doc, map/validate |
| `.jira/` | **копировать** (без `config.env`) | gototask, MCP jira-task |
| `.bitbucket/` | только если legacy BB | MCP bitbucket-task (обычно skip) |
| `.content-extractor/` | **копировать** (без `.venv`, cache) | page-content, serp-study |
| `.xml-river/` | **копировать** (без `.env`, cache/logs/output, `.venv-linux`, `.venv-win`) | xmlriver, serp-study; venv создаётся на Target: `uv venv .venv-linux` и `uv pip install -e .` |
| `.mcpyandexscreen/` | **копировать** `yadisk-fetch.ps1` + README; `imd/` пустой | yadisk-screenshot |
| **`web/`** | **копировать целиком** (код панели, без исключений) | панель документации: задачи + architecture из JSON, порт 8077; см. [`web/README.md`](./web/README.md) |
| **`leantime/`** | **копировать целиком** (compose, `.env`, `mcp.env`, access, bearer, docs) | локальный PM + MCP `leantime`; см. [Leantime](#leantime-локальный-pm--mcp) |
| **`kaiten/`** | **копировать** `doc.md` (research) | справка по Kaiten API; не runtime |
| **`environment-sync`** | **копировать вместе со скилами** | генерация зеркал адаптеров из канона `.cursor/`: `sync-agent-views.sh`, `generate-agent-configs.py`, `generate-mcp-config.py`, `parity-report.json`; см. [Синхронизация](#синхронизация-cursor--codex--адаптеры) |
| `qa/` | **копировать** | browser-verify, prepare-task-test, login-as-user |
| `codeception/` | **копировать** (Full-скрипт + vendor; ручной путь без vendor → composer) | browser-verify, prepare-task-test |
| `architecture/` | **не** копировать контент `*.md` | создать каркас: `index.md`, `_priority.md`, `_map/`; `_context-base.md` создаёт project-doc bootstrap |
| `architecture/.obsidian/` | **не** копировать | Obsidian vault старого проекта; при необходимости создать заново |
| `tasks/` | **не** копировать `{N}/` | пустая папка + `_map/` |
| `tasks/{N}/` | **запрещено** копировать | чужие задачи Copytrust |
| `tasks/index.md` | **не** копировать | см. секцию ниже - только генерация |
| `tasks/_map/file-to-tasks.tsv` | **не** копировать | пишет `build-tasks-index.ps1 -AlsoTsv` |
| `serpanalise/` | опционально | skill serpanalise-report |
| `.seoq/` | **не** копировать | SEO-пайплайн Copytrust |
| `Stagehand/` | **не** копировать | локальные эксперименты |
| `releases/` | **не** копировать | релизные артефакты |
| `tmp/` | **не** копировать | временные JSON/MD |
| `backups/` | **не** копировать | локальные бэкапы |
| `jsondoc_scripts/` | **копировать скриптом** (без `runs/`, `work/`, `state/`) | pipeline jsondoc: `jsondoc.py`, `jsondoc/`, `schemas`, `tests` |
| `buisnes_analis/` | **копировать скриптом** (без `registry.json`, `quarantine.json`, `work/`, `registry.snapshots`, `reports/`) | business-analyst: скрипты, схемы, `config`, `tests` |
| `optimizeform/`, `preza/`, `testanalyze/`, `5.7.3test/` | **не** копировать | артефакты Copytrust |

### Корневые файлы `.doc/*.md` и прочее

| Файл | Действие |
|------|----------|
| `harnes/doc_rules.md`, `harnes/index.md`, `harnes/readmy_doc.md`, `rebase_project.md` (+ `.ps1`, `_gi.ps1`), `mcp.index.md`, **`harnes/tests.md`**, `harnes/testaudit.md`, `harnes/jsondoc.md`, `harnes/state/13-agent-migration.md`, `harnes/state/14-project-migration.md` | **копировать** (это `$docFiles` скрипта) |
| **`harnes/readmy.md`** (legacy реестр), **`harnes/testaudit.md`** (канон тест-аудита), **`harnes/jsondoc.md`** (спецификация движка), **`harnes/tests.md`** (канон QA), **`harnes/readmy_doc.md`** (гайд документирования), **`harnes/readmy.md`** (legacy реестр) | **копировать вручную** (в `$docFiles` скрипта их пока нет) |
| `doc_readme.md` | опционально (дубль/старый гайд; канон - `readmy_doc.md`) |
| `jsondoc.md` | опционально (в паре с `jsondoc_scripts/`) |
| `5.7.1.md` … `5.7.4.md`, `mail.md`, `speedform.md`, `optim.md`, `documentation_audit.md`, `developer_guide.md`, `qauth_new!.md`, `tz_cursor_setup_*.md`, `tmp-deploy-710c1ec.yml` | **не** копировать (артефакты Copytrust, архитектурные gitverce/deploytask не копируются как контент Copytrust) |
| `gb_copydev5.sql`, `Методика … .pdf` (+ их Zone.Identifier) | **не** копировать |

### `.doc/tasks/index.md` - отдельно и обязательно

Это **сгенерированный индекс**, не ручной документ.

- Пишет: [`.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1`](../.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1)
- Читают: skill **task-doc** (шаг B4.5), rule **task-doc.mdc**, skill **doc-verify** (V6 + `find-related-tasks.ps1`)
- С `-AlsoTsv` ещё: `.doc/tasks/_map/file-to-tasks.tsv`

На образце сейчас 176 числовых папок `.doc/tasks/{N}` (задачи Copytrust). **Копировать `index.md` и `file-to-tasks.tsv` нельзя** - утащите чужой реестр.

На целевом проекте:

1. Создать пустые `.doc/tasks/` и `.doc/tasks/_map/`.
2. Появятся первые `{N}/task.md` (gototask / вручную).
3. Запустить:

```powershell
powershell -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1 -AlsoTsv
```

4. Появятся свежие `tasks/index.md` + `_map/file-to-tasks.tsv` уже по **новым** задачам.

Пока задач нет - `index.md` может отсутствовать; это нормально. Не класть stub из Copytrust.

---

## Матрица skill / rule → обязательные пути

Сверка: если skill в профиле FULL/CORE есть, пути в колонке "Must copy" должны оказаться на целевом диске.

| Skill / rule | Must copy (пути от корня репо) | Создать пустым / после setup |
|--------------|--------------------------------|------------------------------|
| все always rules | `.cursor/rules/*.mdc` (12 файлов) | - |
| Codex rules | `.codex/rules/*.md` (12 пар, паритет полный) | - |
| Qoder view | `.qoder/rules/*.md`, `.qoder/skills/**`, `.qoder/settings.json` | пересобираются `sync-agent-views.sh` из `.cursor/rules`, `.agents/skills`, `.cursor/mcp.json` |
| Qwen view | `.qwen/rules/*.md`, `.qwen/skills/rule-*/`, `.qwen/settings.json` | пересобираются `sync-agent-views.sh`; `.agents/skills` и `AGENTS.md` читаются нативно |
| **project-doc** | `.doc/harnes/doc_rules.md`, `docscripts/*`, `AGENTS` | `architecture/index.md`, `_context-base.md`, `_priority.md`, `_map/` |
| **prepare-plan** | skill; Codex `assets/` + `references/`; `doc_rules`, architecture index | планы пишутся в `tasks/{N}/` |
| **task-doc** | skill; `docscripts/build-tasks-index.ps1`; Cursor `rules/task-doc.mdc` | `tasks/`, `tasks/_map/`; **`tasks/index.md` генерировать**, не копировать |
| **doc-verify** | `docscripts/get-verify-batch.ps1`, `mark-verify-done.ps1`, `find-related-tasks.ps1`, `build-tasks-index.ps1`; Codex `skills/documentation-router/children/doc-verify/reference.md` | `architecture/_map/verify-registry.tsv`; для V6 нужен актуальный `tasks/index.md` / `file-to-tasks.tsv` |
| **gototask** | `skills/task-router/children/gototask/{SKILL,config.json,scripts/*}`; `.agents/skills/task-router/children/jira/scripts/server.php` + `src/`; Codex `go-task.ps1` | `config.env` из example |
| **task-diff** | `skills/task-router/children/task-diff/scripts/task-diff.ps1`; Codex `task-diff.ps1` | - |
| **task-code-review** | skill + `agents/openai.yaml` | - |
| **prepare-task-test** | `.doc/qa/**`, **`.doc/harnes/tests.md`**, `.tools/codeception/**` | vendor из Full-export или `composer install` |
| **browser-verify** | то же + `qa/browser-setup.md`; `codeception/scripts/*` | app docker + **selenium-chrome-test :4444** или chromedriver `:9515` |
| **page-content** | `.agents/skills/page-content/**`; `scripts/extract-page-content.ps1` | Python venv / `.env` |
| **xmlriver** | `.doc/skil_data/xmlriver/**` (код); `invoke-xmlriver.ps1` | `.env` с API key |
| **serp-study** | xmlriver + page-content + `study-serp.ps1` | - |
| **yadisk-screenshot** | `.agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1`, README; rule `yadisk-screenshot.mdc` | пустой `imd/` |
| **serpanalise-report** | skill scripts + `.doc/serpanalise/` | только если нужен SEO-отчёт |
| **login-as-user** | обычно **не копировать** | Copytrust-only |
| MCP phpstan/php-deps | `.cursor|codex/mcp-servers/php-toolchain/`, `tools/`, `scripts/php-docker.*`, `setup.ps1` | `npm install` / composer via setup |
| MCP mysql/jira | `mcp.env.example`, `.jira/` | `mcp.env`, `config.env`, docker up |
| MCP **leantime** | `.doc/skil_data/leantime/**` вкл. `docker/.env` + `mcp/mcp.env`; mcp.json / config.toml | `docker compose up` в `leantime/docker`; `uvx` |
| text-style | `.cursor/rules/text-style.mdc` + `.codex/rules/text-style.md` | - |
| DeepSeek Harness | `.dsh/skills/`, `.dsh/adapters/`, `.dsh/scripts/`, `.dsh/tests/`, `.dsh/models.overlay.json` | `.dsh/project.patch.yml`, `DSH-RULES.md` через `sync-agent-views.sh` |

---

## Локальная среда разработки (Docker)

### Docker Desktop: какие контейнеры нужны

На машине-образце в Docker Desktop видны **много** compose-групп. Для MCP и skills **этого** проекта нужны только перечисленные ниже. Остальное (laravel-saas, foodninja, чужие `php:8.x-cli`) к Copytrust AI-kit **не относится** - на новый компьютер не переносить.

#### Нужны (Copytrust / AI-kit)

| Имя в Docker Desktop / контейнер | Где лежит определение | Порты (образец) | Для чего (MCP / skills) |
|----------------------------------|----------------------|-----------------|-------------------------|
| **`copytrust-dev`** → `copytrust-dev-php-apache-1`, `copytrust-dev-mysql-1` | [`tools/docker-dev/compose.yaml`](../tools/docker-dev/compose.yaml) | HTTP **8030**, MySQL **8031** | **Обязательно** для рабочего стенда: MCP `mysql`, `jira-task` (`docker exec … php …/.agents/skills/task-router/children/jira/scripts/server.php`), `php-docker.cmd` / phpstan через контейнер, gototask, повседневная разработка |
| **`copytrust-test`** → `*-php-apache-1`, `*-mysql-1` (+ soap) | [`tools/docker-test/compose.yaml`](../tools/docker-test/compose.yaml) | HTTP **8230**, MySQL **8231** | **Опционально** для e2e: browser-verify / prepare-task-test / login-as-user на отдельном стенде (часто Stopped, пока не гоняют тесты) |
| **`selenium-chrome-test`** | **не в compose репо** - отдельный `docker run` | **4444** (WebDriver), **7900** (noVNC UI) | Codeception `--env chromedriver` (см. [qa/browser-setup.md](./qa/browser-setup.md)). Альтернатива: локальный chromedriver `:9515` без этого контейнера |
| **Sourcegraph** (группа: `caddy`, `sourcegraph-frontend-*`, `pgsql`, `gitserver-0`, `src-serve-git`, …) | [`sourcegraph-local/`](../sourcegraph-local/) (`start-single.sh` / compose) | UI/MCP **7080** | MCP `sourcegraph` (`http://127.0.0.1:7080/.api/mcp/v1`) |
| **`leantime_app`** + **`leantime_db`** (опц.) | [`.doc/skil_data/leantime/docker/`](./leantime/docker/) | HTTP **8095** | MCP `leantime` (daniel-eder / `uvx`); UI admin; не замена Jira/`CT-N` |

#### Физически на диске (образец)

| Что | Путь на диске | Примечание |
|-----|---------------|------------|
| **copytrust-dev** | `tools/docker-dev/compose.yaml` (+ Dockerfile, mysql/) | код монтируется с корня репо; конфиги с `../../../.config` |
| **copytrust-test** | `tools/docker-test/compose.yaml` | отдельные порты 8230/8231 и своя БД |
| **selenium-chrome-test** | **файлов в репо нет** | только образ Hub `selenium/standalone-chrome:4.21.0`, создан `docker run --name selenium-chrome-test …`; mounts пустые - всё внутри контейнера |
| **Leantime** | `.doc/skil_data/leantime/docker/docker-compose.yml` | образ `leantime/leantime:latest` + `mysql:8.4`; volumes docker named; `restart: unless-stopped` |
| **SG скрипты kit** | `sourcegraph-local/*.yml`, `start-single.sh`, `config/` | вручную; export их не копирует с 2026-11-05 |
| **SG полный стек (факт сейчас)** | `sourcegraph-local/upstream/docker-compose/` + `docker-compose.override.yaml` | отсюда подняты `caddy` (:7080) и остальные SG-контейнеры |
| **SG данные** | `~/.sourcegraph/data`, `~/.sourcegraph/config` + docker volumes | **не** в git; на новом ПК создаются заново |

Контейнеры папкой не копируются: на новом ПК заново `docker compose up` / `docker run`.

#### Что такое "e2e на отдельном стенде"

**e2e** (end-to-end) - автотесты UI: Codeception / skill browser-verify открывают браузер и кликают по живому сайту.

| Стенд | Compose | Порты | Смысл |
|-------|---------|-------|-------|
| **dev** | `tools/docker-dev` → `copytrust-dev` | 8030 / 8031 | Разработка + MCP mysql/jira; ручная работа |
| **test** | `tools/docker-test` → `copytrust-test` | 8230 / 8231 | **Вторая** копия PHP+MySQL на этой же машине, чтобы прогон e2e не ломал данные **dev** |

"Отдельный стенд" ≠ другой компьютер. Это второй набор контейнеров того же проекта. Канон: [`tools/docker-test/README.md`](../tools/docker-test/README.md). Часто достаточно только **dev** + selenium/chromedriver; `copytrust-test` поднимают, когда нужен чистый контур под тесты.

Канон имён PHP-контейнера в mcp.json / gototask на образце: `copytrust-dev-php-apache-1`. На новом проекте - своё `COMPOSE_PROJECT_NAME` + правка mcp.json.

#### Не нужны (чужие проекты на той же машине)

| Группа на скрине | Зачем игнорировать |
|------------------|--------------------|
| `laravel-saas-kit-main` / `laravel-saas-kit-mimo` | другой продукт |
| `foodninja_*` | другой продукт |
| `docker-compose` / `test2` / случайные `php:8.4-cli` | не Copytrust kit |
| Docker Desktop **MCP Toolkit (BETA)** в сайдбаре | продукт Docker; **не** замена `.cursor/mcp.json` проекта |

#### Где что лежит (перенос на другой ПК)

```
<org>/                              # например copytrust/
├── .config/                        # sibling: prepend.php, .env, .secrets.env
└── <project>/                      # git root (testdeploydocker или новый)
    ├── tools/docker-dev/           # ← copytrust-dev (в git / clone приложения)
    ├── tools/docker-test/          # ← copytrust-test
    ├── sourcegraph-local/          # ← SG стек (экспорт AI-kit / отдельно на машину)
    ├── .cursor/mcp.json            # jira → имя php-контейнера; mysql → порт 8031
    └── .doc/qa/browser-setup.md    # selenium-chrome-test + chromedriver :9515
```

**Важно:** контейнеры сами по себе **не копируются** папкой. На новом ПК воссоздают по [Воссоздание контейнеров с нуля](#воссоздание-контейнеров-с-нуля) ниже.

---

## Leantime (локальный PM + MCP)

Опциональный контур: локальный [Leantime](https://leantime.io) + community MCP [daniel-eder/leantime-mcp](https://github.com/daniel-eder/leantime-mcp). **Не** замена Jira / `CT-{N}` / gototask. Задачи Leantime - числовые id; моста к `.doc/tasks/{N}/` нет.

Канон на образце: [leantime/mcp.md](./leantime/mcp.md), [leantime/access.md](./leantime/access.md), [leantime/api-local.md](./leantime/api-local.md).

### Что копирует export

**Полный стенд с доступами** (исключение из правила "не копировать секреты"):

| Копировать | Примечание |
|------------|------------|
| весь `.doc/skil_data/leantime/` | docs, `rpc.sh`, compose, `sample.env` |
| **`docker/.env`** | MySQL + LEAN_* + admin (как на образце) |
| **`mcp/mcp.env`** | `LEANTIME_URL` + Company API Key |
| **`access.md`** | login/пароль UI |
| **`browser-test/.bearer_token`** | если есть (Bearer smoke) |
| MCP launch + snippet | `mcp/launch.sh`, `cursor-mcp.snippet.json` |

Данные MySQL в docker volumes **не** в папке `.doc/` - на новом ПК после `compose up` либо пустая БД (нужен install/admin), либо перенос volume отдельно. Файлы env/API key/UI-логин едут с export.

Записи MCP уже в kit: `.cursor/mcp.json` → `leantime`, `.codex/config.toml` → `[mcp_servers.leantime]`, зеркало `.codex/mcp.json`.

### Подъём на новом ПК

```bash
cd .doc/skil_data/leantime/docker
docker compose up -d
# UI: http://localhost:8095 — логин/пароль в access.md (и LEAN_ADMIN_* в .env если заданы)
```

1. `uvx` на хосте (для MCP).
2. Reload MCP / новый thread Codex. Smoke: `list_projects` (ключ уже в `mcp/mcp.env`).

Автозапуск контейнеров: `restart: unless-stopped` (если Docker Desktop/Engine стартует после reboot). MCP стартует только с Cursor/Codex сессией.

Рядом research Kaiten (не runtime): [kaiten/doc.md](./kaiten/doc.md) - export копирует файл.

---

## Воссоздание контейнеров с нуля

Если на новой машине **нет** `copytrust-dev` / selenium / Sourcegraph - поднять заново по конфигам ниже. Образы Docker Hub скачает сам. Полные README: [docker-dev](../tools/docker-dev/README.md), [docker-test](../tools/docker-test/README.md), [sourcegraph-local](../sourcegraph-local/README.md), [browser-setup](./qa/browser-setup.md).

### 0. Требования на машине

| Что | Зачем |
|-----|--------|
| Docker Desktop (Win/Mac) или Docker Engine + Compose | все контейнеры |
| WSL2 backend (на Win) | удобно для SG scripts и php в Linux |
| Git clone **приложения** с `tools/docker-dev` (+ `docker-test`) | compose файлы в git, не в AI-kit export |
| AI-kit ([rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1)) | правила, скилы, `.cursor/mcp.json`; `sourcegraph-local/` вручную |
| **Свободные порты** | 8030, 8031 (dev); опц. 8230, 8231 (test); 4444, 7900 (selenium); 7080 (SG); опц. **8095** (Leantime) |

### 1. Sibling `.config` (обязательно для PHP в docker-dev)

Путь относительно compose: `../../../.config` из `tools/docker-dev` = `<org>/.config` рядом с репо.

```
<org>/
  .config/
    prepend.php      # обязателен для boot PHP в контейнере
    .env             # runtime приложения
    .secrets.env     # секреты приложения
  <project>/         # git root
    tools/docker-dev/
```

Секреты заполнить заново (не копировать прод вслепую). Без `.config` контейнер PHP не поднимется как на образце.

**Минимальный `prepend.php` (образец Copytrust - Smarty bootstrap; под другой app заменить или оставить пустой stub):**

```php
<?php
// Mount в контейнере: /var/www/.config/prepend.php (ro)
// Подключается до приложения. Секреты сюда НЕ класть.
$smartyBootstrap = '/var/www/html/vendor/smarty/smarty/libs/bootstrap.php';
if (file_exists($smartyBootstrap)) {
    require_once $smartyBootstrap;
}
$base = '/var/www/html/vendor/smarty/smarty/libs/sysplugins/';
if (file_exists($base . 'smartyexception.php')) {
    require_once $base . 'smartyexception.php';
}
if (file_exists($base . 'smartycompilerexception.php')) {
    require_once $base . 'smartycompilerexception.php';
}
```

Если Smarty/путей нет - достаточно файла-заглушки:

```php
<?php
// sibling .config/prepend.php - stub; допиши require под свой app
```

**`.env` / `.secrets.env`:** взять структуру со старого ПК или из README приложения; пароли/ключи - новые. Export kit **не** создаёт sibling `.config` автоматически (только опционально пустую папку рядом с Target - см. скрипт).

**Проверка mount из контейнера:**

```bash
docker compose -f tools/docker-dev/compose.yaml exec php-apache ls -la /var/www/.config
# ожидается prepend.php; если No such file - путь sibling неверный (см. типичные ошибки)
```

**Win + репо в WSL (`\\wsl$\...`):** compose лучше запускать **из WSL** (`cd /home/.../project/tools/docker-dev`), не через UNC с Windows PowerShell. Иначе mount `../../../.config` часто пустой или Permission denied.

### 2. `copytrust-dev` (обязателен для MCP mysql / jira / gototask)

**Файлы:**

| Файл | Роль |
|------|------|
| [`tools/docker-dev/compose.yaml`](../tools/docker-dev/compose.yaml) | сервисы: `mysql`, `php-apache`, `php7.1-cli`, `node-cli` |
| `tools/docker-dev/.env.dist` → **`.env`** | порты, БД, `COMPOSE_PROJECT_NAME` |
| `tools/docker-dev/php-apache/` | Dockerfile + apache |
| `tools/docker-dev/mysql/` | образ MySQL; опц. `dump.sql` |
| корень репо: `.env.example` → `.env`, `.htaccess.dist` → `.htaccess` | приложение |

**Канон `.env` (из `.env.dist` образца - поменять имя проекта/порты под себя):**

```env
COMPOSE_PROJECT_NAME=copytrust-dev

UID=1000
GID=1000

APACHE_PORT=8030
MYSQL_PORT=8031

MYSQL_DATABASE=db
MYSQL_USER=user
MYSQL_PASSWORD=password
MYSQL_ROOT_PASSWORD=root_password
```

`UID`/`GID`: на WSL/Linux выставить `id -u` / `id -g`, иначе `composer install` может писать `vendor` от root и потом host не сможет править. На Win Docker Desktop чаще ок с `1000`.

Имена контейнеров при таком `COMPOSE_PROJECT_NAME`:
- `copytrust-dev-php-apache-1`
- `copytrust-dev-mysql-1`

**Mounts (из compose):**
- код: `../../` → `/var/www/html`
- конфиги: `../../../.config` → `/var/www/.config:ro`

**Команды с нуля:**

```bash
# из корня репо / Windows PowerShell: cd tools\docker-dev

# 1) env
cp .env.dist .env          # Win: Copy-Item .env.dist .env
# поправить COMPOSE_PROJECT_NAME / порты / MYSQL_*

# 2) корень приложения
cd ../..
cp .env.example .env
cp .htaccess.dist .htaccess
# в .htaccess: RewriteCond %{HTTP_HOST} !=localhost:8030 перед https-редиректами

# 3) sibling .config уже есть (шаг 1)

# 4) MySQL
cd tools/docker-dev
docker compose up -d mysql

# 5) зависимости + миграции (канон README)
docker compose run --rm php7.1-cli php composer.phar install
docker compose run --rm node-cli yarn install
docker compose run --rm node-cli yarn dev
docker compose run --rm php7.1-cli php vendor/doctrine/migrations/bin/doctrine-migrations \
  --no-interaction migrations:migrate \
  --db-configuration=sql/migrations-db.php \
  --configuration=sql/migrations.yml

# 6) Apache
docker compose build php-apache
docker compose up -d php-apache

# 7) проверка
curl -sI http://127.0.0.1:8030/ | head -5
docker ps --filter "name=copytrust-dev"
```

**После подъёма связать с AI-kit:**

| Куда | Значение |
|------|----------|
| `.cursor/mcp.env` + `.codex/mcp.env` | `MYSQL_PORT=8031` (или свой), `MYSQL_*` = как в `.env` |
| `.cursor/mcp.json` → `jira-task` args | имя `…-php-apache-1` из `docker ps` |
| `gototask.ps1` (оба kit) | то же имя контейнера |

`restart: unless-stopped` у mysql/php-apache - после рестарта Docker Desktop поднимутся сами, если не делали `stop`.

### 3. `copytrust-test` (опционально, e2e)

**Файлы:** [`tools/docker-test/compose.yaml`](../tools/docker-test/compose.yaml), `.env.dist` → `.env`.

**Канон `.env`:**

```env
COMPOSE_PROJECT_NAME=copytrust-test
UID=1000
GID=1000
APACHE_PORT=8230
MYSQL_PORT=8231
MYSQL_DATABASE=db
MYSQL_USER=user
MYSQL_PASSWORD=password
MYSQL_ROOT_PASSWORD=root_password
```

Сервисы как у dev + **soap-server**. Канон шагов: [docker-test/README.md](../tools/docker-test/README.md) (дамп → `tools/codeception/tests/Support/Data/dump.sql`, migrate, `up -d php-apache`).

```bash
cd tools/docker-test
cp .env.dist .env
docker compose up -d mysql
# … migrate / dump по README …
docker compose up -d php-apache
```

### 4. `selenium-chrome-test` (WebDriver для Codeception)

**Файлов в репо нет** - только образ Hub. С нуля:

```bash
docker rm -f selenium-chrome-test 2>/dev/null
docker run -d --name selenium-chrome-test \
  --restart unless-stopped \
  -p 4444:4444 \
  -p 7900:7900 \
  --shm-size=2g \
  selenium/standalone-chrome:4.21.0
```

| Порт | Назначение |
|------|------------|
| **4444** | WebDriver (Codeception `--env chromedriver`) |
| **7900** | noVNC UI: http://127.0.0.1:7900 |

Проверка: `curl -s http://127.0.0.1:4444/status`.  
Альтернатива без контейнера: локальный chromedriver `:9515` - [browser-setup.md](./qa/browser-setup.md).

Повторный старт после reboot: `docker start selenium-chrome-test` (если создали с `--restart unless-stopped` - сам).

### 5. Sourcegraph (`:7080`) с нуля

**Рекомендация для нового ПК (green MCP быстрее):** из **WSL** `./start-single.sh` (данные в `~/.sourcegraph/`). Полный стек `./start.sh` + `upstream/` - как на машине-образце; тяжелее, но привычный multi-container.

**Файлы Sourcegraph:** export **не** копирует `sourcegraph-local/` с 2026-11-05. Для полного `start.sh` развернуть каталог вручную один раз:

```bash
cd sourcegraph-local
git clone --depth 1 --branch v7.4.0 \
  https://github.com/sourcegraph/deploy-sourcegraph-docker.git upstream
```

**Конфиги:**

| Файл | Роль |
|------|------|
| `sourcegraph-local/.env.example` → `.env` | `SG_URL=http://127.0.0.1:7080` и др. |
| `config/repos.conf.example` → `config/repos.conf` | строки `АБС_ПУТЬ\|имя.git` |
| `config/mcp.token` | после создания admin (одна строка `sgp_…`) |
| `docker-compose*.yml` / `start.sh` / `start-single.sh` | подъём стека |

**Первый раз (канон README):**

```bash
cd sourcegraph-local

# upstream compose (один раз; полный стек 7.4)
git clone --depth 1 --branch v7.4.0 \
  https://github.com/sourcegraph/deploy-sourcegraph-docker.git upstream

cp config/repos.conf.example config/repos.conf
# вписать: /abs/path/to/your-project|your-project.git

cp .env.example .env   # при необходимости

./start.sh
# UI http://localhost:7080 → Create admin
# User settings → Access tokens → scope mcp → config/mcp.token

./sync-mirror.sh
./register-repos.sh
# Site admin → Repositories → Indexed
```

Упрощённый single-container вариант: `./start-single.sh` (см. скрипт; данные в `~/.sourcegraph/`).

**В IDE после подъёма:** токен в `.cursor/mcp.json` headers; фильтр `repo:^src-serve-git-3434/repos/{имя}$`. Детали: [MCP.md](../sourcegraph-local/MCP.md), [День 1](#день-1-куда-что-прописать-со-старта).

### 6. Сводка: что должно быть в `docker ps`

| Контейнер / фильтр | Порты | Без него сломается |
|--------------------|-------|--------------------|
| `{project}-dev-php-apache-1` | 8030→80 | jira-task, gototask, php-docker, сайт |
| `{project}-dev-mysql-1` | 8031→3306 | mysql MCP, приложение |
| `selenium-chrome-test` (опц.) | 4444, 7900 | Codeception `--env chromedriver` |
| `{project}-test-*` (опц.) | 8230, 8231 | e2e на отдельном стенде |
| SG: `caddy` / frontend / … или single | 7080 | MCP sourcegraph |

```bash
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' \
  | grep -E 'copytrust-dev|copytrust-test|selenium-chrome|caddy|sourcegraph|7080' || true
```

### Чеклист: другой компьютер, чтобы MCP/skills завелись

1. **Docker Desktop** установлен и запущен (Linux VM / WSL2 backend ок).
2. **AI-kit** - [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) (или уже лежит в репо).
3. **Код приложения + `tools/docker-*`** - `git clone` целевого проекта (экспорт kit **не** заменяет app compose).
4. Sibling **`<org>/.config/`** с `prepend.php`, `.env`, `.secrets.env` (секреты заново).
5. `cd tools/docker-dev` → `.env` из `.env.dist` → `docker compose up -d` → живы `*-php-apache-1` и `*-mysql-1`.
6. В `.cursor/mcp.env`: `MYSQL_PORT` = host-порт MySQL (образец **8031**, не чужой `3306` от foodninja).
7. В `.cursor/mcp.json`: имя контейнера jira-task = фактическое `docker ps` имя PHP.
8. **e2e / browser-verify:** либо  
   - `docker run … --name selenium-chrome-test …` (4444/7900) + Codeception `--env chromedriver`, либо  
   - локальный Chrome + chromedriver `:9515` по [browser-setup.md](./qa/browser-setup.md).  
   Playwright MCP - отдельный Chrome на хосте/WSL, **не** контейнер selenium (если не настроили иначе).
9. **Sourcegraph MCP:** `sourcegraph-local` up на `:7080` + token в mcp.json (один SG на машину можно шарить между проектами).
10. Host tools: Node/npx, uvx, CBM binary, PowerShell - см. [матрицу MCP](#матрица-mcp-что-должно-завестись).

Команда selenium на новом ПК (канон из browser-setup):

```bash
docker run -d --name selenium-chrome-test \
  -p 4444:4444 -p 7900:7900 --shm-size=2g \
  selenium/standalone-chrome:4.21.0
# UI отладки: http://127.0.0.1:7900
```

Подъём app-стенда:

```powershell
cd tools\docker-dev
Copy-Item .env.dist .env   # поправить порты/БД под машину
docker compose up -d
docker ps --filter "name=copytrust-dev"   # или своё COMPOSE_PROJECT_NAME
```

### Матрица стендов

| | `tools/docker-dev` | `tools/docker-test` |
|--|--------------------|---------------------|
| `COMPOSE_PROJECT_NAME` | `copytrust-dev` | `copytrust-test` |
| HTTP | **8030** | **8230** |
| MySQL host port | **8031** | **8231** |
| Контейнер PHP | `copytrust-dev-php-apache-1` | `copytrust-test-php-apache-1` |
| Контейнер MySQL | `copytrust-dev-mysql-1` | `copytrust-test-mysql-1` |
| Сервисы | mysql, php-apache, php7.1-cli, node-cli | + **soap-server** |
| Для чего | повседневная разработка, MySQL MCP, jira `docker exec` | e2e / login-as-user / browser-verify |
| Env | `.env.dist` → `.env` | `.env.dist` → `.env` |

В `.env.dist` часто `MYSQL_DATABASE=db`, а live/`mcp.env` могут быть `gb_copydev5`. На новом проекте: **одно** имя БД во всех файлах (compose, mcp.env, codeception).

### Skills ↔ контейнеры (факт по SKILL.md / scripts)

Проверено по `.cursor/skills` и `.codex/skills` (зеркало). Имени **`selenium-chrome-test` в скилах нет** - только `--env chromedriver` и ссылка на [qa/browser-setup.md](./qa/browser-setup.md) (там уже `docker start selenium-chrome-test` / порт 4444).

| Skill | copytrust-dev (8030/8031) | copytrust-test (8230/8231) | selenium / chromedriver | Sourcegraph (:7080) |
|-------|---------------------------|----------------------------|-------------------------|---------------------|
| **gototask** | **да** - `docker exec copytrust-dev-php-apache-1` → jira `server.php` | нет | нет | нет |
| **browser-verify** | часто хватает для URL приложения | **да по тексту skill** - «стенд `tools/docker-test` поднят» | **да** - `codecept … --env chromedriver` (+ browser-setup: 4444 selenium **или** 9515) | нет |
| **prepare-task-test** | нет напрямую (пишет Cest) | нет напрямую | **да в команде запуска** - `--env chromedriver` (прогон обычно через browser-verify) | нет |
| **login-as-user** | нет | **да** - только `tools/docker-test`, не прод | косвенно (браузер) | нет |
| **task-doc** | mysql MCP часто через dev | нет | опц. playwright smoke | **да** - MCP Gate |
| **doc-verify** | нет | нет | нет | **да** - обязательный Gate |
| **project-doc** | нет | нет | нет | **да** - после CBM |
| **prepare-plan** | нет | нет | опц. playwright | **да** - поиск кандидатов |
| **task-diff** / **task-code-review** | нет | нет | нет | нет (git) |
| **page-content** / **serp-study** / **xmlriver** | нет | нет | свой Playwright Chromium в venv extractor, **не** selenium-chrome-test | нет |
| **yadisk-screenshot** | нет | нет | нет | нет |

**Rules** (не skills), где нужен SG: `bitbucket-tasks`, `doc-rules`, `project-doc`, `task-doc`, `doc-verify`.

**MCP без skill, но с docker-dev:** `jira-task` и `mysql` в `mcp.json` → контейнеры `copytrust-dev-*`.

Итого для переноса:
1. **Минимум MCP/задач:** `copytrust-dev` + (для поиска) Sourcegraph.
2. **e2e skills:** `browser-verify` / `prepare-task-test` / `login-as-user` → `docker-test` + WebDriver (`selenium-chrome-test` **или** локальный chromedriver :9515 по browser-setup).
3. Selenium-контейнер - инфраструктура из browser-setup, не отдельный skill.

### Порядок подъёма docker-dev (сводка)

Полный прогон с конфигами `.env` и командами: [Воссоздание контейнеров с нуля](#воссоздание-контейнеров-с-нуля) §2.  
Канон деталей: [`tools/docker-dev/README.md`](../tools/docker-dev/README.md).

Кратко: sibling `.config` → корневой `.env` / `.htaccess` → `tools/docker-dev/.env` из `.env.dist` → `up -d mysql` → composer/yarn/migrate → `up -d php-apache` → http://localhost:8030/.

### docker-test

Полный прогон: [Воссоздание §3](#3-copytrust-test-опционально-e2e). Канон: [`tools/docker-test/README.md`](../tools/docker-test/README.md). Порты **8230/8231**. Дамп Codeception: `tools/codeception/tests/Support/Data/dump.sql`.

### Два Codeception

| Путь | Роль | Перенос |
|------|------|---------|
| `tools/codeception/` | продуктовый Acceptance (git) | клон репо + `.env.dist` |
| `.tools/codeception/` | suite агента (browser-verify, prepare-task-test) | **копировать с диска** вместе с kit |

Host для agent suite: **PHP 8.3+** + Composer (в контейнере приложения - PHP 7.1). Chromedriver `:9515`, Chrome - см. [qa/browser-setup.md](./qa/browser-setup.md).

Пример переменных `.tools/codeception/.env.dist`: `APP_PORT`, `MYSQL_*`, `CHROMEDRIVER_*`, путь к `chrome.exe` / binary.

---

## Инструменты вне git (машина)

| Инструмент | Где | Зачем |
|------------|-----|-------|
| **Весь AI-kit на диске** | не в Bitbucket | источник переноса |
| **`<org>/.config/`** | sibling репо | boot PHP в Docker |
| Node.js + npx | PATH | MCP, php-toolchain |
| uv / uvx | PATH | serena, semgrep, git MCP |
| Docker Desktop / daemon | - | compose, jira exec |
| codebase-memory-mcp | Win LOCALAPPDATA / `~/.local/bin` | граф |
| tmux (Linux) | apt | CBM UI :9749 |
| Sourcegraph local | `sourcegraph-local/` или общий | :7080 MCP |
| Chrome for Testing + chromedriver | `~/.local/chrome-for-testing/` + deps | Playwright + Codeception |
| PHP 7.1 (контейнер) + PHP 8.3 (host) | docker / PATH | app vs `.tools/codeception` |
| PowerShell / pwsh | Win / Linux | gototask, setup, docscripts |
| Python 3.10+ venv | `.agents/skills/page-content/scripts`, `.xml-river` | page-content, SERP |
| Yarn (в node-cli) | docker-dev | frontend |
| **%USERPROFILE%\.codex\** | global Codex | trust (`global-trust.snippet.toml`), model provider |
| **Kilo adapter `.kilo/`** | корень репо | зеркала skills/rules + `kilo.jsonc` (без Ollama); канон описания - [dirtree.md](./harnes/dirtree.md) |

---

## День 1: куда что прописать (со старта)

Сначала общий порядок: [Новый комп: мастер-план Day0 → green](#новый-комп-мастер-план-day0--green). Ниже - **куда писать** файлы. Шаблоны mcp.env/jira можно создать до Docker; зелёный MCP - только после [Воссоздание §2](#2-copytrust-dev-обязателен-для-mcp-mysql--jira--gototask) (и SG при необходимости).

**Главное:** Sourcegraph **сам новый проект не добавит.** Один SG на машину (`http://127.0.0.1:7080` + один токен). Репо регистрируют вручную в `repos.conf` → sync → register. Фильтр: `repo:^src-serve-git-3434/repos/{имя}$`.

### Шпаргалка: куда писать (коротко)

| Что | Куда |
|-----|------|
| **Jira** (URL, email, API token, ключ проекта `CT`→свой) | `.doc/skil_data/jira/config.env` |
| **MySQL MCP** | `.cursor/mcp.env` + `.codex/mcp.env` (одинаковые `MYSQL_*`, порт = docker-dev host, образец **8031**) |
| **Имя PHP-контейнера** | `.cursor/mcp.json` / `.codex/mcp.json` → `jira-task.args`; плюс hardcode в `gototask.ps1` (оба kit) |
| **SG токен** | Cursor: `.cursor/mcp.json` → `headers.Authorization: token sgp_…` (**mcp.env для HTTP Cursor не читается**). Codex: `.codex/mcp.env` → `SOURCEGRAPH_MCP_TOKEN`. Копия: `sourcegraph-local/config/mcp.token` |
| **SG этот репо** | `sourcegraph-local/config/repos.conf` + `./sync-mirror.sh` + `./register-repos.sh` |
| **SG фильтр в агенте** | skills/rules: заменить `testdeploydocker` на имя из repos.conf ([Search-replace](#search-replace-copytrust--новый-проект)) |
| **Serena** | `.serena/project.yml` → `project_name` (export уже ставит имя папки) |
| **Релиз gototask** | `.cursor/skills/task-router/children/gototask/config.json` (+ Codex) → `releaseBranch` |
| **Chrome Playwright** | `.cursor/mcp.json` → `PLAYWRIGHT_*` / `CHROME_PATH` ([browser-setup.md](./qa/browser-setup.md)) |
| **CBM** | один раз MCP `index_repository` на абсолютный путь корня проекта |
| **XML River / extractor** | `.doc/skil_data/xmlriver/.env`, `.agents/skills/page-content/scripts/.env` |
| **Leantime MCP** (опц.) | `.doc/skil_data/leantime/mcp/mcp.env` (`LEANTIME_*`); контейнеры `leantime_*` на **8095** |
| **Leantime UI** | [access.md](./leantime/access.md) / `LEAN_ADMIN_*` в `docker/.env` |
| **App стенд** | [Воссоздание контейнеров с нуля](#воссоздание-контейнеров-с-нуля) §1–2 |
| **e2e / selenium / SG стек** | там же §3–5 |
| **e2e** | `.tools/codeception/.env`; selenium **или** chromedriver; опц. `tools/docker-test` |
| **Codex trust** | `%USERPROFILE%\.codex\config.toml` + `global-trust.snippet.toml` с новым путём |

### Порядок настройки (Full) - чеклист #1–15

| # | Что | Файл / действие | Зачем |
|---|-----|-----------------|--------|
| 1 | Open Folder | корень нового репо (не родитель) | Cursor/Codex видят kit |
| 2 | MySQL MCP | `.cursor/mcp.env` **и** `.codex/mcp.env` (из example, **одинаковые** `MYSQL_*`) | порт = host MySQL docker-dev |
| 3 | PHP-контейнер | mcp.json `jira-task` + `gototask.ps1` | jira-task / gototask / php-docker |
| 4 | Jira | `.doc/skil_data/jira/config.env` | gototask, MCP jira-task |
| 5 | Релизные ветки | `skills/task-router/children/gototask/config.json` | merge-release |
| 6 | Serena | `.serena/project.yml` | LSP / serena MCP |
| 7 | SG токен | mcp.json headers / Codex mcp.env | MCP sourcegraph зелёный |
| 8 | SG **этот** репо | `repos.conf` → sync → register → Indexed | иначе `sg_*` пустой |
| 9 | Фильтр `repo:` | search-replace по kit | doc-verify / prepare-plan / bitbucket-tasks |
| 10 | CBM | `index_repository` | codebase-memory-mcp |
| 11 | Playwright Chrome | mcp.json env paths | playwright MCP |
| 12 | App стенд | [Воссоздание §2](#2-copytrust-dev-обязателен-для-mcp-mysql--jira--gototask): `.config` + `tools/docker-dev` | mysql/jira/php живые |
| 13 | e2e (если нужно) | [§3](#3-copytrust-test-опционально-e2e) + [§4 selenium](#4-selenium-chrome-test-webdriver-для-codeception) или chromedriver | browser-verify |
| 14 | Codex trust | user `config.toml` | Codex видит MCP |
| 15 | Опц. XML/extractor | `.env` в `.xml-river` / `.content-extractor` | xmlriver / page-content |
| 16 | Sourcegraph если контейнеров нет | [Воссоздание §5](#5-sourcegraph-7080-с-нуля) | MCP sourcegraph |

### Примеры заполнения (скопировать и править)

**`.doc/skil_data/jira/config.env`** (из `config.example.env`):

```env
JIRA_BASE_URL=https://YOUR-SITE.atlassian.net
JIRA_PROJECT_KEY=XX
JIRA_EMAIL=you@example.com
JIRA_API_TOKEN=your_atlassian_api_token
```

**`.cursor/mcp.env`** (и то же в `.codex/mcp.env`):

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=8031
MYSQL_USER=user
MYSQL_PASSWORD=password
MYSQL_DATABASE=your_db_name
DOCKER_PHP_CONTAINER=yourproject-dev-php-apache-1
```

**`.cursor/mcp.json` → sourcegraph** (токен явно; без `token ` в файле `mcp.token`, с префиксом в headers):

```json
"sourcegraph": {
  "type": "http",
  "url": "http://127.0.0.1:7080/.api/mcp/v1",
  "disabled": false,
  "headers": {
    "Authorization": "token sgp_local_xxxxxxxx"
  }
}
```

**`sourcegraph-local/config/repos.conf`** (SG сам строку не создаст):

```text
/home/you/projects/your-new-project|your-new-project.git
```

Затем:

```bash
cd sourcegraph-local   # или путь к общему SG на машине
./sync-mirror.sh
./register-repos.sh
# UI: http://localhost:7080/admin/repositories → Indexed
```

В запросах агента / skills:

```text
repo:^src-serve-git-3434/repos/your-new-project$
```

**`jira-task` в mcp.json** - имя контейнера как в `docker ps`:

```json
"args": ["exec", "-i", "yourproject-dev-php-apache-1", "php",
         "/var/www/html/.agents/skills/task-router/children/jira/scripts/server.php"]
```

То же имя поправить в `.cursor/skills/task-router/children/gototask/scripts/gototask.ps1` и Codex-копии.

### Sourcegraph: схема (один на машину)

```
один SG (:7080 + один токен в каждом проекте mcp.json)
        │
        ├── repos.conf  ← СЮДА строка с абсолютным путём нового worktree
        ├── sync-mirror.sh + register-repos.sh
        └── в MCP-запросах: repo:^src-serve-git-3434/repos/{имя}$
```

Канон деталей: [`sourcegraph-local/MCP.md`](../sourcegraph-local/MCP.md).

### Креды: не путать

| Секрет | Куда | Не сюда |
|--------|------|---------|
| Jira | `.doc/skil_data/jira/config.env` | не mcp.json |
| MySQL | оба `mcp.env` | не порт чужого compose (например foodninja `:3306`) |
| PHP container | mcp.json + gototask.ps1 | `DOCKER_PHP_CONTAINER` в mcp.env gototask может **не** читать (П-3) |
| SG token (Cursor) | mcp.json `headers` | Cursor HTTP **игнорирует** mcp.env |
| SG список репо | `repos.conf` | не mcp.json |
| Chrome Playwright | mcp.json env | не путать с `selenium-chrome-test` (тот для Codeception) |

Полная таблица example→live: [Полный каталог секретов](#полный-каталог-секретов-и-env).  
Строки Copytrust→свой: [Search-replace](#search-replace-copytrust--новый-проект).

### Минимальный smoke после правок

1. Settings → MCP: mysql, jira-task, sourcegraph, serena, git - не Error.
2. `sg_list_repos` - видно **новое** имя репо.
3. gototask / «обнови таск N» - появляется `.doc/tasks/{N}/task.md`.
4. MySQL MCP: `list_tables` на своей БД.
5. CBM: `index_status` / поиск по этому проекту. Детали: [MCP: индексация CBM и Sourcegraph](#mcp-индексация-cbm-и-sourcegraph).

---

## MCP: индексация CBM и Sourcegraph

> **Legacy (2026-10-29):** MCP `sourcegraph` выключен в каноне. Агентский маршрут:
> `codebase-memory-mcp` → `graphify` → `serena`, полнотекст через `multi-search.sh` / `rg`.
> Шаги Sourcegraph ниже описывают опциональный стек, не обязательный для kit.

Как работают **codebase-memory-mcp** (CBM) и **Sourcegraph** относительно Cursor workspace.  
Пути к репозиторию в блоках CBM/SG в `.cursor/mcp.json` **не задаются**.

Связанные файлы в kit:

- [`.cursor/mcp.json`](../.cursor/mcp.json) - подключение серверов
- [`harnes/mcp/codebase-memory-mcp.md`](harnes/mcp/codebase-memory-mcp.md) - полная инструкция CBM
- [`.cursor/sourcegraph-mcp.md`](../.cursor/sourcegraph-mcp.md) - поиск через Sourcegraph MCP
- [`sourcegraph-local/README.md`](../sourcegraph-local/README.md) - запуск, `repos.conf`, sync
- Короткая копия для корня Target после export: [mcp.index.md](./mcp.index.md)

### Что где привязано к workspace

| MCP | Путь в Cursor MCP? | Как выбирается проект |
|-----|--------------------|------------------------|
| **serena** | да: `--project ${workspaceFolder}` | текущий workspace |
| **git** | да: `--repository ${workspaceFolder}` | текущий workspace |
| **phpstan / php-deps** | да: `MCP_WORKSPACE=${workspaceFolder}` | автоматически |
| **codebase-memory-mcp** | нет | параметр `project` в каждом вызове |
| **sourcegraph** | нет | фильтр `repo:…` в каждом поиске |

CBM и Sourcegraph - мультипроектные сервисы на машину. Open Folder сам по себе их индекс не переключает.

### codebase-memory-mcp

Кеш вне репо:

- Windows: `%USERPROFILE%\.cache\codebase-memory-mcp\`
- WSL/Linux: `~/.cache/codebase-memory-mcp/`

В чате: `Проиндексируй этот проект через codebase-memory-mcp`  
Агент: `index_repository` с **абсолютным** путём корня, `mode = full` (или moderate / fast).

CLI:

```powershell
codebase-memory-mcp cli index_repository "{\"repo_path\": \"C:/path/to/your-project\", \"mode\": \"full\"}"
```

После индексации: `list_projects` → во всех вызовах передавать `project` (`search_graph`, `trace_path`, `get_code_snippet`, `query_graph`, `index_status`). Без `project` - "project not found".

### Sourcegraph

> **Legacy (2026-10-29):** MCP `sourcegraph` выключен в каноне. Агентский маршрут:
> `codebase-memory-mcp` → `graphify` → `serena`, полнотекст через `multi-search.sh` / `rg`.
> Шаги Sourcegraph ниже описывают опциональный стек, не обязательный для kit.


Путь к коду не в mcp.json. Список worktree:

`sourcegraph-local/config/repos.conf` → `WORKTREE_ABS_PATH|MIRROR_NAME.git`

```text
/mnt/c/path/to/your-project|your-project.git
```

(для WSL sync часто `/mnt/c/...`; MCP URL в mcp.json: `http://127.0.0.1:7080/.api/mcp/v1`)

```bash
cd sourcegraph-local
./sync-mirror.sh
./register-repos.sh
# UI Indexed: http://localhost:7080 → Site admin → Repositories
```

В каждом поиске:

```text
repo:^src-serve-git-3434/repos/your-project$
```

| Инструмент | Зачем |
|------------|--------|
| `sg_list_repos` | репо в индексе |
| `sg_keyword_search` / `sg_nls_search` | поиск + `repo:` |
| `sg_list_files` / `sg_read_file` | файлы после сужения |

Без `repo:` - поиск по всем зеркалам. `.doc/` часто не в git-зеркале - `task.md` / architecture через Read.

### Типовой порядок для агента

```text
1. CBM:   list_projects → search_graph / trace_path  (с project=…)
2. SG:    sg_keyword_search  (с repo:^…$)
3. Serena: символы / правки в ${workspaceFolder}
```

Не дублировать: если CBM уже отдал snippet через `get_code_snippet`, тот же файл через `sg_read_file` без нужды не читать.

### Быстрые команды

| Цель | Фраза / действие |
|------|------------------|
| Индекс CBM текущего workspace | "Проиндексируй этот проект через codebase-memory-mcp" |
| Статус CBM | "Покажи list_projects и index_status" |
| Добавить в Sourcegraph | `repos.conf` + sync + register |
| Проверка Sourcegraph | `sg_list_repos`, затем поиск с `repo:^…$` |

Подъём SG с нуля: [§5](#5-sourcegraph-7080-с-нуля). Бинарь CBM: Day0 Host + `codebase-memory-mcp.md`.

---

## Полный каталог секретов и env

Создавать из example/dist. **Не** копировать live-файлы со старого стенда.

| Файл-источник | Куда | Ключевые переменные |
|---------------|------|---------------------|
| `.cursor/mcp.env.example` | `.cursor/mcp.env` | `MYSQL_HOST/PORT/USER/PASSWORD/DATABASE`, `PHP_BIN`, `DOCKER_PHP_CONTAINER`, `NODE_BIN`, `CBM_*`, `LARAGON_ROOT`, комментарий про SG |
| `.codex/mcp.env.example` | `.codex/mcp.env` | то же семейство; **дефолты другие** (часто `3306` / пустая БД) - выровнять с Cursor и docker-dev |
| `.doc/skil_data/jira/config.example.env` | `config.env` | `JIRA_BASE_URL`, `JIRA_PROJECT_KEY`, `JIRA_EMAIL`, `JIRA_API_TOKEN`, `WORKSPACE_ROOT` |
| `.doc/.bitbucket/config.example.env` | только если legacy BB | `BITBUCKET_WORKSPACE`, `REPO_SLUG`, `EMAIL`, `API_TOKEN` |
| `.doc/skil_data/xmlriver/.env.example` | `.env` | `XMLRIVER_USER_ID`, `XMLRIVER_API_KEY` (+ timeout/cache/SERP/Wordstat defaults) |
| `.agents/skills/page-content/scripts/.env.example` | `.env` | `CONTENT_EXTRACTOR_FETCH_PROVIDERS`, parsers, cookies, timeout, screen |
| `sourcegraph-local/.env.example` | `.env` | `SG_URL`, `SG_SERVE_GIT_URL`, опц. `SOURCEGRAPH_MCP_TOKEN` |
| `sourcegraph-local/config/mcp.token.example` | `config/mcp.token` | сырой `sgp_local_…` |
| `sourcegraph-local/config/repos.conf.example` | `repos.conf` | пути worktree → имя.git |
| `tools/docker-dev/.env.dist` | `.env` | `COMPOSE_PROJECT_NAME`, `APACHE_PORT`, `MYSQL_*` |
| `tools/docker-test/.env.dist` | `.env` | то же для test-портов |
| `tools/codeception/.env.dist` | `.env` | APP/MYSQL/Chrome |
| `.tools/codeception/.env.dist` | `.env` | APP/MYSQL/`CHROMEDRIVER_*` |
| корневой `.env.example` | `.env` | продуктовые секреты приложения (mail, AWS, DB, …) - не AI-kit, но нужны для стенда |
| `<org>/.config/.env` + `.secrets.env` | sibling | runtime приложения в контейнере |

### Sourcegraph в Cursor `mcp.json`

Часто зашит `Authorization: token sgp_local_…`. На новом проекте: свой токен; **не** коммитить; Cursor HTTP MCP плохо подхватывает envFile - токен в headers или OS env при старте IDE.

### Playwright env keys (Cursor)

`PLAYWRIGHT_MCP_EXECUTABLE_PATH`, `CHROME_PATH`, `LD_LIBRARY_PATH` - абсолютные пути пользователя; на другой машине заменить (см. [qa/browser-setup.md](./qa/browser-setup.md)).

**Пример Win** (Cursor Open Folder = `C:\...`, обычный Chrome):

```json
"env": {
  "PLAYWRIGHT_MCP_EXECUTABLE_PATH": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "CHROME_PATH": "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
}
```

**Пример WSL** (Chrome for Testing + wrap, как на образце):

```json
"env": {
  "PLAYWRIGHT_MCP_EXECUTABLE_PATH": "/home/YOU/.local/chrome-for-testing/chrome-wrap.sh",
  "CHROME_PATH": "/home/YOU/.local/chrome-for-testing/chrome-wrap.sh",
  "LD_LIBRARY_PATH": "/home/YOU/.local/chrome-deps/root/usr/lib/x86_64-linux-gnu"
}
```

Пути `C:\\Apps\\chrome-fot-tests\\...` со старого ПК на новом **сломают** MCP - всегда проверить `Test-Path` / `ls` до Reload.

---

## Search-replace (Copytrust → новый проект)

| Было | Станет |
|------|--------|
| `testdeploydocker` | имя папки / Serena / SG repo |
| `repo:^src-serve-git-3434/repos/testdeploydocker$` | `repo:^src-serve-git-3434/repos/{новое}$` |
| `copytrust-dev` / `copytrust-dev-php-apache-1` / `copytrust-dev-mysql-1` | `{project}-dev…` |
| `copytrust-test` / `8230` / `8231` | test compose / порты |
| `CT-` / `JIRA_PROJECT_KEY=CT` / `copytrust-team.atlassian.net` | свой Jira |
| `BITBUCKET_WORKSPACE=copytrust` / `copytrust.ru` | свой BB (если нужен) |
| `release/5.6.0.6` / `for5606` / `for_5.6.0.6` | свои релизы |
| `gb_copydev5` / рассинхрон с `MYSQL_DATABASE=db` | одно имя БД |
| `8030` / `8031` | свои порты |
| `/var/www/html/.agents/skills/task-router/children/jira/scripts/server.php` | путь mount в контейнере (если другой docroot) |
| `../../../.config` / `CONFIG_DIR` | путь к sibling configs |
| `/home/newuser/...` | новый user home (NODE_BIN, Chrome, global-trust WSL) |
| `C:\projects\copytrust\testdeploydocker` / `c:\projects\...` | новый путь (examples + `global-trust.snippet.toml`) |
| `C:\Apps\chrome-fot-tests\...` | путь Chrome на новой машине |
| `project-0-testdeploydocker-*` | имена MCP в UI / примеры в SKILL |

Приоритет правок:

1. `.serena/project.yml`
2. gototask `config.json` (оба kit) + hardcode docker в `gototask.ps1`
3. `mcp.json` / `config.toml` - jira-task, SG, Playwright
4. SG filter во всех rules/skills/`doc_rules.md`/`sourcegraph-mcp.md`
5. `AGENTS.md`, `.codex/AGENTS.md`, README-MCP-SETUP
6. `global-trust.snippet.toml` → вставить в `%USERPROFILE%\.codex\config.toml` с **новыми** путями
7. docker `.env`, mcp.env (выровнять Cursor↔Codex), codeception `.env`

### Ветки git

| Конвенция | Адаптация |
|-----------|-----------|
| `features/#{N}` / `bugfixes/#{N}` | оставить или сменить в gototask |
| бэкпорт `_for5606` | под свои релизы или удалить |
| subject коммита с `{N}` / `#{N}` | иначе task-diff пустой |
| remote Bitbucket | свой; проверка веток через `git ls-remote` |

---

## Быстрый экспорт скриптом (Cursor)

**Скрипт экспорта:** [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1)

Совместимость: [export-rebase-project.ps1](../.agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1) → делегирует в канон.

Создаёт каталог Target, копирует kit по этому документу, пишет `.git/info/exclude`, готовит `mcp.env` из example, scrub токенов в `mcp.json`, правит Serena `project_name`, заменяет абсолютные пути образца на Target в конфигах и лаунчерах, очищает `component_registry.json` от удалённых скилов и runtime-путей, при Target=`C:\...` патчит Win-лаунчеры MCP, в конце **must-check** и `EXPORT_NEXT_STEPS.md` с полным чеклистом запуска.

Повторный запуск в тот же каталог не удаляет файлы Target. До копирования скрипт печатает, сколько файлов перезапишется, добавится и сохранится вне kit. После копирования пишет `.doc/.rebase-report.md` и `.doc/.rebase-report.json`: документация проекта, задачи, кастомные скилы, правила и скрипты, перезаписанные файлы kit. Полный список сохранённого лежит в `.doc/.rebase-preserved.txt`. Точное зеркало с удалением лишнего включается флагом `-MirrorKit`.

```powershell
# из корня образца (testdeploydocker), в терминале Cursor / Windows PowerShell:
powershell -NoProfile -ExecutionPolicy Bypass -File .agents\skills\harness-router\children\new-project\scripts\rebase_project.ps1 `
  -Target "C:\laragon\www\test"

# профиль без Jira/gototask:
powershell -NoProfile -ExecutionPolicy Bypass -File .agents\skills\harness-router\children\new-project\scripts\rebase_project.ps1 `
  -Target "C:\laragon\www\test" -Profile Core -ProjectName test

# сразу setup.ps1 (нужны Node/сеть; при уже скопированных vendor/nm обычно не обязателен):
powershell -NoProfile -ExecutionPolicy Bypass -File .agents\skills\harness-router\children\new-project\scripts\rebase_project.ps1 `
  -Target "C:\laragon\www\test" -RunSetup

# из WSL, если Target на диске Windows:
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 `
  -Target "C:\laragon\www\test"
```

После успеха: **File → Open Folder** на Target (уже с app-кодом или после merge clone), затем `EXPORT_NEXT_STEPS.md` и канон [Day0 → green](#новый-комп-мастер-план-day0--green).

**После Full у вас kit, не приложение.** Пока нет `tools/docker-dev` из git clone - mysql/jira контейнеры не появятся.

### Параметры скрипта

| Параметр | Default | Смысл |
|----------|---------|--------|
| `-Target` | обязателен | каталог нового проекта (создаётся) |
| `-Profile` | `Full` | `Full` / `Core` |
| `-ProjectName` | имя папки Target | Serena `project_name` |
| `-Source` | родитель `.doc/` | корень образца |
| `-IncludeKilo` | off | `.kilo` / `.kilocode` |
| `-Mode` | `migrate` | `migrate` / `clean` / `update`; см. [режимы](./harnes/state/14-project-migration.md) |
| `-SkipRuntimeDeps` | off | nm/vendor **копируются** по умолчанию |
| `-RunSetup` | off | `.cursor/setup.ps1` + `.codex/setup.ps1` |
| `-SkipMcpMerge` | off | не сохранять Target-only MCP (boost/…) |
| `-SkipGitInit` / `-SkipExclude` / `-SkipSiblingConfig` | off | отключить шаги |
| `-SkipBackup` / `-SkipReview` | off | не сохранять бэкап / не запускать разбор после переноса |
| `-MirrorKit` | off | точное зеркало: удаляет в Target файлы, которых нет в образце (`rsync --delete` / `robocopy /PURGE`). Режим `clean` включает это поведение |

**Merge MCP (по умолчанию on):** если в Target уже есть `.cursor/mcp.json` / `.codex/config.toml`, скрипт бэкапит их в `.doc/.rebase-mcp-backup/`, копирует kit, затем вливает серверы **только из Target**, которых нет в kit (пример: `laravel-boost`, `laravel-telescope`). Из kit добавляются в т.ч. `sourcegraph`, `leantime`, `graphify`. Одинаковые имена - версия **kit** (образец).

### Что копирует Full (факт скрипта)

| Блок | Да | Нет / исключено |
|------|----|-----------------|
| `AGENTS.md`, `.cursor/`, `.codex/` | да | живой `mcp.env`; артефакты |
| Runtime MCP | `php-toolchain/node_modules`, `tools/vendor` (оба kit) | корневой app `/node_modules` (~277M webpack) |
| `.serena/project.yml` | да | `cache/`, `memories/` |
| `.doc` стандарты | `doc_rules`, `readmy_doc`, `rebase_project.md`+`.ps1`+`_gi.ps1`, `tests` | - |
| `.doc` инфра | `docscripts`, `.content-extractor`, `.xml-river`, `.mcpyandexscreen`, **`leantime/` целиком (с `.env` / `mcp.env` / bearer)**, **`web/` целиком (панель документации)**, **`task-analytics/`** (код, без `out/`), **`kaiten/doc.md`**, `.jira`, `qa`, `codeception`+`vendor` | `.venv`, `screen/`, `dump.sql`, `imd/*`, `tasks/{N}`, architecture-контент, serpanalise/seoq |
| `sourcegraph-local` | нет | **не копируется** с 2026-11-05; разворачивается вручную |
| Sibling `../.config` | пустой README | секреты Copytrust |
| Skills | 20 рабочих | удаляет `login-as-user`, `serpanalise-report` |
| MCP | kit + **merge** Target-only | `sourcegraph`/`leantime`/`graphify` из kit; boost с Target; бэкап `.doc/.rebase-mcp-backup/` |

Ориентир размера после Full: **~130-140 MB** (тест `C:\laragon\www\_rebase_export_audit`, 2026-07-18).

### MCP: Windows vs WSL (факт с экрана)

Открытие Target как `C:\laragon\www\...` в **Cursor Windows**:

| MCP на скрине | Статус | Причина / действие |
|---------------|--------|--------------------|
| phpstan-mcp / php-deps-mcp | **Error** без патча | `command: bash` + путь `C:\...\.sh` → `System32\bash.exe` (WSL) ломает Win-путь. Скрипт патчит на `cmd` + [`.cursor/scripts/node-mcp.cmd`](../.cursor/scripts/node-mcp.cmd) |
| codebase-memory-mcp | обычно OK / патч | Win: `codebase-memory-mcp-launch.cmd` → `%LOCALAPPDATA%\Programs\codebase-memory-mcp\*.exe` |
| jira-task | Loading | нет Docker-контейнера `copytrust-dev-php-apache-1` - переименовать в mcp.json под свой |
| serena | Loading | первый `uvx` pull - подождать |
| mysql, playwright, context7, git, semgrep, xdebug, sourcegraph | зелёные при host-tools | npx/uvx/http; SG нужен `:7080` + token |
| **leantime** | обычно OK после compose up | env/API key уже в export; иначе `docker compose up` + `uvx` |
| дубли CBM / SG в UI | норма | project MCP + user-level MCP |

| Открыли проект как | Лаунчер phpstan/php-deps/CBM |
|--------------------|------------------------------|
| `C:\...` (Windows Cursor) | `cmd` + `node-mcp.cmd` / `codebase-memory-mcp-launch.cmd` (патч экспорта) |
| WSL Remote / `\\wsl$\...` | `bash` + `node-mcp.sh` / `*.sh` (без Win-патча) |

**Корневой `/node_modules` приложения не участвует в MCP.** Нужны только toolchain nm + `tools/vendor`.

### Матрица MCP (что должно завестись)

| MCP | В экспорте | Host / стенд |
|-----|------------|--------------|
| playwright | mcp.json | Node+npx; Chrome paths (Win: chrome.exe; WSL: wrap.sh) |
| serena | `.serena/project.yml` | `uvx`, Open Folder = корень |
| context7 / xdebug / mysql | mcp.json + mcp.env | Node+npx; mysql: `scripts/run-with-mcp-env.sh` + `mysql-mcp-proxy.mjs` (listen 127.0.0.1:3306 → MYSQL_PORT стенда, образец 8031) |
| semgrep / git | mcp.json | `uvx` |
| phpstan / php-deps | nm + vendor + Win/WSL launcher | PHP или `php-docker.cmd` + контейнер |
| jira-task | `.agents/skills/task-router/children/jira/scripts/server.php` | Docker PHP + JIRA_* + **новое** имя контейнера |
| codebase-memory | launch cmd/sh | CBM binary на машине |
| sourcegraph | нет, вручную | развернуть `sourcegraph-local/` отдельно, token в mcp.json headers |

Skills (gototask, task-diff, prepare-plan, project-doc, browser-verify, …): PowerShell/Markdown - на Win Cursor ок при PowerShell. SG shell-скрипты и часть e2e удобнее из WSL. App-код + `.tools/docker-*` - локально на Target, не из этого export.

### Подводные камни копирования (обнаружено при тестах)

1. **robocopy всего `sourcegraph-local` через `\\wsl.localhost\...`** зависает на `repos-mirror` даже с `/XD` - скрипт использует **allowlist** файлов + Copy-Item для `config`/`lib`.
2. Файлы `config/nginx*.conf` иногда `root:600` - нечитаемы; bootstrap SG пересоздаст; скрипт skip + WARN.
3. UTF-8 **BOM** обязателен для Windows PowerShell 5.1.
4. После экспорта на Win: Refresh MCP у phpstan/php-deps (или Reload Window).

---

## MCP: Windows vs WSL - детали и проверки

См. подраздел в [Быстрый экспорт](#быстрый-экспорт-скриптом-cursor). Якорь для ссылок из чеклистов.

Кратко: kit с Linux-диска на `C:\` копируется нормально; ломается не копирование, а **запуск `bash`+`.sh` из Cursor Windows**. Исправление - в [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) (`Patch-CursorMcpForWindowsHost`).

---

## Пошаговая процедура (FULL)

### 0. Чеклист до копирования

```text
Источник kit (путь на диске, не git): _______________
Целевой корень репо: _______________
Sibling .config путь: _______________
Стек Serena languages: _______________
Compose project / PHP container (dev): _______________
MySQL host:port / db / user (dev): _______________
Нужен docker-test? порты: _______________
Jira base / project key: _______________
Release branch: _______________
Sourcegraph repo name: _______________
Нужен .tools/codeception + browser-verify? (да/нет): _______________
Нужен Kilo (.kilo без node_modules)? (обычно нет): _______________
Нужен login-as-user / serpanalise? (обычно нет): _______________
```

**Предпочтительно:** [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) вместо ручного robocopy ниже.

### 1. Копирование kit (PowerShell, ручной fallback)

```powershell
$Source = "C:\projects\copytrust\testdeploydocker"
$Target = "C:\projects\your-org\your-new-project"
$OrgConfig = "C:\projects\copytrust\.config"      # образец
$TargetConfig = "C:\projects\your-org\.config"  # sibling нового репо

# Sibling configs приложения (без слепого копирования секретов прода)
New-Item -ItemType Directory -Path $TargetConfig -Force | Out-Null
# Скопировать структуру; секреты заполнить вручную:
# prepend.php, .env.example→.env, .secrets.env

Copy-Item "$Source\AGENTS.md" $Target -Force

foreach ($root in @(".cursor", ".codex")) {
  robocopy "$Source\$root" "$Target\$root" /E `
    /XD node_modules vendor artifacts memories `
    /XF mcp.env package-lock.json composer.lock
}

robocopy "$Source\.serena" "$Target\.serena" /E /XD memories cache /XF project.local.yml

# .doc: стандарты + инфра + jira + qa + agent codeception
New-Item -ItemType Directory -Path "$Target\.doc" -Force | Out-Null
foreach ($f in @(
  "doc_rules.md","readmy_doc.md","rebase_project.md","rebase_project.ps1","rebase_project_gi.ps1","mcp.index.md","tests.md"
)) {
  Copy-Item "$Source\.doc\$f" "$Target\.doc\" -Force -ErrorAction SilentlyContinue
}
foreach ($d in @(
  "docscripts",".content-extractor",".xml-river",".mcpyandexscreen","web","task-analytics",
  ".jira","qa","codeception"
)) {
  if (Test-Path "$Source\.doc\$d") {
    robocopy "$Source\.doc\$d" "$Target\.doc\$d" /E `
      /XD node_modules .venv __pycache__ cache imd vendor logs output `
      /XF .env config.env out_copytrust.json
  }
}
New-Item -ItemType Directory -Path "$Target\.doc\architecture\_map" -Force | Out-Null
New-Item -ItemType Directory -Path "$Target\.doc\tasks" -Force | Out-Null
New-Item -ItemType Directory -Path "$Target\.doc\tasks\_map" -Force | Out-Null
New-Item -ItemType Directory -Path "$Target\.doc\qa\reports" -Force | Out-Null
New-Item -ItemType Directory -Path "$Target\.doc\.mcpyandexscreen\imd" -Force | Out-Null
# НЕ копировать: .doc/tasks/index.md, .doc/tasks/_map/file-to-tasks.tsv, .doc/tasks/{N}/
# Индекс появится после: build-tasks-index.ps1 -AlsoTsv
# Проверка обязательных файлов после copy:
# Test-Path "$Target\.doc\tests.md"
# Test-Path "$Target\.doc\.mcpyandexscreen\yadisk-fetch.ps1"
# Test-Path "$Target\.codex\skills\prepare-plan\assets\plan.template.md"
# Test-Path "$Target\.codex\skills\doc-verify\reference.md"
# Test-Path "$Target\.cursor\skills\gototask\scripts\gototask.ps1"
# Test-Path "$Target\.codex\go-task.ps1"

# Sourcegraph: либо общий инстанс на машине, либо robocopy sourcegraph-local (без .env / mcp.token / repos data)
# Kilo (опционально): robocopy .kilo / .kilocode без node_modules; переписать agents
```

Коды `robocopy` 0-7 = успех.

**Не копировать вручную:** живые `mcp.env` / `config.env` / токены, `tasks/{N}/`, architecture-контент Copytrust, `serpanalise/` (если SEO не нужен), `.seoq/`, `Stagehand/`, `.playwright-mcp/`, `memories/`, дампы SQL, `imd/*`, корневой app `/node_modules`, SG `repos-mirror`.

**Скрипт Full дополнительно копирует** (не забыть при ручном fallback): `php-toolchain/node_modules`, `tools/vendor` (оба kit), `.tools/codeception/vendor`, SG allowlist, Win-лаунчеры `.cmd`.

Продуктовый `tools/docker-*` - из **git clone** целевого репо (или адаптация compose), не из AI-kit export.

### 2. Порядок setup после копирования

0. **Сразу** создать `$Target/.git/info/exclude` (блок из секции exclude) и при необходимости skip-worktree на compose/FirstCest - иначе `git status` заспамит весь kit и есть риск случайного commit.
1. Sibling `.config` заполнен.
2. `tools/docker-dev/.env` + корневой `.env` / `.htaccess`; сверить локальный `compose.yaml` (mount `.config`) с remote.
3. `docker compose up` (mysql → deps → migrate → php-apache).
4. `.cursor/mcp.env` + `.codex/mcp.env` из example; **одинаковые** `MYSQL_*`. Если runtime deps уже скопированы скриптом - `setup.ps1` опционален; иначе `.\.cursor\setup.ps1` и `.\.codex\setup.ps1`.
5. Jira `config.env`; xml-river / content-extractor `.env` + venv при необходимости (`pip install -e .` - `.venv` не копировали).
6. SG: `sourcegraph-local/start-single.sh` + token + `register-repos.sh`; CBM `index_repository` на `$Target`.
7. Codex: trust с новыми путями; smoke MCP - `node .cursor\scripts\test-mcp-servers.mjs`.
8. e2e: docker-test (если нужен); свой `dump.sql` / БД (дамп Copytrust не тащили); chromedriver :9515; `.env` из `.env.dist`.
9. Каркас docs: stub `architecture/index.md` уже от скрипта; дальше project-doc / `map-project.ps1`.
10. После первых задач: `build-tasks-index.ps1 -AlsoTsv`.
11. **Win Cursor:** Refresh phpstan/php-deps после экспорта; переименовать jira docker container в mcp.json.

### 3. Проверка must-copy (PowerShell)

```powershell
Set-Location $Target
$must = @(
  "AGENTS.md",
  ".cursor\mcp.json",".cursor\setup.ps1",".cursor\rules\text-style.mdc",
  ".cursor\skills\gototask\scripts\gototask.ps1",
  ".cursor\skills\gototask\config.json",
  ".cursor\skills\task-diff\scripts\task-diff.ps1",
  ".cursor\scripts\php-docker.cmd",".cursor\scripts\node-mcp.sh",".cursor\scripts\node-mcp.cmd",
  ".cursor\scripts\codebase-memory-mcp-launch.cmd",
  ".cursor\mcp-servers\php-toolchain\server.js",
  ".cursor\mcp-servers\php-toolchain\node_modules\@modelcontextprotocol\sdk\package.json",
  ".cursor\tools\vendor\bin\phpstan",
  ".codex\config.toml",".codex\AGENTS.md",".codex\go-task.ps1",".codex\task-diff.ps1",
  ".codex\skills\prepare-plan\assets\plan.template.md",
  ".codex\skills\doc-verify\reference.md",
  ".codex\scripts\run-with-mcp-env.sh",".codex\lib\kit-root.ps1",
  ".doc\doc_rules.md",".doc\tests.md",".doc\readmy_doc.md",".doc\rebase_project.md",".agents\skills\harness-router\children\new-project\scripts\rebase_project.ps1",
  ".doc\docscripts\map-project.ps1",".doc\docscripts\build-tasks-index.ps1",
  ".doc\.jira\server.php",".doc\.mcpyandexscreen\yadisk-fetch.ps1",
  ".doc\qa\index.md",".doc\qa\fragments.md",".doc\qa\browser-setup.md",
  ".doc\codeception\codeception.yml",".doc\codeception\composer.json",
  ".doc\codeception\vendor\autoload.php",
  "sourcegraph-local\README.md","sourcegraph-local\start-single.sh",
  ".serena\project.yml"
)
$must | ForEach-Object {
  [PSCustomObject]@{ Path = $_; OK = (Test-Path $_) }
} | Where-Object { -not $_.OK } | Format-Table -AutoSize
# Пустой вывод = все must-файлы на месте

# Явно НЕ должно быть чужого индекса задач:
if (Test-Path ".doc\tasks\index.md") {
  Write-Warning "Найден .doc/tasks/index.md - убедитесь что он сгенерирован ЗДЕСЬ, а не скопирован из Copytrust"
}
Get-ChildItem ".doc\tasks" -Directory -ErrorAction SilentlyContinue |
  Where-Object { $_.Name -match '^\d+$' } |
  Select-Object -First 5 Name
# Если видите 1146/1335/... - это чужие папки задач, удалить
```

### 4. Проектные правки (минимум)

1. Serena `project_name` / `languages`.
2. gototask `config.json` + docker container в ps1 (оба kit).
3. MCP jira-task / SG / Playwright paths.
4. Заменить SG `repo:` filter везде.
5. AGENTS - имя/стек; удалить `login-as-user`, `serpanalise-report` если не нужны.
6. Выровнять Cursor ↔ Codex `mcp.env` (не оставлять Codex на 3306 при dev на 8031).

### 5. Codex machine bootstrap

1. Trust репо (открыть **корень** `$Target`).
2. Дописать в `%USERPROFILE%\.codex\config.toml` фрагмент из `global-trust.snippet.toml` с путями **нового** проекта (Win + WSL UNC).
3. Опционально: `.codex/codex-sale/` для desktop proxy.
4. Smoke MCP: `node .cursor\scripts\test-mcp-servers.mjs`; `codex mcp list`.

### 6. Kilo (опционально)

- Копировать `.kilo/` и `.kilocode/` без `node_modules`; корневой `kilo.json` - по необходимости (оба в exclude).
- Фактически `.kilo/` - это адаптер: зеркала `skills/`, `rules/`, `kilo.jsonc`, `node_modules`. Зеркала генерируются из канона `.cursor/` через `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` - можно не копировать, а сгенерировать на месте.
- Прежние пункты про Ollama `:11434` и модель в `kilo.json` устарели - текущий adapter их не требует.
- Канон описания: [dirtree.md](./harnes/dirtree.md).

---

## Профиль CORE

Без трекера задач. Цель: docs + MCP + универсальные skills на чужом репо, без Jira/gototask/e2e-агента.

**Экспорт:** `-Profile Core` у [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) (вырезает task-skills, `.jira`/`qa`/`codeception`, отключает jira/bitbucket MCP).

### Что оставить / убрать

| Оставить | Убрать |
|----------|--------|
| Skills: 23 - 8 = **15 рабочих** (business-analyst, project-doc, doc-verify, prepare-plan, page-content, xmlriver, serp-study, yadisk-screenshot, git-task-blame, harness-improvement, jira-report, send-to-git, task-change-report, task-intake, test-task) | gototask, task-diff, task-doc, task-code-review, prepare-task-test, browser-verify, login-as-user, serpanalise-report |
| Rules: `doc-rules`, `project-doc`, `project-doc-indexing`, `yadisk-screenshot`, `prepare-plan`, `text-style` | `bitbucket-tasks`, `task-doc` |
| `.doc`: `doc_rules`, `readmy_doc`, `rebase_project.*`, `tests.md`, `docscripts`, extractor, xml-river, yadisk, **leantime целиком (с env)**, **web целиком (панель документации)**, kaiten research (плюс вручную `readmy.md`, `synh_harnes/`) | `.jira/`, `qa/`, `codeception/`, `tasks/{N}/`, architecture-контент старого кода, serpanalise/seoq |
| MCP: serena, git, mysql, CBM, phpstan, …, **leantime** (опц.) | jira-task / bitbucket-task → `"disabled": true` |
| Codex | без `go-task.ps1`, `task-diff.ps1` |

> [!WARNING] Известная оговорка CORE
> `git-task-blame`, `harness-improvement`, `jira-report`, `send-to-git`, `task-change-report`, `test-task` скриптом **не вырезаются** (`rebase_project.ps1` режет только 8 перечисленных) - Core-export фактически оставляет больше skills, чем заявлено. Часть из них (jira-report, send-to-git, test-task) тяготеет к FULL-контуру - возможный рассинхрон логики CORE со скриптом; при чистом Core удалить вручную.

`.doc/tasks/` на Target: **только пустая папка** (скрипт так и делает). Не robocopy `{N}/` из Copytrust.

### После Core-export

1. Open Folder = корень Target; Reload.
2. `mcp.env` из example (MYSQL_* если нужен mysql MCP).
3. В `AGENTS.md` / `.codex/AGENTS.md` убрать ссылки на gototask / Bitbucket, если трекер не планируете.
4. Создать `.doc/architecture/index.md` (шаблон в `doc_rules.md`) → `map-project.ps1` → skill project-doc.
5. CBM: `index_repository` на абсолютный путь Target.
6. Jira позже: отдельно вернуть `.doc/skil_data/jira/`, skills gototask/task-diff, rule bitbucket-tasks, включить MCP - это уже путь к Full, не Core.

### Smoke Core

| Проверка | OK |
|----------|-----|
| нет `.cursor/skills/gototask` | папки нет |
| jira-task / bitbucket-task | disabled |
| `.doc/tasks/` пустой | нет `task.md` из Copytrust |
| `map-project.ps1` | `_map/file-registry.tsv` |
| MCP serena / git / CBM | connected |

### Типичные ошибки Core

| Симптом | Решение |
|---------|---------|
| Агент ищет `.doc/skil_data/jira` / gototask | Core без трекера - почистить AGENTS.md |
| В Target есть `.doc/tasks/1612/` | удалить содержимое `tasks/`, оставить пустой каталог |
| Скопированы `5.7.*.md`, `gb_copydev5.sql` | оставить только стандарты из матрицы `.doc/` |

---

## Сервис панели и харнес-миррора

`copytrust-tools` это один PHP-сервис на `127.0.0.1:8077`: панель задач, просмотрщик харнеса и запуск разрешённых скриптов по кнопкам. Код едет в kit, состояние и рантайм создаются на Target.

| Область | Перенос | Примечание |
|---|---|---|
| `.doc/web` код | да | `web` в `$docDirs`, Full и Core |
| `.doc/task-analytics` код | да | без `out` |
| `.doc/web/state` | нет | задания и логи, `$docXd` |
| `.doc/web/ADAPTERS.local.md` | нет | локальные пути, `$docXf` |
| `.doc/web/config/actions.local.json` | нет | локальные дополнения, `$docXf` |
| `copytrust-tools:local` | нет | собирается на Target |
| CBM, CodeGraph, node | нет | вне сервиса |

Установка на Target:

```bash
cd .doc/web
./install.sh --check
./install.sh --project
HOST_UID=$(id -u) HOST_GID=$(id -g) docker compose -p copytrust-tools -f compose.tools.yml up -d --build
./verify.sh
```

`-RunSetup` у `rebase_project.ps1` вызывает `install.ps1 -Check` и `-Project`. Если проверка не прошла, сервис не считается установленным.

---

## Синхронизация Cursor ↔ Codex ↔ адаптеры

Канон - `.cursor/`. Зеркала остальных сред **генерируются**, а не правятся руками: утилита [`.agents/skills/harness-router/children/environment-sync/`](../.agents/skills/harness-router/children/environment-sync/SKILL.md).

| Инструмент `synh_harnes/` | Что делает |
|---------------------------|------------|
| `sync-agent-views.sh` | точка входа: синхронизирует зеркала 5 сред (`.codex`, `.kilo`, `.agents`, `.antigravity`, `.gemini`) из канона `.cursor/` |
| `generate-agent-configs.py` | генерирует rules/skills/scripts адаптеров; убирает Cursor frontmatter `.mdc` для Codex/Kilo |
| `generate-mcp-config.py` | транслирует `.cursor/mcp.json` в нативные MCP-конфиги сред (Antigravity/Gemini без `${workspaceFolder}`/`envFile`; Kilo → `kilo.jsonc`) |
| `parity-report.json` | отчёт parity зеркал (сверка составов канона и адаптеров) |

Пары (канон → генерируемое зеркало):

| Cursor (канон) | Codex + адаптеры |
|--------|-------|
| `.cursor/mcp.json` | `.codex/config.toml` (+ `.codex/mcp.json` docs/smoke); MCP-конфиги адаптеров - из `generate-mcp-config.py` |
| `.cursor/skills/{name}/` | `.codex/skills/{name}/` + `.agents/`, `.kilo/`, `.antigravity/`, `.gemini/` (зеркала) |
| `.cursor/rules/*.mdc` | `.codex/rules/*.md` - полный паритет, **12 пар** |
| `.cursor/mcp.env` | `.codex/mcp.env` (**одинаковые MYSQL_***) |
| `AGENTS.md` | `.codex/AGENTS.md` |
| MCP `leantime` | тот же `launch.sh`; secrets только в `.doc/skil_data/leantime/mcp/mcp.env` |

Codex **не** читает `.cursor/skills/` в рантайме. Зеркала `.agents/`, `.kilo/`, `.antigravity/`, `.gemini/` тоже служат только своим средам и правятся только генерацией из канона.

---

## Проверка после переноса

| Проверка | Ожидание |
|----------|----------|
| Kit скопирован с диска, не из пустого clone | папки `.cursor`/`.codex`/`.doc` есть |
| `.git/info/exclude` воссоздан | `git check-ignore -v .cursor/mcp.json` → exclude |
| skip-worktree на compose/FirstCest (если нужны локальные оверрайды) | `git ls-files -v` показывает `S` |
| Sibling `.config` | PHP в контейнере стартует |
| `http://localhost:{APACHE_PORT}/` | 200, ЧПУ ок |
| `.cursor/mcp.env` и `.codex/mcp.env` | свои креды, **одинаковый** MYSQL_PORT |
| MCP serena / git / mysql / CBM | connected |
| SG `sg_list_repos` | новое имя репо |
| CBM index | путь = `$Target` |
| `map-project.ps1` | `_map/file-registry.tsv` |
| gototask N (FULL) | `.doc/tasks/N/task.md` |
| e2e (если нужно) | chromedriver :9515; `.tools/codeception` smoke |
| `rg testdeploydocker` по kit | пусто (кроме rebase_project / истории) |
| `rg copytrust-dev-php` | только новое имя контейнера |

```powershell
node .cursor\scripts\test-mcp-servers.mjs   # общий smoke MCP kit (Cursor и Codex)
```

---

## Типичные ошибки

| phpstan/php-deps Error на Win Cursor | `bash`+`.sh` + путь `C:\...` | экспорт патчит `node-mcp.cmd`; Refresh MCP |
| jira-task Loading | нет контейнера со старым именем | mcp.json → своё имя + docker up |
| serena Loading долго | первый `uvx` | подождать / сеть |
| robocopy SG hang через WSL UNC | полный tree + repos-mirror | использовать [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) allowlist |
| После `git clone` нет `.cursor`/`.doc` | kit в local exclude | копировать с диска / скрипт + exclude |
| `git status` полный kit после copy | забыли `.git/info/exclude` | вставить блок exclude (П-11) |
| PHP в docker без конфигов | нет sibling `.config` | создать `../../../.config` + `prepend.php` |
| `/var/www/.config` пустой в контейнере | compose с Win UNC / неверный sibling | запуск compose из WSL; путь `<org>/.config` рядом с репо; `ls` в контейнере |
| `vendor` root-owned / Permission denied | UID/GID ≠ пользователь хоста | `id -u`/`id -g` в docker `.env`, пересоздать сервисы |
| jira/gototask docker fail | старое имя контейнера | mcp.json + gototask.ps1 |
| MySQL MCP refused | порт 8031 / рассинхрон Cursor↔Codex mcp.env | выровнять PORT |
| SG пусто | старый `repo:…/testdeploydocker$` | filter + sync-mirror |
| CBM старый проект | индекс со старого пути | `index_repository` заново |
| Playwright / Codeception no chrome | чужие пути / нет chromedriver | [browser-setup.md](./qa/browser-setup.md) |
| browser-verify / prepare-task-test | нет `.tools/codeception` или **`tests.md`** | докопировать оба |
| yadisk skill падает | нет `yadisk-fetch.ps1` (скопировали только пустой imd) | докопировать `.mcpyandexscreen/yadisk-fetch.ps1` |
| Codex prepare-plan без шаблона | не скопировался `.codex/skills/prepare-plan/assets/` | robocopy skills целиком, не только Cursor |
| task-diff пустой | subject без `{N}` | конвенция коммитов |
| Codex без MCP | нет trust / не корень | global-trust + открыть корень |
| БД `db` vs `gb_copydev5` | dist ≠ live | одно имя везде |

---

## Связи

- [Сценарий C: AI-kit only](#сценарий-c-ai-kit-only-среда-без-app) - среда MCP без Copytrust-app
- [Самодостаточность и промпт агенту](#самодостаточность-и-промпт-агенту) - что закрывает md + готовый промпт
- [Новый комп: мастер-план Day0 → green](#новый-комп-мастер-план-day0--green) - host install + единый порядок + Definition of Done
- [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) - **канон скрипта экспорта** (рядом с этим файлом)
- [rebase_project_gi.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project_gi.ps1) - локальный `.git/info/exclude` + skip-worktree (запуск из корня Target)
- [mcp.index.md](./mcp.index.md) - краткая шпаргалка CBM/SG; полный текст в [секции индексации](#mcp-индексация-cbm-и-sourcegraph)
- [export-rebase-project.ps1](../.agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1) - wrapper совместимости
- [doc_rules.md](harnes/doc_rules.md) - стандарт документации, MCP-маршрут
- [dirtree.md](./harnes/dirtree.md) - раскладка каталогов харнеса; состав в [state/02-skills.md](./harnes/state/02-skills.md), [state/03-rules.md](./harnes/state/03-rules.md), [state/04-mcp.md](./harnes/state/04-mcp.md)
- [environment-sync](../.agents/skills/harness-router/children/environment-sync/SKILL.md) - генерация зеркал адаптеров из канона `.cursor/`
- [readmy_doc.md](harnes/readmy_doc.md) - docscripts
- [Профиль CORE](#профиль-core) - docs/MCP без трекера
- [qa/browser-setup.md](./qa/browser-setup.md) - Chrome / chromedriver / Playwright WSL
- [tests.md](harnes/tests.md) - чек-лист e2e / prepare-task-test (§7-8)
- [tasks/index.md](./tasks/index.md) - индекс задач (на образце сгенерирован; на новом проекте создать скриптом)
- [`.cursor/scripts/node-mcp.cmd`](../.cursor/scripts/node-mcp.cmd) / [node-mcp.sh](../.cursor/scripts/node-mcp.sh) - лаунчеры phpstan MCP
- [`.cursor/README.md`](../.cursor/README.md) - MCP kit Cursor
- [`.codex/AGENTS.md`](../.codex/AGENTS.md) / [CODEX-CONFIG-NOTES.md](../.codex/CODEX-CONFIG-NOTES.md)
- [`.doc/skil_data/jira/README.md`](./.jira/README.md)
- [Воссоздание контейнеров с нуля](#воссоздание-контейнеров-с-нуля) - `.env` / compose / selenium / SG с чистой машины
- [`tools/docker-dev/README.md`](../tools/docker-dev/README.md) / [`tools/docker-test/README.md`](../tools/docker-test/README.md)
- [Docker Desktop: какие контейнеры нужны](#docker-desktop-какие-контейнеры-нужны) - что со скрина переносить
- [`sourcegraph-local/README.md`](../sourcegraph-local/README.md) / [`sourcegraph-local/MCP.md`](../sourcegraph-local/MCP.md)
- [`harnes/mcp/codebase-memory-mcp.md`](harnes/mcp/codebase-memory-mcp.md) - установка CBM exe

---

## Известные проблемы и ограничения

### П-1: Один документ переноса

FULL, CORE и локальная среда - этот файл (`-Profile Full|Core`). Отдельный `migrateproject.md` снят.

### П-2: Токен Sourcegraph в git / mcp.json

Не коммитить живой `sgp_local_…`. Cursor HTTP MCP: токен в headers (envFile для type:http не подхватывается).

### П-3: Hardcode docker в gototask.ps1

`DOCKER_PHP_CONTAINER` в mcp.env не подхватывается gototask - править ps1 в обоих kit.

### П-4: login-as-user

Copytrust-only; скрипт удаляет на Target; не переносить без переписывания.

### П-5: Kit не в remote

Перенос всегда с filesystem; clone origin недостаточен.

### П-6: Паритет Codex rules (решено)

Зеркала `.codex/rules/*.md` полные: **12 пар** `.mdc` ↔ `.md`, неполных пар **0** (раньше было 4 пары из 9 - устарело).

### П-7: mcp.env.example Cursor ≠ Codex

Разные дефолты портов/БД - после setup выровнять вручную.

### П-8: Codex task-doc rule (решено)

- Было: `.codex/skills/task-doc/SKILL.md` ссылался на `.codex/rules/task-doc.md`, файла не было.
- Сейчас: файл существует, пара `task-doc.mdc` ↔ `task-doc.md` синхронизирована (12/12 пар, см. П-6).

### П-9: Без `.doc/harnes/tests.md` ломается e2e-контур

- `prepare-task-test` и `browser-verify` требуют `.doc/harnes/tests.md` (§7/§8).

### П-10: Скопировали `tasks/index.md` из Copytrust

- Симптом: в индексе сотни чужих `#1146`, `#1335`, …; doc-verify V6 тянет не те задачи.
- Решение: не копировать; генерировать `build-tasks-index.ps1 -AlsoTsv` на новом проекте.

### П-11: Забыли воссоздать `.git/info/exclude` / skip-worktree

- Симптом: `git status` полный `.cursor` / `.doc`; или compose / FirstCest уезжают в commit.
- Решение: скрипт пишет exclude; skip-worktree на 4 файла вручную при локальных оверрайдах.

### П-12: Win Cursor + bash MCP (phpstan/php-deps Error)

- Симптом: на скрине MCP phpstan/php-deps красные; Open Folder = `C:\...`.
- Причина: `System32\bash.exe` = WSL, Win-путь к `.sh` не открывается.
- Решение: [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) патчит на `node-mcp.cmd`; Refresh MCP.

### П-13: Sourcegraph robocopy hang / root:600 nginx

- Симптом: экспорт зависает на `sourcegraph-local`; или PermissionDenied на nginx.conf.
- Причина: `repos-mirror` ~360M через UNC; часть conf от docker `root:600`.
- Решение: allowlist в скрипте; skip unreadable; bootstrap SG на Target.

### П-14: Корневой app `node_modules` ≠ MCP

- Не путать с `.cursor/mcp-servers/php-toolchain/node_modules`. Корневой webpack-tree (~277M) экспортом не копируется и для MCP не нужен.

### П-15: Чужие контейнеры в Docker Desktop

- Симптом: на скрине десятки групп (`laravel-saas`, `foodninja`, …); непонятно что тащить на новый ПК.
- Решение: для MCP/skills Copytrust нужны только `copytrust-dev` (+ опц. `copytrust-test`), `selenium-chrome-test`, стек `sourcegraph-local`. Остальное не копировать. См. [Docker Desktop: какие контейнеры нужны](#docker-desktop-какие-контейнеры-нужны).

### П-16: Папку контейнеров нельзя «скопировать»

- Контейнеры/образы живут в Docker Engine, не в каталоге проекта. Перенос = Docker Desktop на новом ПК + `docker compose up` из `tools/docker-*` + (опц.) `docker run` selenium + SG start. AI-kit (`rebase_project.ps1`) контейнеры не создаёт.

### П-17: На новом ПК только doc + ps1

- Симптом: скрипт есть, `.cursor` нет / MCP пустой.
- Причина: export читает полное дерево-источник; один `.ps1` без kit не создаст skills/MCP.
- Решение: [Day0](#что-нужно-до-скрипта-иначе-только-md--ps1-не-хватит) - привезти kit (export на старом ПК или zip) + clone app + host tools.

### П-18: Sibling `.config` и mount на Win/WSL

- Симптом: PHP контейнер up, сайт 500 / нет конфигов; `ls /var/www/.config` пусто.
- Причина: compose запущен с Windows по пути `\\wsl.localhost\...` или `.config` не рядом с репо.
- Решение: структура `<org>/.config` + `<org>/<project>`; `docker compose` из Linux shell в `tools/docker-dev`; проверить mount таблицей выше.

### П-19: Документ vs “one-click”

- Симптом: ожидание, что одна флешка + пустой Docker сразу дадут зелёные CBM/SG.
- Причина: бинарники host и токены не едут внутри md; volumes Leantime не в kit.
- Решение: сценарий C + [Самодостаточность](#самодостаточность-и-промпт-агенту); Host install; новый SG token; CBM exe + index.

### П-20: Второй Sourcegraph / второй CBM на новый проект

- Симптом: несколько SG на разных портах, путаница токенов.
- Решение: один SG `:7080` на машину; в каждом проекте - свой `repos.conf` entry и headers token (можно один и тот же token).

---

## История изменений

- 2026-11-11: v1.29 - путь скрипта export исправлен на `.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1`; Codeception переведён на `.tools/codeception`, канон тестов на `.doc/harnes/tests.md`; отмечены архивные `docscripts`, `synh_harnes`, `qa/browser-setup.md`; число скилов 77/76.

<!-- updated: 2026-11-03, service -->
- 2026-11-03: v1.28 - повторный экспорт не удаляет файлы Target: `rsync` и `robocopy` работают без удаления, точное зеркало включается флагом `-MirrorKit`. Перед копированием печатается сверка, после копирования пишется `.doc/.rebase-report.md`, `.doc/.rebase-report.json` и `.doc/.rebase-preserved.txt` с документацией проекта, задачами, кастомными скилами, правилами и списком перезаписанных файлов kit. `copy-dsh-kit.ps1` обновляет `.dsh` через merge, а не пересоздаёт каталоги.
- 2026-11-03: v1.27 - исправления после аудита переноса в `testmigrate`: `mysql` в каноне переведён на `${workspaceFolder}`; экспорт заменяет абсолютные пути образца на Target в `.cursor/mcp.json`, `.codex/config.toml`, `.kilo/kilo.jsonc`, `.agents/mcp.json`, antigravity-конфигах, `AGENTS.md` и `mcp.index.md`; копируются `jsondoc_scripts` и `buisnes_analis` без данных продукта; не копируются venv, `qa/tmp-runs`, `.kilo/mcp.env`; реестр компонентов очищается; must-check ловит stale-пути и запрещённые артефакты; `EXPORT_NEXT_STEPS.md` переписан как полный чеклист (секреты, имена, индексы, Codex, панель, QA, ошибки); `.codex/push-test.sh` и `.codex/run-push-test.sh` переведены с CRLF на LF и на переносимый корень; smoke `test-mcp-servers.mjs` больше не требует продуктовых файлов для CBM, serena и codegraph.
- 2026-11-03: v1.26 - перенос сервиса `copytrust-tools`: панель и просмотрщик на одном порту 8077, реестр кнопок с AJAX и прогрессом, `state` и локальные адаптеры исключены из копирования, новые файлы в must-check, `-RunSetup` вызывает `install.ps1`.
- 2026-10-30: v1.25 - перенос `task-analytics/`: код инструмента анализа диалогов Kilo (`bin`, `lib`, `config`, `schemas`, `tests`, README) добавлен в `$docDirs` и must-check; `out/` не переносится и считается на новом проекте заново. Панель `.doc/web` получила вкладку "Аналитика" и блок "Диалоги и метрики", данные читаются из `tasks/{N}/dialogs/` и `task-analytics/out/` после `scan`.
- 2026-10-29: v1.24 - `$docFiles` дополнен `harnes/doc_rules.md`, `harnes/index.md` и документами миграций; Core вырезает task-скилы и из `.kilo`; must-check проверяет `graphify-mcp-serve.sh` и документы миграций; в EXPORT_NEXT_STEPS добавлены синк сред и `graphify update .`; обертка получила `-SkipMcpMerge`.
- 2026-10-01: v1.23 - панель документации `.doc/web` (PHP, без БД): задачи из task.json с фильтром по релизу + architecture из JSON, страница задачи по модели change-report со свежестью workflow-context; перенос скриптом `rebase_project.ps1` (каталог `web` в `$docDirs`, Full и Core целиком без исключений) и ручным fallback; канон панели `.doc/web/README.md`.
- 2026-09-26: v1.22 - актуализация по сверке с диском: инвентарь 22 skills / 12 rules / 12 пар Codex (П-6, П-8 решены); адаптеры `.agents/`, `.kilo/`, `.antigravity/`, `.gemini/` и `.agents/skills/harness-router/children/environment-sync/scripts/` в раскладке, карте и новой секции [Синхронизация](#синхронизация-cursor--codex--адаптеры); skip-worktree факт (1 файл), exclude дополнен фактическими записями Kilo/cbmignore/codeception; чистка мёртвых ссылок (`verify-codex-mcp.ps1` → `test-mcp-servers.mjs`, `run-with-mcp-env.ps1` → `.sh`, `tasks-571-audit/`, несуществующие корневые файлы `.doc/`); DoD + xdebug/leantime; mysql MCP через `run-with-mcp-env.sh` + `mysql-mcp-proxy.mjs`; CORE = 14 skills с оговоркой про невырезаемые task-скилы; Kilo без Ollama; переименован дубль заголовка "MCP: Windows vs WSL"; задача 176 папок в `.doc/tasks/`.
- 2026-07-22: v1.21 - export **merge MCP**: kit добавляет `sourcegraph`/`leantime`; Target-only (`laravel-boost`, `graphify`, …) сохраняются (бэкап `.doc/.rebase-mcp-backup/`); `-SkipMcpMerge` отключает.
- 2026-07-22: v1.20 - сценарий **C AI-kit only**, DoD C, таблица “один раз на машину”, самодостаточность + готовый промпт агенту, Day0 A/B/C, П-19/П-20.
- 2026-07-22: v1.19.1 - Leantime export **с** `docker/.env`, `mcp/mcp.env`, access, bearer (полный стенд); must-check требует эти файлы.
- 2026-07-22: v1.19 - `.doc/skil_data/leantime` (compose + MCP daniel-eder) и `kaiten/doc.md` в карте переноса; MCP `leantime` в инвентаре; Day0/День1/Docker/export/CORE; уточнены doc-skills без новых папок.- 2026-07-18: v1.18 - секция [MCP: индексация CBM и Sourcegraph](#mcp-индексация-cbm-и-sourcegraph) + [mcp.index.md](./mcp.index.md) (из audit Target).
- 2026-07-18: v1.17 - [rebase_project_gi.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project_gi.ps1): локальный exclude + skip-worktree из корня Target.
- 2026-07-18: v1.16 - `migrateproject.md` слит в [Профиль CORE](#профиль-core); файл удалён; Core export без migrateproject / без task-doc rule.
- 2026-07-18: v1.15 - аудит нового ПК: шаблон `prepend.php`, UID/GID, Playwright Win/WSL примеры, mount UNC (П-18), EXPORT_NEXT_STEPS → Day0.
- 2026-07-18: v1.14 - мастер-план **Day0 → green** (host install, два сценария, DoD smoke, политики vendor/SG/skills); аудит нового компа.
- 2026-07-18: v1.13 - секция «Воссоздание контейнеров с нуля»: `.env` docker-dev/test, selenium `docker run`, SG start, связка mcp.env/jira-task, `docker ps` сводка.
- 2026-07-18: v1.12 - «День 1» расширен: шпаргалка + примеры Jira/mcp.env/SG repos.conf/jira-task; SG не авто-add явно.
- 2026-07-18: v1.11 - секция «День 1: куда что прописать» (SG не авто-add, Jira/mcp.env/repos.conf/smoke).
- 2026-07-18: v1.10 - Docker Desktop: карта контейнеров со скрина (нужны / не нужны), selenium-chrome-test, чеклист другого ПК, П-15/П-16; skills↔контейнеры.
- 2026-07-18: v1.9 - канон скрипта [rebase_project.ps1](../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) рядом с md; wrapper в docscripts; полная матрица MCP/Win/WSL/runtime; П-12..П-14; must-check расширен.
- 2026-07-18: v1.8 - Win Cursor: `node-mcp.cmd` + патч mcp.json; корневой app `node_modules` не для MCP.
- 2026-07-18: v1.7 - SG allowlist Copy-Item; skip root:600 nginx; must-check PASS ~137M.
- 2026-07-18: v1.6 - SG + runtime deps по умолчанию; матрица в EXPORT_NEXT_STEPS; opt-out Skip*.
- 2026-07-18: v1.5 - первый export-скрипт в docscripts; BOM; must-check; stub architecture.
- 2026-07-17: v1.4 - exclude + skip-worktree + sibling `.config`.
- 2026-07-17: v1.3 - полная карта `.doc/`; политика `tasks/index.md`; skills 15.
- 2026-07-17: v1.2 - матрица must-copy, `tests.md`, yadisk-fetch.
- 2026-07-17: v1.1 - kit вне git, docker, codeception, env, Codex trust.
- 2026-07-17: v1.0 - первичный инвентарь.
