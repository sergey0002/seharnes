# Скрипт: `.agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/generate_report.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, ../assets/report-model.schema.json, ../scripts/workflow_contract.py]
tags: [harness, script, task-change-report, html, evidence]
-->

## Суть
Генератор детерминированного HTML-отчёта об изменениях задачи (task-change-report). Принимает `report-model.json` (написанный агентом) + исходные артефакты задачи (`task.md`, `diff.md`, `doc.md`, `test.md`, `verdict.json`, `ac-matrix.json`), собирает evidence-first модель, валидирует по JSON Schema, рендерит интерактивный HTML с Mermaid-диаграммами, diff-просмотрщиком, тест-вердиктом, чек-листами, AC-матрицей, Jira-комментариями и готовым ответом для Jira. Пишет `report.html`, `report-data.json`, `report-manifest.json` (хеши входов/выходов для freshness). Не выдумывает объяснения — только форматирует то, что передал агент в модели.

## Когда запускать
В конце задачи, после `test-task` (есть `verdict.json`) и `task-doc` (есть `doc.md`). Вызывается из `task-change-report` SKILL.md. Можно вызвать вручную для перегенерации (`--force`). Если не запустить — нет HTML-отчёта для команды/стейкхолдеров, нет `report-data.json` для аудита.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--task` | | string | **да** | | Номер задачи (только цифры) |
| `--project-root` | | string | нет | `.` | Корень проекта |
| `--output` | | string | нет | `.doc/tasks/{N}/reports/change-report` | Каталог вывода |
| `--model` | | string | нет | `<output>/report-model.json` | Путь к report-model.json (агент пишет заранее) |
| `--offline` | | flag | нет | | Не подключать CDN (Mermaid, Fancybox) — для оффлайн-просмотра |
| `--context` | | string | нет | | Путь к `workflow-context.json` (валидированный preflight) для scoped-режима |
| `--force` | | flag | нет | | Разрешить перезапись существующего HTML (caller owns user consent) |
| `--if-missing` | | flag | нет | | Пропустить генерацию, если HTML существует и свеж (проверка manifest) |
| `--open` | | flag | нет | | Открыть сгенерированный HTML в браузере |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: `status: "generated"` или `"reused"` или `"skipped"` | Разобрать JSON stdout: `path`, `metrics` |
| 1 | `scan` partial (не используется здесь) | — |
| 2 | Ошибка: нет model, схема невалидна, stale HTML без `--force`, небезопасные пути, context blocked | Прочитать `errors` в JSON stdout, исправить причину |

## Что читает и что пишет
**Читает (все пути относительно `--project-root`):**
- `report-model.json` — модель отчёта (агентский ввод, обязателен)
- `.doc/tasks/{N}/task.md` — описание задачи из Jira
- `.doc/tasks/{N}/diff.md` — полный diff задачи
- `.doc/tasks/{N}/diff.files.md` — список файлов
- `.doc/tasks/{N}/doc.md` — документация задачи (pitfalls, decisions, arch links)
- `.doc/tasks/{N}/test.md` — ветки логики, чек-лист, ограничения
- `.doc/tasks/{N}/test-runs/{stamp}/verdict.json` — результат тестов
- `.doc/tasks/{N}/ac-matrix.json` — матрица критериев приёмки
- `workflow-context.json` (если `--context`) — скоуп, источники, facts, steps
- JSON Schema: `../assets/report-model.schema.json`

**Пишет в `--output`:**
- `report.html` — интерактивный HTML отчёт
- `report-data.json` — полная модель данных для аудита/пост-обработки
- `report-manifest.json` — манифест: `model_sha256`, `git_head`, `branch`, `input_hashes`, `output_hashes`, `missing_scoped_files`

## Побочные эффекты
- Создаёт каталог `--output` и файлы внутри
- `git` вызовы (read-only): `rev-parse`, `branch`, `log`, `ls-remote` (для release info)
- Сетевые запросы: нет (кроме CDN в HTML при `--offline` false)
- Не меняет исходные артефакты задачи

## Окружение и зависимости
- Python 3.10+
- `jsonschema` (pip)
- `git` в PATH
- Внутренний модуль: `workflow_contract.py` (preflight, schema)
- Ассеты: `../assets/report-model.schema.json`, `../assets/workflow-context.schema.json`
- CDN (при `--offline` false): `mermaid@10`, `@fancyapps/ui@5`

## Примеры
```bash
# Базовая генерация (model уже лежит в output/)
python .agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/generate_report.py --task 2538

# С указанием model и output
python .../generate_report.py --task 2538 --project-root . --model .doc/tasks/2538/reports/change-report/report-model.json --output .doc/tasks/2538/reports/change-report

# С workflow-context (scoped режим для stage)
python .../generate_report.py --task 2538 --context .doc/tasks/2538/workflow-context.json

# Перегенерация с force
python .../generate_report.py --task 2538 --force

# Пропустить если свеж
python .../generate_report.py --task 2538 --if-missing

# Открыть в браузере после генерации
python .../generate_report.py --task 2538 --open

# Оффлайн версия (без CDN)
python .../generate_report.py --task 2538 --offline
```

## Ограничения
- Не пишет `report-model.json` — агент должен подготовить его заранее (согласно SKILL.md)
- Не вызывает LLM — только форматирует переданные данные
- Валидация Mermaid-диаграмм строгая: неизвестный тип, несбалансированные скобки, неэкранированные кавычки — ошибка
- `--if-missing` пропускает генерацию ТОЛЬКО если manifest существует и все output-хеши совпадают; иначе — blocked (нужен `--force`)
- Scoped режим (`--context`) требует явного scope.files и не допускает whole-task diff/test артефакты для stage
- Jira output (`jira_reply`) разрешен только если `jira` в `allowed_steps` context
- Все пути в model/evidence/sources должны быть project-relative, внутри проекта, без `..` и абсолютных путей

## Связи
- Вызывается: `task-change-report` SKILL.md, вручную
- Зависит от: `workflow_contract.py` (preflight), `report-model.schema.json`, артефактов задачи
- Результат потребляет: человек (HTML), аудит (`report-data.json`), CI (manifest freshness)
- Связанные: `task-report` (короткий комментарий в трекер), `task-doc` (doc.md), `test-task` (verdict.json)

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода