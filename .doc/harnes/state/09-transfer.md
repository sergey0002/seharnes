# Устаревший снимок переноса kit (rebase)

<!-- meta
type: architecture
status: outdated
updated: 2026-10-29
related: [../index.md, ./01-canon-envs.md, ./04-mcp.md]
tags: [harness, transfer, rebase, export, docker]
-->

---

## Суть

Этот файл сохраняет исторический снимок процедуры переноса kit от 2026-10-29.
Его команды, профили и состав файлов устарели и не являются инструкцией для новых
переносов. Текущая операционная карта находится в
[state/14-project-migration.md](./14-project-migration.md), исполняемая процедура
в [rebase_project.md](../../rebase_project.md), а актуальный entrypoint - в
[скиле new-project](../../../.agents/skills/harness-router/children/new-project/SKILL.md).

Не исправляй этот исторический снимок синхронно с текущим кодом. Обновляй только
ссылки на него и явную пометку outdated.

---

## 1. Профили и сценарии

Два профиля export:

| Профиль | Когда | Состав |
|---|---|---|
| FULL | Jira плюс git-ветки плюс PHP, Docker, e2e | Весь kit, gototask, task-diff, jira-task, docker-dev (плюс docker-test и codeception), опционально Leantime. После вырезки Copytrust-only остается 21 скил |
| CORE | Другой проект, только docs плюс MCP | Без трекера и task-скилов. Остается 15, но скрипт режет только 8, часть task-тяготеющих скилов удалить вручную (см. раздел 11) |

Три сценария развертывания:

| Сценарий | Состав |
|---|---|
| A: тот же app | Copytrust на новой машине: kit плюс docker плюс SG плюс CBM |
| B: другой app | Full или Core: kit плюс search-replace имен плюс своя архитектура |
| C: AI-kit only | Среда без app: MCP плюс skills, без mysql, jira и gototask |

Один SG-стек и один CBM-бинарь на машину, не дублировать на проект. Kit
(`.cursor` плюс `.codex` плюс `.doc`) на каждый проект. Не переносится: чужие
`tasks/{N}`, содержимое architecture Copytrust, живые токены, volumes Leantime.

Сценарий C (AI-kit only): цель Cursor MCP и skills как на образце (serena, git, CBM,
Sourcegraph, playwright, phpstan и php-deps, semgrep, context7, опц. leantime).
Не цель: сайт Copytrust, mysql MCP к app-БД, jira-task, gototask. Когда: флешка или zip
с Target после export (профиль Core предпочтительно), новый Win с пустым Docker,
в корне уже есть или будет код другого проекта для индексации (app compose Copytrust
не нужен). Один раз на машину: Docker Desktop, Node, uv и uvx, Chrome, Cursor,
CBM exe в `%LOCALAPPDATA%\Programs\codebase-memory-mcp\`, Sourcegraph стек `:7080`
(шарить, один на машину в `sourcegraph-local/` любого доверенного kit, в каждом проекте
только token плюс строка в `repos.conf`), AI-kit на проект, CBM `index_repository`
на корень проекта, SG register репо на имя. Не поднимать второй SG и второй CBM-бинарь.
Чеклист агента C: host install (без Node, uv, CBM exe MCP не зеленые); Open Folder
корень Target с kit, `.doc\rebase_project_gi.ps1` если есть `.git`, не родитель `<org>/`;
search-replace имен под проект; Win Cursor убедиться что phpstan и php-deps
на `node-mcp.cmd` (export патчит), иначе Error; Sourcegraph если `:7080` уже up
не второй стек, иначе поднять с нуля, новый Access token в mcp.json headers;
`repos.conf` плюс sync плюс register этого корня (SG сам репо не добавит); CBM exe
есть Reload MCP плюс `index_repository` на абсолютный путь корня; Reload Window,
зеленые serena, git, sourcegraph, codebase-memory-mcp, playwright, context7, semgrep,
phpstan, php-deps, xdebug, leantime после compose up (mysql и jira могут быть Error
или disabled, для C это OK); опц. Leantime `cd .doc/skil_data/leantime/docker && docker compose up -d`
(volumes пустые, UI и API key в access). Явно не делать в C: sibling `.config`,
copytrust-dev и test, selenium, Jira `config.env`, gototask smoke, копирование
`tasks/{N}` и architecture-контента Copytrust. DoD C: host команды есть
(`docker version`, `node -v`, `uvx --version`, CBM `--version`); Cursor MCP serena, git,
sourcegraph, codebase-memory-mcp, playwright, phpstan, php-deps не Error;
`sg_list_repos` и keyword search видно это репо; CBM `index_status` и `search_graph`
индекс этого корня; mysql и jira-task могут быть disabled или Error, не блокер;
нет `.doc/tasks/{N}` из Copytrust, architecture stub свой.

Master-план Day0 в green (чистая Windows плюс WSL2). До скрипта нужно: источник AI-kit
(полное дерево образца с `.cursor`, `.codex`, `.doc` на USB, zip, сети, или готовый
Target после export на старом ПК; один `rebase_project.ps1` без kit-дерева ничего
не скопирует); код приложения (для A и B `git clone` с `tools/docker-dev`, для C
не обязателен Copytrust, нужен любой корень под индекс); host tools (см. ниже);
Cursor и опц. Codex (Open Folder корень с kit плюс app если A и B). Порядок A и B:
`git clone` app (B: или код другого репо), export или копия Target, sibling
`<org>/.config`, Day0 в green полный. Порядок C: kit на флешке, app Copytrust не нужен,
export лучше Core, пропуск sibling, чеклист C. Нельзя A и B: открыть пустой Target
только с kit и ждать mysql и jira, без app compose контейнеров нет. Можно C: kit плюс
host tools плюс SG плюс CBM без php-apache.

Day0 host install (Windows, часть в WSL): Docker Desktop (docker.com, WSL2 backend,
Start on login); Git (git-scm.com или winget); Node.js 20 плюс (nodejs.org или winget);
uv и uvx (docs.astral.sh); codebase-memory-mcp UI (Win `install.ps1 --ui`
в `%LOCALAPPDATA%\Programs\codebase-memory-mcp\`, WSL UI linux amd64 в `~/.local/bin`
плюс tmux); PowerShell (Win PS 5.1 плюс встроен или pwsh); PHP 8.3 плюс Composer
(Laragon или windows.php.net плюс Composer, или только через docker PHP); Chrome
(обычный или Chrome for Testing, см. `qa/browser-setup.md`); Cursor (cursor.com,
удобнее Open Folder `C:\...` с Win-лаунчерами, WSL Remote дает bash плюс `.sh`).
Проверка host: `docker version`, `node -v`, `npx -v`, `uvx --version`, CBM `--version`.

Единый чеклист Day0 в green (для C шаги 3-7, 12 и mysql и jira в DoD пропуск,
вместо этого чеклист C и DoD C; шаблоны секретов можно создать заранее, MCP зеленый
только после host tools плюс для A и B Docker app, для всех SG плюс CBM): 0 host
install; 1 kit плюс для A и B clone app, `rebase_project_gi.ps1`; 2 Open Folder корень,
Reload; 3 sibling `.config/`; 4 copytrust-dev up; 5 `.cursor/mcp.env` плюс `.codex/mcp.env`
с MYSQL; 6 имя PHP в mcp.json jira-task плюс gototask; 7 `.doc/skil_data/jira/config.env` Full;
8 search-replace имен; 9 Sourcegraph `:7080` плюс token плюс repos.conf; 10 CBM
`index_repository`; 11 Playwright paths; 11a опц. Leantime; 12 опц. e2e selenium
и docker-test; 13 Codex trust; 14 DoD полная или DoD C. Если Target `C:\...`
и копировали вручную без скрипта: прогнать export еще раз или вручную поставить
`node-mcp.cmd` в mcp.json, иначе phpstan и php-deps Error.

DoD полный стенд A и B: `docker ps` есть `{project}-dev-php-apache-1`
и `{project}-dev-mysql-1`; `curl -sI http://127.0.0.1:8030/` (или свой порт) HTTP 200
и 302; Cursor Settings MCP mysql, jira-task, sourcegraph, serena, git, phpstan, php-deps,
CBM, xdebug, leantime не Error; MySQL MCP `list_tables` таблицы своей БД; `sg_list_repos`
новое имя репо; gototask и обнови таск N дает `.doc/tasks/{N}/task.md`; CBM `index_status`
и search_graph проект проиндексирован; опц. e2e `curl -s http://127.0.0.1:4444/status`
или chromedriver `:9515`. Опц. после Node: `node .agents\skills\harness-router\children\mcp-audit\scripts\test-mcp-servers.mjs`.

Политики которые раньше путали: AI-kit only против app (C не требовать php-apache,
mysql, jira; A и B полный DoD); один SG и один CBM exe (на машину один раз, в каждом
проекте token плюс repos.conf плюс index_repository, не плодить второй стек);
codeception vendor (Full-скрипт копирует `.doc/codeception/vendor`, ручной robocopy
без vendor потом `composer install` в `.doc/codeception`, оба ок); node_modules
(корневой app webpack не копировать, MCP нужны `.cursor` и codex `mcp-servers/php-toolchain/node_modules`
плюс `tools/vendor`, скрипт Full копирует); Sourcegraph с нуля (для green MCP на новом
ПК из WSL `./start-single.sh` проще или полный `./start.sh` плюс upstream как на образце,
export не тащит `upstream/`, clone один раз если полный стек, токен в Cursor mcp.json
headers); skills count (образец 22, Full-export удаляет login-as-user плюс
serpanalise-report, итого 20); `.config/prepend.php` (только A и B, структура
обязательна, шаблон в каноне раздел sibling); UID и GID в docker `.env` (на Linux и WSL
`id -u` и `id -g`, на чистом Win плюс Docker Desktop часто хватает 1000); корень
Open Folder (Cursor Open Folder git и kit root, не родитель `<org>/`); Leantime volumes
(env на флешке есть, данные MySQL в named volumes нет, после up на новом ПК БД пустая
пока не install или не перенесен volume).

---

## 2. Локальный git exclude и skip-worktree

Главный ответ почему clone пустой по AI-kit. Два локальных механизма (оба не уезжают
в Bitbucket): exclude (`.git/info/exclude`, только на этой копии, untracked пути
не видны `git status` и не попадут в add); skip-worktree (`git update-index
--skip-worktree`, флаг локальный, tracked файл есть в remote, но локальные правки
git игнорирует); плюс sibling configs (`../.config/` рядом с репо, вне репо, PHP Docker
mount). После `git clone` на новой машине нет exclude, нет skip-worktree, нет kit
на диске. Нужно: скопировать деревья с диска, заново прописать exclude, при
необходимости выставить skip-worktree.

### 2.1. Локальный каталог `.tools/`

С 2026-11-05 локальный dev-инструментарий лежит в `.tools/` и целиком игнорируется строкой `/.tools/`.
Экспорт `rebase_project.ps1` копирует безопасный набор `.tools`: `docker-dev/compose.yaml`, `docker-dev/php-apache`, `php74`, `php85-scan`, `codeception/tests/_envs`.
Не копируются машинные `.env`, `dump.sql`, `vendor`, `_output`, `__pycache__` и данные MySQL.
Флаг `-SkipTools` отключает перенос набора.
Блок exclude, который пишут `rebase_project.ps1` и `rebase_project_gi.ps1`, содержит `/.tools/` и legacy-пути `/tools/...` для проектов со старой раскладкой.
Скилы `disposable-db.sh` и `static-on-diff.py`, а также php-toolchain ищут `.tools/` и откатываются на `tools/`, поэтому kit работает в проектах с обеими раскладками.

Полный `.git/info/exclude` образца (канон для копии): `/.cursor/`, `/.codex/`,
`/.agents/`, `/.kilo/`, `/.doc/`, `/.serena/`,
`/.playwright-mcp/`, `/AGENTS.md`, `/php_error.log`, `kilo.json`, `/.tools/`,
docker-dev local overrides (`/tools/docker-dev/README.md`, `compose.yaml`,
`/tools/docker-dev/php-apache/Dockerfile`, `/tools/docker-dev/php-apache/apache/`),
Sourcegraph local stack (`/sourcegraph-local/`), CodeGraph index (`/.codegraph/`),
CodePrism index (`~/.local/share/codeprism/`),
legacy Graphify (`/graphify-out/`),
Local Codeception admin credentials
(`/tools/codeception/tests/Acceptance/FirstCest.php`), Kilo Code agent worktrees
(`.kilo/worktrees/`), Kilo Agent Manager state (`.kilo/agent-manager.json`), Kilo setup
script варианты (`.kilo/setup-script` плюс расширения), Local Codeception suite edits
(`/tools/codeception/tests/`, working copy `.doc/codeception`), Codebase-memory ignore
(root и plain `.cbmignore`).

Ценность что переносить: `.cursor/` около 60M плюс критично (MCP, rules, skills, setup),
да без живого `mcp.env`, с `mcp-servers/php-toolchain/node_modules` и `tools/vendor`
(runtime MCP); `.codeprism.toml` локальный, в git не коммитится и на Target создается заново (языки, исключения, security); `.codex/` аналогично; `.doc/` до 1.4G сырой критично стандарт плюс инфра,
tasks и architecture контент нет, выборочно по карте, без `.venv`, `imd`, `tasks/{N}`,
с `codeception/vendor` для тестов; `.serena/project.yml` мал важно (языки LSP), да без
`cache/` (около 27M), `memories/`, `project.local.yml`; `AGENTS.md` 1K важно (вход Cursor,
не путать с каталогом-зеркалом `.agents/`); `sourcegraph-local/` около 378M сырой важно
стек SG, скрипты плюс config мал, без `repos-mirror` (около 360M), `backups`, `upstream`,
живых токенов; корневой `/node_modules` около 277M webpack и Vue приложения не для MCP,
не копировать экспортом; `.kilo/`, `kilo.json` около 120M с nm опционально
только если нужен Kilo, без `node_modules`; `.agents/skills` канон скилов
(28 skills), `.agents/rules` и `mcp_config.json` генерируются из `.cursor/` через
synh_harnes; `.playwright-mcp/` около 4M кеш скринов MCP не копировать; `php_error.log`
мусор; `tools/docker-dev/compose.yaml` (плюс README, Dockerfile, `php-apache/apache/`)
мал критично для стенда (mount `../../../.config`, порты), в remote есть, локальный
skip-worktree перенести диффом при отличии, экспорт kit не тащит `tools/docker-*`;
`tools/codeception/.../FirstCest.php` мал логин админа в тесте (есть пароль),
локальные креды, не коммитить, на новом проекте свой логин плюс skip-worktree.

skip-worktree факт на образце: сейчас один файл (`git ls-files -v | findstr /B "S "`):
`S tools/docker-dev/compose.yaml` (локально монтирует sibling `.config`, ценная правка
стенда; раньше флаги стояли и на FirstCest.php, README.md, Dockerfile php-apache,
сняты; в exclude пути остались как защита от случайного `git add`). На новом проекте
после адаптации: `git update-index --skip-worktree tools/docker-dev/compose.yaml`,
при локальных кредах в тесте плюс FirstCest.php, проверка `git ls-files -v | findstr /B "S "`.

Sibling вне репо (тоже локальное, не в exclude): `<org>/.config/` (prepend.php, .env,
.secrets.env, mount Docker), `start.bat`, human docs txt, `<project>/` git root.
Без `.config` PHP-контейнер не поднимется как на стенде. Перенести структуру (секреты
заполнить заново).

После копирования kit сразу заблокировать снова. Скрипт предпочтительно из корня Target:
`cd C:\path\to\project`, `powershell -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project_gi.ps1`
(перезаписать exclude `-Force`, без skip-worktree `-NoSkipWorktree`). Канон скрипта
`rebase_project_gi.ps1` пишет `.git/info/exclude` и по умолчанию skip-worktree
на compose и FirstCest если файлы tracked. Вручную: вставить в `$Target/.git/info/exclude`
блок exclude выше (пути те же, docker-dev и FirstCest строки оставить даже если файлы
tracked, защита от случайного `git add` после untrack); выставить skip-worktree
на файлы с локальными оверрайдами (на образце сейчас только compose.yaml, плюс
FirstCest.php если там локальные креды); проверка `Set-Location $Target`,
`git check-ignore -v .cursor/mcp.json .doc/doc_rules.md AGENTS.md sourcegraph-local/README.md`
(ожидаются строки из exclude), `git status --short | Select-String -Pattern '^\?\? \.cursor|^\?\? \.doc|^\?\? AGENTS'`
(пусто exclude работает). Внутри kit свои `.gitignore` (например `.cursor/.gitignore`
игнорит `mcp.env`, `node_modules`, `tools/vendor`), едут вместе с папками.

Кратко kit не в git: `git clone` с Bitbucket не принесет AI-kit. Перенос filesystem copy
плюс recreate `.git/info/exclude` плюс skip-worktree. В git origin: код приложения,
`tools/docker-test`, часть `tools/docker-dev` и codeception как tracked. Только локально:
`.cursor/`, `.codex/`, `.doc/`, `.serena/`, `AGENTS.md`, `sourcegraph-local/`, опц. Kilo,
локальные оверрайды compose и FirstCest через skip-worktree, sibling `<org>/.config/`.

---

## 3. Раскладка каталогов на машине

`<org>/` (например copytrust): `.config/` вне репо mount в PHP-контейнер (prepend.php,
.env, .secrets.env), `start.bat` опц. human bootstrap, `<project>/` корень репо.
Корень репо: `AGENTS.md`; `.cursor/` (mcp.json вкл. leantime, rules 37,
scripts, setup.ps1); `.codex/` (config.toml, AGENTS.md, skills, go-task.ps1, task-diff.ps1);
`.agents/` канон скилов (28 skills), `.agents/rules` и `mcp_config.json` генерируются;
`.kilo/` правила и kilo.jsonc, скилы читает из `.agents` (node_modules не копировать);
`.serena/project.yml`; `.doc/` (doc_rules.md, readmy_doc.md, tests.md, rebase_project.md
плюс ps1 и _gi.ps1, docscripts с map-project и build-tasks-index, `.jira/` с server.php
плюс config.env локально, `.content-extractor/`, `.xml-river/`, `.mcpyandexscreen/`
с кешем imd, `web/` панель документации порт 8077 PHP без БД export
целиком, `leantime/` PM Docker `:8095` плюс MCP export с .env, mcp.env, access,
`kaiten/doc.md` research API не runtime, `qa/` index fragments browser-setup flows,
`codeception/` agent suite Full-export с vendor, `architecture/` каркас index плюс _map
контент с нуля, `.obsidian` не копировать, `tasks/` пусто плюс _map, index.md не копировать
генерировать); `sourcegraph-local/` или один инстанс на машину; `tools/` (docker-dev
8030 и 8031, docker-test 8230 и 8231 плюс soap, codeception продуктовый suite в git);
`.htaccess`; `.env` и `.env.testing`. Compose в `tools/docker-dev` монтирует конфиги
как `../../../.config` (то есть `<org>/.config`). Без sibling `.config` PHP-приложение
в контейнере не поднимется как на стенде.

---

## 4. Инвентарь AI-kit

Cursor rules `.cursor/rules/` (12): text-style always да; doc-rules always да ссылка
на bitbucket-tasks; bitbucket-tasks always частично (Jira `CT-{N}`, SG filter,
`release/5.6.0.6`, имя файла legacy, содержимое Jira плюс git); project-doc
agent-requestable да SG testdeploydocker; project-doc-indexing agent-requestable да;
task-doc agent-requestable частично SG filter; prepare-plan agent-requestable частично
CT-N и export-task; yadisk-screenshot agent-requestable да; doc-verify agent-requestable
частично SG filter; harness-improvement agent-requestable да; test-task
agent-requestable частично (оркестратор, chromedriver policy, стенд Copytrust).
Codex rules полное зеркало 11 пар `.mdc` в `.md`, неполных пар 0, при правках rules
синхронизировать все пары, зеркала остальных сред через synh_harnes.

Skills зеркало `.agents/skills/` в `.codex/skills/` 23 в 23. Добавлены после 2026-07-17:
git-task-blame, harness-improvement, jira-report, send-to-git,
task-change-report, test-task. Документационные: project-doc, doc-verify, task-doc,
prepare-plan. Нюансы переноса: project-doc Cursor SKILL полный, batch через docscripts
плюс file-registry, CBM и SG при SECTION; doc-verify Cursor SKILL в канон Codex
`skills/documentation-router/children/doc-verify/SKILL.md` (must copy Codex tree); task-doc FULL,
после правок build-tasks-index.ps1, rule только в Cursor; prepare-plan Codex обязательны
`assets/` плюс `references/`, Cursor часто только SKILL.md. Профили: project-doc CORE
плюс FULL (docscripts, architecture, SG filter); doc-verify CORE плюс FULL (CBM плюс SG
плюс serena, Codex reference.md); prepare-plan CORE плюс FULL (CT-N и export, Codex
assets плюс references); task-doc FULL (tasks, build-tasks-index.ps1); gototask FULL
(`.doc/skil_data/jira/`, config.json, scripts ps1); task-diff FULL (task-diff.ps1 плюс Codex
wrapper); task-code-review FULL (agents openai.yaml внутри skill); prepare-task-test FULL
(`.doc/qa/` плюс `.doc/codeception/` плюс `.doc/tests.md`); browser-verify FULL плюс e2e
(то же плюс `qa/browser-setup.md` плюс Chrome); login-as-user Copytrust-only
(`qa/fragments.md` плюс docker-test, не переносить без переписывания); page-content
CORE плюс FULL (`.doc/skil_data/page-content/` плюс extract-page-content.ps1); xmlriver
CORE плюс FULL (`.doc/skil_data/xmlriver/` плюс invoke-xmlriver.ps1); serp-study CORE плюс FULL
(xmlriver плюс page-content плюс study-serp.ps1); yadisk-screenshot CORE плюс FULL
(`.agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1` плюс пустой imd); serpanalise-report
опционально (`.doc/skil_data/serpanalise-report/` плюс scripts skill);
git-task-blame FULL (`git log -L`, проверка веток origin, риск конфликта);
codeprism CORE плюс FULL (пакет `codeprism-ai`, venv `.cursor/tools/codeprism-ai`,
индекс в user-data строится на Target);
harness-improvement CORE плюс FULL (component_registry.json плюс parity-проверки);
jira-report FULL (collect-shots.py, стиль Sergey0002); send-to-git FULL (выполнение
только после явного да); task-change-report CORE плюс FULL (generate_report.py плюс
report-model.json); test-task FULL (оркестратор resolve в impact в Cest в browser-verify
в отчет раздел 8). Скрипты skills копируются вместе с папкой skill (robocopy skills).
Codex wrappers: `.codex/go-task.ps1`, `.codex/task-diff.ps1`. Асимметрия деревьев
(не баг переноса): prepare-plan assets и references есть в Codex обязательны,
в Cursor нет только SKILL.md; doc-verify reference.md есть в Codex, в Cursor нет
(Cursor SKILL ссылается на Codex); rules task-doc пара есть и синхронизирована.

Корневые инструкции: `AGENTS.md` Cursor; `.codex/AGENTS.md` Codex (канон плюс anti-loop);
`.codex/config.toml` Codex MCP runtime; `.codex/CODEX-CONFIG-NOTES.md` global против
project config; `.codex/global-trust.snippet.toml` фрагмент для `%USERPROFILE%\.codex\config.toml`;
`.codex/codex-sale/` опциональный прокси desktop Codex (Windows).

MCP-серверы portable-правки: serena да (`.serena/project.yml`); git да (workspace);
context7 да; semgrep да; mysql да (`mcp.env` в `MYSQL_*` порт стенда, запуск через
`scripts/run-with-mcp-env.sh` плюс `mysql-mcp-proxy.mjs` релея listen `127.0.0.1:3306`
в target `MYSQL_PORT` образец 8031); phpstan-mcp и php-deps-mcp PHP (`PHP_BIN`,
`DOCKER_PHP_CONTAINER`, `setup.ps1` в composer `.cursor/tools` и `.codex/tools`);
codebase-memory-mcp да (бинарь вне git, `index_repository` на новый корень); codeprism
да (venv `codeprism-ai` вне git, создается заново, индекс в user-data строится
`codeprism index .`); sourcegraph
да (токен, filter `repo:^.../{имя}$` в rules и skills); playwright да
(`PLAYWRIGHT_MCP_EXECUTABLE_PATH`, `CHROME_PATH`, `LD_LIBRARY_PATH`); jira-task FULL
(docker container плюс путь `/var/www/html/.agents/skills/task-router/children/jira/scripts/server.php`); bitbucket-task legacy
(`disabled: true`); leantime опц. CORE плюс FULL (`bash` плюс `.agents/skills/task-router/children/leantime/scripts/launch.sh`,
secrets в `.doc/skil_data/leantime/mcp/mcp.env` не kit `mcp.env`, контейнер `:8095`); xdebug
опционально свой Xdebug; deepwiki обычно off. Скрипты kit факт на диске: Cursor
`.cursor/scripts/` и Codex `.codex/scripts/` (codebase-memory-mcp-launch.sh плюс cmd,
codebase-memory-mcp-ui.sh, node-mcp.sh плюс cmd, run-with-mcp-env.sh плюс mysql-mcp-proxy.mjs,
php-docker.cmd, js, ps1, sh, test-mcp-servers.mjs). Проверка MCP после переноса общий
`node .agents\skills\harness-router\children\mcp-audit\scripts\test-mcp-servers.mjs` (работает для обоих kit, отдельного
Codex-verify скрипта нет). Корень kit: оба `setup.ps1`, Codex еще go-task.ps1,
task-diff.ps1, `lib/kit-root.ps1`. Также входят в robocopy kit: `mcp-servers/php-toolchain/`
(после copy `npm install` если без `node_modules`), `tools/` (внутри composer.json,
phpda.yml.example, vendor через setup.ps1), composer-php-tools.json, README, recommendations.md,
sourcegraph-mcp.md и `rules/mcp/codebase-memory-mcp.mdc`. Опционально не критично: push-test.sh,
run-push-test.sh.

Документация `.doc/` что копировать: doc_rules.md, readmy_doc.md, rebase_project.md
(плюс ps1, _gi.ps1), mcp.index.md, tests.md; docscripts все ps1 и _lib.ps1; `.content-extractor/`
(без `.venv`, `out_*.json`); `.xml-river/` (без `.env`, cache, logs, output);
`.mcpyandexscreen/` как README плюс пустой imd; скрипт в
`.agents/skills/yadisk-screenshot/scripts/`; `.jira/` без
config.env (FULL); leantime целиком compose плюс `docker/.env` плюс `mcp/mcp.env`
плюс access плюс bearer (секреты Leantime нужны для переноса стенда); kaiten doc.md
опц. research; `qa/` (index, fragments, browser-setup, flows); codeception (FULL плюс e2e,
Full-скрипт с vendor, иначе composer install); `web/` целиком панель документации
(PHP, без исключений); каркас создать пустым architecture и _map, tasks, tasks и _map,
qa и reports. prepare-task-test и browser-verify без `.doc/codeception/` и без
`.doc/tests.md` не работают. `tools/codeception` отдельный продуктовый suite (в git).
docscripts полный список все нужны: _lib.ps1, map-project.ps1, get-indexing-batch.ps1,
mark-noise.ps1, validate-docs.ps1, sync-docs.ps1, audit-docs.ps1, generate-doc-index.ps1,
generate-file-registry.ps1, get-verify-batch.ps1, mark-verify-done.ps1,
find-related-tasks.ps1, build-tasks-index.ps1, плюс вспомогательные _batch-ai-links.py,
_fix_indexed_files_order.py, _restore_cicd_from_transcript.py. Не копировать:
architecture `*.md` контент старого кода (кроме каркаса ниже); содержимое `tasks/{N}/`,
`tasks/index.md` со старыми задачами; serpanalise, `.seoq/`, Stagehand,
releases, tmp, backups; корневые `5.7.*.md`, аудиты, SQL-дампы, developer_guide и прочие;
`gb_copydev5.sql`, Методика PDF (плюс Zone.Identifier).

---

## 5. Полная карта `.doc/` (факт на диске 2026-09-26)

Каждый top-level элемент учтен. Skills 22 в Cursor и Codex (зеркала остальных сред
генерируются). Ключевое в `.doc/`: leantime (локальный PM плюс MCP), kaiten (research API),
каноны harnes (tests, testaudit, jsondoc, readmy, readmy_doc) плюс synh_harnes (генерация зеркал).

Каталоги: docscripts копировать (project-doc, doc-verify, task-doc, map и validate);
`.jira/` копировать без config.env (gototask, MCP jira-task); `.bitbucket/` только если
legacy BB (MCP bitbucket-task обычно skip); `.content-extractor/` копировать без .venv
и cache (page-content, serp-study); `.xml-river/` копировать без .env и cache, logs,
output (xmlriver, serp-study); `.mcpyandexscreen/` копировать README,
imd пустой, скрипт едет в `.agents/skills/yadisk-screenshot/scripts/`; `web/` копировать целиком код панели без исключений
(панель документации задачи плюс architecture из JSON, порт 8077, см. `web/README.md`);
leantime копировать целиком compose, .env, mcp.env, access, bearer, docs (локальный PM
плюс MCP leantime); kaiten копировать doc.md research (справка по Kaiten API, не runtime);
synh_harnes копировать вручную (нет в `$docDirs` скрипта, генерация зеркал адаптеров
из канона `.cursor/`: sync-agent-views.sh, generate-agent-configs.py, generate-mcp-config.py,
parity-report.json, см. раздел 12); `qa/` копировать (browser-verify, prepare-task-test,
login-as-user); codeception копировать Full-скрипт плюс vendor, ручной путь без vendor
в composer (browser-verify, prepare-task-test); architecture не копировать контент `*.md`,
создать каркас index.md, _priority.md, _map (`_context-base.md` создает project-doc
bootstrap); `architecture/.obsidian/` не копировать (Obsidian vault старого проекта,
при необходимости создать заново); tasks не копировать `{N}/`, пустая папка плюс _map;
`tasks/{N}/` запрещено копировать (чужие задачи Copytrust); `tasks/index.md` не копировать
(см. ниже, только генерация); `tasks/_map/file-to-tasks.tsv` не копировать (пишет
build-tasks-index.ps1 -AlsoTsv); serpanalise опционально (skill serpanalise-report);
`.seoq/` не копировать
(SEO-пайплайн Copytrust); Stagehand не копировать (локальные эксперименты); releases
не копировать (релизные артефакты); tmp не копировать (временные JSON и MD); backups
не копировать (локальные бэкапы); jsondoc_scripts опционально без runs и state (pipeline
jsondoc jsondoc.py, schemas); optimizeform, preza, testanalyze,
`5.7.3test/` не копировать (артефакты Copytrust).

Корневые файлы `.doc/*.md`: doc_rules.md, rebase_project.md (плюс ps1,
_gi.ps1), mcp.index.md копировать (это `$docFiles` скрипта); все каноны harnes
(tests, testaudit, jsondoc, readmy, readmy_doc) - отдельными записями `$docFiles`,
каталог `.doc/harnes` создает скрипт;
jsondoc.md в harnes/; auditplan.md в harnes/plan/; deploytask.md и gitverce.md
jsondoc.md в harnes/; auditplan.md в harnes/plan/; deploytask.md и gitverce.md
перенесены в architecture/ рядом с cicd; `5.7.1.md` - `5.7.4.md`, mail.md, speedform.md, optim.md,
documentation_audit.md, developer_guide.md, `qauth_new!.md`, `tz_cursor_setup_*.md`,
`tmp-deploy-710c1ec.yml` не копировать (артефакты Copytrust); `gb_copydev5.sql`,
Методика PDF (плюс Zone.Identifier) не копировать.

`.doc/tasks/index.md` отдельно и обязательно: это сгенерированный индекс, не ручной
документ. Пишет `build-tasks-index.ps1`. Читают skill task-doc (шаг B4.5), rule
task-doc.mdc, skill doc-verify (V6 плюс find-related-tasks.ps1). С -AlsoTsv еще
`.doc/tasks/_map/file-to-tasks.tsv`. На образце 176 числовых папок `.doc/tasks/{N}`
(задачи Copytrust). Копировать index.md и file-to-tasks.tsv нельзя, утащите чужой реестр.
На целевом: создать пустые `.doc/tasks/` и `.doc/tasks/_map/`; появятся первые
`{N}/task.md` (gototask или вручную); запустить
`powershell -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1 -AlsoTsv`;
появятся свежие tasks и index.md плюс file-to-tasks.tsv уже по новым задачам. Пока задач
нет index.md может отсутствовать, нормально. Не класть stub из Copytrust.

---

## 6. Матрица skill и rule в обязательные пути

Сверка: если skill в профиле FULL и CORE есть, пути в колонке Must copy должны оказаться
на целевом диске. Все always rules `.cursor/rules/*.mdc` (12 файлов). Codex rules
`.codex/rules/*.md` (12 пар, паритет полный). project-doc: `.doc/doc_rules.md`,
docscripts, AGENTS; создать architecture index.md, _context-base.md, _priority.md, _map.
prepare-plan: skill, Codex assets плюс references, doc_rules, architecture index; планы
в tasks. task-doc: skill, `docscripts/build-tasks-index.ps1`, Cursor rules task-doc.mdc;
создать tasks, tasks и _map, tasks и index.md генерировать не копировать. doc-verify:
`docscripts/get-verify-batch.ps1`, mark-verify-done.ps1, find-related-tasks.ps1,
build-tasks-index.ps1, Codex `skills/documentation-router/children/doc-verify/SKILL.md`; создать
`architecture/_map/verify-registry.tsv`, для V6 нужен актуальный tasks и index.md
и file-to-tasks.tsv. gototask: `skills/task-router/children/gototask/` SKILL config.json scripts,
`.agents/skills/task-router/children/jira/scripts/server.php` плюс src, Codex go-task.ps1; создать config.env из example.
task-diff: `skills/task-router/children/task-diff/scripts/task-diff.ps1`, Codex task-diff.ps1. task-code-review:
skill плюс agents openai.yaml. prepare-task-test: `.doc/qa/**`, `.doc/tests.md`,
`.doc/codeception/**`; vendor из Full-export или composer install. browser-verify:
то же плюс `qa/browser-setup.md`, `codeception/scripts/*`; app docker плюс
selenium-chrome-test `:4444` или chromedriver `:9515`. page-content:
`.doc/skil_data/page-content/**`, `skills/page-content/scripts/extract-page-content.ps1`;
Python venv и .env. xmlriver: `.doc/skil_data/xmlriver/**` код, invoke-xmlriver.ps1; .env с API key.
serp-study: xmlriver плюс page-content плюс study-serp.ps1. yadisk-screenshot:
`.agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1`, README, rule yadisk-screenshot.mdc; пустой imd.
serpanalise-report: skill scripts плюс `.doc/skil_data/serpanalise-report/`, только если нужен SEO-отчет.
login-as-user: обычно не копировать (Copytrust-only). MCP phpstan и php-deps:
`.cursor` и codex `mcp-servers/php-toolchain/`, tools, `scripts/php-docker.*`, setup.ps1;
`npm install` и composer via setup. MCP mysql и jira: mcp.env.example, `.jira/`;
mcp.env, config.env, docker up. MCP leantime: `.doc/skil_data/leantime/**` вкл. `docker/.env`
плюс `mcp/mcp.env`, mcp.json и config.toml; `docker compose up` в leantime и docker, uvx.
text-style: `.cursor/rules/text-style.mdc` плюс `.codex/rules/text-style.md`.

---

## 7. Локальная среда Docker

Для MCP и skills этого проекта нужны только перечисленные. Остальное (laravel-saas,
foodninja, чужие `php:8.x-cli`) к Copytrust AI-kit не относится, на новый компьютер
не переносить.

Нужны: `copytrust-dev` (`copytrust-dev-php-apache-1`, `copytrust-dev-mysql-1`)
определение `tools/docker-dev/compose.yaml`, порты HTTP 8030 MySQL 8031, обязательно
для рабочего стенда (MCP mysql, jira-task через `docker exec ... php .../.agents/skills/task-router/children/jira/scripts/server.php`,
php-docker.cmd и phpstan через контейнер, gototask, разработка); `copytrust-test`
(`*-php-apache-1`, `*-mysql-1` плюс soap) определение `tools/docker-test/compose.yaml`,
порты 8230 и 8231, опционально для e2e browser-verify, prepare-task-test, login-as-user
на отдельном стенде (часто Stopped пока не гоняют тесты); `selenium-chrome-test`
не в compose репо, отдельный `docker run`, порты 4444 WebDriver и 7900 noVNC UI,
Codeception `--env chromedriver` (см. `qa/browser-setup.md`), альтернатива локальный
chromedriver `:9515` без контейнера; Sourcegraph группа (caddy, sourcegraph-frontend,
pgsql, gitserver-0, src-serve-git) определение `sourcegraph-local/` (start-single.sh
и compose), UI и MCP 7080, MCP sourcegraph (`http://127.0.0.1:7080/.api/mcp/v1`);
`leantime_app` плюс `leantime_db` опц. определение `.doc/skil_data/leantime/docker/`
(образ leantime latest плюс mysql 8.4, volumes named, restart unless-stopped), HTTP 8095,
MCP leantime (daniel-eder и uvx), UI admin, не замена Jira и CT-N.

Физически на диске: copytrust-dev `tools/docker-dev/compose.yaml` (плюс Dockerfile,
mysql), код монтируется с корня репо, конфиги с `../../../.config`; copytrust-test
`tools/docker-test/compose.yaml`, отдельные порты и своя БД; selenium-chrome-test файлов
в репо нет, только образ Hub `selenium/standalone-chrome:4.21.0` создан `docker run`,
mounts пустые; Leantime `.doc/skil_data/leantime/docker/docker-compose.yml`; SG скрипты kit
`sourcegraph-local/*.yml`, start-single.sh, config (то что копирует export); SG полный
стек факт `sourcegraph-local/upstream/docker-compose/` плюс override, отсюда подняты
caddy (`:7080`) и остальные; SG данные `~/.sourcegraph/data`, `~/.sourcegraph/config`
плюс docker volumes не в git, на новом ПК создаются заново. Контейнеры папкой
не копируются: на новом ПК заново `docker compose up` и `docker run`.

e2e на отдельном стенде: автотесты UI (Codeception и skill browser-verify открывают
браузер и кликают по живому сайту). Стенд dev `tools/docker-dev` в copytrust-dev
порты 8030 и 8031 (разработка плюс MCP mysql и jira, ручная работа). Стенд test
`tools/docker-test` в copytrust-test порты 8230 и 8231 (вторая копия PHP плюс MySQL
на той же машине, чтобы прогон e2e не ломал данные dev).

Воссоздание контейнеров с нуля (кратко, полные команды в каноне): требования на машине
(Docker Desktop, sibling `.config`, порты свободны); sibling `.config` обязательно
для PHP в docker-dev (prepend.php, .env, .secrets.env, структура, типичные ошибки
пути); `copytrust-dev` обязателен для MCP mysql, jira, gototask (env COMPOSE_PROJECT_NAME
и порты и MYSQL, корень приложения, sibling `.config`, MySQL, зависимости плюс миграции
по README, Apache, проверка); `copytrust-test` опционально e2e (migrate и dump по README);
`selenium-chrome-test` WebDriver для Codeception (`docker run`, UI отладки
`http://127.0.0.1:7900`); Sourcegraph `:7080` с нуля (upstream compose один раз полный
стек 7.4, вписать `abs/path|project.git`, UI `http://localhost:7080` Create admin,
User settings Access tokens scope mcp в config и mcp.token, Site admin Repositories
Indexed); сводка что должно быть в `docker ps`; чеклист другой компьютер чтобы MCP
и skills завелись; матрица стендов; skills в контейнеры факт по SKILL.md и scripts
(gototask, jira-task, mysql, php-docker в copytrust-dev; browser-verify, prepare-task-test,
login-as-user в copytrust-test плюс selenium; sourcegraph MCP в SG стек; leantime MCP
в leantime compose); порядок подъема docker-dev сводка; docker-test; два Codeception
(продуктовый `tools/codeception` в git и агентский `.doc/codeception` export с vendor).

Leantime локальный PM плюс MCP: что копирует export (compose, docker `.env`,
`mcp/mcp.env`, access, bearer, docs целиком); подъем на новом ПК (`docker compose up`
в leantime и docker, UI `http://localhost:8095` логин и пароль в access.md и LEAN_ADMIN
в .env если заданы, MCP launch.sh, API key).

Инструменты вне git (машина): Docker Desktop, Node и uv и uvx, Chrome, Cursor, CBM exe,
PHP и Composer опц. через docker, Python venv опц. для extractor.

---

## 8. День 1: куда что прописать

Сначала общий порядок Day0 в green выше. Ниже куда писать файлы. Шаблоны mcp.env
и jira можно создать до Docker; зеленый MCP только после воссоздания copytrust-dev
(и SG при необходимости). Главное: Sourcegraph сам новый проект не добавит. Один SG
на машину (`http://127.0.0.1:7080` плюс один токен). Репо регистрируют вручную
repos.conf в sync в register. Фильтр `repo:^src-serve-git-3434/repos/{имя}$`.

Шпаргалка куда писать: Jira (URL, email, API token, ключ проекта `CT` в свой)
`.doc/skil_data/jira/config.env`; MySQL MCP `.cursor/mcp.env` плюс `.codex/mcp.env` (одинаковые
`MYSQL_*`, порт docker-dev host, образец 8031); имя PHP-контейнера `.cursor/mcp.json`
и `.codex/mcp.json` в jira-task args плюс hardcode в gototask.ps1 (оба kit);
SG токен Cursor `.cursor/mcp.json` в headers.Authorization `token sgp_...`
(mcp.env для HTTP Cursor не читается), Codex `.codex/mcp.env` в SOURCEGRAPH_MCP_TOKEN,
копия `sourcegraph-local/config/mcp.token`; SG этот репо `sourcegraph-local/config/repos.conf`
плюс sync-mirror.sh плюс register-repos.sh; SG фильтр в агенте skills и rules заменить
testdeploydocker на имя из repos.conf (search-replace ниже); Serena `.serena/project.yml`
в project_name (export уже ставит имя папки); релиз gototask `skills/task-router/children/gototask/config.json`
плюс Codex в releaseBranch; Chrome Playwright `.cursor/mcp.json` в PLAYWRIGHT и CHROME_PATH
(`qa/browser-setup.md`); CBM один раз MCP `index_repository` на абсолютный путь корня;
XML River и extractor `.doc/skil_data/xmlriver/.env`, `.doc/skil_data/page-content/.env`; Leantime MCP
опц. `.doc/skil_data/leantime/mcp/mcp.env` (LEANTIME), контейнеры leantime на 8095; Leantime UI
access.md и LEAN_ADMIN в `docker/.env`; app стенд воссоздание разделы 1-2; e2e и selenium
и SG стек там же 3-5; e2e `.doc/codeception/.env`, selenium или chromedriver, опц.
`tools/docker-test`; Codex trust `%USERPROFILE%\.codex\config.toml` плюс
global-trust.snippet.toml с новым путем.

Порядок настройки Full чеклист 1-15: 1 Open Folder корень нового репо (не родитель,
Cursor и Codex видят kit); 2 MySQL MCP `.cursor/mcp.env` и `.codex/mcp.env` (из example,
одинаковые `MYSQL_*`, порт host MySQL docker-dev); 3 PHP-контейнер mcp.json jira-task
плюс gototask.ps1 (jira-task, gototask, php-docker); 4 Jira `.doc/skil_data/jira/config.env`
(gototask, MCP jira-task); 5 релизные ветки `skills/task-router/children/gototask/config.json` (merge-release);
6 Serena `.serena/project.yml` (LSP, serena MCP); 7 SG токен mcp.json headers и Codex
mcp.env (MCP sourcegraph зеленый); 8 SG этот репо repos.conf в sync в register в Indexed
(иначе `sg_*` пустой); 9 фильтр `repo:` search-replace по kit (doc-verify, prepare-plan,
bitbucket-tasks); 10 CBM `index_repository` (codebase-memory-mcp); 11 Playwright Chrome
mcp.json env paths (playwright MCP); 12 app стенд воссоздание раздел 2 (`.config` плюс
`tools/docker-dev`, mysql, jira, php живые); 13 e2e если нужно раздел 3 плюс раздел 4
selenium или chromedriver (browser-verify); 14 Codex trust user config.toml (Codex видит
MCP); 15 опц. XML и extractor .env (xmlriver, page-content); 16 Sourcegraph если
контейнеров нет воссоздание раздел 5 (MCP sourcegraph).

Примеры заполнения в каноне дословно: `.doc/skil_data/jira/config.env` из config.example.env
(JIRA_BASE_URL, PROJECT_KEY, EMAIL, API_TOKEN); `.cursor/mcp.env` и то же в `.codex/mcp.env`
(MYSQL_HOST `127.0.0.1`, MYSQL_PORT 8031, MYSQL_USER user, MYSQL_PASSWORD password,
MYSQL_DATABASE your_db_name, DOCKER_PHP_CONTAINER yourproject-dev-php-apache-1);
`.cursor/mcp.json` sourcegraph (type http, url `http://127.0.0.1:7080/.api/mcp/v1`,
disabled false, headers Authorization `token sgp_local_xxxxxxxx`, токен явно, без token
в файле mcp.token с префиксом в headers); `sourcegraph-local/config/repos.conf`
(SG сам строку не создаст, формат `/home/you/projects/your-new-project|your-new-project.git`),
затем `cd sourcegraph-local`, sync-mirror.sh, register-repos.sh, UI
`http://localhost:7080/admin/repositories` в Indexed; в запросах агента и skills
`repo:^src-serve-git-3434/repos/your-new-project$`; jira-task в mcp.json имя контейнера
как в `docker ps` (args exec -i yourproject-dev-php-apache-1 php `/var/www/html/.agents/skills/task-router/children/jira/scripts/server.php`),
то же имя в gototask.ps1 Cursor и Codex. Sourcegraph схема один на машину: один SG
(`:7080` плюс один токен в каждом проекте mcp.json), repos.conf строка с абсолютным путем
нового worktree, sync-mirror.sh плюс register-repos.sh, в MCP-запросах фильтр с именем,
канон деталей `sourcegraph-local/MCP.md`. Креды не путать: Jira в `.doc/skil_data/jira/config.env`
не mcp.json; MySQL в оба mcp.env не порт чужого compose (например foodninja `:3306`);
PHP container mcp.json плюс gototask.ps1, DOCKER_PHP_CONTAINER в mcp.env gototask может
не читать (П-3); SG token Cursor в mcp.json headers, Cursor HTTP игнорит mcp.env;
SG список репо repos.conf не mcp.json; Chrome Playwright mcp.json env, не путать
с selenium-chrome-test (тот для Codeception). Полная таблица example в live и строки
Copytrust в свой в каноне (каталог секретов, search-replace). Минимальный smoke после
правок: Settings MCP mysql, jira-task, sourcegraph, serena, git не Error; `sg_list_repos`
видно новое имя; gototask и обнови таск N дает `.doc/tasks/{N}/task.md`; MySQL MCP
`list_tables` на своей БД; CBM `index_status` и поиск по этому проекту, детали раздел
индексации ниже.

MCP индексация CBM и Sourcegraph: как работают относительно Cursor workspace. Пути
к репозиторию в блоках CBM и SG в `.cursor/mcp.json` не задаются. Связанные файлы:
`.cursor/mcp.json` подключение, `.cursor/rules/mcp/codebase-memory-mcp.mdc` и
`../mcp/codebase-memory-mcp.md` правила и эксплуатация CBM,
`.cursor/sourcegraph-mcp.md` поиск через Sourcegraph MCP, `sourcegraph-local/README.md`
запуск repos.conf sync, короткая копия для корня Target после export mcp.index.md.
Что где привязано: serena да `--project ${workspaceFolder}` текущий workspace; git да
`--repository ${workspaceFolder}` текущий workspace; phpstan и php-deps да
`MCP_WORKSPACE=${workspaceFolder}` автоматически; codebase-memory-mcp нет, параметр
`project` в каждом вызове; sourcegraph нет, фильтр `repo:...` в каждом поиске. CBM
и Sourcegraph мультипроектные сервисы на машину, Open Folder сам индекс не переключает.
codebase-memory-mcp кеш вне репо (Windows `%USERPROFILE%\.cache\codebase-memory-mcp\`,
WSL и Linux `~/.cache/codebase-memory-mcp/`); в чате `Проиндексируй этот проект через
codebase-memory-mcp`, агент `index_repository` с абсолютным путем корня mode full
(или moderate, fast), CLI `codebase-memory-mcp cli index_repository` с repo_path
и mode; после индексации `list_projects`, во всех вызовах передавать `project`
(search_graph, trace_path, get_code_snippet, query_graph, index_status), без project
project not found. Sourcegraph: путь к коду не в mcp.json, список worktree
`sourcegraph-local/config/repos.conf` формат `WORKTREE_ABS_PATH|MIRROR_NAME.git`
(для WSL sync часто `/mnt/c/...`, MCP URL `http://127.0.0.1:7080/.api/mcp/v1`),
`cd sourcegraph-local`, sync-mirror.sh, register-repos.sh, UI Indexed
`http://localhost:7080` Site admin Repositories; в каждом поиске фильтр
`repo:^src-serve-git-3434/repos/your-project$`.

Полный каталог секретов и env в каноне дословно по файлам (example в live):
Cursor и Codex mcp.env, `.doc/skil_data/jira/config.env`, `.doc/skil_data/xmlriver/.env`,
`.doc/skil_data/page-content/.env`, leantime `docker/.env` и `mcp/mcp.env`,
`sourcegraph-local/.env` и mcp.token, SG в Cursor mcp.json. Sourcegraph в Cursor mcp.json:
токен в headers (envFile для type http не подхватывается). Playwright env keys Cursor:
PLAYWRIGHT_MCP_EXECUTABLE_PATH, CHROME_PATH, LD_LIBRARY_PATH (Win chrome.exe, WSL wrap.sh).

Search-replace Copytrust в новый проект: testdeploydocker в новое имя, фильтр
`repo:^src-serve-git-3434/repos/{имя}$` везде, `copytrust-dev-php-apache-1` в свое имя
контейнера, `CT-` в свой ключ трекера, `release/5.6.0.6` в свой релиз, `gb_copydev5`
в свою БД, порты 8030 и 8031 в свои. Ветки git: `features/#{N}` и `bugfixes/#{N}`
оставить или сменить в gototask; бэкпорт `_for5606` под свои релизы или удалить;
subject коммита с `{N}` и `#{N}` иначе task-diff пустой; remote Bitbucket свой,
проверка веток через `git ls-remote`.

---

## 9. Экспорт скриптом rebase_project.ps1 (канон)

Запуск из корня образца testdeploydocker в терминале Cursor и Windows PowerShell:
`powershell -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project.ps1 -Target "C:\laragon\www\test"`;
профиль без Jira и gototask добавить `-Profile Core -ProjectName test`; сразу setup.ps1
(нужны Node и сеть, при уже скопированных vendor и nm обычно не обязателен) добавить
`-RunSetup`; из WSL если Target на диске Windows `powershell.exe -NoProfile
-ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 -Target "C:\laragon\www\test"`.
После успеха File Open Folder на Target (уже с app-кодом или после merge clone), затем
EXPORT_NEXT_STEPS.md и канон Day0 в green. После Full kit, не приложение: пока нет
`tools/docker-dev` из git clone, mysql и jira контейнеры не появятся.

Параметры: `-Target` обязателен (каталог нового проекта, создается); `-Profile` default
Full (Full и Core); `-ProjectName` default имя папки Target (Serena project_name);
`-Source` default родитель `.doc/` (корень образца); `-IncludeKilo` off
(`.kilo`); `-SkipSourcegraph` off (SG копируется по умолчанию allowlist);
`-SkipRuntimeDeps` off (nm и vendor копируются по умолчанию); `-RunSetup` off
(`.cursor/setup.ps1` плюс `.codex/setup.ps1`); `-SkipMcpMerge` off (не сохранять
Target-only MCP); `-SkipGitInit`, `-SkipExclude`, `-SkipSiblingConfig` off (отключить шаги);
`-IncludeSourcegraph` legacy (SG и так on, для совместимости).

Merge MCP по умолчанию on: если в Target уже есть `.cursor/mcp.json` и `.codex/config.toml`,
скрипт бэкапит их в `.doc/.rebase-mcp-backup/`, копирует kit, затем вливает серверы
только из Target которых нет в kit (пример laravel-boost, laravel-telescope).
Из kit добавляются в т.ч. sourcegraph, leantime. Одинаковые имена версия kit (образец).

Что копирует Full факт скрипта: AGENTS.md, `.cursor/`, `.codex/` да (живой mcp.env нет,
артефакты нет); runtime MCP `php-toolchain/node_modules`, `tools/vendor` оба kit
(корневой app `/node_modules` около 277M webpack нет); `.serena/project.yml` да
(cache, memories нет); `.doc` стандарты doc_rules, readmy_doc, rebase_project.md плюс
ps1 плюс _gi.ps1, tests; `.doc` инфра docscripts, `.content-extractor`, `.xml-river`,
`.mcpyandexscreen`, leantime целиком (с `.env`, `mcp.env`, bearer), `web/` целиком
(панель документации), `kaiten/doc.md`, `.jira`, `qa`, codeception плюс vendor
(`.venv`, screen, dump.sql, imd, tasks, architecture-контент, serpanalise, seoq
нет); sourcegraph-local allowlist скриптов плюс читаемый config и lib (repos-mirror,
backups, upstream, mcp.token нет, root 600 nginx conf skip); sibling `../.config` пустой
README (секреты Copytrust нет); skills 20 рабочих (удаляет login-as-user,
serpanalise-report); MCP kit плюс merge Target-only (sourcegraph и leantime из kit,
graphify из kit, boost с Target, бэкап `.doc/.rebase-mcp-backup/`). Ориентир размера после Full
130-140 MB (тест `_rebase_export_audit`, 2026-07-18).

MCP Windows против WSL факт с экрана: открытие Target как `C:\laragon\www\...`
в Cursor Windows дает phpstan-mcp и php-deps-mcp Error без патча (command bash плюс путь
`C:\...\.sh` в `System32\bash.exe` WSL ломает Win-путь, скрипт патчит на cmd плюс
`.cursor/scripts/node-mcp.cmd`); codebase-memory-mcp обычно OK и патч (Win
`codebase-memory-mcp-launch.cmd` в `%LOCALAPPDATA%\Programs\codebase-memory-mcp\*.exe`);
jira-task Loading (нет Docker-контейнера `copytrust-dev-php-apache-1`, переименовать
в mcp.json под свой); serena Loading (первый uvx pull, подождать); mysql, playwright,
context7, git, semgrep, xdebug, sourcegraph зеленые при host-tools (npx, uvx, http,
SG нужен `:7080` плюс token); leantime обычно OK после compose up (env и API key уже
в export, иначе `docker compose up` плюс uvx); дубли CBM и SG в UI норма (project MCP
плюс user-level MCP). Открыли проект как `C:\...` Windows Cursor: cmd плюс node-mcp.cmd
и codebase-memory-mcp-launch.cmd (патч экспорта). Открыли через WSL Remote и `\\wsl$\...`:
bash плюс node-mcp.sh и sh (без Win-патча). Корневой `/node_modules` приложения
не участвует в MCP, нужны только toolchain nm плюс `tools/vendor`.

Матрица MCP что должно завестись: playwright (mcp.json; Node плюс npx, Chrome paths
Win chrome.exe WSL wrap.sh); serena (`.serena/project.yml`; uvx, Open Folder корень);
context7, xdebug, mysql (mcp.json плюс mcp.env; Node плюс npx, mysql run-with-mcp-env.sh
плюс mysql-mcp-proxy.mjs listen `127.0.0.1:3306` в MYSQL_PORT стенда образец 8031);
semgrep, git (mcp.json, uvx); phpstan и php-deps (nm плюс vendor плюс Win и WSL launcher,
PHP или php-docker.cmd плюс контейнер); jira-task (`.agents/skills/task-router/children/jira/scripts/server.php`, Docker PHP
плюс JIRA плюс новое имя контейнера); codebase-memory (launch cmd и sh, CBM binary
на машине); sourcegraph (`sourcegraph-local/` allowlist, start-single.sh удобнее WSL,
token в mcp.json headers). Skills gototask, task-diff, prepare-plan, project-doc,
browser-verify: PowerShell и Markdown, на Win Cursor ок при PowerShell. SG shell-скрипты
и часть e2e удобнее из WSL. App-код плюс `tools/docker-*` из git целевого проекта,
не из export.

Подводные камни копирования: robocopy всего sourcegraph-local через `\\wsl.localhost\...`
зависает на repos-mirror даже с XD, скрипт использует allowlist файлов плюс Copy-Item
для config и lib; файлы `config/nginx*.conf` иногда root 600 нечитаемы, bootstrap SG
пересоздаст, скрипт skip плюс WARN; UTF-8 BOM обязателен для Windows PowerShell 5.1;
после экспорта на Win Refresh MCP у phpstan и php-deps (или Reload Window).

Устройство скрипта по функциям: Resolve-FullPath; Invoke-Robo (robocopy на Win,
rsync на Linux и WSL и mac с exclude, fallback Copy-Item, robocopy коды 0-7 успех,
8 плюс throw); Scrub-McpJson (убрать живой Sourcegraph token из headers в REPLACE
плейсхолдер, заглушить абсолютные WSL и user Chrome paths оставив ключи, UTF-8 без BOM);
Test-IsWindowsTargetPath (`C:\...` или UNC Cursor native Windows, не WSL home);
Patch-CursorMcpForWindowsHost (phpstan и php-deps на cmd плюс node-mcp.cmd, CBM на cmd
плюс launch.cmd, ConvertTo-Json Depth 30); Disable-McpServers (jira-task, bitbucket-task
в Core); Merge-McpJsonPreserveTargetOnly (kit поверх Target, sourcegraph и leantime
из образца добавляются, серверы только у Target сохраняются, одинаковые имена версия kit);
Get-TomlTopLevelMcpNames, Get-TomlMcpServerChunk, Merge-CodexTomlPreserveTargetOnly
(все секции `[mcp_servers.NAME]` до чужого, append с маркером preserved from Target);
Write-GitExclude (блок exclude выше, если exclude существует и нет маркера export-rebase-project
append, иначе write); Set-SerenaProjectName (regex project_name в yml, иначе warn вручную);
Remove-CoreOnlyNoise (удаляет 8 скилов gototask, task-diff, task-doc, task-code-review,
prepare-task-test, login-as-user, serpanalise-report, browser-verify в `.cursor` и `.codex`,
плюс `.codex/go-task.ps1` и task-diff.ps1, плюс bitbucket-tasks mdc и md, плюс task-doc mdc
и md, плюс `.doc/skil_data/jira`, `qa`, codeception, плюс Disable jira и bitbucket);
Write-NextSteps (пишет EXPORT_NEXT_STEPS.md в Target, матрица MCP, Windows против WSL,
Sourcegraph контур, тесты, host tools, Git, не скопировано намеренно, канон Day0).
Main: Source default родитель `.doc/`, Target resolve, ProjectName default имя папки,
проверка `.cursor/mcp.json` и `.doc/rebase_project.md` в источнике (иначе throw);
создание Target; sibling `../.config` с README если нет; git init если нет; git exclude
если есть `.git`; AGENTS.md; бэкап MCP Target в `.doc/.rebase-mcp-backup/` если не SkipMcpMerge;
копирование `.cursor` и `.codex` с exclude node_modules, vendor, artifacts, memories, cache
и mcp.env, package-lock, composer.lock; runtime deps если не Skip (php-toolchain node_modules
плюс package-lock и package.json, tools vendor плюс composer lock, json, phar, Full еще
codeception vendor плюс lock, иначе warn setup); `.serena` без memories, cache,
project.local.yml плюс Set-SerenaProjectName; `.doc` стандарты docFiles (doc_rules, rebase_project.md, rebase_project.ps1, rebase_project_gi.ps1, mcp.index.md,
harnes/tests.md, harnes/testaudit.md, harnes/jsondoc.md, harnes/readmy.md, harnes/readmy_doc.md) плюс mcp.index.md в корень Target; docDirs (docscripts, synh_harnes,
`.content-extractor`, `.xml-river`, `.mcpyandexscreen`, leantime, web, task-analytics, Full плюс `.jira`,
`qa`, codeception) с exclude node_modules, .venv, pycache, cache, imd, vendor, logs, output,
_output, screen, pytest_cache и `.env`, config.env, out_copytrust.json, dump.sql, composer.lock,
mcp.env, .bearer_token (web целиком без исключений, task-analytics без out и pycache,
codeception без dump.sql и fail-артефактов, leantime полный стенд с docker .env, mcp.env, bearer); kaiten doc.md один файл; Leantime fallback
из sample и example если .env нет; каркас architecture и _map, tasks, tasks и _map, qa и reports,
mcpyandexscreen и imd; минимальный `architecture/index.md` stub с ProjectName; гарантировать
yadisk-fetch; IncludeKilo опц. (`.kilo` без node_modules, plans, worktrees и без
agent-manager.json и permissions fragment на Target регенерируется синком, корневой
kilo.json, Scrub kilo.jsonc); CopySourcegraph allowlist
(README, MCP, env.example, gitignore, compose yml и single и override и version,
add-local-repo, backup, bootstrap, install-autostart, migrate-to-compose, post-start,
register-repos, start-single, start, stop, sync-after-commit, sync-mirror, upgrade-single,
плюс config и lib рекурсивно кроме mcp.token и .env, skip unreadable root 600, плюс пустые
repos, repos-mirror, backups, плюс sourcegraph `.env` из example); секреты mcp.env из example
(Cursor и Codex, если нет), Full jira config.env из example; Scrub mcp.json Cursor и Codex
плюс antigravity_mcp_config.json (инлайнит SG-токен, чистим тем же scrub); Windows host
патч лаунчеров если Target Win-путь; merge MCP если не Skip (Cursor, Codex json, Codex toml);
удалить Copytrust-only skills login-as-user и serpanalise-report даже в Full; Core вырезать
task и jira skills если профиль Core (плюс в config.toml regex enabled true в false
для jira и bitbucket, плюс Disable в обоих mcp.json); RunSetup опц. (оба setup.ps1,
catch warn); Write-NextSteps; аудит must-файлов (список must ниже, пропуск gototask и task-diff
путей в Core, MISSING красным, forbidden чужой tasks index.md и числовые tasks и login-as-user
и serpanalise и непустой repos-mirror); exclude smoke `git check-ignore -v .cursor/mcp.json`
если есть `.git`; финал маркер `EXPORT_REBASE_DONE target profile project`.

Must-check скрипта: AGENTS.md; `.cursor/mcp.json`, setup.ps1, `rules/text-style.mdc`,
`skills/task-router/children/gototask/scripts/gototask.ps1`, `skills/task-router/children/gototask/config.json`,
`skills/task-router/children/task-diff/scripts/task-diff.ps1`, `scripts/php-docker.cmd`, `scripts/node-mcp.sh`,
`scripts/node-mcp.cmd`, `mcp-servers/php-toolchain/server.js`, `.codex/config.toml`,
`.codex/AGENTS.md`, `.codex/go-task.ps1`, `.codex/task-diff.ps1`,
`.codex/skills/prepare-plan/assets/plan.template.md`, `.codex/scripts/run-with-mcp-env.sh`,
`.codex/lib/kit-root.ps1`, `.doc/doc_rules.md`, tests.md, readmy.md, readmy_doc.md,
rebase_project.md, rebase_project.ps1, rebase_project_gi.ps1, mcp.index.md,
`docscripts/map-project.ps1`, `docscripts/build-tasks-index.ps1`,
`docscripts/export-rebase-project.ps1`, `scripts/node-mcp.cmd`,
`scripts/codebase-memory-mcp-launch.cmd`, `.agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1`,
`.doc/web/README.md`, router.php, docker-compose.yml, start.sh, stop.sh, `app/lib.php`,
`public/index.php`, `.agents/skills/task-router/children/analytics/README.md`, `scripts/task-analytics.py`,
`scripts/lib/db.py`, `scripts/lib/facts.py`, `scripts/lib/attribute.py`,
`scripts/lib/metrics.py`, `scripts/lib/compliance.py`, `scripts/lib/slices.py`,
`scripts/lib/corpus.py`, `scripts/lib/render.py`, `assets/config/thresholds.json`,
`assets/config/required-calls.json`, `assets/config/slices.json`,
`assets/schemas/analysis.schema.json`, `.doc/architecture/index.md`, `.agents/skills/task-router/children/leantime/scripts/launch.sh`,
`.doc/skil_data/leantime/docker/docker-compose.yml`, `.doc/skil_data/leantime/docker/.env`,
`.doc/skil_data/leantime/mcp/mcp.env`, `.doc/skil_data/leantime/access.md`, `.doc/skil_data/leantime/mcp.md`,
`.serena/project.yml`, EXPORT_NEXT_STEPS.md; Full плюс `.agents/skills/task-router/children/jira/scripts/server.php`,
`.doc/qa/index.md`, fragments.md, browser-setup.md, `.doc/codeception/codeception.yml`,
composer.json; CopySourcegraph плюс sourcegraph-local README.md, MCP.md, start-single.sh,
`.env.example`; CopyRuntimeDeps плюс оба kit toolchain sdk package.json, оба kit tools
vendor phpstan, Full плюс codeception vendor autoload.php. Forbidden: чужой
`.doc/tasks/index.md`, числовые `.doc/tasks/{N}/`, login-as-user, `.doc/skil_data/serpanalise-report`,
непустой repos-mirror. Итог must-check PASS или WARN со списками, плюс exclude smoke.

EXPORT_NEXT_STEPS.md в Target содержит: целевой проект и Serena имя; сразу в Cursor
(File Open Folder корень Name не родитель, полный Reload, Settings MCP зеленые
по матрице, заполнить секреты Day1 канон, кратко оба mcp.env с MYSQL под свой docker-dev,
`.doc/skil_data/jira/config.env` с JIRA, Cursor mcp.json SG token в headers, repos.conf плюс
sync и register, search-replace Copytrust-строк testdeploydocker, copytrust-dev-php-apache-1,
repo filter, CT, CBM index_repository на корень, Codex trust плюс global-trust.snippet.toml
с новым путем); матрица MCP что уже в экспорте и что нужно на машине и стенде (playwright,
serena, context7, mysql, xdebug, semgrep, git, phpstan и php-deps с Win node-mcp.cmd
и WSL bash плюс node-mcp.sh, jira-task с новым именем контейнера, codebase-memory-mcp
Win exe и WSL bin, sourcegraph start-single.sh лучше из WSL плюс token, leantime опц.
compose плюс uvx); Windows против WSL важно (открыли `C:\...` в Cursor Windows нужен
Windows launch node-mcp.cmd, bash из PATH WSL и ломает пути в Error у phpstan и php-deps;
открыли через WSL Remote оставляйте bash плюс node-mcp.sh; корневой node_modules
приложения не нужен для MCP и не копируется); Sourcegraph обязательный контур (SG сам
репо не добавит, если контейнеров нет сначала воссоздание раздел 5, `cd sourcegraph-local`
.env из example, start.sh или start-single.sh, Site-admin Access token scope mcp, Cursor
token в `.cursor/mcp.json` sourcegraph headers Authorization, config repos.conf плюс
sync-mirror.sh плюс register-repos.sh, канон Day1 плюс воссоздание); тесты и browser-verify
и prepare-task-test (codeception vendor уже скопирован если не SkipRuntimeDeps, нужен свой
dump.sql и БД стенда дамп Copytrust не тащили, Chrome плюс chromedriver browser-setup.md,
app-код и tools и docker-test из git целевого проекта не из export); host tools не в репо
(Node 20 плюс npm npx, uv и uvx, Docker Desktop, codebase-memory-mcp binary, опц. Python venv
для content-extractor `pip install -e .`, .venv 200M плюс не копировали); Git (exclude уже
записан повторно rebase_project_gi.ps1, локальные оверрайды docker-dev и FirstCest
skip-worktree тот же скрипт); не скопировано намеренно (живые секреты и SG token и mcp.token,
repos-mirror backups upstream, tasks и architecture-контент Copytrust, content-extractor
.venv и screen, codeception dump.sql, serena cache, docker volumes Leantime только файлы,
после up БД новая или перенос volume вручную); документ канон на новый ПК Day0 в green,
День 1, воссоздание; Sourcegraph сам новый репо не добавит, один ps1 без дерева kit
не развернет MCP.

---

## 10. Пошаговая процедура FULL (ручной fallback)

Чеклист до копирования: источник kit путь на диске не git; целевой корень репо; sibling
.config путь; стек Serena languages; compose project и PHP container dev; MySQL host,
port, db, user dev; нужен docker-test порты; Jira base и project key; release branch;
Sourcegraph repo name; нужен `.doc/codeception` плюс browser-verify да и нет; нужен Kilo
обычно нет; нужен login-as-user и serpanalise обычно нет. Предпочтительно rebase_project.ps1
вместо ручного robocopy ниже.

Копирование kit PowerShell ручной fallback: переменные Source, Target, OrgConfig образец,
TargetConfig sibling нового репо; sibling configs приложения без слепого копирования
секретов прода (New-Item TargetConfig, скопировать структуру, секреты заполнить вручную
prepend.php, .env.example в .env, .secrets.env); Copy-Item AGENTS.md; foreach root
`.cursor`, `.codex` robocopy с exclude node_modules vendor artifacts memories cache
и mcp.env package-lock.json composer.lock; robocopy `.serena` с exclude memories cache
и project.local.yml; New-Item `.doc`; foreach f (doc_rules.md, readmy_doc.md,
rebase_project.md, rebase_project.ps1, rebase_project_gi.ps1, mcp.index.md, tests.md)
Copy-Item; foreach d (docscripts, `.content-extractor`, `.xml-river`, `.mcpyandexscreen`,
web, `.jira`, `qa`, codeception) robocopy с exclude node_modules, .venv, pycache, cache,
imd, vendor, logs, output и `.env`, config.env, out_copytrust.json; New-Item architecture
и _map, tasks, tasks и _map, qa и reports, mcpyandexscreen и imd; не копировать
`.doc/tasks/index.md`, file-to-tasks.tsv, `tasks/{N}/` (индекс после build-tasks-index.ps1
-AltsTsv); проверка обязательных файлов после copy (Test-Path tests.md,
`.agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1`,
Codex plan.template.md, Codex doc-verify reference.md, Cursor gototask.ps1, Codex go-task.ps1);
Sourcegraph либо общий инстанс на машине либо robocopy sourcegraph-local без .env,
mcp.token, repos data; Kilo опционально robocopy `.kilo` без node_modules,
переписать agents. Коды robocopy 0-7 успех. Не копировать вручную: живые mcp.env и
config.env и токены, `tasks/{N}/`, architecture-контент Copytrust, serpanalise если SEO
не нужен, `.seoq/`, Stagehand, `.playwright-mcp/`, memories, дампы SQL,
imd, корневой app node_modules, SG repos-mirror. Скрипт Full дополнительно копирует
(не забыть при ручном fallback): php-toolchain node_modules, tools vendor оба kit,
`.doc/codeception/vendor`, SG allowlist, Win-лаунчеры cmd. Продуктовый `tools/docker-*`
из git clone целевого репо или адаптация compose, не из AI-kit export.

Порядок setup после копирования: 0 сразу создать `$Target/.git/info/exclude` (блок exclude)
и при необходимости skip-worktree на compose и FirstCest, иначе `git status` заспамит
весь kit и риск случайного commit; 1 sibling `.config` заполнен; 2 `tools/docker-dev/.env`
плюс корневой `.env` и `.htaccess`, сверить локальный compose.yaml (mount `.config`)
с remote; 3 `docker compose up` (mysql в deps в migrate в php-apache); 4 `.cursor/mcp.env`
плюс `.codex/mcp.env` из example одинаковые MYSQL; если runtime deps уже скопированы
скриптом setup.ps1 опционален, иначе оба setup.ps1; 5 Jira config.env, xml-river и
content-extractor .env плюс venv при необходимости (`pip install -e .`, .venv не копировали);
6 SG start-single.sh плюс token плюс register-repos.sh, CBM index_repository на Target;
7 Codex trust с новыми путями, smoke MCP `node .agents\skills\harness-router\children\mcp-audit\scripts\test-mcp-servers.mjs`;
8 e2e docker-test если нужен, свой dump.sql и БД дамп Copytrust не тащили, chromedriver
`:9515`, `.env` из `.env.dist`; 9 каркас docs stub architecture index.md уже от скрипта,
дальше project-doc и map-project.ps1; 10 после первых задач build-tasks-index.ps1 -AlsoTsv;
11 Win Cursor Refresh phpstan и php-deps после экспорта, переименовать jira docker container
в mcp.json.

Проверка must-copy PowerShell: Set-Location Target, массив must (AGENTS.md; `.cursor/mcp.json`,
setup.ps1, `rules/text-style.mdc`, gototask.ps1, gototask config.json, task-diff.ps1,
`scripts/php-docker.cmd`, `scripts/node-mcp.sh`, `scripts/node-mcp.cmd`,
`scripts/codebase-memory-mcp-launch.cmd`, `mcp-servers/php-toolchain/server.js`,
`mcp-servers/php-toolchain/node_modules/.../sdk/package.json`, `tools/vendor/bin/phpstan`,
`.codex/config.toml`, `.codex/AGENTS.md`, `.codex/go-task.ps1`, `.codex/task-diff.ps1`,
`.codex/skills/prepare-plan/assets/plan.template.md`, `.codex/skills/documentation-router/children/doc-verify/SKILL.md`,
`.codex/scripts/run-with-mcp-env.sh`, `.codex/lib/kit-root.ps1`, `.doc/doc_rules.md`,
tests.md, readmy_doc.md, rebase_project.md, rebase_project.ps1, docscripts map-project.ps1,
build-tasks-index.ps1, `.agents/skills/task-router/children/jira/scripts/server.php`, `.agents/skills/yadisk-screenshot/scripts/yadisk-fetch.ps1`,
`.doc/qa/index.md`, fragments.md, browser-setup.md, `.doc/codeception/codeception.yml`,
composer.json, `codeception/vendor/autoload.php`, sourcegraph-local README.md,
start-single.sh, `.serena/project.yml`); вывод где OK false, пустой вывод все must на месте;
явно не должно быть чужого индекса задач (если есть `.doc/tasks/index.md` убедиться
что сгенерирован здесь не скопирован из Copytrust; числовые `.doc/tasks` 1146, 1335
чужие папки удалить).

Проектные правки минимум: Serena project_name и languages; gototask config.json плюс
docker container в ps1 оба kit; MCP jira-task, SG, Playwright paths; заменить SG `repo:`
filter везде; AGENTS имя и стек, удалить login-as-user, serpanalise-report если не нужны;
выровнять Cursor в Codex mcp.env (не оставлять Codex на 3306 при dev на 8031). Codex machine
bootstrap: trust репо открыть корень Target; дописать в `%USERPROFILE%\.codex\config.toml`
фрагмент из global-trust.snippet.toml с путями нового проекта Win плюс WSL UNC; опционально
`.codex/codex-sale/` для desktop proxy; smoke MCP `node .agents\skills\harness-router\children\mcp-audit\scripts\test-mcp-servers.mjs`,
`codex mcp list`. Kilo опционально: копировать `.kilo/` без node_modules,
корневой kilo.json по необходимости оба в exclude; фактически `.kilo/` адаптер (зеркала
skills, rules, kilo.jsonc, node_modules), зеркала генерируются из канона `.cursor/` через
sync-agent-views.sh, можно не копировать а сгенерировать на месте; прежние пункты про Ollama
`:11434` и модель в kilo.json устарели, текущий adapter их не требует; канон описания
[dirtree.md](../dirtree.md).

---

## 11. Профиль CORE

Без трекера задач. Цель docs плюс MCP плюс универсальные skills на чужом репо,
без Jira, gototask, e2e-агента. Экспорт `-Profile Core` у rebase_project.ps1 (вырезает
task-skills, `.jira`, `qa`, codeception, отключает jira и bitbucket MCP).

Что оставить и убрать: оставить skills 23 минус 8 равно 15 рабочих (business-analyst,
project-doc, doc-verify, prepare-plan, page-content, xmlriver, serp-study,
yadisk-screenshot, git-task-blame, harness-improvement, jira-report, send-to-git,
task-change-report, task-intake, test-task); убрать gototask, task-diff, task-doc, task-code-review,
prepare-task-test, browser-verify, login-as-user, serpanalise-report; rules оставить
doc-rules, project-doc, project-doc-indexing, yadisk-screenshot, prepare-plan, text-style;
убрать bitbucket-tasks, task-doc; `.doc` оставить doc_rules, readmy_doc, rebase_project,
tests.md, docscripts, extractor, xml-river, yadisk, leantime целиком с env, web целиком
панель документации, kaiten research (плюс вручную readmy.md, synh_harnes);
убрать `.jira/`, `qa/`, codeception, `tasks/{N}/`, architecture-контент старого кода,
serpanalise, seoq; MCP оставить serena, git, mysql, CBM, phpstan, leantime опц.;
убрать jira-task и bitbucket-task в `"disabled": true`; Codex без go-task.ps1, task-diff.ps1.
Известная оговорка CORE: git-task-blame, harness-improvement, jira-report,
send-to-git, task-change-report, test-task скриптом не вырезаются (rebase_project.ps1
режет только 8 перечисленных), Core-export оставляет больше skills, чем заявлено. Часть из них
(jira-report, send-to-git, test-task) тяготеет к FULL-контуру, возможный рассинхрон
логики CORE со скриптом, при чистом Core удалить вручную. `.doc/tasks/` на Target только
пустая папка (скрипт так и делает). Не robocopy `{N}/` из Copytrust.

После Core-export: Open Folder корень Target, Reload; mcp.env из example (MYSQL если
нужен mysql MCP); в AGENTS.md и `.codex/AGENTS.md` убрать ссылки на gototask и Bitbucket
если трекер не планируете; создать `.doc/architecture/index.md` (шаблон в doc_rules.md)
в map-project.ps1 в skill project-doc; CBM index_repository на абсолютный путь Target;
Jira позже отдельно вернуть `.doc/skil_data/jira/`, skills gototask и task-diff, rule bitbucket-tasks,
включить MCP, это уже путь к Full не Core. Smoke Core: нет `.agents/skills/task-router/children/gototask`
папки нет; jira-task и bitbucket-task disabled; `.doc/tasks/` пустой нет task.md
из Copytrust; map-project.ps1 дает `_map/file-registry.tsv`; MCP serena, git, CBM
connected. Типичные ошибки Core: агент ищет `.doc/skil_data/jira` и gototask (Core без трекера,
почистить AGENTS.md); в Target есть `.doc/tasks/1612/` (удалить содержимое tasks,
оставить пустой каталог); скопированы `5.7.*.md`, `gb_copydev5.sql` (оставить только
стандарты из матрицы `.doc/`).

---

## 12. Синхронизация Cursor, Codex, адаптеры

Канон `.cursor/`. Зеркала остальных сред генерируются, не правятся руками: утилита
`.doc/skil_data/harness-core/` (README). Инструмент synh_harnes: sync-agent-views.sh точка входа
синхронизирует зеркала 3 сред (`.codex`, `.kilo`, `.agents`)
из канона; generate-agent-configs.py генерирует rules, skills, scripts адаптеров,
убирает Cursor frontmatter `.mdc` для Codex и Kilo; generate-mcp-config.py транслирует
`.cursor/mcp.json` в нативные MCP-конфиги сред (Antigravity через `.agents` без
`${workspaceFolder}` и envFile, Kilo в kilo.jsonc); parity-report.json отчет parity
зеркал (сверка составов канона и адаптеров).

Пары канон в генерируемое зеркало: `.cursor/mcp.json` в `.codex/config.toml` (плюс
`.codex/mcp.json` docs и smoke, MCP-конфиги адаптеров из generate-mcp-config.py);
`.agents/skills/{name}/` в `.codex/skills/{name}/` плюс `.agents/`, `.kilo/`;
`.cursor/rules/*.mdc` в `.codex/rules/*.md`
полный паритет; `.cursor/mcp.env` в `.codex/mcp.env` одинаковые MYSQL;
AGENTS.md в `.codex/AGENTS.md`; MCP leantime тот же launch.sh, secrets только
в `.doc/skil_data/leantime/mcp/mcp.env`. Codex не читает `.agents/skills/` в рантайме. Зеркала
`.agents/`, `.kilo/` тоже служат только своим средам
и правятся только генерацией из канона.

---

## 13. Проверка после переноса и типичные ошибки

Проверка: kit скопирован с диска не из пустого clone (папки `.cursor`, `.codex`, `.doc`
есть); `.git/info/exclude` воссоздан (`git check-ignore -v .cursor/mcp.json` в exclude);
skip-worktree на compose и FirstCest если нужны локальные оверрайды (`git ls-files -v`
показывает S); sibling `.config` (PHP в контейнере стартует); `http://localhost:{APACHE_PORT}/`
200 ЧПУ ок; `.cursor/mcp.env` и `.codex/mcp.env` свои креды одинаковый MYSQL_PORT;
MCP serena, git, mysql, CBM connected; SG `sg_list_repos` новое имя репо; CBM index
путь Target; map-project.ps1 дает `_map/file-registry.tsv`; gototask N FULL дает
`.doc/tasks/N/task.md`; e2e если нужно chromedriver `:9515`, `.doc/codeception` smoke;
`rg testdeploydocker` по kit пусто (кроме rebase_project и истории);
`rg copytrust-dev-php` только новое имя контейнера; общий smoke MCP kit Cursor и Codex
`node .agents\skills\harness-router\children\mcp-audit\scripts\test-mcp-servers.mjs`.

Типичные ошибки: phpstan и php-deps Error на Win Cursor (`bash` плюс `.sh` плюс путь
`C:\...`, экспорт патчит node-mcp.cmd, Refresh MCP); jira-task Loading (нет контейнера
со старым именем, mcp.json в свое имя плюс docker up); serena Loading долго (первый uvx,
подождать, сеть); robocopy SG hang через WSL UNC (полный tree плюс repos-mirror,
использовать rebase_project.ps1 allowlist); после `git clone` нет `.cursor` и `.doc`
(kit в local exclude, копировать с диска и скрипт плюс exclude); `git status` полный kit
после copy (забыли `.git/info/exclude`, вставить блок exclude); PHP в docker без конфигов
(нет sibling `.config`, создать `../../../.config` плюс prepend.php); `/var/www/.config`
пустой в контейнере (compose с Win UNC или неверный sibling, запуск compose из WSL,
путь `<org>/.config` рядом с репо, ls в контейнере); vendor root-owned и Permission denied
(UID и GID не пользователь хоста, `id -u` и `id -g` в docker `.env`, пересоздать сервисы);
jira и gototask docker fail (старое имя контейнера, mcp.json плюс gototask.ps1); MySQL MCP
refused (порт 8031, рассинхрон Cursor и Codex mcp.env, выровнять PORT); SG пусто (старый
`repo:.../testdeploydocker$`, filter плюс sync-mirror); CBM старый проект (индекс со старого
пути, index_repository заново); Playwright и Codeception no chrome (чужие пути, нет
chromedriver, browser-setup.md); browser-verify и prepare-task-test (нет `.doc/codeception`
или tests.md, докопировать оба); yadisk skill падает (нет yadisk-fetch.ps1, скопировали
только пустой imd, докопировать); Codex prepare-plan без шаблона (не скопировался
`.codex/skills/prepare-plan/assets/`, robocopy skills целиком не только Cursor); task-diff
пустой (subject без `{N}`, конвенция коммитов); Codex без MCP (нет trust, не корень,
global-trust плюс открыть корень); БД db против gb_copydev5 (dist не live, одно имя везде).

Известные проблемы и ограничения канона П-1 - П-20: П-1 один документ переноса (FULL, CORE
и локальная среда этот файл `-Profile Full|Core`, отдельный migrateproject.md снят);
П-2 токен Sourcegraph в git и mcp.json (не коммитить живой `sgp_local_...`, Cursor HTTP MCP
токен в headers, envFile для type http не подхватывается); П-3 hardcode docker в gototask.ps1
(DOCKER_PHP_CONTAINER в mcp.env не подхватывается gototask, править ps1 в обоих kit);
П-4 login-as-user (Copytrust-only, скрипт удаляет на Target, не переносить без переписывания);
П-5 kit не в remote (перенос всегда с filesystem, clone origin недостаточен); П-6 паритет
Codex rules решено (зеркала `.codex/rules/*.md` полные 12 пар, неполных пар 0, раньше 4 из 9
устарело); П-7 mcp.env.example Cursor не равно Codex (разные дефолты портов и БД, после setup
выровнять вручную); П-8 Codex task-doc rule решено (было Codex SKILL ссылался на Codex
rules task-doc.md файла не было, сейчас файл существует, пара синхронизирована 12 из 12);
П-9 без `.doc/tests.md` ломается e2e-контур (prepare-task-test и browser-verify требуют
tests.md раздел 7 и 8); П-10 скопировали `tasks/index.md` из Copytrust (симптом в индексе
сотни чужих `#1146`, `#1335`, doc-verify V6 тянет не те задачи, решение не копировать,
генерировать build-tasks-index.ps1 -AlsoTsv); П-11 забыли воссоздать `.git/info/exclude`
и skip-worktree (симптом `git status` полный `.cursor` и `.doc` или compose и FirstCest
уезжают в commit, решение скрипт пишет exclude, skip-worktree на 4 файла вручную при
локальных оверрайдах); П-12 Win Cursor плюс bash MCP phpstan и php-deps Error (симптом
на скрине MCP красные Open Folder `C:\...`, причина `System32\bash.exe` WSL Win-путь
к `.sh` не открывается, решение rebase_project.ps1 патчит на node-mcp.cmd, Refresh MCP);
П-13 Sourcegraph robocopy hang и root 600 nginx (симптом экспорт зависает на sourcegraph-local
или PermissionDenied на nginx.conf, причина repos-mirror около 360M через UNC часть conf
от docker root 600, решение allowlist в скрипте, skip unreadable, bootstrap SG на Target);
П-14 корневой app node_modules не равно MCP (не путать с `.cursor/mcp-servers/php-toolchain/node_modules`,
корневой webpack-tree около 277M экспортом не копируется и для MCP не нужен); П-15 чужие
контейнеры в Docker Desktop (симптом десятки групп laravel-saas foodninja, непонятно что тащить,
решение для MCP и skills Copytrust нужны только copytrust-dev плюс опц. copytrust-test,
selenium-chrome-test, стек sourcegraph-local, остальное не копировать); П-16 папку контейнеров
нельзя скопировать (контейнеры и образы живут в Docker Engine не в каталоге проекта, перенос
Docker Desktop на новом ПК плюс `docker compose up` из `tools/docker-*` плюс опц. `docker run`
selenium плюс SG start, AI-kit контейнеры не создает); П-17 на новом ПК только doc плюс ps1
(симптом скрипт есть `.cursor` нет MCP пустой, причина export читает полное дерево-источник,
один ps1 без kit не создаст skills и MCP, решение Day0 привезти kit export на старом ПК или zip
плюс clone app плюс host tools); П-18 sibling `.config` и mount на Win и WSL (симптом PHP
контейнер up сайт 500 и нет конфигов `ls /var/www/.config` пусто, причина compose запущен
с Windows по пути `\\wsl.localhost\...` или `.config` не рядом с репо, решение структура
`<org>/.config` плюс `<org>/<project>`, `docker compose` из Linux shell в `tools/docker-dev`,
проверить mount); П-19 документ против one-click (симптом ожидание что одна флешка плюс пустой
Docker сразу дадут зеленые CBM и SG, причина бинарники host и токены не едут внутри md,
volumes Leantime не в kit, решение сценарий C плюс самодостаточность, Host install, новый SG
token, CBM exe плюс index); П-20 второй Sourcegraph и второй CBM на новый проект (симптом
несколько SG на разных портах путаница токенов, решение один SG `:7080` на машину, в каждом
проекте свой repos.conf entry и headers token можно один и тот же token).

История версий канона: v1.23 2026-10-01 панель документации `.doc/web` (PHP без БД, задачи
из task.json с фильтром по релизу плюс architecture из JSON, страница задачи по модели
change-report со свежестью workflow-context, перенос скриптом каталог web в `$docDirs`
Full и Core целиком без исключений, ручной fallback, канон панели `.doc/web/README.md`);
v1.22 2026-09-26 актуализация по сверке с диском (инвентарь 22 skills, 12 rules, 12 пар Codex,
П-6 и П-8 решены, адаптеры `.agents/`, `.kilo/`, `.antigravity/`, `.gemini/` и synh_harnes
в раскладке карте и секции синхронизации, skip-worktree факт 1 файл, exclude дополнен
Kilo, cbmignore, codeception, чистка мертвых ссылок verify-codex-mcp.ps1 в test-mcp-servers.mjs
и run-with-mcp-env.ps1 в sh и `tasks-571-audit/` и несуществующие корневые `.doc/`, DoD плюс
xdebug и leantime, mysql MCP через run-with-mcp-env.sh плюс mysql-mcp-proxy.mjs, CORE 14 skills
с оговоркой про невырезаемые task-скилы, Kilo без Ollama, переименован дубль заголовка MCP
Windows против WSL, задач 176 папок); v1.21 2026-07-22 export merge MCP (kit добавляет
sourcegraph и leantime, Target-only laravel-boost graphify сохраняются бэкап
`.doc/.rebase-mcp-backup/`, SkipMcpMerge отключает); v1.20 2026-07-22 сценарий C AI-kit only,
DoD C, таблица один раз на машину, самодостаточность плюс готовый промпт, Day0 A и B и C,
П-19 и П-20; v1.19.1 2026-07-22 Leantime export с `docker/.env`, `mcp/mcp.env`, access, bearer,
must-check требует файлы; v1.19 2026-07-22 `.doc/skil_data/leantime` и kaiten doc.md в карте, MCP leantime
в инвентаре, Day0, День1, Docker, export, CORE, уточнены doc-skills без новых папок; v1.18
2026-07-18 секция индексации CBM и Sourcegraph плюс mcp.index.md из audit Target; v1.17
2026-07-18 rebase_project_gi.ps1 локальный exclude плюс skip-worktree из корня Target;
v1.16 2026-07-18 migrateproject.md слит в профиль CORE, файл удален, Core export без
migrateproject и без task-doc rule; v1.15 2026-07-18 аудит нового ПК шаблон prepend.php,
UID и GID, Playwright Win и WSL примеры, mount UNC П-18, EXPORT_NEXT_STEPS в Day0; v1.14
2026-07-18 мастер-план Day0 в green host install два сценария DoD smoke политики vendor,
SG, skills, аудит нового компа; v1.13 2026-07-18 воссоздание контейнеров с нуля .env
docker-dev и test selenium docker run SG start связка mcp.env и jira-task docker ps сводка;
v1.12 2026-07-18 День 1 расширен шпаргалка плюс примеры Jira, mcp.env, SG repos.conf,
jira-task, SG не авто-add явно; v1.11 2026-07-18 День 1 куда что прописать SG не авто-add
Jira, mcp.env, repos.conf, smoke; v1.10 2026-07-18 Docker Desktop карта контейнеров со скрина
нужны и не нужны selenium-chrome-test чеклист другого ПК П-15 и П-16 skills в контейнеры;
v1.9 2026-07-18 канон скрипта rebase_project.ps1 рядом с md wrapper в docscripts полная
матрица MCP, Win, WSL, runtime П-12 - П-14 must-check расширен; v1.8 2026-07-18 Win Cursor
node-mcp.cmd плюс патч mcp.json корневой app node_modules не для MCP; v1.7 2026-07-18
SG allowlist Copy-Item skip root 600 nginx must-check PASS около 137M; v1.6 2026-07-18
SG плюс runtime deps по умолчанию матрица в EXPORT_NEXT_STEPS opt-out Skip; v1.5 2026-07-18
первый export-скрипт в docscripts BOM must-check stub architecture; v1.4 2026-07-17
exclude плюс skip-worktree плюс sibling `.config`; v1.3 2026-07-17 полная карта `.doc/`
политика tasks index.md skills 15; v1.2 2026-07-17 матрица must-copy tests.md yadisk-fetch;
v1.1 2026-07-17 kit вне git docker codeception env Codex trust.

---

## 14. rebase_project_gi.ps1 (195 строк)

Канон `.agents/skills/harness-router/children/new-project/scripts/rebase_project_gi.ps1`. Локальный git exclude плюс опционально skip-worktree
для AI-kit. Запуск из корня проекта где `.git`, либо `-RepoRoot`. Не коммитится: пишет
только `.git/info/exclude` и флаги index. Примеры: `cd C:\laragon\www\myproject`,
`powershell -NoProfile -ExecutionPolicy Bypass -File .doc\rebase_project_gi.ps1`;
с явным корнем `... -RepoRoot "C:\laragon\www\myproject" -Force`; без skip-worktree
`-NoSkipWorktree`. Параметры: RepoRoot пусто (авто: если скрипт лежит в `.doc/` родитель
часто корень репо, иначе cwd, иначе throw нет корня git); Force (перезаписать exclude);
NoSkipWorktree (флаги не ставить). Функции: Resolve-RepoRoot (явный путь с `.git`,
иначе родитель `.doc/` с `.git`, иначе cwd с `.git`); Get-ExcludeBlock (блок exclude
зеркала реальные копии исключаются рабочие 3 среды и legacy-защита: `.cursor/`, `.codex/`,
`.agents/`, `.kilo/`, `.antigravity/`, `.gemini/`, `.doc/`, `.serena/`, `.playwright-mcp/`,
`AGENTS.md`, `php_error.log`, `.kilocode/`, `kilo.json`, docker-dev local overrides,
Sourcegraph local stack, Local Codeception admin credentials, Kilo worktrees и Agent
Manager state и setup варианты и legacy, Local Codeception suite edits, Codebase-memory
ignore); Write-GitExcludeLocal (создать `.git/info`, если exclude существует и нет Force:
маркер rebase_project_gi.ps1 или export-rebase-project уже есть OK, иначе append блока;
с Force write UTF-8 без BOM); Set-SkipWorktreeLocal (файлы `tools/docker-dev/compose.yaml`,
`tools/docker-dev/README.md`, `tools/docker-dev/php-apache/Dockerfile`,
`tools/codeception/tests/Acceptance/FirstCest.php`; пропуск если нет файла или untracked,
иначе `git update-index --skip-worktree`, OK или WARN); Test-ExcludeSmoke (пробы
`.cursor/mcp.json`, `.doc/doc_rules.md`, `AGENTS.md`, `sourcegraph-local/README.md`:
пропуск если нет на диске, иначе `git check-ignore -v`, OK hits или FAIL не игнорируется;
плюс `git ls-files -v` строки S по `tools/(docker-dev|codeception)`; вернуть hits).
Main: root Resolve-RepoRoot, exclude, skip-worktree если не NoSkipWorktree, проверка,
финал `REBASE_GI_DONE root exclude_hits`, exit 0. Канон: rebase_project.md секция
local exclude.

---

## 15. Аудит скриптов переноса (2026-09-28): корректны с 7 правками

Оба скрипта прочитаны целиком и сверены с диском. Логика переноса корректна
(robocopy/rsync/Copy-Item каскад, scrub секретов, MCP merge, search-replace каркас,
must/forbidden аудит в конце). Найдены и исправлены 7 дефектов:

| # | Дефект | Исправление |
|---|---|---|
| R1 | must-check требовал `.codex/scripts/run-with-mcp-env.ps1` - файла нет (только `.sh`), ложный MISSING | Строка удалена из must-списка `rebase_project.ps1` |
| R2 | must-check требовал `.codex/skills/doc-verify/reference.md` - файла нет ни в каноне, ни в зеркале | Строка удалена из must-списка |
| R3 | `$docFiles` не копировал `readmy.md` и `testaudit.md` - мастер-реестр и канон веток терялись | Оба добавлены в `$docFiles` и must-список |
| R4 | `$docDirs` не копировал `synh_harnes/` - Target получал kit без генератора зеркал | `synh_harnes` добавлен в `$docDirs` |
| R5 | Scrub чистил только `.cursor/mcp.json` и `.codex/mcp.json`; `antigravity_mcp_config.json` с инлайн-SG-токеном уезжал как есть | Scrub применен и к `antigravity_mcp_config.json` |
| R6 | `-IncludeKilo` копировал `.kilo/` целиком без scrub `kilo.jsonc` (SG remote token в headers) и без исключения worktrees/permissions-fragment | Exclude `worktrees`, `agent-manager.json`, `kilo-permissions.fragment.jsonc` плюс scrub `kilo.jsonc`; зеркала регенерируются синком на Target |
| R7 | exclude-блоки обоих скриптов прятали только `.agents/.kilo`, но не `.antigravity/.gemini` - реальные копии светились в `git status` | Обе строки добавлены в `Write-GitExclude` и `Get-ExcludeBlock` |

Итог: после 7 правок скрипты корректны. На Target после экспорта обязателен
`sync-agent-views.sh` (регенерация 5 зеркал плюс parity с freshness-гейтом) -
экспортированные зеркала транспортные, канон `.cursor/`.

---

## Связи

- [Точка входа](../index.md) - карта каталога и список на удаление
- [Канон и среды](./01-canon-envs.md) - синк и parity
- [MCP](./04-mcp.md) - серверы и адаптация
- Канон переноса: `../rebase_project.md`
- Скрипт экспорта: `../rebase_project.ps1`
- Скрипт exclude: `../rebase_project_gi.ps1`
- Wrapper: `../docscripts/export-rebase-project.ps1`

---

## История изменений

- 2026-11-10: помечен историческим снимком; актуальные шаги переноса находятся в state/14-project-migration.md и rebase_project.md.
- 2026-11-05: пути gototask, task-diff и doc-verify приведены к иерархии `skills/.../children`; упоминание несуществующего `reference.md` удалено.
- 2026-11-05: локальный `tools/` переименован в `.tools/`; скрипты переноса пишут `/.tools/` в exclude, не копируют каталог, а скилы ищут `.tools/` с откатом на `tools/`.
- 2026-11-05: миграция копирует безопасный набор `.tools` без `.env`, `dump.sql`, `vendor`, `_output`, `__pycache__`; добавлен `-SkipTools`. `sourcegraph-local` исключен из миграции.
- 2026-10-01: расширена до полной рабочей карты rebase_project.md (v1.23), rebase_project.ps1, rebase_project_gi.ps1
- 2026-10-30: в docDirs и must-check добавлен `task-analytics/` (код анализа диалогов, без `out/`); панель `.doc/web` показывает аналитику из `tasks/{N}/dialogs/`
