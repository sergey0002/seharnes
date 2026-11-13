# Скрипт: `.agents/skills/task-router/children/task-spec/scripts/task_spec.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, task_spec, task-spec]
-->

## Суть
Инструмент для сбора требований к задаче из свободной переписки и превращения их в единый документ `task.md`. Работает с черновиками (drafts) в `.doc/skil_data/task-spec/{id}/`: хранит замечания (`notes.md`), вложения (`attachments/`), метаданные (`meta.json`), и по команде `finalize` публикует итоговый `task.md`. Каждый черновик имеет уникальный ID (timestamp + slug), статусы `collecting` / `formulated`, поддерживает переключение между черновиками. Вывод всех команд — JSON для парсинга агентами.

## Когда запускать
- В начале работы над новой задачей: `task_spec.py start --title "Название"`
- Во время обсуждения: `task_spec.py add --text "замечание" --kind requirement` (или `bug`, `decision`, `question`, `remark`)
- Для скриншотов/файлов: `task_spec.py attach --path /путь/к/файлу --caption "описание"`
- Для проверки текущего состояния: `task_spec.py show` или `task_spec.py current`
- Когда требования собраны: `task_spec.py finalize --file /путь/к/task.md --title "Финальное название"`
- **Не** запускать после того, как задача уже заведена в Jira — это инструмент пре-постановки

## Аргументы
### Глобальные
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root | | string | нет | . | Корень проекта (где лежит `.doc/`) |

### Подкоманды
| Команда | Аргументы | Описание |
|---|---|---|
| `start` | `--title` (string), `--slug` (string) | Создать новый черновик с уникальным ID |
| `add` | `--text` (string), `--stdin` (flag), `--kind` (choice: remark/bug/requirement/decision/question), `--id` (string) | Добавить замечание в активный или указанный черновик |
| `attach` | `--path` (string, required), `--caption` (string), `--id` (string) | Скопировать файл в attachments черновика, добавить ссылку в notes.md |
| `show` | `--id` (string) | Вывести полное содержимое черновика (JSON) |
| `finalize` | `--file` (string, required), `--title` (string), `--id` (string) | Проверить ссылки на вложения, скопировать file -> task.md, сменить статус на formulated |
| `current` | — | Показать ID активного черновика |
| `use` | `--id` (string, required) | Сделать указанный черновик активным |
| `list` | — | Список всех черновиков (JSON) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (любая команда) | Парсить stdout JSON |
| 1 | Ошибка валидации (пустой текст, битые ссылки при finalize) | Прочитать stderr / JSON `{"status":"error","error":"..."}` |
| 2 | Ошибка состояния (нет активного черновика, черновик не найден) | Создать черновик через `start` или переключить через `use` |

## Что читает и что пишет
**Читает:**
- `.doc/skil_data/task-spec/{id}/meta.json` — метаданные черновика
- `.doc/skil_data/task-spec/{id}/notes.md` — накопленные замечания
- `.doc/skil_data/task-spec/{id}/attachments/*` — вложения (при finalize проверяет ссылки)
- Файл, переданный в `--file` при `finalize` — исходный task.md для публикации

**Пишет:**
- `.doc/skil_data/task-spec/{id}/meta.json` — обновлённые метаданные (updated, status)
- `.doc/skil_data/task-spec/{id}/notes.md` — добавленные секции замечаний/вложений
- `.doc/skil_data/task-spec/{id}/attachments/{NNN-name.ext}` — скопированные файлы
- `.doc/skil_data/task-spec/current.json` — ID активного черновика
- `.doc/skil_data/task-spec/index.json` — индекс всех черновиков
- При `finalize`: целевой `task.md` (копия из `--file`)

**Сеть:** не использует.

## Побочные эффекты
- file writes (создаёт/обновляет файлы черновиков, индексы, копирует вложения)
- Не меняет внешние системы, не делает сетевых запросов

## Окружение и зависимости
Переменных окружения не использует.

**Зависимости:** Python 3.8+, стандартная библиотека (`argparse`, `json`, `re`, `shutil`, `pathlib`, `datetime`, `urllib.parse`). Никаких внешних пакетов.

## Примеры
```bash
# Начать сбор требований
python3 task_spec.py start --title "Исправить расчёт скидки" --slug fix-discount

# Добавить замечание (remark)
python3 task_spec.py add --text "Скидка не применяется при оплате бонусами" --kind bug

# Добавить требование из stdin
cat requirements.txt | python3 task_spec.py add --stdin --kind requirement

# Прикрепить скриншот
python3 task_spec.py attach --path ~/screenshots/error.png --caption "Ошибка в корзине"

# Посмотреть текущий черновик
python3 task_spec.py show

# Зафинализировать (после ручного написания task.md)
python3 task_spec.py finalize --file ./my-task.md --title "Исправить расчёт скидки при бонусах"

# Список всех черновиков
python3 task_spec.py list
```

**Пример JSON-вывода (start):**
```json
{
  "status": "collecting",
  "id": "20261107-143022-fix-discount",
  "dir": ".doc/skil_data/task-spec/20261107-143022-fix-discount",
  "task": ".doc/skil_data/task-spec/20261107-143022-fix-discount/task.md"
}
```

## Ограничения
- Не создаёт задачу в Jira — только локальный `task.md` для последующего импорта
- `finalize` требует, чтобы все ссылки на вложения в переданном `task.md` были валидны (файлы существуют в `attachments/`)
- Один активный черновик на проект (`current.json`)
- slug генерируется из title (транслитерация кириллицы), дубликаты получают суффикс `-2`, `-3`...
- `--kind` при `add` влияет только на метку в notes.md (`### R-NNNN (time, kind)`)
- Не проверяет качество требований — только структуру и ссылки

## Связи
- Используется `task-spec` скилом (триггер «постановка задачи», «собери требования»)
- Результат (`task.md` из черновика) передаётся в `task-intake` для заведения в Jira
- Индекс черновиков (`.doc/skil_data/task-spec/index.json`) читается для истории
- Документирован в `../../SKILL.md` (раздел «Сбор требований»)

## История изменений
- 2026-11-07: заполнена полная документация по коду (был draft)