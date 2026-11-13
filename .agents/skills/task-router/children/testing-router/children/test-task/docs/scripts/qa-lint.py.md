# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-lint.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md]
tags: [harness, script, qa-lint]
-->

## Суть
Обязательный линт изменённых файлов перед прогоном. PHP: `php -l` на каждом .php (вне `.doc/qa`). JS/Vue: ESLint с конфигом `patch-max.js` (локально) или fallback на `.eslintrc.strict.js`. При `--task` сужает JS-проверку до строк патча задачи (импортирует логику из `static-on-diff.py`), чтобы legacy-код вне ханка не валил gate. Поддержка Docker для PHP (образ `copytrust-codecept:8.3`) и ESLint (node:22 + volume `copytrust-eslint-nm`). Результат в JSON для `verdict.json.artifacts.lint`.

## Когда запускать
- В `test-task.sh` как обязательный pre-check (перед Codeception).
- В `preflight.sh` (через `check-tests.sh`).
- Локально перед коммитом: `python3 .../qa-lint.py --task 2605`.
- В CI как quality gate.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task | | string | нет | | Номер задачи; включает task-scoped тесты и patch-only ESLint |
| --run-dir | | string | нет | | Каталог прогона для записи `lint.json` |
| --with-support | | flag | нет | | Также линтить `.tools/codeception/tests/Support` (обычно пропускается) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Линт пройден (нет ошибок на строках патча) | OK |
| 1 | Есть ошибки php -l или ESLint (на патче при --task) | Исправить код |
| 127 | PHP/ESLint недоступны и нет Docker | Установить инструменты или Docker |

## Что читает и что пишет
- Читает: `git status --porcelain` (изменённые файлы), при `--task` — `.doc/tasks/{N}/tests/**/*.php`, `.doc/tasks/{N}/diff.files.md` (для patch-фильтра), `.doc/qa/eslint/patch-max.js`.
- Пишет: при `--run-dir` — `{run-dir}/lint.json` со структурой `{status, files, checks[], errors[]}`. Stdout — тот же JSON.

## Побочные эффекты
- Может запустить Docker контейнеры для PHP/ESLint при отсутствии локально.
- Использует volume `copytrust-eslint-nm` для кэша node_modules.

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| QA_PHPUNIT_CONTAINER | Контейнер для PHP (default `copytrust-dev-php-apache-1`) |

## Примеры
```bash
# Линт только текущих изменений (без задачи)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-lint.py

# Линт с задачей (patch-only ESLint + task tests)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-lint.py --task 2605 --run-dir .doc/tasks/2605/test-runs/2026-11-07_143000

# С Support (для полной проверки)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-lint.py --task 2605 --with-support
```

## Ограничения
- `Support` каталог исключён по умолчанию: его полный rglob замедлял линт и валил чужими файлами. Отдельный чек-лист `check-tests.sh` (check-selectors + check-tests-load) покрывает Support.
- При `--task` ESLint фильтруется по строкам патча через `static-on-diff.changed_lines`; без задачи — проверяются весь файлы (strict).
- Отчёт ESLint разбирается из stdout отдельно от stderr. Предупреждения yarn в stderr (`warning ... peer dependency`) не ломают разбор и не блокируют гейт.
- PHP `-l` запускается на каждом файле отдельно (хост) или батчем в Docker.
- Не проверяет CSS, TPL, SQL — только PHP, JS, Vue.

## Связи
- Вызывается: `test-task.sh`, `preflight.sh` (через `check-tests.sh`), `gates.py` (G12).
- Зависит: `static-on-diff.py` (импорт для patch-фильтра), Docker, ESLint/PHP.
- Результат: `lint.json` → `verdict.json.artifacts.lint` → G12.

## История изменений
- 2026-11-11: отчёт ESLint разбирается из stdout, stderr хранится отдельно; предупреждения yarn в stderr больше не дают ложный `ESLint failed or was unavailable`.
- 2026-11-07: полная документация на основе реализации (был draft скелет)