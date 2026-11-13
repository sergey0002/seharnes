# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, build-testanalyze]
-->

## Суть
Собирает исследовательский корпус `.doc/testanalyze/` из существующих папок задач `.doc/tasks/{N}/`. Извлекает: стейджи (`initial`, `stage2/`, `stage3/`...), Jira-историю из `task.md` (комментарии, QA-сигналы), git-коммиты с номером задачи, попарные дифы между стейджами (tip-коммиты) и от первого к последнему, сопоставление с скилами планирования/тестирования (`prepare-plan`, `test-task`, `browser-verify`, `gototask`, `task-diff`, `login-as-user`, `task-doc`). Цель — понять, почему появляются stage2+ (баги ручного QA) и улучшить workflow.

## Когда запускать
- Анализ паттернов стейджей по репозиторию (почему задачи растут в стейджи)
- Исследование пробелов тестирования: multi-stage без Cest/test.md/test-runs
- Подготовка данных для улучшения `prepare-plan` и `test-task`
- Запускает разработчик или агент при аудите QA-процесса

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --all |  | flag | нет |  | все папки задач (по умолчанию) |
| --staged-only |  | flag | нет |  | только задачи с папками stage* |
| --multi-stage |  | flag | нет |  | только задачи с >=2 планами/стейджами |
| --task |  | int | нет |  | номер задачи (повторяемый) |
| --with-diffs |  | flag | нет |  | записать stat/name-status дифов между стейджами |
| --full-diff |  | flag | нет |  | также писать .patch файлы |
| --refresh-jira |  | flag | нет |  | экспорт task.md через Jira PHP скрипт |
| --limit |  | int | нет | 0 | лимит задач для обработки |
| --skip-readme |  | flag | нет |  | не перезаписывать README.md |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех | продолжать |
| 1 | Ошибка выполнения | проверить stderr |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/task.md` — Jira экспорт (заголовок, поля, комментарии)
- `.doc/tasks/{N}/plan.md` и `stage*/plan.md` — планы с мета-блоками
- `.doc/tasks/{N}/diff.md` — git diff по коммитам задачи
- `.tools/codeception/tests/Acceptance/Task/{N}_*Cest.php` — наличие Cest
- Git история (`git log --grep`, `git diff-tree`)

**Пишет:**
- `.doc/testanalyze/tasks/{N}/stages.json` — структурированные стейджи, коммиты, дифы
- `.doc/testanalyze/tasks/{N}/overview.md` — человекочитаемая сводка
- `.doc/testanalyze/tasks/{N}/diffs/*.stat.txt`, `*.files.txt`, `*.patch` — дифы (при --with-diffs)
- `.doc/testanalyze/index.md` — сводная таблица по всем задачам
- `.doc/testanalyze/summary.json` — машинный агрегат
- `.doc/testanalyze/skills-map.md` — карта скилов
- `.doc/testanalyze/README.md` — описание корпуса

## Побочные эффекты
- file writes (создание директорий и файлов в `.doc/testanalyze/`)
- git чтение (read-only)
- опционально: запуск Jira PHP-экспортера (`--refresh-jira`)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO_ROOT | Корень репозитория (вычисляется автоматически) |
| PHP | Для `--refresh-jira` (host или docker) |

## Примеры
```bash
# Полный прогон по всем задачам с дифами
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --with-diffs

# Только multi-stage задачи, с полными патчами
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --multi-stage --with-diffs --full-diff

# Конкретная задача с Jira-обновлением
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --task 2410 --with-diffs --refresh-jira
```

## Ограничения
- Не создаёт новые задачи, не меняет код проекта
- Дифы считаются только по tip-коммитам стейджей (мета head/merged или date-bucket)
- Legacy номера задач (Bitbucket) извлекаются эвристически
- `full-diff` может быть большим (транкация на 2MB)
- Не проверяет корректность самих планов — только собирает факты

## Связи
- Вызывается: `build-testanalyze.sh` (обёртка)
- Использует: `.doc/harnes/tests.md` (канон QA), `.doc/harnes/testaudit.md §9` (ветки логики)
- Результат читается: исследователями QA-процесса, `gates.py` (G13), аудиторами

## История изменений
- 2026-11-07: полная документация на основе кода (status: draft → actual)