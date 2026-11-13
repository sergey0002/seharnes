# Скрипт: `.agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/workflow_contract.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, ../assets/workflow-context.schema.json, ../scripts/generate_report.py]
tags: [harness, script, workflow-contract, preflight, evidence, json-schema]
-->

## Суть
Read-only валидатор workflow-контекста для task-change-report. Проверяет `workflow-context.json` на соответствие JSON Schema (`workflow-context.schema.json`), верифицирует существование и свежесть (sha256) всех объявленных источников (`sources[]`), проверяет evidence-цепочки фактов (`facts[].evidence`), валидирует структуру Jira-входа (если разрешен), проверяет статусы шагов (`steps.diff`, `steps.documentation`, `steps.jira`, `steps.html`) и их артефакты. Не пишет файлы, не вызывает LLM — только читает и возвращает JSON-статус: `malformed` / `blocked` / `ready` / `complete`. Используется `generate_report.py` как preflight gate.

## Когда запускать
Автоматически из `generate_report.py --context` перед рендером. Можно вызвать вручную для диагностики: «почему контекст не проходит preflight?». Если не запустить — `generate_report` может срендерить отчёт на устаревших/неполных данных.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--context` | | string | **да** | | Путь к `workflow-context.json` (relative to project root или абсолютный внутри проекта) |
| `--project-root` | | string | **да** | | Корень проекта (containment root) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | `status: "complete"` — все шаги passed, контекст свежий, можно reuse | Перейти к генерации HTML |
| 1 | `status: "ready"` или `"blocked"` — есть `needed_steps` или ошибки | Прочитать `errors`, `needed_steps`, `next_action`; исправить контекст/запустить недостающие шаги |
| 2 | `status: "malformed"` — схема недоступна, контекст не читается, дубликаты ключей, non-finite числа | Исправить сам JSON контекста |

## Что читает и что пишет
**Читает:**
- `workflow-context.json` — контекст workflow (sources, facts, scope, steps, jira, allowed_steps, refresh_authorized)
- `../assets/workflow-context.schema.json` — JSON Schema для валидации структуры
- Все файлы, перечисленные в `sources[].path` (проверка существования и sha256)
- Файлы артефактов шагов (`steps.*.artifacts[].path`)

**Пишет:** только JSON на stdout (см. структуру ниже). Файлы не создаёт.

## Структура выходного JSON
```json
{
  "status": "malformed|blocked|ready|complete",
  "count": {"sources": N, "facts": M, "needed_steps": K, "reusable_steps": L},
  "coverage": {"sources_verified": X, "sources_total": Y, "scope_kind": "task|stage", "scope_files": Z, "scope_commits": C},
  "paths": ["sorted", "unique", "source", "paths"],
  "errors": [{"code": "...", "at": "$.path.to.field"}, ...],
  "next_action": "fix_context|resolve_blockers|refresh_sources|request_refresh_consent|run_diff|run_documentation|run_jira|run_html|reuse",
  "input_hash": "sha256_of_declared_inputs",
  "needed_steps": ["diff", "documentation", ...],
  "reusable_steps": ["diff", ...]
}
```

### Коды ошибок (`errors[].code`)
| Код | Где | Значение |
|---|---|---|
| `schema_type`, `schema_enum`, `schema_string` | схема | Тип/enum/pattern не совпадает |
| `missing_field` | схема | Отсутствует required поле |
| `unknown_fields` | схема | Поле не в properties (additionalProperties=false) |
| `duplicates` | схема | Дубликаты в массиве (uniqueItems) |
| `empty_list` | схема | Массив короче minItems |
| `duplicate_key` | парсинг | Дубликат ключа в JSON объекте |
| `nonfinite` | парсинг | NaN/Infinity в числе |
| `unsafe_path` | пути | Абсолютный, `..`, `\`, `:`, control chars, не внутри проекта |
| `missing_file` | sources/artifacts | Файл не существует |
| `stale_hash` | sources/artifacts | sha256 файла не совпадает с декларированным |
| `duplicate_source` | sources | Два одинаковых path в sources[] |
| `empty_scope` | scope | Пусты scope.files и scope.commits |
| `unsafe_scope_path` | scope | Небезопасный путь в scope.files[] |
| `task_scope_mismatch` | scope | scope.kind=task но scope.id != context.task_id |
| `unverified_evidence` | facts/jira | Evidence путь не в verified sources |
| `duplicate_fact` | facts | Два fact с одинаковым id |
| `jira_not_authorized` | jira | jira есть но "jira" не в allowed_steps |
| `jira_release_line` | jira | Последняя строка текста не "релиз {release}" |
| `jira_style` | jira | Текст содержит em-dash, guillemets, markdown-списки |
| `stale_step` | steps | step.input_hash != текущий input_hash |
| `missing_artifacts` | steps | У passed шага нет artifacts |
| `missing_jira` | steps | Шаг jira passed но context.jira нет |
| `step_blocked` | steps | У шага status=blocked |
| `checkpoint_*` | checkpoint | Ошибки ребаза (см. код) |

### `next_action`
| Значение | Когда |
|---|---|
| `fix_context` | status=malformed |
| `resolve_blockers` | есть ошибки (кроме stale/missing) |
| `refresh_sources` | есть stale_hash/missing_file И refresh_authorized=true |
| `request_refresh_consent` | есть stale_hash/missing_file И refresh_authorized=false |
| `run_<step>` | status=ready, needed_steps[0] = step |
| `reuse` | status=complete |

## Функции (для импорта)
| Функция | Назначение |
|---|---|
| `preflight(context, project_root)` | Основной вход: вернуть статус без записи |
| `checkpoint(context, project_root, facts, generated_sources=())` | Ребаз контекста после upstream writes (diff/documentation), возвращает обновлённый контекст |
| `input_hash(context)` | Хеш декларированных входов (без steps, jira) |
| `SCHEMA` | Path к schema файлу |

## Побочные эффекты
Нет (read-only). Только читает файлы для проверки хешей.

## Окружение и зависимости
- Python 3.10+
- `jsonschema` не требуется (встроенный минимальный валидатор для используемых ключевых слов)
- Стандартная библиотека: `json`, `hashlib`, `pathlib`, `re`, `copy`, `argparse`

## Примеры
```bash
# Preflight проверка контекста
python .agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/workflow_contract.py --context .doc/tasks/2538/workflow-context.json --project-root .

# Из generate_report.py (внутри скрипта)
from workflow_contract import preflight
result = preflight(context, root)
if result["status"] not in ("ready", "complete"):
    raise ValueError(f"Workflow context blocked: {result['errors']}")
```

## Ограничения
- Не валидирует семантическую полноту (обнаружил ли автор все релевантные файлы, правильно ли интерпретировал evidence) — только структурную и freshness
- Встроенный JSON Schema валидатор поддерживает только ключевые слова, используемые в bundled schema: `type`, `enum`, `properties`, `required`, `additionalProperties`, `items`, `minItems`, `uniqueItems`, `minLength`, `pattern`, `$ref`, `$defs`
- `checkpoint` запрещает ребаз не-diff/documentation шагов и требует явного `generated_sources` для новых артефактов
- Все пути должны быть POSIX project-relative, без `..`, без абсолютных путей
- Не делает сетевых запросов

## Связи
- Вызывается: `generate_report.py` (preflight), вручную для диагностики
- Зависит от: `workflow-context.schema.json`, исходных файлов проекта
- Результат потребляет: `generate_report.py` (gate), человек (диагностика)
- Связанные: `task-change-report` SKILL.md, `generate_report.py`

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода