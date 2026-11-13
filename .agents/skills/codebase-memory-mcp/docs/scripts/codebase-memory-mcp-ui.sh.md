# Скрипт: `.agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-ui.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/codebase-memory-mcp.md]
tags: [harness, script, codebase-memory-mcp, cbm, ui, tmux]
-->

## Суть
Запускает встроенный 3D web UI codebase-memory-mcp в фоновом tmux-сессии. Проверяет, не занят ли порт, убивает старую сессию при необходимости, запускает через общий лаунчер и ждёт готовности порта. Используется когда нужен визуальный интерфейс графа кода.

## Когда запускать
- При необходимости визуально исследовать граф кода в браузере
- После `codegraph init` для просмотра 3D-визуализации
- Вместо авто-UI в `codebase-memory-mcp-launch.sh` (который отключён по умолчанию)

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| — | — | — | — | Аргументов нет, настройка через окружение |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | UI запущен и порт слушает | Открыть `http://127.0.0.1:9749/` |
| 1 | tmux не установлен | Установить tmux: `sudo apt install tmux` |
| 127 | Бинарник CBM не найден | См. документацию CBM |

## Что читает и что пишет
- **Читает**: переменные `CBM_UI_PORT` (default 9749), `CBM_UI_TMUX_SESSION` (default `cbm-ui`)
- **Пишет**: запускает tmux-сессию, пишет логи в stdout/stderr

## Побочные эффекты
- Создаёт/пересоздаёт tmux сессию `cbm-ui`
- Запускает CBM процесс с `--ui=true` в фоне
- Открывает TCP-порт на 127.0.0.1

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `CBM_UI_PORT` | Порт для UI (default: 9749) |
| `CBM_UI_TMUX_SESSION` | Имя tmux сессии (default: `cbm-ui`) |
| `tmux` | Обязателен для фонового запуска на WSL/Linux |

## Примеры
```bash
# Запуск UI на порту по умолчанию
bash .agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-ui.sh

# Кастомный порт
CBM_UI_PORT=8080 bash .agents/skills/codebase-memory-mcp/scripts/codebase-memory-mcp-ui.sh
```

## Ограничения
- Требует `tmux` (не работает с screen или nohup)
- Только для Linux/WSL (не Windows native)
- UI доступен только на 127.0.0.1 (в WSL нужен порт-проброс для браузера на Windows)
- Автозапуск UI в главном лаунчере отключён (`CBM_ENABLE_UI=0`) — этот скрипт для ручного запуска

## Связи
- Основной лаунчер: `codebase-memory-mcp-launch.sh`
- Systemd unit: `mcp-codebase-memory.service`
- Документация: `.doc/harnes/mcp/codebase-memory-mcp.md`, `.doc/harnes/state/15-mcp-stack.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)