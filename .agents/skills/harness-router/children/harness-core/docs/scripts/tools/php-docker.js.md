# Скрипт: `.tools/scripts/php-docker.js`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, php, docker, nodejs, path-translation]
-->

## Суть
Node.js враппер для запуска PHP CLI внутри Docker-контейнера приложения. Транслирует Windows/WSL пути в Linux-пути контейнера (`/var/www/html/...`). Используется когда нужен PHP внутри контейнера, но вызов происходит с хоста (в т.ч. из Windows).

## Когда запускать
- При необходимости выполнить PHP-скрипт/команду в окружении контейнера
- Из Windows-сред (Cursor native, Codex) через `php-docker.cmd` → этот скрипт
- Автоматически вызывается `php-docker.sh` если Node.js доступен

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `[php args...]` | string[] | да | — | Аргументы для `php` внутри контейнера (пути транслируются) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | PHP выполнен успешно | — |
| 1 | Ошибка выполнения PHP / контейнер недоступен | Проверить Docker и контейнер |

## Что читает и что пишет
- **Читает**: переменную `DOCKER_PHP_CONTAINER` (default: `copytrust-dev-php-apache-1`), пути аргументов
- **Пишет**: stdout/stderr PHP процесса в контейнере (inherit)

## Побочные эффекты
- Запускает `docker exec -i <container> php <translated_args>`
- Транслирует пути: `<repo_root>/...` → `/var/www/html/...`

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `DOCKER_PHP_CONTAINER` | Имя контейнера с PHP (default: `copytrust-dev-php-apache-1`) |
| `Node.js` | Для запуска этого скрипта |

## Примеры
```bash
# Через php-docker.sh (автовыбор node/sh)
php-docker.sh -l file.php
php-docker.sh -r 'echo "test";'

# Прямой вызов (если нужен node)
node .tools/scripts/php-docker.js -l /path/to/file.php
```

## Ограничения
- Работает только если Docker контейнер запущен и доступен
- Транслирует только пути внутри репозитория; абсолютные пути вне репо — как есть
- Нужен Node.js (ES modules, `import` syntax)

## Связи
- Bash-враппер: `php-docker.sh` (автовыбор node или нативный docker exec)
- PowerShell: `php-docker.ps1`
- Windows cmd: `php-docker.cmd` → этот скрипт через node
- Контейнер: `.tools/docker-dev/php-apache` / `.tools/docker-test`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)