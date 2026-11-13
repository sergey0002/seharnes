# Скрипт: `verify_generated_copies.py`

<!-- meta
type: script
status: actual
updated: 2026-11-13
related: [../../SKILL.md]
tags: [harness, sync, qoder, qwen, dsh, validation]
-->

## Суть

Проверяет, что в `.qwen/skills` и `.dsh/skills` лежат только discovery-обёртки или `rule-*`, а не устаревшие полные копии скилов. Полный набор файлов разрешён только Qoder.

## Когда запускать

В doctor и после ручной правки generated views, чтобы поймать legacy-копии и лишние файлы.

## Аргументы

| Аргумент | Значение |
|---|---|
| `--root` | Корень установленного харнеса. |

## Коды выхода

`0` - views корректны; `1` - найдена полная копия или лишний файл; `2` - ошибка чтения или отсутствует канон.

## Что читает и что пишет

Читает `.agents/skills`, `.qwen/skills` и `.dsh/skills`. Ничего не пишет.

## Побочные эффекты

Нет.

## Окружение и зависимости

Python 3. Использует только стандартную библиотеку.

## Примеры

```sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_generated_copies.py --root .
```

## Ограничения

Скрипт проверяет маркер `generated discovery wrapper` и состав файлов, но не сверяет текст обёртки с каноном. Синтаксис и содержимое правил проверяют `generate-qwen-config.py --check` и `native-discovery`.

## Связи

Вызывается гейтом `generated-copies` в `harness_cli.py doctor`. Дополняет `generate-agent-configs.py --check-discovery`.

## История изменений

- 2026-11-13: добавлена проверка legacy-копий Qwen и DSH.
