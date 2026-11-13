# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, gates]
-->

## Суть
Гейты готовности задачи к ручному тестированию. Переводит «вроде проверил» в машинную проверку. Пока хоть один блокирующий гейт красный — задача не ready-for-qa. Состав выведен из разбора 13 задач, которые не приняли с первого раза.

**Гейты:**
- G0 — статика на файлах задачи (PHPStan L8 + ESLint patch-max)
- G1 — юнит-тесты задачи (есть phpunit.json в run-dir или файлы в tests/lib)
- G2 — тесты задачи существуют (Cest + test.md)
- G3 — последний прогон зелёный (verdict.json green=true)
- G4 — прогон без шума: консоль и модалки ошибок чистые (checkpoints)
- G5 — чек-лист в test.md заполнен (13 категорий, все отмечены)
- G6 — есть проверка эффекта в БД (seeInDatabase / grabFromDatabase)
- G7 — литералы из task.md закреплены в тестах (отметка в test.md)
- G8 — стенд жив после прогона (HTTP 200/301/302 на главной)
- G9 — тесты не утекли в git (.doc/ вне отслеживания)
- G10 — нет сырых селекторов и мёртвых data-test (check-selectors.py)
- G11 — для багов: зафиксирован red-first (тест падал до фикса)
- G12 — машинный AC, lint, PHPUnit, DB, hash-контроль, comparison, llm-review, manifest fingerprint
- G13 — ветки логики из Decomposition закрыты (каждый R имеет строку в ## Ветки логики, статус covered/n-a, реальный Class::method)
- G14 — файлы из diff.files.md покрыты Patches плана или ## Отклонения
- G15 — строки ## Ветки логики со status covered подтверждены зелёным testcase в verdict

Не все проверяются полностью автоматически. Те, что требуют суждения агента (G7, G11), проверяются по явной отметке в test.md.

## Когда запускать
- После прогона `task-test.sh` (автоматически)
- Перед ручным тестированием / передачей в QA
- В CI как quality gate

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| task |  | string | да |  | Номер задачи |
| --json |  | flag | нет |  | Машинный JSON вывод |
| --skip-static |  | flag | нет |  | Пропустить G0 (долгий PHPStan) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все блокирующие гейты зелёные (ready=true) | задача готова к ручному тестированию |
| 1 | Есть красные блокирующие гейты | прочитать вывод, исправить проблемы |
| 2 | Нет каталога задачи | проверить номер задачи |

## Что читает и что пишет
**Читает:**
- `.doc/tasks/{N}/diff.files.md` — изменённые файлы
- `.doc/tasks/{N}/test.md` — чек-лист, red-first, литералы
- `.doc/tasks/{N}/plan.md` — Decomposition, Правки, Отклонения
- `.doc/tasks/{N}/tests/**/*Cest.php` — код тестов
- `.doc/tasks/{N}/test-runs/{latest}/verdict.json` — сводка прогона
- `.doc/tasks/{N}/test-runs/{latest}/ac-results.json` — AC результаты
- `.doc/tasks/{N}/test-runs/{latest}/comparison.json` — регрессия
- `.doc/tasks/{N}/test-runs/{latest}/llm-review.json` — LLM разбор
- `.doc/tasks/{N}/test-runs/{latest}/manifest.json` — fingerprint вводов
- `.doc/tasks/{N}/test-runs/{latest}/static.json`, `lint.json`, `phpunit.json`, `ac-check.json`, `db-isolation.json`, `neighbor-results.json`
- `.doc/qa/_map/data-test.tsv` — реестр (через check-selectors.py)

**Пишет:**
- `{run-dir}/gates.json` — результат всех гейтов (в последнем run-dir)
- stdout — человекочитаемый отчёт или JSON

## Побочные эффекты
- HTTP запрос к стенду (G8, curl на QA_APP_URL)
- Запуск подпроцессов: `check-selectors.py`, `qa-manifest.py`, `git ls-files`
- File write: `gates.json`

## Окружение и зависимости
| Переменная | Описание | По умолчанию |
|---|---|---|
| QA_APP_URL | URL стенда для G8 | `http://127.0.0.1:8030/` |
| QA_PHPSTAN_LEVEL | Уровень PHPStan для G0 | `8` |
| QA_LLM_REQUIRED | Для llm-review.py | `0` |
| QA_LLM_API_KEY | OpenAI API ключ | — |

## Примеры
```bash
# Полная проверка
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py 2605

# Машинный вывод для CI
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py 2605 --json

# Без PHPStan (быстрее)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py 2605 --skip-static
```

## Ограничения
- Требует свежий прогон (verdict.json + артефакты)
- G0 запускает PHPStan L8 по патчу — может быть медленным (--skip-static ускоряет)
- G6/G7/G11 требуют явных отметок в test.md — агент не гадает
- G12 строгий: требует все артефакты со status=passed (или skipped/not_required где уместно)
- Не проверяет бизнес-логику — только технические контракты

## Связи
- Вызывается: `task-test.sh` (после прогона), вручную перед QA
- Зависит: `make-verdict.py`, `compare-runs.py`, `llm-review.py`, `qa-manifest.py`, `check-selectors.py`, `static-on-diff.py`
- Канон: `.doc/harnes/tests.md`, `.doc/harnes/testaudit.md §9`

## История изменений
- 2026-11-07: полная документация (status: draft → actual)