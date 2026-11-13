---
name: doc-script
description: >
  Документирование скриптов харнеса: документация лежит внутри скила-владельца
  в docs/scripts/, без ID и реестра. Скрипт извлекает аргументы, коды выхода,
  окружение и побочные эффекты, агент заполняет смысл.
  Use when: задокументируй скрипт, аудит скриптов, проверь аргументы скрипта.
---

# Doc Script

Документация скрипта лежит рядом с владельцем. Ассоциация строится по пути файла,
не по ID.

## Правило размещения

| Скрипт лежит | Владелец | Документ |
|---|---|---|
| `.agents/skills/{...}/scripts/{rel}` | ближайший скил с `SKILL.md` | `{skill}/docs/scripts/{rel}.md` |
| `.tools/scripts/{rel}` | `harness-core` | `harness-core/docs/scripts/tools/{rel}.md` |

Примеры:

```
.agents/skills/harness-router/children/doc-script/scripts/doc_script.py
-> .agents/skills/harness-router/children/doc-script/docs/scripts/doc_script.py.md

.tools/scripts/multi-search.sh
-> .agents/skills/harness-router/children/harness-core/docs/scripts/tools/multi-search.sh.md
```

## Шаги

1. `--list` показывает все скрипты и вычисленный путь документа. Если владелец
   не найден, скрипт не попадает в список.
2. `--script <path>` создает скелет `status: draft` с аргументами из кода.
3. Агент читает скрипт и заполняет разделы: `Суть`, `Когда запускать`,
   `Что читает и что пишет`, `Примеры`, `Ограничения`, `Связи`.
4. Агент ставит `status: actual`.
5. `--audit` проверяет: документ есть, статус `actual`, все разделы, аргументы
   совпадают с кодом, нет фраз `Заполнить:` и шаблонных заглушек.

Если скрипт читает argv вручную или пробрасывает его без разбора, добавь в meta
строку `argv: manual` или `argv: passthrough`. Тогда `--audit` не требует
автоматического разбора аргументов и проверяет ручную таблицу. Значение
`argv: passthrough` ставят обёрткам вида `exec "$@"`, `node-mcp`, `php-docker`.
Значение `argv: manual` ставят скриптам с `sys.argv`, `$argv` или позиционными
параметрами, которые разбираются вручную.

## Что извлекает скрипт

| Расширение | Аргументы |
|---|---|
| `.sh` | `getopts`, флаги `-x` и `--long` |
| `.ps1` | блок `param(...)` |
| `.py` | `argparse.add_argument` |
| `.js`, `.mjs` | `option()` и `argument()` |
| `.php` | `addArgument` Symfony Console |

Плюс: `exit N`, переменные окружения `$VAR`, побочные эффекты по паттернам
(git, docker, сеть, запись файлов, база).

## Команды

```bash
python3 .agents/skills/harness-router/children/doc-script/scripts/doc_script.py --list
python3 .agents/skills/harness-router/children/doc-script/scripts/doc_script.py --script .tools/scripts/multi-search.sh
python3 .agents/skills/harness-router/children/doc-script/scripts/doc_script.py --audit
```

`--all` создает скелеты только для отсутствующих документов. Массовый запуск
запрещен: скелет без смысла это мусор, который валит аудит.

## Зачем агенту документ

Документ дает все для вызова скрипта: аргументы, коды выхода, что читает и пишет,
побочные эффекты. Агенту не нужно читать исходник скрипта, чтобы его вызвать.

## Связи

- Шаблон: `.doc/harnes/component-docs.md` §3.
- Вызывается из `improvement` при проблеме в документации скрипта.
- Зеркало: узлы `type=script`, поле `analysis` заполняется из этого документа.
