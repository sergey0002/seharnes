---
name: environment-sync
description: Синхронизация правил, скилов и MCP между средами.
---

# environment-sync

## Когда применять

- Когда нужен сценарий environment-sync в управлении харнесом.

## Вход

- Корень проекта и конфиги `harness-router`.

## Шаги

1. Из корня проекта выполнить `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`. До записи скрипт проверит Qoder: неизвестные файлы, ссылки и MCP-серверы блокируют синхронизацию и требуют отдельного решения. Изменённые управляемые файлы Qoder сохраняются в резервной копии. Различия существующего MCP требуют просмотра и отдельного флага `--replace-managed-mcp`; неизвестные серверы этот флаг не удаляет.
2. Проверить результаты генераторов, parity и `verify_rule_triggers.py`. Codex и Cursor читают `.agents/skills` напрямую. Старые копии убираются; отличающиеся файлы сохраняются в `.doc/skil_data/environment-sync/backups/`. Antigravity получает `.agents/skills.json`, DSH получает указатели вложенных скилов.
3. Проверить visibility-контракт через `harness_mirror.py --root . visibility --summary`. `gate: true` обязан быть inline во всех средах; `attach: glob` обязан срабатывать по пути или присутствовать в сгенерированной glob-таблице.
4. При ошибке исправить канон или генератор и повторить синк. Не редактировать views вручную.

## Выход

- Синхронизированные представления и отчет с результатами parity, trigger и visibility проверок.

## Ограничения

- Не дублировать код родителя.
- Не хранить состояние в скиле.

## История изменений

- 2026-11-12: исправлены native discovery, bootstrap Codex, тип globs Antigravity и ссылки правил. Канон остаётся прежним.
