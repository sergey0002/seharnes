# Скрипт: `.agents/skills/task-router/children/testing-router/children/browser-verify/scripts/chromedriver-host-relay.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, ../scripts/start-chromedriver-wsl.sh]
tags: [harness, script, browser-verify, chromedriver, relay, wsl, docker]
-->

## Суть
HTTP релей на loopback (127.0.0.1) для обхода ограничения ChromeDriver 111+ на Host header. ChromeDriver отклоняет запросы с нелокальным Host (`host.docker.internal:9515`). Docker Desktop на WSL достигает WSL только через `host.docker.internal`, поэтому контейнерный Codeception (php-webdriver) не может подключиться напрямую. Релей слушает на `127.0.0.1:9515`, форвардит на настоящий chromedriver на `127.0.0.1:9516`, подменяя `Host` на `127.0.0.1:9516`. Оба конца — loopback, драйвер сохраняет свою IP allowlist защиту.

## Когда запускать
Автоматически из `start-chromedriver-wsl.sh` после запуска chromedriver на 9516. Можно запустить вручную если нужен отдельный релей на других портах. Если не запустить — Codeception в Docker получит `502` / "Rejecting request with non-local host" при попытке подключиться к `host.docker.internal:9515`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--listen-port` | | int | нет | 9515 | Порт, на котором релей слушает входящие запросы (loopback) |
| `--upstream-port` | | int | нет | 9516 | Порт upstream chromedriver (loopback) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | (не возвращается — сервер работает вечно) | — |
| 1 | Ошибка аргументов / bind failed | Проверить порт свободен |
| SIGTERM/SIGINT | Нормальное завершение | — |

Процесс не завершается сам (serve_forever). Остановка — `pkill -f chromedriver-host-relay.py`.

## Что читает и что пишет
**Читает:** входящие HTTP запросы на `127.0.0.1:listen-port`
**Пишет:** проксированные ответы от upstream, логи только при ошибках (stdout/stderr не используются, `log_message` заглушен)

## Побочные эффекты
- Открывает TCP слушатель на loopback
- Форит HTTP соединения к upstream chromedriver
- Не пишет файлы, не меняет состояние системы

## Окружение и зависимости
- Python 3.8+
- Стандартная библиотека: `argparse`, `http.client`, `http.server` (ThreadingHTTPServer)
- Нет внешних зависимостей
- Upstream chromedriver должен быть запущен на `upstream-port` до старта релея

## Примеры
```bash
# Стандартный запуск (через start-chromedriver-wsl.sh)
python chromedriver-host-relay.py --listen-port 9515 --upstream-port 9516

# На других портах
python chromedriver-host-relay.py --listen-port 9515 --upstream-port 9517
```

## Ограничения
- Только HTTP/1.0 (protocol_version = "HTTP/1.0") — для совместимости с php-webdriver curl client, который реюзал сокеты при 1.1
- Не поддерживает HTTPS/WSS
- Не делает health-check upstream — если chromedriver упадёт, релей вернёт 502
- Однопоточный на запрос (ThreadingHTTPServer — поток на запрос)
- Таймаут upstream соединения 600 сек (жёстко в коде)
- Не фильтрует путь — проксирует всё на upstream

## Связи
- Вызывается: `start-chromedriver-wsl.sh` (после запуска chromedriver), вручную
- Зависит от: запущенного chromedriver на `upstream-port`
- Результат потребляет: Codeception в Docker (подключается к `host.docker.internal:9515` → релей → chromedriver:9516)
- Связанные: `start-chromedriver-wsl.sh`, `browser-verify` SKILL.md, `.doc/qa/browser-setup.md`

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода