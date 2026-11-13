# Скрипт: `.agents/skills/exhaustive-research-decision-v6/scripts/check_gates.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md, ../../assets/templates]
tags: [harness, script, research, gates, check_gates]
-->

## Суть
Проверяет комплект артефактов исследования v6 и закрывает 19 гейтов: наличие обязательных файлов, заголовки CSV, заполненность ключевых полей, отсутствие заглушек, согласованность матрицы и итогового отчета. Умеет создать чистый набор артефактов из `assets/templates`. Внешних зависимостей нет.

## Когда запускать
После каждого этапа исследования и перед передачей результата. Если запустить раньше, проверка покажет незаполненные файлы и заглушки; если не запускать перед передачей, отчет уйдет без подтвержденных гейтов.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `target` | | string | да, если нет `--init-v6` | | каталог `research/<task-id>` с артефактами v6 |
| `--init-v6 DIR` | | string | нет | | создать дерево артефактов из шаблонов в каталоге `DIR` |
| `--force` | | flag | нет | | перезаписать непустой каталог при `--init-v6` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | `PASS` или `INIT-V6 OK` | продолжить работу, результат подтвержден |
| 1 | `FAIL` или `INCOMPLETE` | разобрать `ERROR` и `WARN`, дополнить артефакты и повторить |
| 2 | ошибка аргументов или ввода-вывода | исправить путь, права или непустой каталог и повторить |

## Что читает и что пишет
Читает обязательные файлы `00-brief.md`, `00-state.md`, `99-handoff.md`, `candidates.csv`, `criteria.csv`, `decision-matrix.csv`, `verification.md`, `final-report.md` и остальные файлы из `REQUIRED_FILES`. Пишет `gates.json` в каталог проверки. При `--init-v6` копирует файлы из `assets/templates` в целевой каталог. Сеть и база не используются.

## Побочные эффекты
- Перезаписывает `gates.json` при каждой проверке.
- Создает каталоги и копирует шаблоны при `--init-v6`.
- Не меняет остальные артефакты.

## Окружение и зависимости
Python 3.10 или новее, стандартная библиотека (`argparse`, `csv`, `json`, `pathlib`). Переменные окружения не нужны.

## Примеры
```bash
python3 .agents/skills/exhaustive-research-decision-v6/scripts/check_gates.py research/my-task
python3 .agents/skills/exhaustive-research-decision-v6/scripts/check_gates.py --init-v6 research/my-task
python3 .agents/skills/exhaustive-research-decision-v6/scripts/check_gates.py --init-v6 research/my-task --force
```

## Ограничения
Проверяет структуру, заголовки и заполненность, но не смысловое качество доказательств. Требует точных имен файлов и колонок из `REQUIRED_HEADERS`. Не создает задачи и не запускает исследование.

## Связи
- Скил: `.agents/skills/exhaustive-research-decision-v6/SKILL.md`.
- Шаблоны: `.agents/skills/exhaustive-research-decision-v6/assets/templates/`.
- Результат проверки: `research/<task-id>/gates.json`.

## История изменений
- 2026-11-11: документ создан, аргументы и поведение сверены с кодом.
