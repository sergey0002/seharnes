# Скрипт: `.agents/skills/skill-auditor/scripts/eval_runner.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md, ./score_aggregator.py.md, ./static_audit.py.md]
tags: [harness, script, skill-auditor, evals, benchmark]
-->

## Суть
Помощник детерминированной оценки навыка: готовит изолированный workspace для A/B-прогонов и считает итоги по оценкам `execution-evaluator`. Считает четыре корзины `WORKING`, `GAP`, `REDUNDANT`, `REGRESSION`, честный Impact Score только по `AB_MEANINGFUL` и пятиосевой Runtime Execution Score. Смысловую оценку не выполняет, берет готовые AI-оценки.

## Когда запускать
После того как `execution-evaluator` выдал `eval_judgments.json`, и перед сборкой итогового отчета аудита. Без оценок скрипт не даст содержательного результата.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `prepare` | | подкоманда | да, одна из двух | | готовит workspace и `eval_plan.json` |
| `prepare --evals PATH` | | string | да | | путь к `evals/evals.json` проверяемого скила |
| `prepare --workspace DIR` | | string | да | | каталог для прогонов `runs/` |
| `prepare --applicability PATH` | | string | нет | | JSON с классификацией AI-гейта: `AB_MEANINGFUL`, `WITH_SKILL_ONLY`, `HYBRID` |
| `score` | | подкоманда | да, одна из двух | | считает бенчмарк по оценкам |
| `score --judgments PATH` | | string | да | | `eval_judgments.json` от `execution-evaluator` |
| `score --output PATH` | `-o` | string | нет | `-` (stdout) | путь для JSON-бенчмарка |
| `score --markdown-out PATH` | | string | нет | | путь для Markdown-отчета |
| `score --lang LANG` | | string | нет | из `config.json` | язык вывода, например `ru` или `en` |
| `score --fail-on-regression` | | flag | нет | | вернуть код 2 при непустой корзине `REGRESSION` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | успех | забрать JSON и Markdown из указанных путей |
| 1 | неверные аргументы или поврежденный JSON | исправить входные файлы и повторить |
| 2 | найдена регрессия при `--fail-on-regression` | остановить улучшение и разобрать корзину `REGRESSION` |

## Что читает и что пишет
Читает `evals.json`, необязательный JSON применимости и `eval_judgments.json`. Настройки языка берет из `config.json` скила. В режиме `prepare` создает каталоги workspace и `eval_plan.json`, в режиме `score` пишет JSON-бенчмарк, Markdown-отчет и выводит JSON в stdout при `--output -`.

## Побочные эффекты
- Создает каталоги и файлы в workspace.
- Пишет выходные JSON и Markdown по указанным путям.
- Сеть не использует.

## Окружение и зависимости
Python 3.9 или новее, только стандартная библиотека. Внешние API не вызываются.

## Примеры
```bash
python3 .agents/skills/skill-auditor/scripts/eval_runner.py prepare \
  --evals path/to/skill/evals/evals.json \
  --workspace /tmp/skill-eval

python3 .agents/skills/skill-auditor/scripts/eval_runner.py score \
  --judgments /tmp/skill-eval/eval_judgments.json \
  --output /tmp/skill-eval/benchmark.json \
  --markdown-out /tmp/skill-eval/benchmark.md
```

## Ограничения
Не классифицирует кейсы и не выставляет оценки вместо AI. Не проверяет корректность полей `eval_judgments.json` глубже базовой структуры. Один прогон соответствует одному набору оценок.

## Связи
- Скил: `.agents/skills/skill-auditor/SKILL.md`.
- Вход от `execution-evaluator`: `eval_judgments.json`.
- Итоговые оценки: `score_aggregator.py`, документ `./score_aggregator.py.md`.

## История изменений
- 2026-11-11: документ создан, аргументы и поведение сверены с кодом.
