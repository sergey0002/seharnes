# Скрипт: `.agents/skills/harness-router/children/skill-authoring/scripts/audit_skill.py`

<!-- meta
type: script
status: actual
updated: 2026-11-10
related: [../../SKILL.md]
tags: [harness, script, audit_skill]
-->

## Суть
Аудит одного или всех скилов харнеса по правилам проекта: структура каталогов, frontmatter SKILL.md, README.md, skill.json, скрипты, тесты, документация, индексы, реестр, родительский роутер, зависимости. Проверяет: имя папки (kebab-case), наличие SKILL.md, frontmatter name=папка, allowed поля (name, description, license, compatibility, metadata, allowed-tools, argument-hint), description не пустой, без ссылок, HTML, раздела `## Связи` и маркера незаполненного раздела, нет симлинков, посторонних каталогов, .mdc внутри скила, тестов вне tests/, секретов, абсолютных путей (warn). skill.json: schema=1, name=папка, entry=SKILL.md, readme=README.md, resources={scripts,references,assets} (массивы строк, отсортированные, существующие), tests[] существуют, children[] имеют SKILL.md, dependencies.skills[] существуют в каноне. Документация: карточка в `.doc/harnes/skills/{name}.md`, строка в `.doc/harnes/index.md`. Реестр: запись в `component_registry.json` с required_files. Родительский роутер: скил в children[] родителя, в SKILL.md родителя есть строковый роутер `` `{name}` ``. Скоринг: 100 - 15*errors - 5*warnings. Exit: 1 если есть errors (или --strict и warnings), 0 если passed.

## Когда запускать
- При создании/редактировании скила: «аудит скила», «проверь скил», «оцени скил».
- В CI для валидации новых/изменённых скилов.
- Агент запускает после `create_skill.py` или ручной правки скила.
- `--all` для полного аудита всех скилов канона.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --name |  | array | нет | [] | Имя скила или relative id; повторяемый |
| --all |  | flag | нет |  | Аудит всех скилов в `.agents/skills/` |
| --strict |  | flag | нет |  | Считать warnings как failure |
| --json |  | flag | нет |  | Машинный JSON-вывод |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все проверенные скилы passed (или warnings без --strict) | Успех |
| 1 | Есть errors (или warnings при --strict) | Исправить скил(ы) |
| 2 | Скил не найден / не передан --name/--all | Проверить аргументы |

## Что читает и что пишет
**Читает:**
- `.agents/skills/{name}/` — SKILL.md, README.md, skill.json, scripts/, references/, assets/, tests/, children/
- `.doc/harnes/skills/{name}.md` — карточка документации
- `.doc/harnes/index.md` — индекс харнеса
- `.agents/skills/harness-router/children/improvement/scripts/component_registry.json` — реестр компонентов
- Родительский skill.json (если скил в children/)

**Пишет:**
- Ничего (только stdout: JSON или текстовый отчёт).

## Побочные эффекты
- Нет побочных эффектов (read-only).

## Окружение и зависимости
- Python 3.7+ (argparse, json, re, sys, pathlib).
- Нет внешних зависимостей.

## Примеры
```bash
# Аудит конкретного скила
python3 .agents/skills/harness-router/children/skill-authoring/scripts/audit_skill.py --root . --name my-skill

# Все скилы, JSON
python3 .agents/skills/harness-router/children/skill-authoring/scripts/audit_skill.py --root . --all --json

# Strict режим (warnings = failure)
python3 .agents/skills/harness-router/children/skill-authoring/scripts/audit_skill.py --root . --name my-skill --strict
```

Пример JSON-вывода:
```json
{
  "status": "warning",
  "checked": 1,
  "errors": 0,
  "warnings": 3,
  "skills": [
    {
      "id": "my-skill",
      "name": "my-skill",
      "path": ".agents/skills/my-skill",
      "score": 85,
      "status": "warning",
      "errors": [],
      "warnings": [
        "нет README.md",
        "нет строки в harnes/index.md: my-skill",
        "resources.scripts не отсортирован"
      ]
    }
  ]
}
```

Пример текстового вывода:
```
Аудит скилов: warning, проверено 1, ошибок 0, предупреждений 3
  my-skill: warning, score 85
    WARN нет README.md
    WARN нет строки в harnes/index.md: my-skill
    WARN resources.scripts не отсортирован
```

## Ограничения
- Проверяет только структурные/формальные правила — не семантическое качество контента.
- Не валидирует содержимое скриптов (только наличие в skill.json, расширения, секреты/абсолютные пути).
- Не проверяет cross-skill зависимости кроме dependencies.skills[].
- frontmatter allowed fields — фиксированный список; новые поля требуют обновления скрипта.
- `--all` сканирует только `.agents/skills/` — view-среды не аудируются.

## Связи
- Вызывается: агент по команде «аудит скила», после `create_skill.py`, CI, `skill-authoring` скил
- Зависит от: структуры `.agents/skills/`, `.doc/harnes/`, `component_registry.json`
- Результат использует: блокировка merge при ошибках, список исправлений для автора скила

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)