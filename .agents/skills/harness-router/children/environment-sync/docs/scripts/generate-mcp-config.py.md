# Скрипт: `.agents/skills/harness-router/children/environment-sync/scripts/generate-mcp-config.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, generate-mcp-config, antigravity, gemini, mcp]
-->

## Суть
Генерирует `mcp_config.json` для Antigravity / Gemini из канонического `.cursor/mcp.json`. Antigravity (Windows-процесс даже при WSL remote) не раскрывает переменные VS Code (`${workspaceFolder}`, `${env:VAR}`) и не поддерживает `envFile`. Скрипт делает два варианта рендера:
- `native` — для Linux/WSL клиентов: инлайнит переменные из `envFile`, раскрывает `${workspaceFolder}` и `${env:VAR}`, убирает `envFile`.
- `windows-wsl` — для Windows Antigravity: stdio-серверы оборачиваются в `wsl.exe -d <distro> -- bash -lc "..."`, чтобы они исполнялись в WSL с тем же тулчейном; HTTP/SSE серверы остаются как URL. Секреты остаются в WSL-файле `mcp.env` и не попадают в Windows-side JSON.

## Когда запускать
- После изменений в `.cursor/mcp.json` или `.cursor/mcp.env`.
- При настройке Antigravity / Gemini для проекта — чтобы получить рабочий `mcp_config.json`.
- В составе `sync-agent-views.sh` — генерация Antigravity view.
- При смене WSL-дистрибутива (`--distro`) для windows-wsl режима.

Если не запускать: Antigravity не сможет запустить stdio MCP-серверы (пути Linux не работают на Windows) или подхватит неправильные переменные окружения.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| root (позиционный) |  | string | нет | (родитель скрипта) | Корень проекта (где лежит `.cursor/mcp.json`) |
| out (позиционный) |  | string | нет | `.doc/skil_data/harness-router/antigravity_mcp_config.json` | Путь к выходному файлу |
| --host |  | choice | нет | native | `native` = Linux/WSL; `windows-wsl` = Windows Antigravity через wsl.exe |
| --distro |  | string | нет | "" | Имя WSL-дистрибутива для `--host windows-wsl` |
| --out |  | string | нет | (см. out позиционный) | Альтернативный способ задать выходной файл |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: конфиг записан | Продолжить |
| 1 | Ошибка чтения/записи, невалидный JSON | Проверить входные файлы и права |
| 2 | Аргумент/входная ошибка: не найден `.cursor/mcp.json` | Указать верный `--root` |

## Что читает и что пишет
**Читает:**
- `.cursor/mcp.json` — каноническая конфигурация MCP-серверов
- `.cursor/mcp.env` — глобальные переменные окружения
- Переменные окружения процесса (`os.environ`) — для `${env:VAR}`

**Пишет:**
- Указанный выходной файл (по умолчанию `.doc/skil_data/harness-router/antigravity_mcp_config.json`) — JSON с `mcpServers`:
  - `native`: все серверы с раскрытыми путями/переменными, без `envFile`, с `serverUrl`/`url` дублями для HTTP.
  - `windows-wsl`: HTTP/SSE — как есть; stdio — обёрнуты в `wsl.exe ... bash -lc "cd /path && set -a && . /path/to/mcp.env && export VAR=... && exec command args"`. Для `xdebug` при включённом состоянии принудительно ставит `XDEBUG_PORT=9004` (отдельный порт от Cursor).

## Побочные эффекты
- file write (атомарная замена через временный файл)
- stdout: путь к сгенерированному файлу и режим хоста

## Окружение и зависимости
- Python 3.8+
- Стандартная библиотека: `argparse`, `json`, `os`, `re`, `shlex`, `sys`, `pathlib`
- Файл `.cursor/mcp.env` (KEY=VALUE, `export`, комментарии, кавычки)
- WSL должен быть установлен и доступен как `wsl.exe` (для windows-wsl режима)

## Примеры
```bash
# Native (Linux/WSL) — для Cursor, Kilo, DSH внутри WSL
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-mcp-config.py . --host native

# Windows Antigravity — stdio через wsl.exe, HTTP как есть
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-mcp-config.py . --host windows-wsl --distro Ubuntu

# Явный выходной файл
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-mcp-config.py /home/user/project /tmp/antigravity_mcp.json --host windows-wsl
```

## Ограничения
- Не поддерживает MCP-типы кроме `stdio`/`local` и `http`/`sse`/`remote`.
- `envFile` полностью инлайнится в `env` — секреты в `mcp.env` должны быть защищены файловыми правами.
- Для `windows-wsl`: работают только stdio-серверы, которые запускаются в WSL. Если сервер ждёт Windows-пути — не сработает.
- `xdebug` получает фиксированный порт 9004 в Antigravity view, чтобы не конфликтовать с Cursor (обычно 9003).
- Выходной файл по умолчанию кладётся в `.doc/skil_data/` — техническая директория, не коммитится в git.
- Не делает транзакцию: если упало на середине — частично записанный файл остаётся.

## Связи
- Вызывается: `sync-agent-views.sh` (Antigravity view), ручной запуск для настройки Antigravity.
- Зависит от: `.cursor/mcp.json`, `.cursor/mcp.env`.
- Генерирует вход для: Antigravity / Gemini (`mcp_config.json`).
- Связанные документы: `.doc/harnes/state/04-mcp.md`, `.doc/harnes/mcp/README.md`.

## История изменений
- 2026-11-07: полная документация на основе анализа кода