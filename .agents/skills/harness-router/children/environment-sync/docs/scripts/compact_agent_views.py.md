# Скрипт: `compact_agent_views.py`

<!-- meta
type: script
status: actual
updated: 2026-11-13
related: [../../SKILL.md]
tags: [harness, sync, compact, git]
-->

## Суть

Удаляет generated views, которые восстанавливаются синхронизацией сред. Оставляет канон `.agents/skills`, `.cursor/rules`, `.cursor/mcp.json` и примеры env. Используется для компактного эталонного репозитория.

## Когда запускать

Перед первым commit эталона, после обновления из Git или когда нужно уменьшить рабочее дерево. Восстановление: `sync-agent-views.sh` или `harness_transfer render`.

## Аргументы

| Аргумент | Значение |
|---|---|
| `--root` | Корень установленного харнеса. |
| `--check` | Показать generated paths без удаления. |
| `--apply` | Удалить перечисленные generated paths. |
| `--force` | Удалить без проверки содержимого Qoder и обёрток. |

## Коды выхода

`0` - удалено, уже компактно или `--check` не нашёл generated paths; `1` - `--check` нашёл generated paths; `2` - проверка не прошла или ошибка.

## Что читает и что пишет

Читает `.agents/skills` и generated views. В `--apply` удаляет только известный список: `.qoder/skills`, `.qoder/rules`, `.qoder/settings.json`, `.qwen/skills`, `.qwen/rules`, `.qwen/settings.json`, `.dsh/skills`, `.codex/rules`, `.codex/rules-index.md`, `.codex/mcp.json`, `.codex/config.toml`, `.kilo/rules`, `.kilo/rules-index.md`, `.kilo/mcp.json`, `.kilo/kilo.jsonc`, `.kilo/kilo-permissions.fragment.jsonc`, `.agents/rules`, `.agents/mcp.json`, `.agents/mcp_config.json`, `.agents/skills.json`, `.cursor/tools/composer.phar`, `.codex/tools/composer.phar`, `.doc/skil_data/environment-sync`, `.doc/skil_data/mirror`, `.doc/harnes/state/.validate-rules-last.json`, `DSH-RULES.md`. Отдельно из `AGENTS.md` удаляется только generated bootstrap-блок, авторский текст сохраняется.

## Побочные эффекты

Без `--force` Qoder-дерево удаляется только при полном совпадении с каноном, а Qwen/DSH — только если это маркированные discovery-обёртки. Локальные изменения блокируют удаление.

## Окружение и зависимости

Python 3 стандартной библиотеки.

## Примеры

```sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/compact_agent_views.py --root . --check
python3 .agents/skills/harness-router/children/environment-sync/scripts/compact_agent_views.py --root . --apply
```

## Ограничения

Скрипт не удаляет `.dsh/adapters`, `.dsh/scripts`, `.dsh/tests`, `.codex/lib`, `.codex/go-task.ps1`, `.serena` и `.tools`. Composer phar не восстанавливается миграцией: Composer ставится в окружение через `.cursor/tools/README.md` и `composer install`. После удаления нужен `sync-agent-views.sh` или `harness_transfer render`.

## Связи

Вызывается `harness_transfer compact`. `.gitignore` эталона исключает те же generated paths, поэтому клон Git уже компактный.

## История изменений

- 2026-11-13: добавлена компактная очистка generated views.
