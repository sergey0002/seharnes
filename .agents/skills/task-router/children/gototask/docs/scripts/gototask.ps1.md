# Скрипт: `.agents/skills/task-router/children/gototask/scripts/gototask.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, gototask]
-->

## Суть
Скрипт автоматизирует переход к задаче Jira: экспортирует описание и комментарии задачи в `.doc/tasks/{TaskNumber}/task.md`, переключает или создает ветку задачи от базового релиза, а также выполняет слияние изменений релиза при необходимости.

## Когда запускать
Скрипт запускается при переходе к работе над новой или существующей задачей по триггерам "перейди к задаче N", "обнови задачу N", "gototask".

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `-TaskNumber` | нет | string | да | нет | номер задачи (например, 2070) |
| `-Action` | нет | string | нет | "inspect" | действие: inspect, export-task, checkout, create-branch, merge-release, sync |
| `-RepoPath` | нет | string | нет | "" | путь к корню git-репозитория |
| `-ConfigPath` | нет | string | нет | "" | путь к конфигурационному файлу gototask config.json |
| `-ReleaseBranch` | нет | string | нет | "" | базовый релиз задачи |
| `-TaskBranch` | нет | string | нет | "" | имя целевой ветки задачи |
| `-LocalChanges` | нет | string | нет | "keep" | обработка локальных изменений: keep, stash, discard |
| `-SkipTaskExport` | нет | switch | нет | выключен | пропускать экспорт task.md из Jira |
| `-ConfirmCreateBranch` | нет | switch | нет | выключен | подтверждение пользователя на создание новой ветки |
| `-ConfirmDiscard` | нет | switch | нет | выключен | подтверждение пользователя на сброс локальных правок |
| `-ConfirmMerge` | нет | switch | нет | выключен | подтверждение пользователя на слияние релиза |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | inspect или export-task завершён; результат экспорта и ingest проверяется по полям JSON | проверить `taskExport` и `jsondocIngest` |
| 2 | задача не найдена в трекере или ошибка конфигурации | проверить номер задачи или настройки доступа к Jira |
| 3 | требуется подтверждение пользователя для создания ветки, сброса или слияния | запросить подтверждение через AskQuestion и передать соответствующий ключ |

## Что читает и что пишет
Читает настройки из `config.json`, данные задачи из API Jira, состояние и ссылки git-репозитория. Пишет файл описания задачи `.doc/tasks/{TaskNumber}/task.md`.

`inspect` и `export-task` возвращают отдельное поле `jsondocIngest`: `status` равен `success`, `failed` или `skipped`. При ошибке запуска указан `reason`, при завершении процесса также указан `exitCode`. Пропуск содержит причину: `task_export_skipped`, `task_export_failed`, `tracker_not_found`, `jsondoc_not_found` или `python3_not_found`. Вывод JSONdoc не публикуется, чтобы не раскрывать секреты. Ошибка ingest не меняет результат успешного экспорта Jira в `taskExport`.

## Побочные эффекты
После apply бизнес-хук снят: анализ правил больше не запускается.
Переключает текущую ветку git, создает новые ветки, выполняет слияние релизной ветки, создает каталог задачи `.doc/tasks/{TaskNumber}/` и файл `task.md`.

## Окружение и зависимости
Требуется PowerShell 5.1+ или PowerShell Core, установленный git CLI, PHP CLI для выполнения `server.php` экспорта Jira.

## Примеры
```powershell
powershell -File .agents/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 2070 -Action inspect
powershell -File .agents/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 2070 -Action sync -ConfirmMerge
powershell -File .agents/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 2070 -Action export-task
```

## Ограничения
Деструктивные действия (`discard`, `create-branch`) требуют обязательной передачи флагов подтверждения. Без флагов скрипт завершается с кодом 3 без изменения рабочей копии.

## Связи
Основной инструмент переключения задач в `task-router`. Результаты экспорта и переключения используются навыками `task-spec`, `prepare-plan`, `task-diff`.

## История изменений
- 2026-11-09: бизнес-хук заменён на проверку кэша атомарного анализа без автоматической публикации.
- 2026-11-09: добавлен контракт отдельного статуса JSONdoc ingest без публикации вывода процесса.
- 2026-11-07: создан проверенный документ скрипта.
