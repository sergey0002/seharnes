# Скрипт: `harness_transfer.py`

<!-- meta
type: script
status: actual
updated: 2026-11-12
related: [../../SKILL.md]
tags: [harness, transfer, preview, git]
-->

## Суть

Строит read-only инвентарь и предпросмотр обновления харнеса для явно выбранных файлов или корней. Сравнивает локальный исходник либо уже полученное локальное bare-хранилище Git с Target и пишет только состояние предпросмотра.

## Когда запускать

Для проверки состава и конфликтов до применения обновления, для диагностики выбранных путей и для сверки Target с установленным receipt. Это не мастер переноса и не применяет изменения.

## Аргументы

| Аргумент | Значение |
|---|---|
| `inventory` | Read-only снимок Source и Target: SHA-256, режим, защищённые пути. |
| `fetch` | Получить одну ветку или тег в локальное bare-хранилище без checkout. |
| `plan` | Read-only предпросмотр обновления с решениями по конфликтам. |
| `verify` | Сверка Target с `.doc/web/state/transfer/receipt.json`. |
| `approve` | Проверяет решения и фиксирует сохранённый план без записи managed-файлов. |
| `apply` | Применяет одобренный план к файлам выбранных корней с backup, журналом и receipt. |
| `rollback` | Восстанавливает активный журнальный прогон из backup. |
| `render` | Пересобирает generated views текущими доверенными генераторами. |
| `compact` | Удаляет generated views и оставляет компактный канон. |
| `adopt` | Строит read-only предпросмотр существующих файлов Target для legacy adopt. |
| `--check` | Проверить views без записи в `render` или показать generated paths в `compact`. |
| `--apply` | Удалить generated paths в `compact`; без флагов `compact` тоже применяет. |
| `--force` | Пропустить проверку содержимого в `compact`. |
| `--plan` | Путь к JSON сохранённого плана. |
| `--decisions` | JSON с решениями по обязательным путям плана. |
| `--approved` | JSON, созданный `approve`, для `apply`. |
| `--render` | После успешного `apply` пересобрать project-local views текущим renderer. |
| `--no-render` | Не пересобирать views автоматически для harness Target. |
| `--url` | Git remote с разрешённой схемой или абсолютный локальный путь при `--allow-local`. |
| `--cache` | Локальное bare-хранилище для `fetch`. |
| `--ref` | Имя ветки или тега для `fetch`. |
| `--allow-local` | Разрешить абсолютный локальный Git-путь в `fetch`. |
| `--timeout` | Предел выполнения `fetch` в секундах, по умолчанию 120. |
| `--source-kind local\|git` | Локальный каталог или локальное bare-хранилище Git. По умолчанию `local`. |
| `--source` | Каталог локального исходника. |
| `--repo` | Уже полученное локальное bare-хранилище Git; сеть не используется. |
| `--commit` | Полный идентификатор commit для Git-источника. |
| `--target` | Каталог проекта; для `plan` может ещё не существовать. |
| `--path` | Явный относительный путь; повторяется для каждого файла. |
| `--root` | Обнаружить файлы под относительным корнем; повторяется. |
| `--exclude` | Исключить путь или префикс из выбранных файлов; повторяется. |
| `--profile` | `core`, `developer` или `project`; без `--root`/`--path` профиль выбирает authored roots и файлы через `profile_manifest`. Generated views исключаются. |
| `--operation` | `install` или `update`; `repair` отклоняется до записи. |
| `--base-commit` | Исторический commit для сравнения; это не receipt. |
| `--use-receipt` | Прочитать `.doc/web/state/transfer/receipt.json` Target. |
| `--local` | Путь, принадлежащий Target; повторяется. |
| `--use-local-policy` | Прочитать `.doc/harnes/state/canon-paths.local.yaml`; нужен baseline и `--root`. |
| `--max-file-bytes` | Максимальный размер файла, по умолчанию 8 МиБ. |
| `--full` | В `verify` дополнительно перечислить файлы под корнями, которых нет в receipt. |
| `--state-dir` | Каталог state, журнала и backup; по умолчанию `.doc/web/state/transfer` Target. |
| `--release-manifest` | Производный манифест релиза для сверки содержимого выбранных файлов. |
| `--jsonl` | События JSONL вместо одного JSON-отчёта. |
| `--non-interactive` | Принимается для общего контракта; скрипт не задаёт вопросов. |

## Коды выхода

`0` - предпросмотр построен и решений не требуется; `2` - нужны решения по конфликтам или добавлениям; `3` - preflight остановлен; `4` - план устарел; `5` - прогон откатан; `6` - нужно ручное восстановление; `fetch`: `0` - ref получен, `3` - preflight остановлен; `verify`: `0` - совпадение, `1` - найдены расхождения, `3` - preflight остановлен; `approve`: `0` - решения приняты, `2` - решения неполные или недопустимые, `4` - Target, Source или срок плана изменились; `apply`: `0` - применено или менять нечего, `2` - решение недопустимо, `3` - preflight, `5` - откат после ошибки, `6` - ручное восстановление; `render`: `0` - views собраны или совпадают, `3` - генератор или проверка не прошли; `compact`: `0` - удалено или уже компактно, `1` - `--check` нашёл generated paths, `2` - проверка не прошла; `adopt`: `0` - решения применены или менять нечего, `2` - построен предпросмотр, нужны решения, `3` - preflight остановлен, `4` - Target изменился после предпросмотра.

## Что читает и что пишет

Читает выбранные файлы Source и Target, объекты локального bare-хранилища Git, экспериментальный receipt и локальную политику. Пишет `plan.json` в `.doc/web/state/plans` установленного Target либо во временный каталог, если receipt отсутствует. `approve` пишет `<plan_id>.approved.json` рядом с планом с правами `0600`. `apply` пишет выбранные managed-файлы, backup и SQLite-журнал в `.doc/web/state/transfer`, receipt пишет последним. `rollback` восстанавливает файлы из backup. `render` пересобирает generated views Target текущими генераторами. `adopt` пишет `adopt`-план в state; с `--plan` и `--decisions` пишет receipt для выбранных файлов и не меняет их содержимое. Вне выбранных корней записи нет.

## Побочные эффекты

Запускает локальный Git для чтения объектов. Checkout, hooks, filters, submodules и код кандидата не выполняются. Создаёт каталог состояния предпросмотра с правами `0700` на POSIX.

## Окружение и зависимости

Python 3 и Git в PATH для Git-источника. Использует библиотеку `scripts/lib/transfer_*.py` и `harness-core/scripts/canon_paths.py`. Известные сигнатуры секретов берутся из установленного Mirror, не из исходника кандидата.

## Примеры

```sh
python3 .agents/skills/harness-router/children/new-project/scripts/harness_transfer.py plan \
  --source-kind git --repo /tmp/seharnes.git --commit FULL_COMMIT_ID \
  --target /tmp/project --root .agents/skills --root .cursor/rules \
  --profile developer --operation update --use-receipt
```

```sh
python3 .agents/skills/harness-router/children/new-project/scripts/harness_transfer.py verify \
  --target /tmp/project --root .agents/skills
```

## Ограничения

Скрипт не проверяет доверие к commit и не разрешает запись без `approve`. `apply` поддерживает обычные файлы, `AGENTS.md` (заменяется только маркированный managed block) и `.cursor/mcp.json` (структурный merge: серверы Target сохраняются, новые и конфликтующие upstream-серверы добавляются disabled). `apply --render` и автоматический режим после commit пересобирают project-local views; generated views не входят в receipt и не откатываются вместе с managed-файлами. Staging renderer до первой записи остаётся открытым пунктом. Остальные настройки адаптеров (`.codex/config.toml`, `.qwen/settings.json`, `.kilo/kilo.jsonc`, `.qoder/settings.json`) отклоняются до lock при выборе в плане; generated views в плане также отклоняются, а после commit пересобираются через `--render`. Панель, supervisor, Docker и Windows-native входы в текущую область не входят. `fetch` получает только одну именованную ветку или тег в `refs/harness/source`, не делает checkout и не запускает hooks, filters или код кандидата. Схемы `https` и `ssh` разрешены, встроенный пароль в URL отклоняется, локальный путь требует `--allow-local`. Release trust, разрешение профиля в набор путей и Windows-тесты ещё не реализованы; их состояние видно в `checks` как `not_run`. Исторический commit и receipt не доказывают владение файлом: при отсутствии baseline каждый существующий файл Target требует решения.

`base`, `source_commit_sha` и `source_tree_digest` показывают происхождение выбранных данных, но не заменяют release manifest. Проверка секретов использует только известные сигнатуры Mirror и не гарантирует обнаружение всех секретов. Защищённые имена не читаются, а только перечисляются. Symlink, junction, hardlink, выход за корень и коллизии регистра отклоняются до записи.

`verify` сравнивает SHA-256 и сообщает о различии режима как предупреждение: режимы Git и Windows не приведены к общей переносимой модели. Смена одного режима не считается изменением содержимого.

## Связи

Вызывается вручную или будущим мастером `harness_wizard.py` и панелью. Использует библиотеку `scripts/lib/transfer_plan.py`, `transfer_inventory.py`, `transfer_git.py`, `transfer_local.py`, `transfer_receipt.py`, `transfer_report.py` и общий reader `canon_paths.py`.

## История изменений

- 2026-11-12: добавлены read-only команды `inventory`, `plan` и `verify`; apply/rollback остаются следующей стадией.
