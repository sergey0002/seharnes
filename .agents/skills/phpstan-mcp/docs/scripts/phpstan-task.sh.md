# Скрипт: `.agents/skills/phpstan-mcp/scripts/phpstan-task.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/mcp/phpstan-mcp.md, .doc/harnes/tests.md]
tags: [harness, script, phpstan, task, static-analysis, docker]
-->

## Суть
Запускает PHPStan только по файлам, изменённым в задаче. Собирает список файлов из `.doc/tasks/{N}/diff.files.md`, git diff (незакоммиченные), git staged и untracked. Фильтрует только `.php`, исключает `vendor/`, `node_modules/`, `templates_c/`, `.tools/`, `.kilo/`, `.cursor/`, `.git/`. Дедуплицирует и запускает `phpstan-docker.sh analyze` с конфигом проекта и заданным уровнем.

## Когда запускать
- После реализации задачи для проверки типов только в затронутых файлах
- В pre-push / pre-commit хуках (по задаче)
- Вместо полного PHPStan для скорости

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `<task-number>` | integer | да | авто из ветки (features/#N / bugfixes/#N) | Номер задачи Jira (CT-N) |
| `[level]` | integer | нет | 0 | Уровень PHPStan (0–9) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Анализ пройден / нет PHP файлов в задаче | — |
| 1 | PHPStan нашёл ошибки | Исправить код в указанных файлах |
| 2 | Неверный номер задачи / не число | Проверить синтаксис: `phpstan-task.sh <task-number> [level]` |

## Что читает и что пишет
- **Читает**: `.doc/tasks/{N}/diff.files.md`, `git diff`, `git diff --cached`, `git ls-files --others`, ветку git
- **Пишет**: список файлов в stderr, вывод PHPStan в stdout/stderr

## Побочные эффекты
- Запускает Docker контейнер через `phpstan-docker.sh`
- Может авто-собрать образ приложения

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `PHPSTAN_DOCKER_IMAGE` | Образ (default: `copytrust-dev-php-apache:latest`) |
| `PHPSTAN_MEMORY_LIMIT` | Memory limit (default: `1G`) |
| `PHPSTAN_AUTO_BUILD` | Автосборка образа (default: `1`) |

## Примеры
```bash
# Явный номер задачи и уровень
bash .agents/skills/phpstan-mcp/scripts/phpstan-task.sh 2606 5

# Автоопределение из ветки (features/#2606 или bugfixes/#2606)
bash .agents/skills/phpstan-mcp/scripts/phpstan-task.sh

# Только уровень 0 (быстрый)
bash .agents/skills/phpstan-mcp/scripts/phpstan-task.sh 2606 0
```

## Ограничения
- Работает только если задача оформлена по правилам (ветка содержит #N, diff.files.md существует)
- Не анализирует файлы вне diff задачи
- Требует Docker и PHPStan phar в `.cursor/tools/vendor/`
- Уровень 0 по умолчанию — только базовые ошибки; для глубокой проверки используйте 5+

## Связи
- Базовый запуск: `phpstan-docker.sh`
- Конфиг: `.cursor/tools/phpstan.neon`
- MCP: `phpstan-mcp` (аналогичный анализ через MCP)
- Документация: `.doc/harnes/mcp/phpstan-mcp.md`, `.doc/harnes/tests.md`, `.doc/harnes/state/15-mcp-stack.md`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)