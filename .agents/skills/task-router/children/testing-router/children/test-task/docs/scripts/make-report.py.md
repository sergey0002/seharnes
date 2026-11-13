# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/make-report.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, make-report]
-->

## Суть
Создаёт единый формальный Markdown-отчёт для одного тестового прогона (`report.md` в run-dir). Собирает: идентичность прогона (SHA256 код/тестов/требований/скилов), обязательные prechecks, все тесты из JUnit XML, AC с evidence, регрессионное сравнение, браузерные evidence (checkpoints, скриншоты), LLM review, финальный вердикт. Зелёный LLM review никогда не переопределяет красный детерминированный гейт.

## Когда запускать
- Автоматически в `task-test.sh` в конце прогона
- Для ручной генерации отчёта из артефактов

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task |  | string | да |  | Номер задачи |
| --run-dir |  | string | да |  | Путь к каталогу прогона |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех | продолжать |
| 1 | Ошибка (в исключениях) | проверить stderr |

## Что читает и что пишет
**Читает:**
- `{run-dir}/verdict.json`
- `{run-dir}/ac-results.json`
- `{run-dir}/comparison.json`
- `{run-dir}/llm-review.json`
- `{run-dir}/manifest.json`
- `{run-dir}/prechecks.jsonl` (опционально)
- `{run-dir}/report.xml` — JUnit отчёт Codeception

**Пишет:**
- `{run-dir}/report.md` — Markdown отчёт

## Побочные эффекты
- File write: `report.md`
- Парсинг XML (JUnit)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Автоматически из task-test.sh
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/make-report.py --task 2605 --run-dir .doc/tasks/2605/test-runs/2026-11-07_143022
```

## Ограничения
- Требует `report.xml` от Codeception (если нет — строка «Browser tests were not executed»)
- Не генерирует HTML — только Markdown
- LLM review включается как есть (не валидируется)

## Связи
- Вызывается: `task-test.sh`
- Читает: `make-verdict.py`, `compare-runs.py`, `llm-review.py`, `qa-manifest.py`
- Используется: для ручного ревью, в CI артефактах

## История изменений
- 2026-11-07: полная документация (status: draft → actual)