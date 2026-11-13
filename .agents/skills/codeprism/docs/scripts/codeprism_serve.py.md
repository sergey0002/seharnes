# Скрипт: `.agents/skills/codeprism/scripts/codeprism_serve.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/codeprism.md]
tags: [harness, script, codeprism, mcp, http, watcher, python]
-->

## Суть
HTTP-сервер CodePrism MCP с in-process файловым вотчером. Upstream `codeprism serve` строит индекс один раз при старте и не следит за файлами. Этот враппер запускает тот же MCP-сервер и, после первичной индексации, включает `ProjectWatcher` внутри процесса сервера — тот использует тот же in-memory граф и хранилище, поэтому сохранённые файлы видны без рестарта. Версия `codeprism-ai` закреплена на 0.1.11 (внутренние API проверяются при старте).

## Когда запускать
- Как долгоживущий HTTP-сервер для CodePrism MCP (порт из `.cursor/mcp.json`)
- Через systemd или вручную для shared режима
- Один инстанс на проект (файловая блокировка предотвращает дубли)

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `[project]` | string | нет | `.` | Корень проекта для индексации |
| `--transport` | `stdio` \| `http` | нет | `stdio` | Транспорт MCP |
| `--port` | integer | при http | — | Порт для HTTP (1..65535) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Сервер остановлен нормально | — |
| 1 | Порт занят / проект уже обслуживается | Проверить, не запущен ли другой инстанс |
| 127 | codeprism-ai не установлен или импорт упал | `pip install codeprism-ai==0.1.11` |

## Что читает и что пишет
- **Читает**: файлы проекта (код, конфиги), `.cursor/mcp.json` (валидация в proxy)
- **Пишет**: HTTP MCP на `127.0.0.1:<port>`, лог в stderr, файловый lock на корне проекта

## Побочные эффекты
- Создаёт файловый lock (`fcntl FLOCK_EX`) на директории проекта — второй инстанс не запустится
- Запускает фоновый `ProjectWatcher` с debounce (по умолчанию из конфига codeprism)
- Исключает директории: `vendor`, `node_modules`, `templates_c`, `dist`, `plugins`, `jscalendar-1.0`, `minified`, `i18n`, `lang`, `migrations`, `fixtures`, `.min.js` файлы
- Отключает tool `index_project` для HTTP клиентов (только чтение)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `CODEPRISM_NO_AUTO_INDEX` | `1` — отключить авто-индексацию при старте (default: `0` — включена) |
| `codeprism-ai==0.1.11` | Закреплённая версия; при обновлении пакета перепроверить live test |

## Примеры
```bash
# HTTP сервер на порту 9141
python3 .agents/skills/codeprism/scripts/codeprism_serve.py /home/user/project --transport http --port 9141

# stdio для прямого подключения
python3 .agents/skills/codeprism/scripts/codeprism_serve.py /home/user/project --transport stdio
```

## Ограничения
- Только HTTP на 127.0.0.1 (host_origin_protection, allowed_hosts: 127.0.0.1, localhost, ::1)
- Один инстанс на проект (flock)
- Версия 0.1.11 закреплена — при обновлении codeprism-ai могут сломаться внутренние хуки
- Не индексирует исключённые директории и `.min.js`
- Требует Python 3.10+ (fcntl, asyncio)

## Связи
- Proxy для stdio клиентов: `codeprism-mcp.sh`
- Конфиг: `.cursor/mcp.json` (type: http, url: http://127.0.0.1:<port>)
- Документация: `.doc/harnes/mcp/codeprism.md`, `.doc/harnes/state/15-mcp-stack.md`
- Проверка: `verify.sh` (fastmcp Client → get_graph_stats)
- Тесты: `test_codeprism_serve.py`, `test_codeprism_mcp.py`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)