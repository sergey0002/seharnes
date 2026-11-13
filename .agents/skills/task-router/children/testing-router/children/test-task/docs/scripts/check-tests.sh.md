# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, check-tests]
-->

## Суть
Быстрая предполетная проверка тестов задачи без браузера и стенда. Скрипт собирает
реестр `data-test`, сверяет селекторы Page-объектов, проверяет загрузку всех Cest,
битые симлинки задач и коллизии классов. Полный прогон не заменяет.

## Когда запускать
Запускать после `prepare-task-test` и перед `task-test.sh`, а также после правки
Cest, Page-объектов или `data-test` в шаблонах. Проверка занимает секунды и ловит
ошибки, которые иначе всплывут в полном прогоне.

## Аргументы
Аргументов нет. Скрипт работает с путями проекта, которые вычисляет `lib.sh`.

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | все проверки чистые | запускать `task-test.sh` |
| 1 | хотя бы одна проверка нашла проблему | читать вывод, исправить, повторить |

## Что читает и что пишет
Читает `templates/`, `scripts/`, `admin/`, `frontend/src/` для атрибутов `data-test`,
Cest-файлы и Page-объекты, симлинки задач. Пишет реестр
`.doc/qa/_map/data-test.tsv` через `collect-data-test.py`. В stdout и stderr идет
человеческий отчет по шагам.

## Побочные эффекты
Перезаписывает `.doc/qa/_map/data-test.tsv`. При отсутствии PHP на хосте запускает
Docker-образ `copytrust-codecept:8.3` для проверки загрузки Cest. Стенд и
chromedriver не поднимает.
Каталог скриптов скила монтируется отдельно в `/qa-scripts` только для чтения;
`check-tests-load.php` получает каталог Codeception `/app/.tools/codeception` аргументом.

## Окружение и зависимости
Переменные `REPO_ROOT`, `CODECEPT_DIR`, `QA_DIR`, `SCRIPTS_DIR`, `RUNNER_IMAGE` задает `lib.sh`.
Зависимости: `bash`, `python3`, `php` на хосте или Docker с образом раннера,
`lib.sh` рядом со скриптом.

## Примеры
```bash
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh
```

## Ограничения
Не запускает Acceptance-тесты и не проверяет поведение в браузере. Не поднимает
стенд и WebDriver. Проверяет только загрузку классов, селекторы и реестр
`data-test`, а не бизнес-логику задачи.

## Связи
Вызывается из `test-task` перед полным прогоном. Использует `collect-data-test.py`,
`check-selectors.py` и `check-tests-load.php`. Канон тестирования:
`.doc/harnes/tests.md`.

## История изменений
- 2026-11-07: исправлен запуск загрузчика после переноса в скил; проверена загрузка 45 Cest-классов для 40 задач без браузера и базы.
- 2026-11-07: документ создан из кода, шаги и коды выхода сверены с исходником
