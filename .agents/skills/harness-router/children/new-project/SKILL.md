---
name: new-project
description: >-
  Переносит или обновляет kit харнеса в целевом проекте режимами migrate, clean
  и update. Применять только по запросам перенести харнес, экспортировать kit,
  обновить kit, повторный перенос kit, clean install harness, new-project.
---

# new-project

Перенос kit харнеса в целевой проект и повторное обновление. Основная точка
входа - `rebase_project.ps1`; `harness_cli.py` в этом скиле не используется.

По умолчанию перенос не инициализирует Git и не изменяет `.git/info/exclude`.
Для прежнего поведения нужны явные `-InitGit` и/или `-ManageGitExclude`;
новый `origin` скрипт не назначает.

Перед записью Core проверяет декларации политик Source установленным доверенным Python-reader. При отсутствующей или ослабленной политике перенос останавливается до создания Target; полный preflight релиза и Mirror пока не заменены этой проверкой.
После переноса legacy-скрипт запускает скопированные генераторы Target, поэтому Source должен быть доверенным. Проверка YAML не делает недоверенный Git-источник безопасным.

## Когда применять

- первый перенос харнеса в существующий проект;
- нужен чистый kit без локальных скилов и правил;
- нужно обновить kit в уже перенесенном проекте;
- нужно понять, что было перезаписано и что осталось локальным.

## Вход

- абсолютный путь Target;
- профиль `Full` или `Core`;
- режим `migrate`, `clean` или `update`;
- подтверждение пользователя на перезапись.

## Режимы

| Режим | Поведение |
|---|---|
| `migrate` | бэкап перезаписанных файлов, kit поверх Target, target-only сохраняется, после переноса запускается `migration-review` |
| `clean` | бэкап всех kit-файлов Target, удаление kit-компонентов вне kit, установка только kit, без разбора; запуск без бэкапа запрещён |
| `update` | обновление kit поверх уже перенесенного проекта, локальные дополнения сохраняются, без разбора конфликтов |

## Локальные утилиты стенда

Скрипты `create-workspace.sh` и `create-isolated-workspace.sh` были CopyTrust-специфичными и содержали локальные значения. Они вынесены из переносимого скила в `.doc/skil_data/new-project/local/` и не входят в kit. Для переноса в произвольную папку используй `copy-project`.

## Шаги

1. Выбрать режим и профиль.
2. Запустить перенос:

```powershell
pwsh -NoProfile -File .agents/skills/harness-router/children/new-project/scripts/rebase_project.ps1 `
  -Target "C:\path\to\project" -Profile Full -Mode migrate
```

3. Проверить бэкап и отчет:

```text
.doc/.rebase-backup/{timestamp}/
.doc/.rebase-conflicts.json
.doc/.rebase-kit.json
```

4. После переноса открыть `EXPORT_NEXT_STEPS.md` в Target и выполнять его
   настройки только с параметрами целевого проекта.
5. В режиме `migrate` скрипт сам запускает `migration-review`: без `-Yes` он
   интерактивный, с `-Yes` формирует только отчет. При `-SkipReview` запустить
   разбор вручную:

```bash
python3 .agents/skills/harness-router/children/migration-review/scripts/review_migration.py \
  --root . --interactive
```

6. Скрипт автоматически выполняет локальную синхронизацию из канона Target. Для повторной проверки:

```bash
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh --local-only
```

Синхронизация обязательна для всех режимов и блокирует успешный экспорт при ошибке. Она не меняет глобальные конфиги других проектов.

7. Проверить настройки без записи:

```bash
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py \
  --root . --check
```

Затем заполнить Target по `EXPORT_NEXT_STEPS.md`; не применять фиктивные значения
или `--yes` без проверки предлагаемых путей и настроек.

8. В режиме `clean` локальные компоненты не разбираются: они остаются только в
   бэкапе.
9. В режиме `update` повторный разбор не выполняется. Для отдельного разбора запустить
   `migration-review` вручную.

Перенос DSH kit выполняется явно через `copy-dsh-kit.ps1`. Локальный
`.git/info/exclude` исключает `.dsh` из Git, но не мешает этому шагу. Скрипт
`copy-project` использует только tracked-файлы и потому `.dsh` не переносит.

Полная процедура: `.doc/rebase_project.md` и
`.doc/harnes/state/14-project-migration.md`.

## Выход

- kit в Target;
- безопасный набор `.tools` без `.env`, `dump.sql`, `vendor` и `_output`; отключается `-SkipTools`;
- `.tools/scripts` и `.tools/mcp-servers` копируются всегда: на них ссылаются MCP-конфиги;
- `.tools/codeception` получает `codeception.yml`, `composer.json`, `composer.lock` и `scripts` при включённом `.tools`;
- CodePrism остаётся отключённым, адрес образца заменён заглушкой `http://127.0.0.1:0/mcp`;
- бэкап перезаписанных файлов;
- `.doc/.rebase-conflicts.json`;
- маркер `.doc/.rebase-kit.json`;
- отчет разбора в режиме `migrate`.
- `sourcegraph-local` не копируется; стек SG разворачивается вручную.

## Ограничения

- `clean` удаляет kit-компоненты Target вне kit. Без бэкапа не запускать: `-Mode clean -SkipBackup` завершается ошибкой.
- `update` не разрешает конфликты и не устанавливает локальные скилы.
- Секреты и MCP-значения из оригинала не копируются автоматически.
- Прямой запуск `rebase_project.ps1` выполняет разбор только в режиме `migrate`.
- Must-check проверяет наличие обязательных файлов и отсутствие чужих данных. Пропуск печатает `EXPORT_REBASE_DONE_WITH_WARNINGS` и возвращает код 2; успешный перенос печатает `EXPORT_REBASE_DONE`.
- Существующий `.codex/config.toml` в Target не блокирует повторный экспорт: файл бэкапится, MCP-серверы Target-only сохраняются, CodePrism заменяется заглушкой.

## Read-only предпросмотр и сверка

`scripts/harness_transfer.py` — единая точка проверки и файлового обновления для явно выбранных путей или корней. Команды `fetch`, `inventory`, `plan`, `verify`, `approve`, `apply`, `rollback`, `render`, `compact` и `adopt` работают с локальным каталогом или локальным bare-хранилищем Git. `fetch` получает одну ветку или тег без checkout; сеть используется только в этой команде, код кандидата не запускается.

- `fetch` получает ref в `refs/harness/source`; встроенный пароль в URL отклоняется, локальный путь требует `--allow-local`.
- `inventory` показывает SHA-256, режимы и защищённые пути Source и Target.
- `plan` строит предпросмотр с решениями по конфликтам; при отсутствии baseline каждый существующий файл Target требует решения.
- `verify` сверяет Target с `.doc/web/state/transfer/receipt.json`.
- `approve` проверяет решения и срок, заново сверяет Source и Target.
- `apply` пишет выбранные обычные файлы через backup, журнал и verify; receipt пишется последним.
- `rollback` восстанавливает активный журнальный прогон.
- `render` пересобирает generated views текущими доверенными генераторами; `--check` только проверяет.

`apply` поддерживает обычные файлы, `AGENTS.md` (только managed block) и `.cursor/mcp.json` (структурный merge: серверы Target сохраняются, новые и конфликтующие upstream-серверы добавляются disabled). Остальные настройки адаптеров и generated views (`.qoder/`, `.codex/rules/`, `.kilo/rules/`, `.agents/rules/`) в план apply не включаются: их создаёт renderer. `apply --render` пересобирает views после commit. Панель, supervisor, Docker и Windows-native входы в текущую область не входят.

## История изменений

- 2026-11-11: экспорт больше не блокируется адресом CodePrism в источнике и существующим `.codex/config.toml` в Target; адрес образца заменяется заглушкой. `.tools/scripts` копируется всегда, must-check приведён к текущей раскладке и возвращает код 2 при пропусках, `clean` без бэкапа запрещён.

## Профили и текущее состояние

`Core`, `Developer` и `Project` задают состав kit. `Developer` является развитием прежнего Full, `Project` добавляет приложение. Профильная карта строится `profile_manifest.py`; dry-run и `plan --profile` без явных корней используют её. Generated views при выборе профиля исключаются. Фактический PowerShell-export всё ещё копирует по своим спискам, поэтому единый walker для actual export остаётся задачей P0.

`harness_transfer.py apply` поддерживает обычные файлы, `AGENTS.md` и `.cursor/mcp.json`. Generated views в план не включаются, а пересобираются `render_agent_views.py` или `sync-agent-views.sh`. Receipt, SQLite-журнал, backup и `rollback` подключены. Полный staging renderer до первой записи, профильный отбор путей и Windows/NTFS-тесты остаются открытыми.

`compact_agent_views.py` и `harness_transfer compact` удаляют generated views, `composer.phar` и preflight backups. После клона или компакта среды восстанавливаются обычной командой `sync-agent-views.sh`. `doctor --compact` проверяет компактный эталон без view-гейтов, обычный `doctor` требует восстановленные views.

Локальные CopyTrust workspace-скрипты вынесены в `.doc/skil_data/new-project/local/` и не входят в переносимый скил. `copy-project` остаётся отдельным контрактом Git-снимка приложения.

## Связанные документы

Текущий перенос: `harness_transfer.py`, `harness_wizard.py`, `profile_manifest.py`, `render_agent_views.py`, `compact_agent_views.py`. Исторические сведения о старом `rebase_project.ps1`: `.doc/harnes/state/14-project-migration.md` и `.doc/rebase_project.md`.
