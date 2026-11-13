# Скрипт: `.agents/skills/harness-router/children/add-skill/scripts/add_skill.py`

<!-- meta
type: script
status: actual
updated: 2026-11-10
related: [../../SKILL.md]
tags: [harness, script, add_skill]
-->

## Суть
Устанавливает локальный скил в канон харнеса (`.agents/skills/`) с полной валидацией структуры, созданием недостающих `README.md` и `skill.json`, добавлением карточки документации (`.doc/harnes/skills/{name}.md`), записью в реестр компонентов (`.agents/skills/harness-router/children/improvement/scripts/component_registry.json`), обновлением родительского роутера (skill.json родителя) и индексов (`.doc/harnes/index.md`, `.doc/harnes/state/02-skills.md`). Запускает синхронизацию сред (`sync-agent-views.sh`), включая блокирующую проверку visibility-контракта правил, и валидаторы (`validate_skills.py`, `validate_registry.py`, `rebuild-routers.py --check`). Поддерживает установку из view-среды (codex/qoder/qwen/kilo/agents) с разрешением конфликтов версий, dry-run, бэкап существующего канона, force-перезапись.

## Когда запускать
- При добавлении нового локального скила в проект (после разработки в `.codex/skills/` или `.qoder/skills/` и т.д.).
- При миграции харнеса в новый проект — для установки локальных скилов источника.
- По команде «установи скил», «добавь скил в харнес», «прими локальный скил».
- Агент вызывает после `scan_local_skills.py` для установки найденных canon_local/view_local скилов.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --name |  | array | нет | [] | Имя скила или relative id; повторяемый |
| --all |  | flag | нет |  | Установить все однозначные локальные скилы (canon_local + view_local) |
| --from |  | string | нет |  | Источник для view-local/конфликтного: codex, qoder, qwen, kilo, agents |
| --force |  | flag | нет |  | Заменить существующий канон-скил (с бэкапом) |
| --allow-absolute-paths |  | flag | нет |  | Не предупреждать об абсолютных путях в файлах скила |
| --dry-run |  | flag | нет |  | Вывести план без записи |
| --yes |  | flag | нет |  | Применить без интерактивного подтверждения |
| --no-sync |  | flag | нет |  | Пропустить sync-agent-views.sh |
| --no-validate |  | flag | нет |  | Пропустить валидаторы после установки |
| --json |  | flag | нет |  | Машинный JSON-вывод |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (или dry-run) | Продолжить работу |
| 1 | Ошибки валидации, конфликты, sync/validate failed | Исправить и повторить |
| 2 | Skills root не найден, неверные аргументы | Проверить --root, --name |
| 3 | Отмена пользователем (нет --yes в интерактивном режиме) | Запустить с --yes |

## Что читает и что пишет
**Читает:**
- Исходный скил: `.agents/skills/{name}/` или view-среда (`.codex/skills/`, `.qoder/skills/`, `.qwen/skills/`, `.kilo/skills/`)
- `scan_local_skills.py` отчёт (для --all)
- `.doc/harnes/state/02-skills.md` — состояние скилов
- `.doc/harnes/index.md` — индекс харнеса
- `.agents/skills/harness-router/children/improvement/scripts/component_registry.json` — реестр компонентов
- Родительский `skill.json` (если скил в children/)

**Пишет:**
- Канон: `.agents/skills/{name}/` (копия/обновление)
- `README.md` (если не было) — из frontmatter description SKILL.md
- `skill.json` (если не было) — с resources, children, dependencies
- `.doc/harnes/skills/{name}.md` — карточка документации
- `.doc/harnes/state/02-skills.md` — строка в таблице локальных скилов
- `.doc/harnes/index.md` — ссылка в разделе «Группировка менеджеров»
- `component_registry.json` — запись компонента
- Родительский `skill.json` — добавление в children[]
- Бэкап: `.doc/skil_data/harness-core/install-backup/{timestamp}/{name}/` (при --force)

## Побочные эффекты
- Копирует/обновляет файлы в каноне `.agents/skills/`.
- Запускает `sync-agent-views.sh` (зеркала в .codex, .kilo, .qoder, .qwen, .agents/rules); синк падает, если правило-гейт или path-trigger недоступен в среде.
- Запускает валидаторы: `validate_skills.py`, `validate_registry.py`, `rebuild-routers.py --check`.
- Создаёт бэкап при --force.

## Окружение и зависимости
- Python 3.7+ (argparse, datetime, json, re, shutil, subprocess, sys, tempfile, pathlib, dataclasses).
- `scan_local_skills.py` (импортируется как модуль).
- `bash` для `sync-agent-views.sh`.
- Внешние команды: `python3`, `bash`.

## Примеры
```bash
# Установить конкретный скил из канона (уже в .agents/skills/)
python3 .agents/skills/harness-router/children/add-skill/scripts/add_skill.py --root . --name my-skill --yes

# Установить из codex view (разрешение конфликта)
python3 .agents/skills/harness-router/children/add-skill/scripts/add_skill.py --root . --name my-skill --from codex --yes

# Все однозначные локальные скилы
python3 .agents/skills/harness-router/children/add-skill/scripts/add_skill.py --root . --all --yes

# Dry-run для предпросмотра
python3 .agents/skills/harness-router/children/add-skill/scripts/add_skill.py --root . --name my-skill --dry-run

# JSON-вывод для автоматизации
python3 .agents/skills/harness-router/children/add-skill/scripts/add_skill.py --root . --name my-skill --yes --json
```

Пример JSON-вывода:
```json
{
  "status": "ok",
  "installed": 1,
  "actions": [
    {
      "id": "my-skill",
      "name": "my-skill",
      "kind": "canon-local",
      "actions": ["validate", "use-canon", "readme", "skill.json", "state", "index", "registry", "parent-router"],
      "warnings": [],
      "source": ".agents/skills/my-skill",
      "target": ".agents/skills/my-skill"
    }
  ],
  "next_steps": ["проверить карточку родительского скила и его README"],
  "errors": []
}
```

## Ограничения
- Имя скила должно соответствовать `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
- README описывает назначение и границы, без ссылок.
- Запрещены симлинки, посторонние каталоги (не в ALLOWED_DIRS), секреты (API keys, private keys), абсолютные пути (если не --allow-absolute-paths).
- При конфликте версий (один скил в нескольких view с разным содержимым) нужен `--from`.
- Не устанавливает пакетные скилы (из baseline kit-manifest.json) — только локальные.

## Связи
- Вызывается: агент по команде «установи скил», после `scan_local_skills.py`, `migration-review` (--apply-skills)
- Зависит от: `scan_local_skills.py`, `_lib.ps1` (через sync), валидаторов improvement
- Результат используется: синхронизированные среды, обновлённые индексы, реестр компонентов

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)
- 2026-11-09: зафиксирован visibility-гейт, который выполняет синк после установки