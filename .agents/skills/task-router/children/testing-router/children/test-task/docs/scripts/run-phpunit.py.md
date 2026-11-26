# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/run-phpunit.py`

<!-- meta
type: script
status: actual
 updated: 2026-11-24
related: [../../SKILL.md]
tags: [harness, script, run-phpunit]
-->

## Суть
Запускает PHPUnit 4.8.36 на PHP 7.4.33 контейнера приложения при изменениях серверного PHP. Bootstrap требует runtime-переменные приложения, а PHP 8.3 не запускает `maket.php` из-за `userErrorHandler`. Профиль `task` добавляет изменённые тесты из текущего `git status`, включая untracked файлы, тесты из `diff.files.md` и PHPUnit-файлы, перечисленные в `ac-matrix.json`. Профиль `changed` запускает маппинг `lib/.../Foo.php` → `tests/lib/.../FooTest.php`; профили `full` и `baseline` запускают весь набор unit-тестов. Известные падения PHPUnit 4.8 отмечаются как `baseline_failed`. Результат записывается в `phpunit.json` и JUnit XML.

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
- Читает: `git status` (включая untracked файлы), `.doc/tasks/{N}/diff.files.md`, `.doc/tasks/{N}/ac-matrix.json`, `tests/lib/**/*.php`, `tests/phpunit.xml`.
- Пишет: `{run-dir}/phpunit.json` (status, related_tests, exit_code), `{run-dir}/phpunit.log` (сырой вывод), `{run-dir}/phpunit-junit.xml` (JUnit).
- Docker: `docker exec` в `copytrust-dev-php-apache-1` с `php vendor/phpunit/phpunit/phpunit -c tests/phpunit.xml`; контейнер предоставляет переменные окружения, нужные `maket.php`.

## Побочные эффекты
- Запускает PHPUnit в контейнере приложения (код тестов не меняется, тесты могут писать в БД).
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
- Работает в контейнере приложения (PHP 7.4.33 + PHPUnit 4.8.36). Изолированный PHP 7.4 CLI контейнер без application environment не загружает `AWS_KEY`; PHP 8.3 несовместим с legacy bootstrap `maket.php`.
- Известные флаки: `Error` vs `Exception` в mock-ах, `Mock_` declaration conflicts — помечаются `baseline_failed`, не блокируют задачу.
- Не прогоняет Codeception/acceptance тесты — только `tests/lib` (PHPUnit).
- Маппинг `lib/.../Foo.php` → `tests/lib/.../FooTest.php` работает только для этого паттерна.

## Связи
- Вызывается: `test-task.sh`, `gates.py` (G1, G12).
- Зависит: Docker, контейнер приложения, `tests/phpunit.xml`.
- Результат: `phpunit.json` → `verdict.json.artifacts.phpunit` → G12.

## История изменений
- 2026-11-24: профиль задачи включает AC-matrix PHPUnit-файлы, untracked тесты и точную версию PHP runtime.
- 2026-11-07: полная документация на основе реализации (был draft скелет)
