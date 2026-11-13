# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, lib.sh]
tags: [harness, script, preflight]
-->

## Суть
Предполёт перед браузерным прогоном задачи. Выполняет последовательность:
1. Очистка Smarty `templates_c` + `cache` (как после деплоя)
2. Статика только по строкам патча: PHPStan L8 + ESLint strict (в CI мягче: PHPStan L0 + lint:basic на frontend/entry)
3. `yarn prod`, если в diff есть `frontend/entry/` или `--force-prod`
4. `check-tests.sh` (Cest/селекторы без браузера)

Важно: «Vue-тесты» в GitVerse deploy = ESLint + `yarn prod`, не jest/vitest.

## Когда запускать
- Перед `task-test.sh` (ручной или автоматически)
- В CI перед браузерным прогоном
- При подозрении на старый кэш/сборку

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| task (позиционный) |  | int | да |  | Номер задачи |
| --level |  | string | нет | 8 | Уровень PHPStan |
| --skip-prod |  | flag | нет |  | Пропустить yarn prod |
| --force-prod |  | flag | нет |  | Принудительный yarn prod |
| --skip-static |  | flag | нет |  | Пропустить статику |
| --skip-check |  | flag | нет |  | Пропустить check-tests.sh |
| -h, --help |  | flag | нет |  | Показать справку |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все шаги прошли | продолжать к task-test.sh |
| 1 | Ошибка (die) | прочитать вывод, исправить |
| 2 | Usage error (нет задачи, не число) | исправить вызов |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/diff.files.md` — для определения нужности yarn prod
- `.tools/docker-dev/.env` (через lib.sh) — настройки Docker

**Пишет:**
- Очищает `templates_c/`, `cache/`
- Запускает `yarn prod` → создаёт `frontend/dist/`
- Логи в stdout/stderr

## Побочные эффекты
- Удаляет кэш Smarty
- Собирает фронтенд (yarn prod)
- Запускает PHPStan, ESLint, check-selectors.py
- Требует: yarn, node_modules, docker-dev.env

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO_ROOT | Корень репозитория (из lib.sh) |
| SCRIPTS_DIR | Папка скриптов test-task (из lib.sh) |
| TASKS_DIR | .doc/tasks (из lib.sh) |
| yarn | В PATH |
| php | Для PHPStan |

## Примеры
```bash
# Стандартный preflight
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh 2605

# Без фронтенда (legacy задача)
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh 2605 --skip-prod

# Принудительная пересборка фронта
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh 2605 --force-prod

# Только статика и чек-тесты
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/preflight.sh 2605 --skip-prod --skip-check
```

## Ограничения
- Требует `diff.files.md` (сначала «обнови диф задачи»)
- `yarn prod` нужен yarn + node_modules (один раз `yarn install`)
- PHPStan L8 по патчу может быть медленным (--skip-static ускоряет)
- Не поднимает стенд/базу — только код и сборка

## Связи
- Использует: `lib.sh` (функции clear_smarty_cache, info, log, die)
- Вызывает: `static-on-diff.py`, `check-tests.sh`, `yarn prod`
- Вызывается: вручную перед `task-test.sh`

## История изменений
- 2026-11-07: полная документация (status: draft → actual)