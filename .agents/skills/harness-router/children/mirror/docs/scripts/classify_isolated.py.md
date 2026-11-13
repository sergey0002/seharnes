# Скрипт: `.agents/skills/harness-router/children/mirror/scripts/classify_isolated.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, classify_isolated]
-->

## Суть
Классифицирует изолированные узлы (нет входящих/исходящих рёбер) в графе зеркала харнеса (`.doc/skil_data/mirror/graph.json`). Read-only: не редактирует скилы или граф. Бакетизирует по трём категориям: `leaf-by-design` — лифы по замыслу (yadisk, ponytail, login-as-user, kilo-config — есть в LEAF_HINTS); `should-have-trigger` — в мета/лейбле упоминается trigger/когда/always_apply, но рёбер нет; `dead` — остальные изолированные узлы (кандидаты на удаление или подключение). Выводит JSON или человекочитаемый список.

## Когда запускать
- При аудите зеркала харнеса (`mirror` скил): «визуализируй харнес», «карта харнеса», «аудит харнеса».
- При команде «классифицируй изолированные узлы».
- Агент запускает для понимания, какие скилы лифы по дизайну, а какие потерялись.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --graph |  | Path | нет | `.doc/skil_data/mirror/graph.json` | Путь к файлу графа |
| --json |  | flag | нет |  | Машинный JSON-вывод |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех | Продолжить работу |
| 2 | Файл графа не найден | Запустить mirror build сначала |

## Что читает и что пишет
**Читает:**
- `.doc/skil_data/mirror/graph.json` — граф зеркала (nodes с id/meta, edges с from/source → to/target)

**Пишет:**
- JSON в stdout (при `--json`) или текстовый список по бакетам.

## Побочные эффекты
- Нет побочных эффектов (read-only).

## Окружение и зависимости
- Python 3.7+ (argparse, json, sys, pathlib).
- Нет внешних зависимостей.

## Примеры
```bash
# Человекочитаемый вывод
python3 .agents/skills/harness-router/children/mirror/scripts/classify_isolated.py

# JSON для автоматизации
python3 .agents/skills/harness-router/children/mirror/scripts/classify_isolated.py --json
```

Пример текстового вывода:
```
leaf-by-design: 4
  yadisk-screenshot
  ponytail
  login-as-user
  kilo-config
should-have-trigger: 2
  my-custom-skill
  another-skill
dead: 3
  orphan-skill-1
  orphan-skill-2
  test-skill-temp
```

Пример JSON-вывода:
```json
{
  "counts": {"leaf-by-design": 4, "should-have-trigger": 2, "dead": 3},
  "buckets": {
    "leaf-by-design": ["yadisk-screenshot", "ponytail", "login-as-user", "kilo-config"],
    "should-have-trigger": ["my-custom-skill", "another-skill"],
    "dead": ["orphan-skill-1", "orphan-skill-2", "test-skill-temp"]
  }
}
```

## Ограничения
- Классификация эвристическая: `LEAF_HINTS` жёстко задан в скрипте.
- `should-have-trigger` срабатывает на наличие слов "trigger"/"когда" в description/label или `always_apply` в meta — может дать false positive.
- Не проверяет семантическую корректность изоляции — только структуру графа.
- Граф должен быть построен (`mirror build` или `harness_mirror.py build`).

## Связи
- Вызывается: `mirror` скил, агент вручную, `harness_mirror.py classify`
- Зависит от: `.doc/skil_data/mirror/graph.json` (построен `harness_mirror.py scan` + `build`)
- Результат используется: решение о удалении/подключении dead скилов, документация leaf-by-design

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)