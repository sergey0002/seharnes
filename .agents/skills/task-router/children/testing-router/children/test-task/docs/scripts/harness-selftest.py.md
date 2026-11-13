# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selftest.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md]
tags: [harness, script, harness-selftest]
-->

## Суть
Маленькие офлайн-проверки QA-харнеса: компиляция Python-скриптов, проверка путей к перемещённым хелперам, разбор отчёта ESLint с хвостом stderr, политика Docker-образа PHPStan, валидация `check-ac-matrix.py`. Запускается без браузера, без БД, без стенда — только синтаксис и внутренняя логика.

## Когда запускать
- В `harness-selfcheck.sh` (как часть полного self-check)
- При изменении скриптов в `.agents/skills/task-router/children/testing-router/children/test-task/scripts/`
- Для быстрой проверки до коммита

## Аргументы
Аргументов нет.

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все проверки пройдены | продолжать |
| 1 | Ошибка компиляции или assert | прочитать вывод, исправить |
| 99 | Не используется (артефакт автогенерации) | — |

## Что читает и что пишет
**Читает (компиляция):**
- `doctor.py`, `branch-audit.py`, `run-phpunit.py`, `qa-manifest.py`, `db-isolation.py`, `check-ac-matrix.py`, `gates.py`, `qa-lint.py`, `static-on-diff.py`, `llm-review.py`

**Пишет:** ничего (только stdout/stderr)

## Побочные эффекты
- Запускает `py_compile` на 10 скриптах
- Запускает мокированные тесты логики хелперов (gates, qa-lint, static-on-diff, llm-review)
- Запускает Docker-политику PHPStan через временный мок `docker` в PATH
- Создаёт временные директории для моков

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| python3 | 3.8+ (unittest.mock, tempfile) |
| PATH | Модифицируется для мока docker |

## Примеры
```bash
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selftest.py
# Вывод: harness-selftest: passed
```

## Ограничения
- Не запускает браузерные/интеграционные тесты
- Мокает Docker и filesystem — не проверяет реальные контейнеры
- Проверяет только перечисленные 10 скриптов (список в коде)

## Связи
- Вызывается: `harness-selfcheck.sh`
- Проверяет: все скрипты в `test-task/scripts/`

## История изменений
- 2026-11-11: добавлена проверка `check_eslint_json_tail` — отчёт ESLint разбирается при предупреждении yarn в stderr после JSON.
- 2026-11-07: полная документация (status: draft → actual)