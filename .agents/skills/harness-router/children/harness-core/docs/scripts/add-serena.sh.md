# Скрипт: `.cursor/mcp-stack/add-serena.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/serena.md, .doc/harnes/state/15-mcp-stack.md]
tags: [harness, script, serena, mcp, systemd, shared]
-->

## Суть
Регистрирует проект как общий Serena MCP endpoint через systemd user unit. Serena держит один активный проект на процесс, поэтому создаётся отдельный юнит на проект. Клиенты подключаются по HTTP к общему эндпоинту — количество клиентов не увеличивает число процессов.

## Когда запускать
- При настройке нового проекта для работы с Serena MCP
- После миграции проекта на другую машину
- При изменении порта или корня проекта
- Один раз на проект; повторный вызов пересоздаёт юнит

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `<project_root>` | string | да | — | Абсолютный или относительный путь к корню проекта |
| `[port]` | integer | нет | первый свободный в 9121..9199 | Порт для HTTP-эндпоинта Serena |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Юнит создан и сервис запущен | Проверить `systemctl --user status mcp-serena-<slug>` |
| 1 | Serena бинарник не найден или порт занят / нет свободных портов | Установить Serena: `uv tool install git+https://github.com/oraios/serena` |
| 2 | Не передан project_root | Проверить синтаксис: `add-serena.sh <project_root> [port]` |

## Что читает и что пишет
- **Читает**: наличие `~/.local/bin/serena`, проектный каталог `.serena/`
- **Пишет**: systemd unit в `~/.config/systemd/user/mcp-serena-<slug>.service`, логи в `~/.local/state/mcp-shared/serena-<port>.log`, обновляет `.cursor/mcp.json` (выводит конфиг для ручного добавления)

## Побочные эффекты
- Создаёт/перезаписывает systemd user unit
- Запускает долгоживущий процесс Serena MCP на указанном порту
- Резервирует порт в диапазоне 9121–9199
- Пишет логи в `~/.local/state/mcp-shared/`

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `PATH` | Должен содержать путь к `systemctl --user` и `uv` |
| `HOME` | База для путей юнитов, логов, кэша |

## Примеры
```bash
# Автовыбор порта
bash .cursor/mcp-stack/add-serena.sh /home/user/projects/myproject

# Явный порт
bash .cursor/mcp-stack/add-serena.sh /home/user/projects/myproject 9125
```

## Ограничения
- Требует установленной Serena через uv: `uv tool install git+https://github.com/oraios/serena`
- Работает только на Linux/WSL с systemd --user
- Один проект = один порт = один systemd unit
- Не обновляет `.cursor/mcp.json` автоматически — выводит готовый блок для ручного копирования
- Порт должен быть свободен на момент запуска

## Связи
- Создаёт: systemd unit `mcp-serena-<slug>.service`
- Вызывает: `verify.sh` для проверки после установки
- Документация: `.doc/harnes/mcp/serena.md`, `.doc/harnes/state/15-mcp-stack.md`, `.doc/harnes/state/01-canon-envs.md`
- Парный скрипт: `serena-shared.sh` (альтернативный запуск без systemd)

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)