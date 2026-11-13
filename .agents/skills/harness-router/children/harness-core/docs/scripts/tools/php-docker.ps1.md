# Скрипт: `.tools/scripts/php-docker.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, php, docker, powershell, path-translation]
-->

## Суть
PowerShell-враппер для запуска PHP CLI внутри Docker-контейнера приложения. Транслирует Windows-пути в Linux-пути контейнера (`/var/www/html/...`). Используется в PowerShell/Windows Terminal вместо bash-скриптов.

## Когда запускать
- Из PowerShell, Windows Terminal, Codex/PowerShell
- При необходимости выполнить PHP в контейнере из Windows-среды

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `-Args` (ValueFromRemainingArguments) | string[] | да | — | Аргументы для `php` внутри контейнера (пути транслируются) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | PHP выполнен успешно | — |
| 1 | Ошибка Docker / контейнер недоступен | Проверить Docker |

## Что читает и что пишет
- **Читает**: `$env:DOCKER_PHP_CONTAINER` (default: `copytrust-dev-php-apache-1`), текущий репозиторий
- **Пишет**: stdout/stderr от `docker exec`

## Побочные эффекты
- Запускает `docker exec -i <container> php @translated`
- Транслирует пути: `<repo_root>\...` → `/var/www/html/...`

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `DOCKER_PHP_CONTAINER` | Имя контейнера (default: `copytrust-dev-php-apache-1`) |
| `Docker` | Должен быть доступен в PATH |

## Примеры
```powershell
# Проверка синтаксиса
.cursor\scripts\php-docker.ps1 -l admin\lib\Objects\Item\AdminItemController.php

# Запуск скрипта
.cursor\scripts\php-docker.ps1 script.php arg1 arg2
```

## Ограничения
- Только PowerShell 5.1+
- Требует Docker Desktop / Docker Engine
- Пути вне репозитория передаются как есть

## Связи
- Bash версия: `php-docker.sh` (универсальная)
- Node.js версия: `php-docker.js` (через node)
- Windows cmd: `php-docker.cmd` → `php-docker.js`
- Контейнер: `.tools/docker-dev/php-apache` / `.tools/docker-test`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)

## Аргументы (аудит: 2 колонки)
| Аргумент | Описание |
|---|---|
| `-Args` | Аргументы для `php` внутри контейнера (пути транслируются) |