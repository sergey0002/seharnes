# Скрипт: `.agents/skills/harness-router/children/skill-authoring/scripts/create_skill.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, create_skill]
-->

## Суть
Создаёт каркас нового харнес-скила в `.agents/skills/` (или в `children/` родительского скила) и регистрирует его через `add_skill.py`. Генерирует три файла: `SKILL.md` (frontmatter name/description, шаблон секций: Когда применять, Вход, Шаги, Выход, Ограничения), `README.md` (назначение, как работает, что нужно, чего не делает), `skill.json` (schema=1, kind=leaf/orchestrator, entry=SKILL.md, readme=README.md, resources={scripts,references,assets}=[], tests=[], children=[], dependencies={skills,project}=[], generated=[]). Опционально создаёт placeholder unittest в `tests/test_{name}.py`. Затем вызывает `add_skill.py --name {name} --yes --no-sync` для установки в канон, добавления документации, реестра, родительского роутера и синхронизации view. Поддерживает `--dry-run`, `--force`, `--parent` (создать как child), `--kind` (leaf/orchestrator), `--with-test`.

## Когда запускать
- При команде «создай скил», «напиши скил», «новый скил».
- При начале разработки нового скила для получения правильной структуры.
- Агент запускает с параметрами из задачи.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --name |  | string | да |  | Имя папки скила (kebab-case) |
| --title |  | string | нет | (name) | Человеческий заголовок |
| --description |  | string | нет | "Пользовательский скил харнеса. Применять по явному запросу." | Frontmatter description и README purpose |
| --parent |  | string | нет |  | Parent skill id (создаёт в parent/children/) |
| --kind |  | string | нет | leaf | leaf или orchestrator |
| --with-test |  | flag | нет |  | Создать placeholder unittest |
| --force |  | flag | нет |  | Заменить существующий каркас |
| --dry-run |  | flag | нет |  | Вывести план без записи |
| --no-validate |  | flag | нет |  | Пропустить валидаторы после регистрации |
| --json |  | flag | нет |  | Машинный JSON-вывод |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (или dry-run) | Продолжить работу |
| 1 | Ошибка add_skill.py (валидация, sync, validate failed) | Проверить вывод add_skill |
| 2 | Неверное имя скила / skills root не найден / parent не найден | Исправить аргументы |

## Что читает и что пишет
**Читает:**
- `.agents/skills/` — для проверки существования и parent
- `scan_local_skills.py` — для baseline (ensure_baseline)

**Пишет:**
- `{target}/SKILL.md` — frontmatter + шаблон секций
- `{target}/README.md` — шаблон README
- `{target}/skill.json` — манифест
- `{target}/tests/test_{name}.py` — placeholder unittest (при --with-test)
- Через `add_skill.py`: канон, зеркала, документация, реестр, роутеры

## Побочные эффекты
- Создаёт файлы скила в каноне.
- Запускает `add_skill.py` → `sync-agent-views.sh`, валидаторы, rebuild-routers.

## Окружение и зависимости
- Python 3.7+ (argparse, json, re, subprocess, sys, pathlib).
- `add_skill.py` (подпроцесс).
- `scan_local_skills.py` (модуль для baseline).

## Примеры
```bash
# Базовый листовой скил
python3 .agents/skills/harness-router/children/skill-authoring/scripts/create_skill.py --root . --name my-skill --description "Обработка платежей через NewGateway"

# Дочерний скил под harness-router
python3 .agents/skills/harness-router/children/skill-authoring/scripts/create_skill.py --root . --name my-child --parent harness-router --description "Дочерний скил для X"

# Оркестратор с тестом
python3 .agents/skills/harness-router/children/skill-authoring/scripts/create_skill.py --root . --name my-orchestrator --kind orchestrator --with-test --description "Оркестрация Y"

# Force пересоздание
python3 .agents/skills/harness-router/children/skill-authoring/scripts/create_skill.py --root . --name my-skill --force --description "Новое описание"

# Dry-run
python3 .agents/skills/harness-router/children/skill-authoring/scripts/create_skill.py --root . --name my-skill --dry-run
```

Пример сгенерированного `SKILL.md`:
```markdown
---
name: my-skill
description: Обработка платежей через NewGateway
---

# my-skill

## Когда применять

- пользователь явно просит выполнить работу этого скила;
- задача входит в описанную область без смежных изменений.

## Вход

- корень проекта;
- задача или данные, с которыми работает скил;
- подтверждение пользователя на изменение файлов.

## Шаги

1. Проверить входные данные и границы задачи.
2. Выполнить основную работу по назначению скила.
3. Проверить результат и записать его в ожидаемое место.
4. Сообщить, что изменилось и какие проверки выполнены.

## Выход

- результат работы скила;
- список измененных файлов и проверок;
- известные ограничения, если они есть.

## Ограничения

- Скил создан как каркас. Его шаги нужно уточнить под фактическую задачу.
- Не расширять область задачи без запроса.
```

Пример `skill.json`:
```json
{
  "schema": 1,
  "name": "my-skill",
  "kind": "leaf",
  "entry": "SKILL.md",
  "readme": "README.md",
  "resources": {"scripts": [], "references": [], "assets": []},
  "tests": [],
  "children": [],
  "dependencies": {"skills": [], "project": []},
  "generated": []
}
```

## Ограничения
- Имя скила должно соответствовать `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- `--parent` требует существующего скила с SKILL.md в `.agents/skills/{parent}/`.
- Сгенерированный скил — каркас; автор должен заполнить шаги, ограничения, добавить скрипты в `scripts/` и обновить `skill.json` resources.
- `--with-test` создаёт только placeholder unittest — реальные тесты пишутся вручную.
- Не создаёт документацию в `.doc/harnes/skills/` — `add_skill.py` делает это автоматически.

## Связи
- Вызывается: агент по команде «создай скил», `skill-authoring` скил
- Зависит от: `add_skill.py`, `scan_local_skills.py`, структуры `.agents/skills/`
- Результат использует: новый скил в каноне, синхронизированные view, готовый к разработке

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)