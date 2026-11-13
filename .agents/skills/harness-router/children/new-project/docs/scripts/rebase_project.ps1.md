# Скрипт: `.agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md]
tags: [harness, script, rebase_project]
-->

## Суть
Основной скрипт экспорта AI-kit (Cursor + Codex) и инфраструктуры `.doc/` в новый каталог проекта. Канон рядом с документом: `.doc/rebase_project.md`. Реализует перенос по профилю FULL (с Jira/gototask/qa/codeception) или CORE (без трекера и task-skills). Создаёт целевую папку, копирует необходимое (без секретов kit и без `tasks/{N}`), пишет `.git/info/exclude`, готовит `mcp.env` из example, правит `Serena project_name`. Режимы: `migrate` (первый перенос, конфликты и анализ локальных компонентов), `clean` (удалить kit-компоненты Target и установить только kit), `update` (обновить kit поверх уже перенесенного без разбора конфликтов). MCP merge по умолчанию: kit-серверы (sourcegraph, graphify…) + Target-only (laravel-boost…). Опционально: Windows MCP launchers (phpstan/php-deps/CBM/graphify через cmd), точное зеркало (`-MirrorKit`), бэкап перезаписываемых файлов, post-merge review (`review_migration.py`), Serena порт, git exclude, setup-скрипты.

## Когда запускать
- Первый перенос харнеса в новый проект (`migrate` mode).
- Обновление kit в существующем проекте (`update` mode).
- Полная переустановка kit (`clean` mode).
- Агент/пользователь запускает при команде «перенеси харнес», «новый проект», «обнови kit».

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Target |  | string | да |  | Каталог нового проекта (создаётся) |
| -Source |  | string | нет | '' | Корень репозитория-образца (по умолчанию родитель .doc/) |
| -Profile |  | string | нет | 'Full' | Full (с Jira/gototask/qa/codeception) или Core |
| -Mode |  | string | нет | 'migrate' | migrate / clean / update |
| -ProjectName |  | string | нет | '' | Имя для .serena/project.yml (по умолчанию имя папки Target) |
| -IncludeKilo |  | switch | нет |  | Копировать .kilo / kilo.json (без node_modules) |
| -SkipTools |  | switch | нет |  | Не копировать инфраструктурные `.tools` (docker-dev, php85-scan, Codeception); `.tools/scripts` и `.tools/mcp-servers` копируются всегда |
| -SkipRuntimeDeps |  | switch | нет |  | Не копировать `node_modules` в `.tools/mcp-servers/php-toolchain` и `tools/vendor` (phpstan/phpda + codeception) |
| -SkipGitInit |  | switch | нет |  | Совместимый запрет Git init; по умолчанию он не выполняется |
| -SkipExclude |  | switch | нет |  | Совместимый запрет записи exclude; по умолчанию он не изменяется |
| -InitGit |  | switch | нет |  | Явно создать Git в Target при отсутствии репозитория, без назначения origin |
| -ManageGitExclude |  | switch | нет |  | Явно разрешить запись управляемого блока в .git/info/exclude |
| -IncludeDocs |  | switch | нет |  | При -ManageGitExclude не исключать .doc/ |
| -SkipPreflight |  | switch | нет |  | Не строить SHA256-манифест перед копированием |
| -RunSetup |  | switch | нет |  | Запустить .cursor\setup.ps1 и .codex\setup.ps1 |
| -SkipMcpMerge |  | switch | нет |  | Не мержить Target-only MCP (kit-only) |
| -SkipSiblingConfig |  | switch | нет |  | Не создавать пустой sibling ..\.config |
| -MirrorKit |  | switch | нет |  | Точное зеркало: удалить в Target файлы, которых нет в образце |
| -SerenaPort |  | int | нет | 0 | Порт Serena для Target (0: авто из .dsh/scripts/serena-shared.sh) |
| -SkipBackup |  | switch | нет |  | Не сохранять бэкап перезаписываемых файлов |
| -SkipReview |  | switch | нет |  | Не запускать анализ локальных компонентов (review_migration.py) |
| -Yes |  | switch | нет |  | Не спрашивать подтверждение на перезапись |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех | Продолжить работу |
| 1 | Ошибка (пользователь отменил, целевая папка занята, копирование failed, `clean` без бэкапа) | Проверить вывод, исправить и повторить |
| 2 | Must-check нашёл пропуски или запрещённые файлы | Разобрать `EXPORT_REBASE_DONE_WITH_WARNINGS`, повторить проверку |

## Что читает и что пишет
**Читает (Source):**
- `.cursor/`, `.codex/`, `.kilo/`, `.agents/`, `.qoder/`, `.qwen/` — среды агентов
- `.dsh/` — DSH kit (skills, adapters, scripts, tests, models.overlay.json)
- `.doc/architecture/`, `.doc/harnes/`, `.doc/web/`, `.doc/qa/` — документация (кроме tasks/{N}, skil_data, temp)
- `.serena/` — конфиг Serena
- `.tools/mcp-servers/` — источники MCP-серверов, копируются всегда
- `.tools/scripts/` — обёртки `node-mcp`, `run-with-mcp-env`, `mysql-mcp-proxy`, копируются всегда
- `.tools/` — docker/test инструменты и конфиги Codeception (если не -SkipTools)
- `.tools/mcp-servers/php-toolchain/node_modules/`, `.cursor/tools/vendor/`, `.codex/tools/vendor/` — runtime deps (если не -SkipRuntimeDeps)

**Пишет (Target):**
- Все вышеперечисленные каталоги (кроме исключений)
- `.git/info/exclude` — managed block (исключения сред, .doc/harnes/, .tools/, .serena/, .dsh/, .kilocode/, sourcegraph-local/, graphify-out/, tools/docker-dev/, tools/codeception/)
- `.cursor/mcp.json` — с merge Target-only MCP, скруб секретов/путей, rewrite путей Source→Target; CodePrism отключён, его адрес заменён заглушкой
- `.codex/config.toml` — merge Target-only MCP, rewrite путей
- `.serena/project.yml` — `project_name: <Target имя>`
- `.doc/.rebase-report.md` + `.json` — отчёт переноса (kit stats, custom components, overwritten/added/removed)
- `.doc/.rebase-preserved.txt` — список файлов Target вне kit
- `.doc/.rebase-conflicts.json` — конфликты (backup_dir, overwritten[], mode)
- `.doc/.rebase-backup/<timestamp>/` — бэкап перезаписываемых файлов (если не -SkipBackup)
- `.doc/.rebase-mcp-backup/cursor.mcp.json` — бэкап оригинального MCP
- `.doc/.rebase-kit.json` — маркер kit (mode, kit_version)

## Побочные эффекты
- Создаёт/перезаписывает файлы в Target.
- `git init` только при явном `-InitGit`, если в Target нет .git; без origin.
- Запускает `.cursor/setup.ps1` и `.codex/setup.ps1` (при -RunSetup).
- Запускает `review_migration.py` (при migrate mode, не -SkipReview).
- В режиме `migrate` запускает `review_migration.py`, если не задан `-SkipReview`.
  Review синхронизирует views только после применения предложений. Для любого
  режима после экспорта отдельно запусти `sync-agent-views.sh` в Target.
- Windows MCP launchers: переписывает phpstan/php-deps/CBM/graphify на cmd-wrappers (при Windows Target).

## Окружение и зависимости
- PowerShell 5+ / pwsh.
- `robocopy` (Windows) / `rsync` (Linux/WSL) / `Copy-Item` fallback.
- `git` — для init, exclude, SHA256 манифеста.
- `node`/`npm` — для setup-скриптов (при -RunSetup).
- `python3` — для review_migration.py.
- `bash` — для sync-agent-views.sh.

## Примеры
```powershell
# Базовый перенос (Full profile, migrate mode)
pwsh -NoProfile -ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 -Target "C:\laragon\www\test"

# Core profile, кастомное имя, запуск setup
pwsh -NoProfile -ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 `
  -Target "C:\laragon\www\myapp" -Profile Core -ProjectName myapp -RunSetup

# Update mode (обновление kit без конфликтов)
pwsh -NoProfile -ExecutionPolicy Bypass -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 `
  -Target "C:\laragon\www\existing" -Mode update -Yes
```

Вывод (фрагменты):
```
[1] 10:30:15  Resolve paths  OK, warn=0, 0.1s
[2] 10:30:15  Target directory  OK, warn=0, 0.0s
[3] 10:30:15  Preflight manifest  OK, warn=0, 1.2s
[4] 10:30:16  Copy kit dirs  OK, warn=0, 3.5s
...
Сводка шагов экспорта:
   1. Resolve paths                                      OK   ok=1 warn=0     0.1s
   2. Target directory                                   OK   ok=1 warn=0     0.0s
   3. Preflight manifest                                 OK   ok=1 warn=0     1.2s
   4. Copy kit dirs                                      OK   ok=1 warn=0     3.5s
   ...
Kit: перезаписано=142, добавлено=35, без изменений=1205
Файлов вне kit сохранено: 23. Очистка: -MirrorKit или список .doc/.rebase-preserved.txt

Обзор миграции
  маркер kit: есть
  бэкап: .doc/.rebase-backup/20261107T103000Z (45 файлов, 1.0 MB)
    категории: skill=3, rule=12, script=5, mcp=2, docs=8, other=15
    MCP: .doc/.rebase-mcp-backup (1 файлов, 2.0 KB)
  предложения: skills=5, rules=12, mcp=3, manual=2
  my-skill [install] skill exists in canon but not in the package manifest
  custom-rule [install] local rule is not present in the canonical cursor rules
  legacy-mcp [install] server exists in the original project config and is missing from the current canon
  conflict-skill [manual] the same skill exists in several views with different files
  применено: skill:my-skill, rule:custom-rule, mcp:legacy-mcp
  sync passed
```

## Ограничения
- Не копирует секреты: Sourcegraph token, Chrome paths, LD_LIBRARY_PATH — скрубятся в MCP.
- Не копирует `tasks/{N}/` — задачи переносятся отдельно (`gototask`).
- Не копирует `.doc/skil_data/` и `.doc/temp/` — локальные данные скилов.
- `-MirrorKit` удаляет файлы Target без подтверждения — использовать осторожно.
- `-Mode clean -SkipBackup` запрещён: очистка kit-компонентов без бэкапа не запускается.
- Windows Target: авто-переключение MCP на cmd-wrappers (phpstan/php-deps/CBM/graphify).

## Связи
- Вызывается: агент по команде «перенеси харнес», «новый проект», `new-project` скил, `export-rebase-project.ps1` (wrapper)
- Зависит от: `copy-dsh-kit.ps1`, `review_migration.py`, `sync-agent-views.sh`, `rebase_project_gi.ps1` (git exclude)
- Результат использует: Target проект с kit, `EXPORT_NEXT_STEPS.md` и
  `onboard-project.py --check` для проверки до настройки

## История изменений
- 2026-11-11: CodePrism больше не блокирует перенос адресом источника или существующим `.codex/config.toml`; адрес заменяется заглушкой. `.tools/scripts` копируется всегда, Codeception получает конфиги suite, must-check возвращает код 2, `clean` без бэкапа запрещён.
- 2026-11-07: полная документация на основе кода (status: actual)
- 2026-11-10: уточнены post-export sync, review и onboarding по фактическим вызовам

## Изменения 2026-11-12

Перенос блокируется при пересечении корней. Для migrate/update DSH вызывается с `-PreserveLocal`: target-only файлы не удаляются; самостоятельный вызов без флага сохраняет строгий mirror-контракт. Discovery-указатели DSH не копируются из Source, их создаёт sync. Манифест бэкапа охватывает изменяемые каталоги, включая .tools и документацию; локальные адаптеры Source исключены из копирования.

Full включает .doc/harnes целиком, QA и web без секретов; skil_data только примеры. Core оставляет операционные скилы кода и внутренние адаптеры, исключая authoring/task/Jira, панель и документацию разработки. Финальный sync --local-only выполняется после выбора профиля и merge канона. AGENTS.md существующего проекта и настройки Codex не заменяются шаблоном. Source leaf не подставляется глобально в исходники; меняются только абсолютные пути.

### Изоляция документации (2026-11-12)

Handle jdocmunch определяется через `doc_resolve_repo` для `.doc` текущего проекта. Фиксированный handle исходного проекта не используется. Если индекс Target ещё не создан, это отдельный шаг настройки; перенос не индексирует чужую документацию и не запускает MCP-службы. Core получает операционные правила без команд JSONdoc и ссылок на удалённые task-скилы.

### Связанные документы вне `.doc/harnes`

Full также переносит документы `architecture/deepseek-harness-*`, `local-embeddings`, `local-dev-resources`, `sourcegraph-local` и их JSON-канон, если он существует. Исторический аудит `auditskil777.md` включается при наличии. Контент задач и архитектура приложения не импортируются. Ссылки из авторских документов kit на исключённый контент становятся текстовыми указаниями с пометкой «не входит в kit»; список записывается в `.doc/.rebase-doc-links.json`. Отсутствующая ссылка внутри переносимого harnes/qa/web считается ошибкой переноса.
