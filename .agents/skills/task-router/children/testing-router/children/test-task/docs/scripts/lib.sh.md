# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/lib.sh`

<!-- meta
type: script
 status: actual
updated: 2026-11-24
related: [../../SKILL.md]
tags: [harness, script, lib]
-->

## Суть
Общие функции скриптов тестирования задачи: загрузка окружения, проверка стенда и WebDriver, запуск закреплённого Codeception runner, связывание Cest-тестов задачи и очистка кеша Smarty.

## Когда запускать
`task-test.sh` и связанные скрипты подключают `lib.sh` через `source`. Сам файл отдельно не запускают. Подключение не поднимает стенд и WebDriver.

## Аргументы
Аргументов нет

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 1 | Предусловие или команда завершилась ошибкой | Остановить тестовый прогон и показать диагностику |

## Что читает и что пишет
Читает `.tools/codeception/.env`, каталог `.doc/tasks/{N}/tests`, настройки портов и таймаута из окружения. Проверяет HTTP-ответ приложения и состояние WebDriver. Запускает Codeception в Docker-образе `copytrust-codecept:8.3`; если образ отсутствует, собирает его из `.doc/qa/docker/Dockerfile`. Создаёт или обновляет симлинки `tests/Acceptance/Task/{N}` на тесты в `.doc/tasks/{N}/tests`.

## Побочные эффекты
- Собирает и запускает Docker-контейнер Codeception.
- Отправляет HTTP-запросы к локальному приложению, WebDriver и Selenium.
- Создаёт и заменяет симлинки тестов задачи внутри `.tools/codeception/tests/Acceptance/Task/`.
- Удаляет временные Smarty-файлы в `templates_c/`, `admin/templates_c/` и `cache/`.

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| APP_PORT | Порт HTTP-стенда, по умолчанию `8030` |
| CHROMEDRIVER_APP_URL | Публичный URL приложения, используемый настройками тестового проекта |
| DISPLAY | Дисплей для Selenium-контейнера, если среда требует X11 |
| QA_AC_RESULTS_FILE | Путь для записи результатов браузерных критериев |
| QA_RUN_TIMEOUT | Ограничение времени Codeception |
| QA_VISIBLE_DELAY | Пауза между видимыми действиями браузера |

## Примеры
```bash
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh 2633 --phase browser --filter ExampleCest
```

## Ограничения
Не запускает приложение, ChromeDriver или Selenium. Codeception всегда использует PHP 8.3 runner, а версия PHP сайта остаётся независимой. Удаление симлинка тестов требует сначала убедиться, что он действительно является симлинком.

## Связи
Вызывается `scripts/task-test.sh`, `scripts/check-tests.sh`, `scripts/qa-lint.py` и `scripts/static-on-diff.py`. Контракт запуска описан в `.doc/harnes/tests.md` §5.2 и `.doc/qa/browser-setup.md`.

## История изменений
- 2026-11-24: Codeception закреплён на PHP 8.3 в Docker независимо от PHP хоста.
