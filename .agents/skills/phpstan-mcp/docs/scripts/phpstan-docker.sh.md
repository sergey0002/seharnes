# Скрипт: `.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/phpstan-mcp.md]
tags: [harness, script, phpstan, docker, static-analysis]
-->

## Суть
Запускает PHPStan статический анализ в Docker-контейнере с образом приложения (`copytrust-dev-php-apache:latest`). Монтирует корень проекта в `/app`, использует PHPStan phar из `.cursor/tools/vendor/phpstan/phpstan/phpstan.phar` с конфигом `.cursor/tools/phpstan.neon` (PHP 7.1, level 0 по умолчанию). Авто-собирает образ если отсутствует и `PHPSTAN_AUTO_BUILD=1`.

## Когда запускать
- После правок PHP для проверки типов, аргументов, сигнатур
- По номеру задачи (`phpstan-task.sh`) или явными путями
- В CI/пре-коммит (при наличии Docker)

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `analyze` | command | да | — | Подкоманда PHPStan |
| `-c <config>` | string | нет | `/app/.cursor/tools/phpstan.neon` | Конфиг PHPStan |
| `--level <n>` | integer | нет | 0 | Уровень строгости (0–9) |
| `--no-progress` | flag | нет | — | Отключить прогресс-бар |
| `--error-format=raw` | string | нет | — | Формат ошибок |
| `[paths...]` | string[] | нет | — | Файлы/директории для анализа |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Анализ пройден без ошибок | — |
| 1 | PHPStan нашёл ошибки | Исправить код |
| 2 | Образ не найден / phar не найден / docker недоступен | Построить образ или установить Docker |

## Что читает и что пишет
- **Читает**: PHP файлы проекта (монтируются в `/app`), `.cursor/tools/phpstan.neon`, PHPStan phar
- **Пишет**: Отчёт PHPStan в stdout/stderr (raw format)

## Побочные эффекты
- Запускает Docker контейнер (`docker run --rm`)
- Может авто-собрать образ (`docker build`) если `PHPSTAN_AUTO_BUILD=1` и образ отсутствует
- Использует память контейнера (лимит `PHPSTAN_MEMORY_LIMIT`, default 1G)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `PHPSTAN_DOCKER_IMAGE` | Образ для запуска (default: `copytrust-dev-php-apache:latest`) |
| `PHPSTAN_MEMORY_LIMIT` | PHP memory_limit внутри контейнера (default: `1G`) |
| `PHPSTAN_AUTO_BUILD` | `1` — автосборка образа при отсутствии (default: `1`) |
| `Docker` | Должен быть установлен и доступен |

## Примеры
```bash
# Анализ конкретных файлов уровня 5
bash .agents/skills/phpstan-mcp/scripts/phpstan-docker.sh analyze --level=5 src/Module/Class.php

# Анализ файлов задачи через phpstan-task.sh (рекомендуемый способ)
bash .agents/skills/phpstan-mcp/scripts/phpstan-task.sh 2606 5
```

## Ограничения
- Требует Docker и образа приложения
- PHPStan phar должен быть в `.cursor/tools/vendor/phpstan/phpstan/phpstan.phar` (composer install в `.cursor/tools`)
- Конфиг заточен под PHP 7.1 (`phpVersion: 70100` в phpstan.neon)
- Не работает без Docker (нет хост-параллели для PHP 7.1)

## Связи
- Task-обёртка: `phpstan-task.sh` (собирает файлы по задаче)
- Конфиг: `.cursor/tools/phpstan.neon`
- MCP: `phpstan-mcp` (анализ через MCP)
- Документация: `.doc/harnes/mcp/phpstan-mcp.md`, `.doc/harnes/tests.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)