# Скрипт: `.agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-launch.sh`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/codebase-memory-mcp.md]
tags: [harness, script, codebase-memory-mcp, cbm, launcher, mcp]
-->

## Суть
Универсальный лаунчер codebase-memory-mcp (CBM) для Linux/WSL. Находит бинарник в нескольких локациях (`~/.local/bin/`, Windows AppData через /mnt/c/, WSL-пути), настраивает общий кэш (`CBM_CACHE_DIR`), опционально запускает UI-демона в tmux, и форвардит аргументы в бинарник. Авто-UI отключён по умолчанию (чтобы не съедать ~7GB RAM в WSL дублирующими инстансами).

## Когда запускать
- Как entrypoint для MCP-клиентов (Cursor, Kilo, Codex, dsh) при подключении к CBM
- Ручно для запуска CBM с кастомными флагами
- Через systemd unit `mcp-codebase-memory.service` (shared режим)

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `--ui=true` | flag | нет | false | Запустить встроенный 3D web UI |
| `--port=<n>` | integer | нет | 9749 | Порт для UI (если --ui=true) |
| Любые другие | string[] | да | — | Пробрасываются в CBM бинарник |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | CBM запущен | — |
| 127 | Бинарник не найден | См. `.doc/harnes/mcp/codebase-memory-mcp.md` для инструкций по установке |

## Что читает и что пишет
- **Читает**: переменные окружения `CBM_CACHE_DIR`, `CBM_ENABLE_UI`, `CBM_UI_PORT`, `CBM_UI_TMUX_SESSION`
- **Пишет**: логи в stdout/stderr, при UI — tmux сессия

## Побочные эффекты
- Экспортирует `CBM_CACHE_DIR` (по умолчанию `~/.local/share/mcp-stack/codebase-memory`)
- Может запустить tmux-сессию с UI (`cbm-ui` по умолчанию)
- Запускает долгоживущий CBM процесс

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `CBM_CACHE_DIR` | Директория кэша (default: `~/.local/share/mcp-stack/codebase-memory`) |
| `CBM_ENABLE_UI` | `1` — включить авто-запуск UI в tmux (default: `0` — выключено) |
| `CBM_UI_PORT` | Порт UI (default: 9749) |
| `CBM_UI_TMUX_SESSION` | Имя tmux сессии (default: `cbm-ui`) |

## Примеры
```bash
# Стандартный запуск (MCP stdio для клиентов)
bash .agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-launch.sh

# С UI в tmux
CBM_ENABLE_UI=1 bash .agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-launch.sh --ui=true --port=9749
```

## Ограничения
- Авто-UI отключён по умолчанию (`CBM_ENABLE_UI=0`) — предотвращает дублирование CBM инстансов и утечку RAM
- Находит бинарник в: `~/.local/bin/codebase-memory-mcp`, Windows AppData через `/mnt/c/Users/*/`, или в PATH
- UI требует `tmux` (не screen)
- В WSL: один shared CBM на машину, клиенты подключаются по stdio

## Связи
- Systemd unit: `mcp-codebase-memory.service` (shared, machine-level)
- UI launcher: `codebase-memory-mcp-ui.sh`
- Windows launcher: `codebase-memory-mcp-launch.cmd`
- Документация: `.doc/harnes/mcp/codebase-memory-mcp.md`, `.doc/harnes/state/15-mcp-stack.md`
- Проверка: `verify.sh`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)