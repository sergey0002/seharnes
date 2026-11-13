# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md]
tags: [harness, script, static-on-diff]
-->

## Суть
Запускает статический анализ **только по строкам патча задачи**: PHPStan (level 8 по умолчанию, до 9) и ESLint (patch-max конфиг). Определяет файлы задачи через `diff.files.md`, извлекает изменённые строки через `git blame` (коммиты задачи) и uncommitted diff. Фильтрует ошибки статики, оставляя только те, что попадают в изменённые строки (±slack, дефолт 0). ESLint: три режима — `patch-max` (локально, жёсткий), `.eslintrc.strict.js` (репо), `.eslintrc.basic.js` (CI parity). PHPStan: использует образ `copytrust-codecept:8.3` или хостовый PHP 7.4+ с phar. Не затрагивает legacy-код вне патча.

## Когда запускать
- В `preflight.sh` перед прогоном задачи.
- В `test-task.sh` как обязательный слой (гейт G0).
- Локально для быстрой проверки своих правок: `python3 .../static-on-diff.py 2605`.
- В CI — с флагом `--eslint-ci` для parity с deploy.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| task | | string | да | | Номер задачи CT-N |
| --level | | int | нет | 8 | PHPStan level на строках патча (макс 9) |
| --eslint-ci | | flag | нет | | ESLint `.eslintrc.basic.js` как в GitVerse CI |
| --eslint-strict-repo | | flag | нет | | ESLint `.eslintrc.strict.js` из репо (мягче patch-max) |
| --no-php | | flag | нет | | Пропустить PHPStan |
| --no-eslint | | flag | нет | | Пропустить ESLint |
| --slack | | int | нет | 0 | Допуск строк вокруг патча (после blame обычно 0) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Статика по патчу чистая | OK |
| 1 | Есть ошибки в строках патча | Исправить код |
| 2 | Нет `diff.files.md` или ошибка запуска Docker/PHPStan | Обновить диф задачи или проверить окружение |

## Что читает и что пишет
- Читает: `.doc/tasks/{N}/diff.files.md`, git history (`git blame`, `git diff`), `.tools/phpstan/` (phar, neon-конфиги), `.doc/qa/eslint/patch-max.js`, `.eslintrc.*.js`, `package.json`/`yarn.lock`.
- Пишет: только stdout. При Docker-запуске использует volume `copytrust-eslint-nm` для node_modules.
- Сеть: pull Docker-образов `node:22-bookworm-slim`, `copytrust-codecept:8.3` (при первом запуске).

## Побочные эффекты
- Может собрать Docker-образ `copytrust-codecept:8.3` из `.doc/qa/docker/` при отсутствии.
- Создаёт/использует Docker volume `copytrust-eslint-nm` для кэша node_modules.

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| PHP_BIN | Путь к PHP бинарнику для PHPStan (если не задан — ищет в PATH, иначе Docker) |
| QA_PHPSTAN_LEVEL | Уровень PHPStan (перекрывается --level) |

## Примеры
```bash
# Жёсткая локальная проверка (PHPStan L8 + ESLint patch-max)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py 2605

# Только PHPStan L9
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py 2605 --level 9 --no-eslint

# CI parity (как в GitVerse deploy)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py 2605 --eslint-ci

# Только ESLint strict репо
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py 2605 --eslint-strict-repo --no-php
```

## Ограничения
- Требует `diff.files.md` — без `task-diff` не работает.
- PHPStan на PHP 7.1 кодовой базе запускается в Docker (образ PHP 7.4+ с phar).
- ESLint требует `eslint-plugin-vue` — при отсутствии локально запускается в Docker.
- Blame-базированный подход: после rebase/merge номера строк могут сдвинуться; slack=0 по умолчанию.
- Не проверяет файлы, не входящие в `diff.files.md` (даже если изменены локально).
- Разбор отчёта ESLint идёт через `raw_decode`: текст после JSON-массива (предупреждения yarn в stderr) не считается ошибкой формата.
- Vue-тесты в деплое = ESLint + yarn prod, не jest/vitest.

## Связи
- Вызывается: `preflight.sh`, `test-task.sh`, `qa-lint.py` (через import), `gates.py` (G0).
- Зависит: `diff.files.md`, git history, PHPStan/ESLint конфиги.
- Результат: stdout + код выхода → G0 в `gates.py`.

## История изменений
- 2026-11-11: `parse_eslint_json` разбирает первый JSON-массив через `raw_decode`; предупреждения yarn после отчёта не дают ложный `None`.
- 2026-11-07: полная документация на основе реализации (был draft скелет)