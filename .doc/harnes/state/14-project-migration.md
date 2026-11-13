# Миграция между проектами (перенос kit)

<!-- meta
type: architecture
status: actual
updated: 2026-11-13
related: [../index.md, ./13-agent-migration.md, ../../.agents/skills/harness-router/children/migration-review/README.md, ../../rebase_project.md, ../../.agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1]
tags: [harness, migration, transfer, rebase, export, kit, qoder]
-->

---

## Суть

Перенос агентского kit из этого репозитория в другой проект или на другую машину.
Канон процедуры - `.doc/rebase_project.md`, исполняет `.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1`,
локальный exclude пишет `.agents/skills/harness-router/children/new-project/scripts/rebase_project_gi.ps1`, обертка для совместимости -
`.agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1`. Переносится не приложение, а среда:
правила, скилы, скрипты, MCP, QA-контур и документационные стандарты.

> **Актуализация 2026-11-13.** Текущий перенос выполняет `new-project/scripts/harness_transfer.py` командами `plan`, `approve`, `apply`, `verify` и `rollback`. Имена `Full` и `Core` ниже исторические: текущие профили называются `Core`, `Developer` и `Project`, legacy `Full` отображается в `Developer`. Режим `clean`, автоматический `git init`, запись `.git/info/exclude` и `PURGE` не выполняются. Docker, панель, supervisor, Windows-деплой и серверное окружение в текущую задачу не входят. Разделы ниже сохранены как история старого механизма.

Этот механизм не синхронизирует представления IDE в уже открытом проекте и не
копирует Git-снимок приложения. Для этих операций используй
[environment-sync](../../../.agents/skills/harness-router/children/environment-sync/README.md)
или [copy-project](../../../.agents/skills/harness-router/children/copy-project/README.md).

---

## 1. Файлы канона

| Файл | Роль |
|---|---|
| `.doc/rebase_project.md` | канон переноса, профили, Day0, День 1, ошибки П-1 - П-20 |
| `.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1` | основной скрипт export, копирование и проверки |
| `.agents/skills/harness-router/children/new-project/scripts/rebase_project_gi.ps1` | локальный `.git/info/exclude` плюс skip-worktree на Target |
| `.agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1` | обертка, делегирует в канон |
| `.doc/harnes/state/14-project-migration.md` | этот документ, краткая операционная карта |

---

## 2. Профили и сценарии

| Профиль | Когда | Состав |
|---|---|---|
| Full | Jira, git-ветки, PHP, Docker, e2e | весь kit: gototask, task-diff, jira-task, qa, codeception |
| Core | другой проект, только документация и MCP | без трекера и task-скилов, 15 скилов |

Сценарии:

- A: тот же продукт на новой машине — kit плюс docker плюс codegraph плюс CBM.
- B: другой продукт — kit плюс search-replace имён плюс своя архитектура.
- C: только AI-kit, без приложения, MySQL и Jira.

Один CBM-бинарь на машину. `sourcegraph-local/` миграцией не копируется с
2026-11-05 и разворачивается вручную, если нужен. Kit копируется на каждый проект.

---

## 3. Запуск

По умолчанию перенос не выполняет `git init` и не меняет `.git/info/exclude` целевого проекта. Старое поведение включается явно флагами `-InitGit` и `-ManageGitExclude`; `origin` скрипт не назначает. Это не делает legacy `update` безопасным трёхсторонним обновлением: такой механизм ещё разрабатывается.

Перенос копированием выполняется одной командой. Остальная настройка Target
(секреты, индексы, venv, smoke) перечислена в разделе 8 и в
`EXPORT_NEXT_STEPS.md`.

```powershell
# канон
pwsh -NoProfile -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 `
  -Target "C:\laragon\www\myapp" -Profile Full -ProjectName myapp

# обертка (те же флаги)
pwsh -NoProfile -File .agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1 `
  -Target "C:\laragon\www\myapp" -Profile Full -ProjectName myapp
```

Основные флаги: `-Profile Full|Core`, `-Mode migrate|clean|update`, `-ProjectName`,
`-IncludeKilo`, `-SkipTools`, `-SkipRuntimeDeps`, `-SkipGitInit`, `-SkipExclude`,
`-RunSetup`, `-SkipMcpMerge`, `-SkipSiblingConfig`, `-SkipBackup`, `-SkipReview`,
`-MirrorKit`.
Флаг `-MirrorKit` включает точное зеркало с удалением файлов Target вне kit; по
умолчанию лишнее сохраняется. Режим `clean` включает это поведение.
`sourcegraph-local/` не копируется. Источники MCP-серверов берутся из
`.tools/mcp-servers`; runtime-зависимости `.tools/mcp-servers/php-toolchain/node_modules`
копируются, если не передан `-SkipRuntimeDeps`.

### Режимы переноса

| Режим | Что делает | Анализ после | Когда применять |
|---|---|---|---|
| `migrate` | сохраняет бэкап перезаписанных файлов, копирует kit, сохраняет target-only | да, `migration-review` | первый перенос в существующий проект |
| `clean` | сохраняет бэкап всех kit-файлов Target, удаляет kit-компоненты вне kit, ставит только kit | нет | нужен чистый kit без локальных скилов и правил |
| `update` | обновляет kit-файлы поверх уже перенесенного проекта, локальные дополнения сохраняет | нет | повторная установка новой версии kit |

Перед копированием создается `.doc/.rebase-backup/{timestamp}/`. Для всех
перезаписанных файлов пишется `.doc/.rebase-conflicts.json` с категориями
`skill`, `rule`, `script`, `docs`, `mcp`, путями и путями копий.
В режиме `migrate` после копирования автоматически запускается
[migration-review](../../../.agents/skills/harness-router/children/migration-review/README.md): он читает бэкап, сканирует
локальные скилы, правила и MCP и предлагает установку. В режимах `clean` и
`update` разбор не запускается.

После проверки бэкап можно удалить:

```bash
python3 .agents/skills/harness-router/children/migration-review/scripts/review_migration.py \
  --root . --rm-backup --yes
```

Удаляются `.doc/.rebase-backup/{timestamp}` и `.doc/.rebase-mcp-backup`. Отчет
`.doc/.rebase-conflicts.json` остается с отметкой `backup_removed`.

---

## 4. Что копируется

| Область | Состав |
|---|---|
| Корень | `AGENTS.md` |
| Cursor | `.cursor/` целиком: rules, skills, scripts, mcp.json, mcp.env |
| MCP-серверы | `.tools/mcp-servers/` (php-toolchain), источники без `node_modules`; зависимости при отсутствии `-SkipRuntimeDeps` |
| Обёртки MCP | `.tools/scripts/` целиком: `node-mcp.sh`, `run-with-mcp-env.sh`, `mysql-mcp-proxy.mjs`, `php-docker.*`; на них ссылаются MCP-конфиги |
| Codex | `.codex/` целиком: AGENTS.md, rules, skills, scripts, config.toml, mcp.json |
| Kilo | `.kilo/` только с `-IncludeKilo`, без `agent-manager.json`, `worktrees`, fragment |
| Qoder | `.qoder/rules`, `.qoder/skills`, `.qoder/settings.json`; генерируются из канона на Target |
| Qwen Code | `.qwen/rules`, `.qwen/settings.json`; `.agents/skills` и `AGENTS.md` читаются нативно |
| Serena | `.serena/project.yml`, без `memories` и `cache`; порт выбирается заново |
| Индексные конфиги | `.codeprism.toml` и `.cbmignore` копируются, если в Target их нет |
| Документация | `web`, `qa` |
| JSONdoc и бизнес-правила | движок живёт в `.agents/skills/documentation-router/children/task-doc/scripts` и переносится вместе со скилами; `buisnes_analis` в `.doc/archive` не копируется |
| DSH kit | `.dsh/skills`, `.dsh/adapters`, `.dsh/scripts`, `.dsh/tests`, `.dsh/models.overlay.json` через `copy-dsh-kit.ps1` |
| Канон docs | `doc_rules.md`, `harnes/index.md`, `tests.md`, `testaudit.md`, `jsondoc.md`, `readmy.md`, `readmy_doc.md`, `rebase_project.*`, `mcp.index.md`, документы миграций |
| Full дополнительно | `.jira`, `.tools/codeception` |
| `.tools` | безопасный набор: `.tools/scripts`, `docker-dev/compose.yaml`, `docker-dev/php-apache`, `php85-scan`, `codeception/codeception.yml`, `codeception/composer.json`, `codeception/composer.lock`, `codeception/scripts`, `codeception/tests/_envs`; без `.env`, `dump.sql`, `vendor`, `_output`, `__pycache__` |

---

## 4. Что не копируется

- `.doc/tasks/{N}/` и `tasks/index.md`: чужие задачи.
- `.doc/web/state`, `.doc/web/.env`, `ADAPTERS.local.md`, `actions.local.json`: состояние и локальные пути сервиса `copytrust-tools`.
- Рантайм `copytrust-tools:local`, индексы CBM и CodeGraph: собираются на Target.
- Контент `.doc/architecture/` старого продукта, кроме нового каркаса index.
- `.dsh/project.patch.yml` и `DSH-RULES.md`: генерируются на Target вызовом `sync-agent-views.sh`. Если `project.patch.yml` ведется вручную (нет шапки генератора), синк его не перезаписывает. Kit `.dsh/skills`, `.dsh/adapters`, `.dsh/scripts`, `.dsh/tests` и `models.overlay.json` копируется, см. раздел 4.
- `.codegraph/`: локальный индекс, строится на Target заново через `codegraph init`.
- Секреты: живые `mcp.env` (включая `.kilo/mcp.env`) и `config.env`.
- `sourcegraph-local/` целиком: миграция не копирует стек SG.
- `.tools/.env`, `.tools/docker-dev/mysql/dump.sql`, `.tools/codeception/vendor`, `.tools/**/_output`, `.tools/**/__pycache__`.
- Python venv: `.cursor/tools/codeprism-ai/venv` и `.vex`-каталоги; они содержат абсолютные пути образца и создаются на Target.
- `.doc/archive/buisnes_analis/` и исторические `jsondoc_scripts`-данные: движок `jsondoc.py` переносится вместе скилом `task-doc`, данные продукта остаются в архиве.
- `.doc/qa/tmp-runs`: артефакты прогонов образца.
- `.qoder/settings.local.json`, `.qoder/worktrees`, `.qoder/scheduled_tasks.json` и `~/.qoder/`: локальное состояние Qoder, создается на Target.
- `.qwen/QWEN.local.md`, `.qwen/team-memory`, `~/.qwen/`: личные инструкции и память Qwen, на Target свои.
- Корневой `node_modules/` приложения.

---

## 5. MCP при переносе

По умолчанию включён merge: если на Target уже есть `.cursor/mcp.json` или
`.codex/config.toml`, скрипт бэкапит их в `.doc/.rebase-mcp-backup/`, копирует kit,
затем возвращает серверы, которых нет в kit (например `laravel-boost`).
Одинаковые имена берутся из kit. Отключить: `-SkipMcpMerge`.

Абсолютные пути образца в `.cursor/mcp.json`, `.codex/config.toml`, `.codex/mcp.json`,
`.kilo/kilo.jsonc`, `.agents/mcp.json`, `.qoder/settings.json`, `.qwen/settings.json`, antigravity-конфигах, `AGENTS.md` и `mcp.index.md`
экспорт заменяет на пути Target. Канон `mysql` использует `${workspaceFolder}`, поэтому
синк раскрывает путь в каждой среде. После переноса проверка stale-путей входит в must-check.

Qoder не поддерживает `envFile`, поэтому `.qoder/settings.json` запускает stdio-серверы
через `.tools/scripts/run-with-mcp-env.sh`; секреты остаются в `mcp.env`, а не в JSON.
Транспорт `stdio`/`http`/`sse`, флаги `disabled`, `alwaysAllow`, `includeTools`, `disabledTools`
(в Qoder это `excludeTools`) переносятся. Включенные серверы попадают в
`mcp.enabledProjectMcpServers`, поэтому CLI не спрашивает подтверждение для каждого.
Проектные MCP из Target сохраняются через merge в `.cursor/mcp.json` и затем
попадают в `.qoder/settings.json` при синке.

Qwen Code использует другой формат: HTTP-серверы пишутся в `httpUrl`, SSE в `url`,
выключенные серверы уходят в `mcp.excluded`, а `alwaysAllow` превращается в
`trust: true`. Секреты так же остаются в `mcp.env` через `run-with-mcp-env.sh`.
Правила Qwen делятся на baseline (без `paths`), условные (`paths`) и скилы
`rule-*` для Cursor-правил с model decision.

В kit входят 18 серверов, 14 включённых. `codegraph` приходит как обычный
stdio-сервер, но его индекс `.codegraph/` не переносится и строится заново.
`codeprism` приходит как запись и лаунчер, но его venv `.cursor/tools/codeprism-ai`
не в git: на Target он создается командами `uv venv` плюс `uv pip install codeprism-ai==0.1.11`,
а индекс в user-data строится при первом старте сервера. Адрес образца в Target
не переносится: запись остаётся отключённой с заглушкой `http://127.0.0.1:0/mcp`.
Файл `.codeprism.toml`
локальный, он в `.git/info/exclude` и на Target создается заново по разделу
настроек в [mcp/codeprism.md](../../../.agents/skills/codeprism/docs/mcp/codeprism.md). Обертка
`scripts/codeprism_serve.py` входит в `.cursor` и включает живой наблюдатель
файлов. Индекс привязан к абсолютному пути проекта: при переносе он строится
заново, файл старого пути остается в `~/.local/share/codeprism/` и проекты не
смешивают.

---

## 6. Профиль Core

Core вырезает 10 task-скилов из `.cursor`, `.codex`, `.kilo`, `.agents`, `.qoder` и `.qwen`
(`gototask`, `task-diff`, `task-doc`, `task-code-review`, `prepare-task-test`,
`login-as-user`, `browser-verify`, `test-task`,
`task-intake`, `jira-report`), отключает `jira-task` и `bitbucket-task`, удаляет `.doc/skil_data/jira`, `.doc/qa`, `.tools/codeception`.
Остаются документация, план, MCP и внешние скилы. Часть task-тяготеющих скилов
(например `prepare-plan`) остаётся осознанно.

---

## 7. После переноса

1. Открыть Target как отдельный корень, не родительскую папку.
2. Заполнить секреты: `.cursor/mcp.env`, `.codex/mcp.env`, `.kilo/mcp.env`,
   `.doc/skil_data/jira/config.env`.
3. В режиме `migrate` разобрать предложения `migration-review`; `sourcegraph-local/` при необходимости развернуть отдельно.
4. CBM: `index_repository` на абсолютный путь корня.
5. Среды: `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` (регенерация зеркал, `.qoder`, `.qwen` и сгенерированной части `.dsh`). Kit уже перенесён `copy-dsh-kit.ps1`.
6. Qoder и Qwen Code: открыть Target как проект, проверить `.qoder/rules`, `.qoder/skills`, `.qwen/rules` и MCP в `.qoder/settings.json` и `.qwen/settings.json`. Пользовательские настройки живут в `~/.qoder/settings.json` и `~/.qwen/settings.json`.
7. Мастер настройки: `python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --check`, затем запуск с явными значениями. Скрипт проверяет MCP, выбирает свободные порты, строит codegraph, codeprism venv, jdocmunch и CBM, обновляет `MYSQL_*`, пишет `.doc/onboard-report.md`.
7. Индексы и venv: `codegraph init --yes` в корне проекта, `uv venv` и `uv pip install`
   для `codeprism` (см. раздел 6), `bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index`,
   затем `bash .cursor/mcp-stack/add-serena.sh <root> <serena_port>` и `verify.sh`.
   Перенос стека: `export.sh` / `restore.sh`, см.
   [15-mcp-stack.md](./15-mcp-stack.md).
8. Smoke MCP: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs`.
9. Search-replace имён продукта: имя контейнера, путь, `repo:^...$`, префикс задач.
10. Codex: trust и `.codex/global-trust.snippet.toml` с новым путём.
11. Панель документации: `.doc/web/install.sh --check`, затем `install.sh --project` и `verify.sh`.
12. QA и браузер: свой `dump.sql` и БД стенда, Chrome и chromedriver по
    `.doc/qa/browser-setup.md`, затем прогон Codeception.

Полный чеклист с командами, ожидаемыми результатами и таблицей ошибок -
в `EXPORT_NEXT_STEPS.md` в корне Target. Итог переноса и список сохранённых файлов -
в `.doc/.rebase-report.md` и `.doc/.rebase-preserved.txt`. Канон Дня 1 -
в `.doc/rebase_project.md`.

---

## 8. Встроенные проверки

- Must-check: список обязательных файлов kit, включая канон документации,
  документы миграций, `codegraph-mcp.sh`, `codeprism-mcp.sh`, `jdocmunch-mcp.sh`,
  `.tools/scripts/node-mcp.sh`, `.tools/scripts/run-with-mcp-env.sh`, DSH kit
  (`dsh-router`, `run-ps1.sh`, `smoke.sh`, `models.overlay.json`), Qoder view
  (`rules/doc-rules.md`, `settings.json`, `skills/ponytail/SKILL.md`) и Qwen view
  (`rules/doc-rules.md`, `settings.json`, `skills/rule-code-editing/SKILL.md`).
  Файлы `.tools/codeception` проверяются только без `-SkipTools`, vendor Codeception
  только при копировании runtime-зависимостей.
- Forbidden: чужие `tasks/{N}`, `sourcegraph-local/repos-mirror`, лишние скилы,
  скопированные venv, `qa/tmp-runs`, абсолютный путь образца в конфигах.
- Stale-пути: конфиги не должны содержать абсолютный путь образца; адрес CodePrism
  образца заменён заглушкой.
- Реестр: `component_registry.json` очищается от удалённых скилов и runtime-путей,
  поэтому `validate_registry.py` на Target не падает на отсутствующих компонентах.
- Git: запись локального exclude, `git check-ignore` для `.cursor/mcp.json`.
- Скрипт печатает `EXPORT_REBASE_DONE` и пишет `EXPORT_NEXT_STEPS.md` в Target.
  Пропуск must-check печатает `EXPORT_REBASE_DONE_WITH_WARNINGS` и возвращает код 2.

Синтаксис скриптов проверяется разбором PowerShell:

```powershell
pwsh -NoProfile -Command "[void][System.Management.Automation.Language.Parser]::ParseFile('$PWD/.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1',[ref]$null,[ref]$null)"
```

---

## 8. Исправления после аудита переноса (2026-11-03)

Аудит переноса в `/home/newuser/projects/testmigrate` нашёл восемь дефектов. Все
закрыты в скрипте и каноне; ручной остаётся только замена продуктовых строк.

| Было | Исправление | Проверка на Target |
|---|---|---|
| `mysql` в `.cursor/mcp.json` указывал на абсолютный путь образца | канон переведён на `${workspaceFolder}`, `mysql-mcp-proxy.mjs` вычисляет корень от `import.meta.url` или `MCP_WORKSPACE` | `.cursor`, `.codex`, `.kilo`, `.agents` не содержат путь образца |
| `.codex/config.toml` хранил 12 абсолютных путей образца | `Rewrite-SourcePaths` заменяет путь и имя каталога во всех текстовых файлах kit | `grep testdeploydocker .codex/config.toml` возвращает 0 |
| не копировались `.doc/skil_data/task-doc` и `.doc/skil_data/business-analyst` | каталоги добавлены в `$docDirs`, данные продукта исключены (`runs`, `work`, `state`, `registry.json`, `registry.snapshots`) | `jsondoc.py` и `business_analyst.py` на месте, `validate_registry.py` passed |
| `validate_registry` падал на удалённых скилах и runtime-путях | `Prune-ComponentRegistry` удаляет компоненты, отсутствующие пути и `skill_dependencies` на удалённые скилы | passed в профилях Full и Core |
| копировались Python venv с абсолютными путями | `.cursor/tools/codeprism-ai/venv` исключён | каталога нет; venv создаётся по `EXPORT_NEXT_STEPS.md`, разделы 4.3 и 4.7 |
| копировался `.doc/qa/tmp-runs` | каталог добавлен в exclude | каталога нет |
| `AGENTS.md` сохранял имя образца в строке Serena | имя каталога заменяется на имя Target | строка содержит `9121 testmigrate` |
| `.codex/push-test.sh` и `.codex/run-push-test.sh` не проходили `bash -n` | файлы были с CRLF; переписаны на LF, корень репозитория вычисляется от расположения скрипта, remote больше не перезаписывается | `bash -n` проходит |

Отдельно сделан переносимым smoke `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs`:
CBM сверяет slug проекта, serena и codegraph дают SKIP, если файла или индекса
этого продукта нет, вместо ложного DEGRADED.

Автоматическая замена не покрывает продуктовые строки: имя контейнера,
фильтр `repo:^...`, префикс задач и имя БД. Они перечислены в
`EXPORT_NEXT_STEPS.md`, раздел 3.

---

## 9. Повторный экспорт в тот же каталог

Повторный экспорт не удаляет файлы Target. Поведение одинаковое на Windows и
Linux: kit обновляет свои файлы и добавляет новые, чужие файлы остаются.

| Область | Повторный запуск |
|---|---|
| `.cursor`, `.codex`, `.agents`, `.kilo`, `.qoder`, `.qwen`, `.serena`, `.dsh`, каталоги из `$docDirs` | файлы Target, которых нет в образце, сохраняются; файлы с теми же путями обновляются из kit; ручной `.dsh/project.patch.yml` не перезаписывается |
| `.doc/architecture`, `.doc/tasks`, `.doc/harnes/state` | не копируются и не удаляются |
| `AGENTS.md`, `mcp.index.md`, `kilo.json`, файлы из `$docFiles` | перезаписываются версией образца |
| `.cursor/mcp.json` и `.codex/config.toml` | серверы Target, которых нет в kit, сохраняются через merge; одинаковые имена берутся из kit |
| Исключённые пути (`.env`, `mcp.env`, `state`, `.venv*`, `dump.sql`, `tmp-runs`, `work`, `runs`, `registry.json`) | не копируются и не удаляются |

### Повторный экспорт и синк: где перезапись, где слияние

Экспорт kit и синхронизация зеркал по-разному обращаются с тем, что уже есть в среде.

| Шаг | Поведение с существующими файлами |
|---|---|
| `rebase_project.ps1` (экспорт) | копирует поверх: одинаковые пути обновляются из kit, файлы Target вне kit остаются; удаление только с `-MirrorKit` |
| `sync-agent-views.sh` (синк) | обновляет файлы канона в зеркалах по путям (`.codex`, `.kilo`, `.agents`, `.qoder`, `.qwen`); файлы, которых нет в каноне, сохраняются и не удаляются |
| `.cursor/mcp.json`, `.codex/config.toml` | серверы Target, которых нет в kit, возвращаются merge; одинаковые имена берутся из kit |
| `.kilo/kilo.jsonc`, `.agents/mcp.json`, `.qoder/settings.json`, `.qwen/settings.json` | собираются из `.cursor/mcp.json`; Target-only сервер попадает в них только после merge в канон |
| `~/.qoder/`, `~/.qwen/`, `~/.agents/skills` | находятся вне проекта, синк их не читает и не меняет |

Локальное дополнение можно держать в каноне (`.agents/skills`, `.cursor/rules`) или
прямо в зеркале: синк перезаписывает только файлы канона, остальные сохраняет.
Для переноса между проектами надежнее канон, потому что его копирует экспорт.
Генераторы печатают в stderr, сколько локальных правил, файлов скилов и MCP-серверов
они сохранили.

Git: `.gitignore` проекта не копируется и не перезаписывается. Локальные правила
разработчика пишутся только в `.git/info/exclude` управляемым блоком, остальные
строки файла сохраняются. Харнес по умолчанию в git не добавляется и не
коммитится. Документация `.doc` по умолчанию исключается; для нового проекта с
отслеживаемой документацией используйте `-IncludeDocs` при экспорте или
`--include-docs` в мастере. При `-IncludeDocs` исключаются `.doc/temp/`,
`.doc/skil_data/`, бэкапы `.doc/.rebase-*` и `.doc/web/`. Добавление включается явно:
`--add-harness-to-git` и `--add-docs-to-git` в `onboard-project.py` стейджат
соответствующие пути без коммита.

Скилы переноса: `.agents/skills/harness-router/children/new-project/SKILL.md` запускает экспорт и
этап 0, `.agents/skills/harness-router/children/project-setup/SKILL.md` настраивает MCP, порты, индексы и
git. Скрипты лежат в `scripts/` этих скилов; движок экспорта остается в
`.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1`, потому что его вызывают синк и тесты.

До копирования скрипт печатает, сколько файлов перезапишется, добавится и
сохранится вне kit. После копирования пишется отчёт:

- `.doc/.rebase-report.md` - человеку: документация проекта, задачи, кастомные
  скилы, правила и скрипты, перезаписанные и добавленные файлы kit;
- `.doc/.rebase-report.json` - те же данные машинно;
- `.doc/.rebase-preserved.txt` - полный список файлов Target, которых нет в образце.

Отчёт не удаляет и не выбирает за человека: он показывает, что осталось после
смены kit. Очистка выполняется вручную по списку или флагом `-MirrorKit`.

Точное зеркало с удалением лишнего включается флагом `-MirrorKit`. Он использует
`rsync --delete` на Linux и `robocopy /PURGE` на Windows и нужен только при
осознанной синхронизации с образцом.

Проверено 2026-11-03 на `/home/newuser/projects/testmigrate`: собственные файлы в
`.cursor/skills`, `.cursor/rules`, `.tools/scripts`, `.codex/skills`, `.agents/skills`,
`.doc/qa`, `.doc/skil_data/task-doc` и `.doc/web/app` после повторного
экспорта сохранились и попали в `.doc/.rebase-preserved.txt`;
`.doc/architecture`, `.doc/tasks` и `.doc/harnes/state` сохранены;
Target-only MCP-сервер в `.cursor/mcp.json` сохранён.

---

## Связи

- [Точка входа](../index.md) - карта документации харнеса
- [Итог миграции](./21-harness-migration-2026-11-02.md) - текущий канон, Full и Core
- [Сервис панели](./22-panel-service.md) - перенос, state, install, проверки
- [Формат скила](../skill-format.md) - структура, README, `skill.json`
- [Документирование компонентов](../component-docs.md) - документы скилов, скриптов и MCP
- [Установка компонента](../component-install.md) - установка и перенос нового компонента
- План миграции - что добавить в export и must-check
- Аудит плана - находки по export и DSH kit
- [Миграция между агентами](./13-agent-migration.md) - синк зеркал после переноса
- [migration-review](../../../.agents/skills/harness-router/children/migration-review/README.md) - разбор локальных скилов, правил и MCP после переноса
- [add-skill](../../../.agents/skills/harness-router/children/add-skill/README.md) - установка локального скила
- [skill-authoring](../../../.agents/skills/harness-router/children/skill-authoring/README.md) - создание и аудит скила
- [Канон переноса](../../rebase_project.md) - полная процедура и ошибки П-1 - П-20
- [Основной скрипт](../../../.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1) - экспортирует kit в Target
- [Обертка экспорта](../../../.agents/skills/harness-router/children/new-project/scripts/export-rebase-project.ps1) - делегирует основному скрипту
- [Правила документации](../doc_rules.md) - стандарт `.doc/`
- [Устаревший снимок](./09-transfer.md) - только историческая информация, не использовать как инструкцию
- [Копирование приложения](../../../.agents/skills/harness-router/children/copy-project/README.md) - отдельная операция без kit

---

## Известные проблемы и ограничения

- `.codegraph/` не переносится: до `codegraph init --yes` инструмент подсказывает команду.
- `.codex/config.toml` собирается из канона: экспорт запускает `generate-codex-mcp.py`, синк заменяет MCP-секции. Target-only серверы сохраняются merge, ручная правка MCP-секций перезаписывается.
- Kit `.dsh/skills`, `.dsh/adapters`, `.dsh/scripts`, `.dsh/tests` и `models.overlay.json` появляется после `copy-dsh-kit.ps1`. Сгенерированные `project.patch.yml` и `DSH-RULES.md` появляются только после синка на Target.
- После M10 kit `.dsh/skills/dsh-router` содержит `README.md` и `skill.json`; `copy-dsh-kit.ps1 -Check` и `rebase_project.ps1` обязаны их требовать.
- Kilo копируется только с `-IncludeKilo`; без него `.kilo/` создаст синк.
- Windows и WSL требуют разных лаунчеров MCP: `.cmd` против `.sh` для phpstan и php-deps.
- Секреты и токены не переносятся, их заполняют заново.
- Target-only MCP восстанавливаются только при включённом merge, иначе нужен `-SkipMcpMerge` осознанно.

---

## Исторический контракт Full/Core 2026-11-12

Full: общий канон скилов и средств разработки харнеса, README/docs скилов, всё `.doc/harnes`, `.doc/qa`, `.doc/web` без env/local-файлов. Core: операционные скилы кода и внутренние адаптеры; без authoring, task/Jira, панели, QA-корпуса и документации разработки. Данные `.doc/skil_data` не копируются, кроме файлов-примеров; discovery и граф mirror пересоздаются на Target.

После фильтрации профиля, merge MCP и правки абсолютных путей скрипт обязательно запускает `sync-agent-views.sh --local-only`. Источник не нуждается в готовых зеркалах. Ошибка синхронизации останавливает экспорт. Глобальные конфиги не переключаются на новый проект.

Совпавшие пути kit заменяются после бэкапа. Target-only сохраняется в migrate/update, включая DSH; в clean допускается удаление с бэкапом. Корневые инструкции Target и настройки Codex сохраняются. Бэкап больше не зависит от пропуска preflight и охватывает .tools и документацию. Копирование с неполными исключениями запрещено: нужны rsync или robocopy.

## История изменений

- 2026-11-12: устранены ошибки бэкапа, DSH preserve, discovery, устаревших must-путей; добавлены автоматический локальный sync и разделение Full/Core по назначению.

- 2026-11-11: экспорт перестал блокироваться адресом CodePrism в источнике и существующим `.codex/config.toml` в Target; адрес образца заменяется заглушкой. `.tools/scripts` копируется всегда, `.tools/codeception` получает конфиги suite, must-check приведён к текущей раскладке и возвращает код 2 при пропусках, `clean` без бэкапа запрещён.
- 2026-11-11: источники php-toolchain переносятся из `.tools/mcp-servers`, зависимости Node копируются без `-SkipRuntimeDeps`.
- 2026-11-10: добавлено разграничение трёх операций переноса, исправлены ссылки на актуальные скилы и скрипты
- 2026-10-29: создан как отдельный документ по миграции между проектами
- 2026-10-29: зафиксированы copy/no-copy, merge MCP, профиль Core, post-transfer шаги с graphify и синком
- 2026-11-02: добавлены аудит плана и требование README/skill.json для DSH kit после M10
- 2026-11-03: перенос `jsondoc_scripts` и `buisnes_analis` без данных продукта; абсолютные пути образца заменяются на Target; venv, `qa/tmp-runs` и `.kilo/mcp.env` не копируются; реестр компонентов очищается; must-check проверяет stale-пути; `EXPORT_NEXT_STEPS.md` содержит полный чеклист запуска
- 2026-11-03: исправлены `.codex/push-test.sh` и `.codex/run-push-test.sh` (CRLF, абсолютный корень, перезапись remote); smoke MCP стал переносимым для CBM, serena и codegraph; добавлен раздел 10 с результатами аудита
- 2026-11-03: добавлен раздел 11 о повторном экспорте: что удаляется через `rsync --delete`, что сохраняется и почему нет проверки лишних скилов
- 2026-11-03: добавлена среда Qoder: `.qoder/rules`, `.qoder/skills`, `.qoder/settings.json` генерируются из канона, MCP идет через `run-with-mcp-env.sh`; экспорт и синк обновляют только свои файлы, локальные скилы, правила и MCP-серверы Target сохраняются
- 2026-11-03: добавлена среда Qwen Code: `.qwen/rules` и `.qwen/settings.json` генерируются из канона, `.agents/skills` и `AGENTS.md` читаются нативно; model-decision правила превращаются в скилы `rule-*`, HTTP в `httpUrl`, выключенные серверы в `mcp.excluded`
- 2026-11-03: миграция в сторонний проект сохраняет ручной `.dsh/project.patch.yml`; пустой `.doc/architecture/index.md` не создается, если архитектура лежит в каталоге с другим именем
- 2026-11-05: добавлены режимы `migrate`, `clean`, `update`, бэкап всех перезаписываемых файлов в `.doc/.rebase-backup`, отчет `.doc/.rebase-conflicts.json`, маркер `.doc/.rebase-kit.json` и автоматический разбор `migration-review` в режиме `migrate`
- 2026-11-05: `sourcegraph-local` исключен из миграции; добавлен безопасный набор `.tools` без `.env`, `dump.sql`, `vendor`, `_output`, `__pycache__` и флаг `-SkipTools`
- 2026-11-03: экспорт копирует `.codeprism.toml` и `.cbmignore`, выбирает Target-порт Serena и переписывает его во всех клиентах; в `EXPORT_NEXT_STEPS.md` добавлена таблица фактического состояния MCP и вопросы агенту
- 2026-11-03: добавлен `onboard-project.py`: проверка и настройка MCP, MySQL (включая отключение), свободные порты Serena и веб-панели, codegraph, codeprism venv, jdocmunch, CBM, git-исключения; харнес в git только по явному флагу
- 2026-11-03: git-исключения разделены: харнес исключён по умолчанию, документация `.doc` включается/исключается отдельно (`-IncludeDocs`, `--include-docs`, `--exclude-docs`); веб-порт выбирается с учётом портов соседних проектов
- 2026-11-03: экспорт печатает нумерованные шаги `[N]`, время, статус `OK/WARN`, число OK и WARN и сводку шагов в конце
- 2026-11-04: добавлены скилы `new-project` и `project-setup`, этап 0 с подтверждением перезаписи, флаг `-Yes`, пошаговый отчёт и вход `run-export.ps1`

---

## Известные проблемы и ограничения

- `.codegraph/` не переносится: до `codegraph init --yes` инструмент подсказывает команду.
- `.codex/config.toml` собирается из канона: экспорт запускает `generate-codex-mcp.py`, синк заменяет MCP-секции. Target-only серверы сохраняются merge, ручная правка MCP-секций перезаписывается.
- Kit `.dsh/skills`, `.dsh/adapters`, `.dsh/scripts`, `.dsh/tests` и `models.overlay.json` появляется после `copy-dsh-kit.ps1`. Сгенерированные `project.patch.yml` и `DSH-RULES.md` появляются только после синка на Target.
- После M10 kit `.dsh/skills/dsh-router` содержит `README.md` и `skill.json`; `copy-dsh-kit.ps1 -Check` и `rebase_project.ps1` обязаны их требовать.
- Kilo копируется только с `-IncludeKilo`; без него `.kilo/` создаст синк.
- Windows и WSL требуют разных лаунчеров MCP: `.cmd` против `.sh` для phpstan и php-deps.
- Секреты и токены не переносятся, их заполняют заново.
- Target-only MCP восстанавливаются только при включённом merge, иначе нужен `-SkipMcpMerge` осознанно.
