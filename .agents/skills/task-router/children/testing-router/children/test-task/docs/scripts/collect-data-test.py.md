# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/collect-data-test.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, collect-data-test]
-->

## Суть
Строит реестр всех `data-test` атрибутов проекта: `.doc/qa/_map/data-test.tsv`. Сканирует `templates/`, `scripts/`, `admin/`, `frontend/src/` и собирает атрибуты в трёх формах:
- Статический: `data-test="item-form-step2__name"`
- Vue-биндинг с литералом: `:data-test="'booking-slot'"`
- Шаблонная строка (префикс): `:data-test="\`tariff-delete-btn-${id}\`"` → префикс `tariff-delete-btn-`

Реестр нужен `check-selectors.py`: он сверяет с ним селекторы Page-объектов, чтобы переименование атрибута в шаблоне не превращало `dontSeeElement()` в ложно-зелёную проверку.

## Когда запускать
- Перед `check-selectors.py` (реестр должен быть актуальным)
- После изменений в шаблонах/templates/data-test
- В CI для обновления реестра

## Аргументы
Аргументов нет.

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Реестр создан, есть атрибуты | продолжать |
| 1 | Пусто (0 уникальных атрибутов) | проверить SCAN_DIRS |

## Что читает и что пишет
**Читает:**
- `templates/**/*.{tpl,js,vue,html,php}`
- `scripts/**/*.{tpl,js,vue,html,php}`
- `admin/**/*.{tpl,js,vue,html,php}`
- `frontend/src/**/*.{tpl,js,vue,html,php}`
- Пропускает: `node_modules`, `dist`, `templates_c`, `cache`, `vendor`, `_output`

**Пишет:**
- `.doc/qa/_map/data-test.tsv` — TSV: `name<tab>kind<tab>line<tab>file`
  - `kind`: `static`, `bound`, `prefix`

## Побочные эффекты
- Создаёт директорию `.doc/qa/_map/`
- Перезаписывает реестр

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| REPO | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Стандартный запуск
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/collect-data-test.py

# Вывод: data-test: 247 уникальных, 1842 вхождения -> .doc/qa/_map/data-test.tsv
```

## Ограничения
- Не сканирует `vendor/`, `node_modules/`, кэши
- Для Vue template strings фиксирует только неизменяемый префикс (до `${` или `` ` ``)
- Не проверяет уникальность имён — только собирает
- Реестр не коммитится в git (в `.doc/`)

## Связи
- Вызывается перед: `check-selectors.py`
- Используется: `gates.py` (G10), `check-tests.sh`

## История изменений
- 2026-11-07: полная документация (status: draft → actual)