# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/check-selectors.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, check-selectors]
-->

## Суть
Две проверки селекторов, закрывающие класс «ложно-зелёных тестов»:
1. **Мёртвые data-test в Page/Step** — если шаблон переименовал атрибут, `waitForElement()` падает честно, а `dontSeeElement()` начинает проходить всегда. Скрипт сверяет каждый `data-test` из Page/Step с реестром `.doc/qa/_map/data-test.tsv`.
2. **Сырые селекторы в Cest задач** — селектор в Cest (XPath, `@data-test=`, `contains(@class)`, `document.querySelector`) это копипаста вне Page, не попадающая под проверку 1. Все селекторы должны быть в Page/Step.

Запускается после `collect-data-test.py` (реестр должен быть актуальным).

## Когда запускать
- В preflight перед браузерным прогоном (`preflight.sh` вызывает через `check-tests.sh`)
- В gates.py (G10) при проверке готовности к ручному тестированию
- При рефакторинге шаблонов/Page-объектов

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task |  | string | нет | (пусто = весь репозиторий) | Проверить Cest только этой задачи; `all` или пусто — весь репозиторий |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Всё чисто: нет мёртвых, нет сырых, храповик актуален | продолжать |
| 1 | Есть проблемы (мёртвые / сырые / протухший храповик) | прочитать вывод, исправить |
| 2 | Реестр data-test не найден | сначала запустить `collect-data-test.py` |

## Что читает и что пишет
**Читает:**
- `.doc/qa/_map/data-test.tsv` — реестр data-test (генерируется `collect-data-test.py`)
- `.doc/qa/_map/selectors-legacy.txt` — храповик легаси-файлов с сырыми селекторами
- `.tools/codeception/tests/Support/**/*.php` — Page/Step объекты
- `.doc/tasks/{N}/tests/**/*.php` — Cest задач (или весь репозиторий без --task)

**Пишет:** ничего (только stdout/stderr)

## Побочные эффекты
- Читает файлы (read-only)
- Вывод в stdout для парсинга gates.py

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Сначала обновить реестр
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/collect-data-test.py

# Проверить только задачу 2605
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-selectors.py --task 2605

# Проверить весь репозиторий (медленнее)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-selectors.py
```

## Ограничения
- Реестр должен быть свежим (`collect-data-test.py` перед запуском)
- Храповик `.doc/qa/_map/selectors-legacy.txt` обновляется вручную — скрипт сам сообщает, какие файлы стали чистыми и их пора убрать из храповика
- Без `--task` сканирует Cest всех ~180 задач (медленно)
- Не проверяет PHPUnit тесты — только Codeception Acceptance Cest

## Связи
- Зависит: `collect-data-test.py` (реестр)
- Вызывается: `check-tests.sh`, `gates.py` (G10), `preflight.sh`
- Канон: `.doc/harnes/tests.md` § селекторы

## История изменений
- 2026-11-07: полная документация (status: draft → actual)