# Скрипт: .agents/skills/harness-router/children/copy-project/scripts/copy-project.sh

<!-- meta
type: script
status: actual
updated: 2026-11-10
related: [../SKILL.md, ../assets/startup-checklist.md]
tags: [harness, script, copy-project, git]
-->

## Суть

Создаёт в Target копию Git-снимка Source вместе с `.git` и без harness. В копии
удаляются `.git/worktrees` и lock-файлы, чтобы worktree-регистрации не указывали
на исходный репозиторий. Пишет `STARTUP-REQUIRED.md` со списком найденных шаблонов
окружения, lock-файлов, compose-файлов, каталогов схемы и переменных, которые
нужно заполнить вручную. Секреты из рабочих файлов, база данных и незатреканные
файлы не переносятся; история `.git` копируется как есть.

## Когда запускать

Скил `copy-project` запускает скрипт после проверки состояния репозитория. Запуск
без проверки отчёта даёт копию кода, но не готовое к работе приложение.

## Аргументы

| Аргумент | Обязателен | Значение |
|---|---|---|
| `--source DIR` | да | Корень Git-репозитория |
| `--target DIR` | да | Новая папка, которой ещё нет |
| `--force` | нет | Заменить существующий Target |
| `--include-tracked-changes` | нет | Добавить незакоммиченные изменения tracked-файлов |
| `--report FILE` | нет | Скопировать отчёт в указанный путь после переноса |
| `-h`, `--help` | нет | Показать использование |

## Коды выхода

| Код | Значение |
|---|---|
| 0 | Перенос выполнен, Target создан |
| 1 | Ошибка аргументов, Target существует, перекрытие путей |
| 2 | Source не является Git-репозиторием |
| 3 | Найдено запрещённое состояние: submodules, LFS, символическая ссылка, `.git`-файл |

## Что читает и что пишет

Читает Git-индекс Source, отслеживаемые файлы, `.gitmodules`, атрибуты LFS и
каталог `.git`. Исключает секретные env-файлы по имени даже при наличии в Git:
`.env`, `.env.*` кроме `.example`, `.dist`, `.sample`, `.template`, а также `*.env`.
Копирует `.git` целиком, затем удаляет `worktrees/` и lock-файлы, добавляет
`STARTUP-REQUIRED.md` в `.git/info/exclude` и проверяет, что репозиторий читается.
Пишет staging-каталог рядом с Target, затем Target и `STARTUP-REQUIRED.md`.
Значения переменных не читает и не печатает.

## Побочные эффекты

Создаёт и удаляет staging-каталог. Копирует `.git` с историей, ветками, remotes,
reflog и hooks. При `--force` удаляет существующий Target после успешной
подготовки staging. Source не изменяется: индекс, `.gitignore`, `.git` и рабочие
файлы остаются без изменений.

## Окружение и зависимости

Нужны `bash`, `git`, `realpath`, `find`, `grep`, `sed`, `sort`, `cp`, `mv`.
Работает в Linux и WSL. Символические ссылки и submodules не поддерживаются.

## Примеры

```bash
bash .agents/skills/harness-router/children/copy-project/scripts/copy-project.sh \
  --source /path/to/project \
  --target /path/to/copy
```

```bash
bash .agents/skills/harness-router/children/copy-project/scripts/copy-project.sh \
  --source /path/to/project \
  --target /path/to/copy \
  --include-tracked-changes \
  --report /tmp/copy-report.md
```

## Ограничения

Не устанавливает зависимости, не запускает приложение, не проверяет доступность
базы, не переносит ignored данные вроде загрузок и кэша и не вычищает секреты из
истории `.git`. `.git`-файл (linked worktree, submodule) не поддерживается.
Счётчики исключённых harness-путей и секретных env-файлов выводятся отдельно,
рядом с размером `.git` и состоянием Git в Target.

## Связи

Вызывается скилом `copy-project`. Ручная проверка описана в
`assets/startup-checklist.md`. Перенос kit харнеса выполняет `new-project`.

## История изменений

- 2026-11-09: скрипт создан на основе рабочей логики `create-isolated-workspace.sh`;
  убраны жёстко записанные секреты, добавлены отчёт, запреты и коды выхода.
- 2026-11-10: tracked secrets env-файлы и дополнительные harness-пути исключаются
  явно; отчёт показывает отдельный счётчик секретных env-файлов.
- 2026-11-10: `.git` копируется вместе с проектом; удаляются worktree-регистрации
  и lock-файлы; в отчёт добавлены размер `.git`, remotes и состояние Git. Причина:
  копия CopyTrust2 осталась без репозитория, `git status` падал.
