# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/test-batch.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, lib.sh]
tags: [harness, script, test-batch]
-->

## Суть
Групповой прогон нескольких задач подряд: для каждой задачи выполняет `check-tests.sh` → `task-test.sh` → `gates.py`. Собирает сводку в TSV и JSON. Используется для регрессионного прогона набора задач (например, перед релизом).

## Когда запускать
- Перед релизом для прогона критических задач
- При массовом рефакторинге для проверки смежных задач
- Для ночного/периодического регресса

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| N... (позиционные) |  | int[] | да* |  | Номера задач (один или несколько) |
| --file |  | string | нет |  | Путь к файлу со списком задач (по одному на строку, # комментарии) |
| -h, --help |  | flag | нет |  | Показать справку |

*Хотя бы один номер задачи или --file обязателен.

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все задачи PASS | продолжать |
| 1 | Хотя бы одна задача FAIL | прочитать summary.tsv |
| 2 | Usage error (нет задач, не число) | исправить вызов |

## Что читает и что пишет
**Читает:**
- Аргументы или файл со списком задач
- Для каждой задачи: `.doc/tasks/{N}/diff.files.md` (через вызываемые скрипты)

**Пишет:**
- `.doc/tasks/_batch-runs/{STAMP}/` — директория батча
- `{batch-dir}/{task}.check.log` — лог check-tests.sh
- `{batch-dir}/{task}.run.log` — лог task-test.sh
- `{batch-dir}/{task}.gates.log` — лог gates.py
- `{batch-dir}/summary.tsv` — TSV: task, check_tests, run, gates, status
- `{batch-dir}/summary.json` — JSON: tasks[], passed (bool)

## Побочные эффекты
- Запускает полные прогоны для каждой задачи (последовательно)
- Создаёт директорию батча с логами
- Может быть очень долгим (последовательные браузерные прогоны)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO_ROOT | Корень репозитория (из lib.sh) |
| SCRIPTS_DIR | Папка скриптов test-task (из lib.sh) |
| TASKS_DIR | .doc/tasks (из lib.sh) |
| python3 | Для gates.py |
| yarn, php, docker | Для preflight/task-test внутри |

## Примеры
```bash
# Несколько задач
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/test-batch.sh 2605 2606 2607

# Из файла
echo -e "2605\n2606\n2607" > tasks.txt
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/test-batch.sh --file tasks.txt

# Результат
# Batch: .doc/tasks/_batch-runs/2026-11-07_143022
```

## Ограничения
- Последовательный прогон (не параллельный) — долго на много задач
- Останавливается на первой ошибке внутри задачи (check→run→gates цепочка)
- Не пропускает задачи — если check-tests упал, run и gates не запускаются для этой задачи
- Требует diff.files.md для каждой задачи
- Логи пишутся в файлы, stdout показывает только сводку

## Связи
- Использует: `lib.sh` (info, log, die)
- Вызывает: `check-tests.sh`, `task-test.sh`, `gates.py`
- Канон: `.doc/harnes/tests.md` § batch runs

## История изменений
- 2026-11-07: полная документация (status: draft → actual)