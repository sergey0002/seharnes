# MCP setup — testdeploydocker (copytrust)

Portable kit в [`.codex/`](./README.md). Для этого репозитория БД и PHP идут через **Docker** (`.tools/docker-dev`).

## Быстрый старт

```powershell
# 1. Docker dev (если ещё не поднят)
cd .tools\docker-dev
copy .env.dist .env   # если нет .env
docker compose up -d mysql php-apache

# 2. MCP toolchain
cd ..\..
.\.codex\setup.ps1

# 3. Полный перезапуск Cursor → Settings → MCP
```

## MySQL MCP

| Параметр | Значение |
|----------|----------|
| Хост | `127.0.0.1` |
| Порт | **8031** (проброс из `.tools/docker-dev/.env`) |
| БД | `gb_copydev5` (= `MYSQL_DATABASE` в `.tools/docker-dev/.env`) |
| Пользователь | `user` / `password` |
| HTTP app | `http://localhost:8030` (тот же compose `php-apache`) |

Файл: [`.codex/mcp.env`](./mcp.env) (не в git). При смене `MYSQL_PORT` / `MYSQL_DATABASE` в `.tools/docker-dev/.env` обновите `mcp.env`.

Запуск MCP: `npx -y @f4ww4z/mcp-mysql-server` + `envFile: .codex/mcp.env` (включая `MYSQL_PORT`).

Проверка:

```bash
docker exec copytrust-dev-mysql-1 mysql -u user -ppassword -e "SHOW TABLES" gb_copydev5
```

## PHP MCP (phpstan, php-deps)

На Windows PHP в PATH часто нет — kit использует обёртку [`.codex/scripts/php-docker.cmd`](./scripts/php-docker.cmd) (`PHP_BIN` в `mcp.env`). Контейнер: `copytrust-dev-php-apache-1`.

Установка PHPStan/phpda в kit:

```powershell
cd .tools\docker-dev
docker compose run --rm php7.1-cli bash -c "cd /var/www/html/.codex/tools && curl -sS https://getcomposer.org/installer | php && php composer.phar install --no-interaction --ignore-platform-reqs"
```

## Smoke-test MCP

```powershell
node .codex\scripts\test-mcp-servers.mjs
```

## Требования

- Node.js (`npx`), [uv](https://docs.astral.sh/uv/) (`uvx`)
- Docker Desktop + запущенный `copytrust-dev`
- **codebase-memory-mcp** (UI-вариант):
  - Windows: `codebase-memory-mcp.exe` в `%LOCALAPPDATA%\Programs\codebase-memory-mcp\`
  - WSL/Linux: `~/.local/bin/codebase-memory-mcp` (`codebase-memory-mcp-ui-linux-amd64`), **tmux** для UI :9749

Подробности: [правило CBM](rules/mcp-codebase-memory.md) и [документация сервера](../.doc/harnes/mcp/codebase-memory-mcp.md), серверы: [`.codex/README.md`](README.md).
