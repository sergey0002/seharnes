# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests-load.php`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, check-tests-load]
-->

## Суть
Загружает все Cest без браузера: ловит битые симлинки задач, синтаксические ошибки, коллизии имён классов. Нужен потому, что обычный прогон требует стенда и chromedriver, а эти три проблемы видны и без них. Отдельно ловит случай «симлинк задачи уходит за пределы docker-маунта» — тогда Codeception молча находит 0 тестов задачи и прогон выглядит зелёным.

## Когда запускать
- В `check-tests.sh` как быстрая проверка перед браузерным прогоном
- В preflight (`preflight.sh`)
- При подозрении на битые симлинки или коллизии классов

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| 1 (позиционный) |  | string | нет | `.tools/codeception` | Каталог Codeception (где vendor/autoload.php) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Проблем нет | продолжать |
| 1 | Есть проблемы (битые симлинки, синтаксис, коллизии) | прочитать вывод, исправить |
| 2 | Codeception autoload не найден | проверить путь к Codeception |

## Что читает и что пишет
**Читает:**
- `.tools/codeception/vendor/autoload.php` — автозагрузчик
- `.tools/codeception/tests/Acceptance/**/*Cest.php` — все Cest (followLinks)
- Симлинки в `.tools/codeception/tests/Acceptance/Task/*`

**Пишет:** ничего (только stdout/stderr)

## Побочные эффекты
- Подключает автозагрузчик Codeception и require_once все Cest-файлы
- Может триггерить автозагрузку классов проекта

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| PHP | 8.2+ (для strict_types и современного синтаксиса) |
| Codeception | Установленный в `.tools/codeception` |

## Примеры
```bash
# Через обёртку check-tests.sh (рекомендуется)
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh

# Прямой вызов с кастомным путем
php .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests-load.php /path/to/codeception
```

## Ограничения
- Не запускает тесты — только загружает классы
- Не проверяет Playwright тесты
- Требует рабочий vendor/autoload.php в Codeception директории
- `followLinks()` следует за симлинками — цель должна быть доступна в ФС

## Связи
- Вызывается: `check-tests.sh`, `preflight.sh`
- Проверяет: симлинки из `migrate-task-tests.py`

## История изменений
- 2026-11-07: полная документация (status: draft → actual)