# Codeception в `.tools` и запуск на хосте

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [../tests.md, ../dirtree.md, ../state/12-batch-calls.md, ../state/14-project-migration.md, ../../architecture/cicd.md]
tags: [harness, codeception, tests, docker, php]
-->

---

## Суть

Рабочая копия Acceptance-suite перенесена из `.doc/codeception/` в `.tools/codeception/`.
Симлинки тестов задач пересчитаны, скрипты, правила и документация харнеса ссылаются
на новый путь. Codeception запускается хостовым PHP 8.2+ с флагом
`-d register_argc_argv=1`, Docker-образ `copytrust-codecept:8.3` для этого не нужен.

---

## 1. Наблюдения и причины

| Наблюдение | Причина | Где видно |
|---|---|---|
| Suite лежал в `.doc/codeception/`, канон тестов в `tools/codeception/` | `.doc/` локальная техническая зона, но рабочая копия с vendor и `.env` оставалась в ней | `.tools` уже содержит окружения и инструменты, Codeception логичнее держать рядом |
| Симлинки `Task/{N}` вели на `../../../../tasks/{N}/tests` | путь рассчитан от глубины `.doc/codeception/tests/Acceptance/Task` | 40 ссылок после переноса стали битыми |
| Docker-раннер монтировал `.doc` в `/doc` | тесты задач подключены симлинками из `.doc/tasks` | при переносе маунт перестаёт видеть цели ссылок |
| `php vendor/bin/codecept` на хосте падал | Codeception требует `register_argc_argv=On`, в PHP 8.5 на хосте `Off` | `ConfigurationException: register_argc_argv must be set to On` |

---

## 2. Решение

1. Каталог `.doc/codeception` перемещён в `.tools/codeception` целиком: `tests`, `vendor`,
   `.env`, `.env.dist`, `codeception.yml`, `composer.json`, `composer.lock`, `scripts`, `README.md`.
2. Симлинки `.tools/codeception/tests/Acceptance/Task/{N}` пересозданы на
   `../../../../../.doc/tasks/{N}/tests`.
3. Docker-раннер монтирует корень проекта в `/app` и работает в `/app/.tools/codeception`;
   результат прогона передаётся как `/app/.doc/tasks/...`.
4. Хостовый запуск получает `-d register_argc_argv=1`; флаг добавлен в раннер, руками
   его вписывать не нужно.

---

## 3. Затронутые файлы

| Файл | Изменение |
|---|---|
| `.tools/codeception/**` | рабочая копия suite и её окружение |
| `.cursor/rules/test-task.mdc` | путь suite в правиле запуска |
| `.agents/skills/task-router/children/testing-router/children/test-task/scripts/lib.sh` | `CODECEPT_DIR`, маунт `/app`, флаг `register_argc_argv` |
| `.agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh` | маунт `/app`, путь загрузчика Cest |
| `task-test`, `prepare-task-test`, `browser-verify` | скрипты, `skill.json`, README, документы скриптов |
| `.agents/skills/copytrust/children/platform-browser-test/SKILL.md` | адреса `dev-login.php` |
| `.tools/scripts/multi-search.sh` | исключение `.tools/codeception` из широкого поиска |
| `harness-core/assets/kit.json`, `new-project/scripts/rebase_project.ps1` | набор переноса kit, vendor, исключения |
| `.tools/codeception/README.md` | команды установки и запуска, ссылки на `.doc` |
| `.doc/harnes/tests.md`, `state/12-batch-calls.md`, `state/14-project-migration.md`, `add-editor-environment.md`, `plan/03-web-testing-system.md`, `idea/plangptsol.md`, `idea/ref22.md` | пути и примеры |
| `.doc/architecture/cicd.json`, `.doc/architecture/local-dev-resources.json` | пути suite, команды прогона; виды пересобраны через `jsondoc render` |

---

## 4. Проверка

| Проверка | Результат |
|---|---|
| `php -d register_argc_argv=1 .tools/codeception/vendor/bin/codecept --version` | `Codeception 5.3.2` |
| `codecept list` на хостовом PHP 8.5.4 | команды выводятся, ошибки конфигурации нет |
| `check-tests.sh` | 45 Cest, 40 задач, все симлинки живые |
| `harness-selftest.py` | passed |
| `validate_registry.py`, `validate_skills.py` | passed, 84 скила, 0 ошибок |
| `sync-agent-views.sh` и parity | успешно, флаг и пути есть в зеркалах |
| `bash -n`, `py_compile`, `php -l`, `json.tool` | без ошибок |

---

## 5. Известные ограничения

- Полный Acceptance-прогон по-прежнему требует поднятого стенда `:8030` и chromedriver
  `:9515` или Selenium `:4444`; перенос и флаг это не отменяют.
- Образ `copytrust-codecept:8.3` не собирается автоматически. Хостовый PHP 8.2+ его
  заменяет, Docker нужен только для изоляции.
- `.doc/harnes/state/09-transfer.md` оставлен как устаревший снимок и не переписывался.

---

## Связи

- [tests.md](../tests.md) - канон QA и порядок прогона
- [dirtree.md](../dirtree.md) - раскладка `.tools/`
- [12-batch-calls.md](./12-batch-calls.md) - исключения широкого поиска
- [14-project-migration.md](./14-project-migration.md) - перенос kit между проектами
- cicd.md (проект Target) - CI/CD и локальный прогон Acceptance

## История изменений

- 2026-11-11: рабочая копия Codeception перенесена в `.tools/codeception`, симлинки задач и все ссылки харнеса обновлены, хостовый запуск починен флагом `-d register_argc_argv=1`.
