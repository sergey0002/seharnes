# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/disposable-db.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, disposable-db]
-->

## Суть
Создаёт или удаляет одноразовую MySQL базу для QA миграционных/юнитных фаз. Клонирует структуру (схему, рутины, триггеры) из исходной базы в новую изолированную базу с именем `{source}_qa_{run-id}`. Позволяет прогонять тесты с данными без загрязнения общей dev-базы.

## Когда запускать
- В `task-test.sh` / `browser-verify` перед прогоном тестов, требующих БД
- В CI для изолированных прогонов
- При ручной отладке тестов с БД

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| phase |  | string | да | create | `create` — создать базу, `drop` — удалить |
| run-id |  | string | нет | manual | Идентификатор прогона (входит в имя БД) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех | продолжать |
| 2 | Отказ использовать общую БД (run-id совпадает с source) | изменить run-id |
| 3 | mysqldump не найден в контейнере | установить mysqldump в mysql контейнер |

## Что читает и что пишет
**Читает:**
- `.tools/docker-dev/.env` или `tools/docker-dev/.env` — `MYSQL_ROOT_USER`, `MYSQL_ROOT_PASSWORD`, `MYSQL_DATABASE`
- Docker контейнер `copytrust-dev-mysql-1` (или `QA_MYSQL_CONTAINER`)

**Пишет (в MySQL):**
- `DROP DATABASE IF EXISTS {db_name}; CREATE DATABASE {db_name};`
- Дамп схемы из `SOURCE_DB` → в новую БД (через mysqldump | mysql)

**Вывод (stdout):**
- `QA_DB_NAME={name}` и `QA_DB_SOURCE={source}` при create
- `dropped {name}` при drop

## Побочные эффекты
- Создаёт/удаляет базу данных в MySQL контейнере
- Требует доступный Docker и mysql-контейнер

## Окружение и зависимости
| Переменная | Описание | По умолчанию |
|---|---|---|
| QA_MYSQL_CONTAINER | Имя mysql контейнера | `copytrust-dev-mysql-1` |
| MYSQL_ROOT_USER | Root пользователь | из .env / `root` |
| MYSQL_ROOT_PASS | Root пароль | из .env / `root_password` |
| QA_SOURCE_DB | Исходная БД для клонирования | из .env / `gb_copydev5` |
| QA_DB_NAME | Имя создаваемой БД (переопределяет авто) | авто: `{source}_qa_{run-id}` |

## Примеры
```bash
# Создать базу для прогона 2605
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/disposable-db.sh create 2605
# Вывод: QA_DB_NAME=gb_copydev5_qa_2605
#        QA_DB_SOURCE=gb_copydev5

# Удалить после прогона
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/disposable-db.sh drop 2605
```

## Ограничения
- Отказывается создавать БД с именем, совпадающим с исходной (защита от перезаписи dev-базы)
- Требует `mysqldump` в mysql контейнере
- Не копирует данные — только структуру (--no-data --routines --triggers)
- Контейнер должен быть запущен и доступен через `docker exec`

## Связи
- Вызывается: `task-test.sh`, `browser-verify` (при необходимости БД)
- Использует: `.tools/docker-dev/.env`

## История изменений
- 2026-11-07: полная документация (status: draft → actual)