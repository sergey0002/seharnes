# Copytrust Agent Harness: указатель на актуальные документы (readmy)

<!-- meta
type: index
status: outdated
updated: 2026-11-11
related: [index.md, ./dirtree.md, ./state/01-canon-envs.md, ./state/02-skills.md, ./state/03-rules.md, ./state/04-mcp.md, ./state/05-scripts.md, ./skill-format.md, ./component-docs.md, ./doc_rules.md]
tags: [harness, legacy, redirect]
-->

---

## Суть

Файл был полным реестром харнеса с числами и списками на 2026-09-30. Содержимое устарело: числа, пути и состав компонентов больше не поддерживаются. Вместо копии ниже стоят ссылки на актуальные документы. Имя файла сохранено, чтобы старые ссылки на `readmy.md` не ломались.

Канон скилов это `.agents/skills`, канон правил это `.cursor/rules`, MCP-конфиг это `.cursor/mcp.json`. Полная раскладка и запреты: [dirtree.md](./dirtree.md).

---

## 1. Канон и принципы

Канон, среды, синхронизация, parity и границы харнеса: [state/01-canon-envs.md](./state/01-canon-envs.md). Раскладка каталогов: [dirtree.md](./dirtree.md).

## 2. Раскладка каталогов

Полная раскладка, назначение `.agents/`, `.cursor/` и `.tools/`, размещение скриптов и дерево скила: [dirtree.md](./dirtree.md).

## 3. Скилы

Карта скилов и ссылки на карточки: [state/02-skills.md](./state/02-skills.md). Нормативная структура папки, `SKILL.md`, `skill.json` и дети: [skill-format.md](./skill-format.md). Канон: [.agents/skills/](../../.agents/skills/).

## 4. Рулесы

Карта правил канона и rule-only компонентов: [state/03-rules.md](./state/03-rules.md). Канон: [.cursor/rules/](../../.cursor/rules/).

## 5. MCP-серверы

Состав, статусы, порядок вызова и адаптации сред: [state/04-mcp.md](./state/04-mcp.md). Правила серверов: [state/20-mcp-rules.md](./state/20-mcp-rules.md). Канон: [.cursor/mcp.json](../../.cursor/mcp.json).

## 6. Скрипты

Карта скриптов, назначение и аргументы: [state/05-scripts.md](./state/05-scripts.md). Правила размещения: [dirtree.md](./dirtree.md), раздел 6. Документы компонентов: [component-docs.md](./component-docs.md).

## 7. Документация `.doc/`

Правила чтения и записи, структура `.doc/`, meta и обязательные секции: [doc_rules.md](./doc_rules.md).

## 8. Схемы взаимодействия

Задача, бизнес-анализ, документация, синхронизация и отчеты: [state/07-workflows.md](./state/07-workflows.md).

## 9. Перенос в другой проект

Профили Core, Developer и Project, что копируется и как проверяется перенос: [state/14-project-migration.md](./state/14-project-migration.md). Legacy Full соответствует Developer. Синхронизация сред: [state/13-agent-migration.md](./state/13-agent-migration.md).

## 10. Статус проверок

Актуальное состояние документации и проверок: [index.md](./index.md). Числа из прежних версий `readmy.md` не использовать.

---

## Связи

- [index.md](./index.md) - точка входа в документацию харнеса
- [dirtree.md](./dirtree.md) - канон раскладки каталогов
- [state/01-canon-envs.md](./state/01-canon-envs.md) - канон, среды и parity
- [state/02-skills.md](./state/02-skills.md) - карта скилов
- [state/03-rules.md](./state/03-rules.md) - карта правил
- [state/04-mcp.md](./state/04-mcp.md) - карта MCP
- [state/05-scripts.md](./state/05-scripts.md) - карта скриптов
- [doc_rules.md](./doc_rules.md) - правила документации

---

## Известные проблемы и ограничения

### П-1: Числа и состав из прежних версий недействительны

- Симптом: старые ссылки и цитаты называют 14 правил, 22 скила и канон скилов `.cursor/skills`.
- Причина: файл был снимком на 2026-09-30 и не обновлялся после перехода канона в `.agents/skills`.
- Решение: брать состав из `index.md` и `state/*`, проверять сканом каталога, а не по этому файлу.
- Файлы: `.doc/harnes/readmy.md`

---

## История изменений

- 2026-11-11: устаревшее содержимое удалено, разделы заменены ссылками на актуальные документы. Файл оставлен как указатель для старых ссылок.
- 2026-10-02: файл переведен в исторический снимок, актуальная документация перенесена в `.doc/harnes/state/` и `.doc/harnes/plan/`.
- 2026-09-26: создан как мастер-реестр по итогам аудита харнеса.
