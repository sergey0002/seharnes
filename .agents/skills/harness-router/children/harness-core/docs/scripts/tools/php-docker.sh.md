# Скрипт: `.tools/scripts/php-docker.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, php, docker, bash, path-translation]
-->

## Суть
Bash-враппер для запуска PHP CLI внутри Docker-контейнера приложения. Пытается использовать Node.js-враппер (`php-docker.js`) для корректной трансляции путей, иначе фоллбечит на нативный `docker exec` с ручной трансляцией путей `<repo_root>/...` → `/var/www/html/...`.

## Когда запускать
- При необходимости выполнить PHP-скрипт/команду в окружении контейнера
- Из любых сред (Linux, WSL, Git-Bash) — универсальный вход
- Автоматически выбирает Node.js или нативный docker

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `[php args...]` | string[] | да | — | Аргументы для `php` внутри контейнера (пути транслируются) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | PHP выполнен успешно | — |
| 1 | Ошибка выполнения PHP / контейнер недоступен | Проверить Docker и контейнер |
| 127 | Node.js не найден (фоллбек на нативный) | Внутренний фоллбек, не ошибка |

## Что читает и что пишет
- **Читает**: `DOCKER_PHP_CONTAINER` (default: `copytrust-dev-php-apache-1`), репозиторий корень
- **Пишет**: stdout/stderr PHP процесса в контейнере

## Побочные эффекты
- Запускает `docker exec -i <container> php <translated_args>`
- Транслирует пути репозитория в `/var/www/html/...`

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `DOCKER_PHP_CONTAINER` | Имя контейнера с PHP (default: `copytrust-dev-php-apache-1`) |
| `Node.js` | Опционально — для `php-docker.js` (лучше транслирует пути) |

## Примеры
```bash
# Синтаксическая проверка
bash .tools/scripts/php-docker.sh -l admin/lib/Objects/Item/AdminItemController.php

# Запуск скрипта
bash .tools/scripts/php-docker.sh script.php arg1 arg2

# Инлайн код
bash .tools/scripts/php-docker.sh -r 'echo "hello";'
```

## Ограничения
- Требует запущенного Docker контейнера
- Пути вне репозитория не транслируются
- Фоллбек на нативный docker exec если Node.js недоступен

## Связи
- Node.js версия: `php-docker.js` (лучшая трансляция путей)
- PowerShell: `php-docker.ps1`
- Windows cmd: `php-docker.cmd` → `php-docker.js`
- Контейнер: `.tools/docker-dev/php-apache` / `.tools/docker-test`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)