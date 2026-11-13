---
name: harness-core
description: Базовое ядро харнеса: CLI, библиотека, конфиги и общие инструкции. Fallback для комплексных запросов, которые не покрыты узкими скилами. Применять для сложных цепочек и общей архитектуры харнеса.
---

# Ядро харнеса

Родительский скил для операций с харнесом. Дочерние скилы отвечают за отдельные сценарии, общая библиотека и конфиги лежат здесь.

## Когда применять

- Нужно синхронизировать правила, скилы и MCP между средами.
- Нужно перенести kit в новый проект или повторить экспорт.
- Нужно настроить MCP, порты, индексы и git в проекте.
- Нужно проверить MCP, собрать карту харнеса или найти расхождения.

## Вход

- Корень проекта.
- `assets/environments.json` и `assets/kit.json`.
- Предварительные `assets/policies/skill-format.yaml` и `component-docs.yaml`: строгие проверки структуры, скилов, README, документов скриптов и MCP используют часть YAML-правил вместе со встроенными ограничениями. Полный набор и policy bundle ещё не подключены.
- Значения проекта: контейнер, БД, порты, профиль экспорта.
- Файлы канона: `.cursor/rules`, `.agents/skills`, `.cursor/mcp.json`.

## Шаги

1. Проверить состояние:

```bash
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py doctor
```

2. Синхронизировать среды. Сначала dry-run, затем применение:

```bash
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py sync --dry-run
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py sync --yes
```

3. Перенести kit в новый проект:

```bash
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py export --target <path>
```

4. Настроить проект после экспорта:

```bash
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py setup
```

5. Проверить MCP и карту харнеса:

```bash
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py mcp-audit
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py verify
```

## Маршрутизация

| Запрос | Дочерний скил |
|---|---|
| Настроить MCP, порты и индексы проекта | `project-setup` |
| Перенести kit в новый проект | `new-project` |
| Синхронизировать правила, скилы и MCP | `environment-sync` |
| Проверить MCP и найти расхождения | `mcp-audit` |
| Построить карту харнеса | `mirror` |
| Найти ответ по карте харнеса | `index` |
| Улучшить скил, правило или harness | `children/improvement` |

## Выход

- Синхронизированные представления всех включенных сред.
- Отчет по заменам, добавлениям и сохраненным файлам.
- Kit в целевом проекте и отчет экспорта.
- Настроенные MCP, порты, индексы и git-исключения.
- Отчет аудита MCP и карта харнеса.

## Ограничения

- Родитель не дублирует скрипты детей.
- Общая библиотека только в `scripts/lib`.
- Один скрипт имеет одного владельца.
- Состояние и кеши не попадают в скилы.
- Коммиты и push не выполняются без явного запроса.
- Дочерние скилы: `children/project-setup`, `children/new-project`, `children/environment-sync`, `children/mcp-audit`, `children/mirror`, `children/index`.
