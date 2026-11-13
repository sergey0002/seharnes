# Скрипт: `.agents/skills/skill-auditor/scripts/score_aggregator.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md, ./static_audit.py.md, ./eval_runner.py.md]
tags: [harness, script, skill-auditor, scoring, sarif]
-->

## Суть
Собирает итоговую оценку навыка из `static_audit.json` и JSON-находок субагентов. Проверяет схему находок, считает Coverage Confidence, применяет профиль политики `strict`, `balanced` или `permissive`, строит ROI быстрых побед и экспортирует SARIF 2.1.0. Умеет сравнивать проходы через `--compare-prev` и печатать Markdown-сводку.

## Когда запускать
После `static_audit.py` и после того как субагенты или исполнитель выдали файлы `finding_*.json`. Скрипт нужен для финального балла, списка приоритетных правок и CI-гейта.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--static PATH` | | string | да | | путь к `static_audit.json` |
| `--findings PATH...` | | string[] | да | | файлы находок или каталоги с `finding_*.json` |
| `--output PATH` | `-o` | string | нет | `-` (stdout) | путь для итогового JSON |
| `--markdown-out PATH` | | string | нет | | путь для Markdown-сводки |
| `--sarif-out PATH` | | string | нет | | путь для SARIF 2.1.0 |
| `--compare-prev PATH` | | string | нет | | предыдущий `audit_summary.json` для сравнения проходов |
| `--config PATH` | | string | нет | `../config.json` | конфиг скила с каталогом измерений и языком |
| `--lang LANG` | | string | нет | из `config.json` | язык вывода |
| `--policy PROFILE` | | `strict`, `balanced`, `permissive` | нет | из конфига | профиль политики оценок |
| `--fail-on-gate` | | flag | нет | | вернуть код 2 при провале Security или Spec-гейта |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | агрегация завершена | забрать JSON, Markdown и SARIF |
| 1 | неверный аргумент, отсутствует файл или сломана схема | исправить входные данные и повторить |
| 2 | провален CI-гейт при `--fail-on-gate` | остановить конвейер и разобрать блокеры |

## Что читает и что пишет
Читает `static_audit.json`, все `finding_*.json`, необязательный предыдущий `audit_summary.json` и `config.json` скила. Пишет итоговый `audit_summary.json`, Markdown-таблицу, SARIF и поле `round_comparison` при сравнении проходов. Сеть не использует.

## Побочные эффекты
- Создает каталоги для выходных файлов.
- Пишет JSON, Markdown и SARIF.
- Не меняет проверяемый скил.

## Окружение и зависимости
Python 3.9 или новее, только стандартная библиотека. PyYAML не требуется.

## Примеры
```bash
python3 .agents/skills/skill-auditor/scripts/score_aggregator.py \
  --static /tmp/audit/static_audit.json \
  --findings /tmp/audit/findings \
  --output /tmp/audit/audit_summary.json \
  --markdown-out /tmp/audit/summary.md \
  --policy balanced
```

## Ограничения
Не выставляет смысловые оценки вместо субагентов. Требует согласованных идентификаторов критериев между статическим отчетом и находками. SARIF содержит только те находки, которые есть во входных JSON.

## Связи
- Скил: `.agents/skills/skill-auditor/SKILL.md`.
- Статический вход: `static_audit.py`, документ `./static_audit.py.md`.
- Оценки прогонов: `eval_runner.py`, документ `./eval_runner.py.md`.
- Конфиг: `.agents/skills/skill-auditor/config.json`.

## История изменений
- 2026-11-11: документ создан, аргументы и поведение сверены с кодом.
