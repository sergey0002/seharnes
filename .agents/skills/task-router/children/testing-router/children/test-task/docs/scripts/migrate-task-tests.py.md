# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/migrate-task-tests.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, migrate-task-tests]
-->

## Суть
Разовый перенос Task-Cest из общей папки в папки задач.
**Было:** `.tools/codeception/tests/Acceptance/Task/2236_QualityWarningCest.php`
**Стало:** `.doc/tasks/2236/tests/QualityWarningCest.php` + симлинк `tests/Acceptance/Task/2236 -> ../../../../tasks/2236/tests`

Зачем: тест задачи должен лежать рядом с `task.md`, `plan.md` и `test-runs`, а не в общей куче. Номер задачи уходит из имени файла в неймспейс `Tests\Acceptance\Task\T{N}` — так два разных `QualityWarningCest` не столкнутся именами классов.

## Когда запускать
- Один раз при миграции существующих Cest в новую структуру
- При добавлении новых задач со старыми Cest (ручной запуск)

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --dry-run |  | flag | нет |  | Только показать что будет сделано, не менять файлы |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (перенесено или нечего переносить) | продолжать |
| 1 | Ошибка выполнения | проверить stderr |
| 2 | Нет исходной директории Task suite | проверить путь |

## Что читает и что пишет
**Читает:**
- `.tools/codeception/tests/Acceptance/Task/*.php` — файлы вида `{N}_*Cest.php`

**Пишет:**
- `.doc/tasks/{N}/tests/{ClassName}Cest.php` — с обновлённым namespace `Tests\Acceptance\Task\T{N}`
- Симлинк `.tools/codeception/tests/Acceptance/Task/{N} -> ../../../../../.doc/tasks/{N}/tests`
- Удаляет исходный файл из Task suite

## Побочные эффекты
- Перемещение файлов (mv + write)
- Создание/удаление симлинков
- Изменение namespace в PHP-файлах

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Сухой прогон
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/migrate-task-tests.py --dry-run

# Реальный перенос
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/migrate-task-tests.py

# После переноса проверить селекторы
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-selectors.py
```

## Ограничения
- Ожидает namespace `Tests\Acceptance\Task;` в исходных файлах
- Если namespace не найден — предупреждение, но переносит как есть
- Симлинк создаётся только если цель не существует или уже симлинк
- Не откатывает изменения (нет --undo)

## Связи
- После миграции: `check-selectors.py` (реестр data-test может измениться)
- Проверяет: `check-tests-load.php` (симлинки)

## История изменений
- 2026-11-07: полная документация (status: draft → actual)