# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/llm-review.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, llm-review]
-->

## Суть
Опциональный LLM-разбор компактных QA-данных прогона. Никогда не переопределяет детерминированные гейты. Формирует JSON-ввод из verdict.json, ac-results.json, comparison.json, prechecks.jsonl, checkpoint-ошибок и отправляет в OpenAI-compatible API. Результат пишется в `llm-review.json` с полями: `decision` (pass|review|fail), `confidence` (0..1), `findings[]`, `summary`. Используется в G12 как один из артефактов.

## Когда запускать
- Автоматически в `task-test.sh` после прогона (если настроен API ключ)
- В `gates.py` (G12 проверяет llm-review.json status)
- Для ручного AI-аудита прогона

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task |  | string | да |  | Номер задачи |
| --run-dir |  | string | да |  | Путь к каталогу прогона |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Пропущен (нет ключа) или пройден | продолжать |
| 1 | Ошибка API / невалидный ответ / required но нет ключа | проверить настройку LLM |

## Что читает и что пишет
**Читает:**
- `{run-dir}/verdict.json`
- `{run-dir}/ac-results.json`
- `{run-dir}/comparison.json`
- `{run-dir}/prechecks.jsonl` (опционально)
- `.tools/codeception/.env` — для чтения переменных окружения (fallback)

**Пишет:**
- `{run-dir}/llm-review.json` — результат разбора

## Побочные эффекты
- HTTP POST к OpenAI-compatible endpoint
- Запись файла

## Окружение и зависимости
| Переменная | Описание | По умолчанию |
|---|---|---|
| QA_LLM_API_KEY | API ключ (или OPENAI_API_KEY) | — |
| QA_LLM_MODEL | Модель | `gpt-4o-mini` |
| QA_LLM_ENDPOINT | Endpoint | `https://api.openai.com/v1/responses` |
| QA_LLM_REQUIRED | Если `1/true/yes` — отсутствие ключа = ошибка | `0` |

## Примеры
```bash
# Автоматически из task-test.sh
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/llm-review.py --task 2605 --run-dir .doc/tasks/2605/test-runs/2026-11-07_143022

# Ручной запуск (требует ключ в .env)
export QA_LLM_API_KEY=sk-...
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/llm-review.py --task 2605 --run-dir .doc/tasks/2605/test-runs/2026-11-07_143022
```

## Ограничения
- Без ключа — всегда `skipped` (не блокирует, если не `QA_LLM_REQUIRED`)
- Не переопределяет детерминированные гейты (G0-G11, G13-G15)
- Макс 1200 токенов ответа
- Таймаут 120с
- Входной JSON сортируется по ключам для стабильного hash (inputSha256)

## Связи
- Вызывается: `task-test.sh`, `gates.py` (G12)
- Читает артефакты: `make-verdict.py`, `compare-runs.py`, `make-report.py`
- Канон: `.doc/harnes/tests.md` (LLM как советник, не судья)

## История изменений
- 2026-11-07: полная документация (status: draft → actual)