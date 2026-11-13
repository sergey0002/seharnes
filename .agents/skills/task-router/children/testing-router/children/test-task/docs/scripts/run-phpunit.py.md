# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/run-phpunit.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, run-phpunit]
-->

## Суть
Запускает PHPUnit 4.8 в контейнере приложения (`copytrust-dev-php-apache-1`, PHP 7.1) только при наличии изменений в серверном PHP-коде. Мапит изменённые `lib/.../Foo.php` → `tests/lib/.../FooTest.php`. Профили: `task` (только связанные + явные из `diff.files.md`), `changed` (только маппинг), `full`/`baseline` (все `tests/lib/*Test.php`). Детектит известные нестабильности PHPUnit 4.8 (mock incompatibility, Error vs Exception) — помечает `baseline_failed`, не блокирует. Результат в `phpunit.json` + JUnit XML.

## Когда запускать
- В `test-task.sh` автоматически при наличии PHP-правок.
- Локально для прогона unit-тестов задачи: `python3 .../run-phpunit.py --task 2605 --run-dir ... --profile task`.
- В CI для baseline-прогона: `--profile baseline`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task | | string | нет | | Номер задачи; добавляет явные тесты из `diff.files.md` |
| --run-dir | | string | да | | Каталог для артефактов (phpunit.json, phpunit.log, phpunit-junit.xml) |
| --profile | | string | нет | task | `task`/`changed`/`full`/`baseline` — набор тестов |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Пройдено / пропущено (нет серверных изменений / нет тестов) / baseline_failed | OK для task/changed; baseline_failed не блокирует |
| 1 | Провалено (новые фейлы) / инфраструктура сломана / Docker/контейнер недоступен | Исправить тесты или окружение |
| 2 | Невалидный run-dir | Проверить аргументы |

## Что читает и что пишет
- Читает: `git status`, `.doc/tasks/{N}/diff.files.md`, `tests/lib/**/*Test.php`, `tests/phpunit.xml`.
- Пишет: `{run-dir}/phpunit.json` (status, related_tests, exit_code), `{run-dir}/phpunit.log` (сырой вывод), `{run-dir}/phpunit-junit.xml` (JUnit).
- Docker: `docker exec` в `copytrust-dev-php-apache-1` с `php vendor/phpunit/phpunit/phpunit -c tests/phpunit.xml`.

## Побочные эффекты
- Запускает тесты в контейнере приложения (read-only для кода, может писать в БД если тесты это делают).
- Не меняет файловую систему хоста.

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| QA_PHPUNIT_CONTAINER | Имя контейнера (default `copytrust-dev-php-apache-1`) |
| APP_WORKDIR | Рабочая директория в контейнере (default `/var/www/html`) |

## Примеры
```bash
# Профиль задачи (только связанные тесты)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/run-phpunit.py --task 2605 --run-dir .doc/tasks/2605/test-runs/2026-11-07_143000 --profile task

# Полный прогон всех unit-тестов (baseline)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/run-phpunit.py --run-dir .doc/qa/tmp-runs/baseline --profile baseline
```

## Ограничения
- Работает **только** в контейнере приложения (PHP 7.1 + PHPUnit 4.8). Хостовый PHPUnit не используется (bootstrap `maket.php` падает).
- Известные флаки: `Error` vs `Exception` в mock-ах, `Mock_` declaration conflicts — помечаются `baseline_failed`, не блокируют задачу.
- Не прогоняет Codeception/acceptance тесты — только `tests/lib` (PHPUnit).
- Маппинг `lib/.../Foo.php` → `tests/lib/.../FooTest.php` работает только для этого паттерна.

## Связи
- Вызывается: `test-task.sh`, `gates.py` (G1, G12).
- Зависит: Docker, контейнер приложения, `tests/phpunit.xml`.
- Результат: `phpunit.json` → `verdict.json.artifacts.phpunit` → G12.

## История изменений
- 2026-11-07: полная документация на основе реализации (был draft скелет)