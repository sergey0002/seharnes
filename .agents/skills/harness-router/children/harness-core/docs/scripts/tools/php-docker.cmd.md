# Скрипт: `.tools/scripts/php-docker.cmd`

<!-- meta
type: script
status: actual
argv: passthrough
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, php, docker, windows, cmd, nodejs]
-->

## Суть
Windows CMD-лаунчер для `php-docker.js` (Node.js). Находит Node.js (`%ProgramFiles%\nodejs\node.exe` → `%LocalAppData%\Programs\node\node.exe` → `node` в PATH) и запускает JS-враппер, который транслирует пути и делает `docker exec`.

## Когда запускать
- В cmd.exe, Windows Terminal (cmd профиль), старых скриптах .bat
- Когда нужен PHP в контейнере из нативного Windows окружения

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `%*` (все аргументы) | string[] | да | — | Пробрасываются в `php-docker.js` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | PHP выполнен успешно | — |
| 1 | Node.js не найден / Docker ошибка | Установить Node.js и/или Docker |

## Что читает и что пишет
- **Читает**: путь к Node.js, `php-docker.js` рядом с этим скриптом
- **Пишет**: stdout/stderr от Node.js скрипта

## Побочные эффекты
- Запускает Node.js процесс
- Делегирует всё в `php-docker.js`

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `NODE` (внутренняя) | Путь к node.exe (автопоиск) |
| `Node.js` | Должен быть установлен |
| `Docker` | Контейнер должен быть запущен |

## Примеры
```cmd
REM Проверка синтаксиса
.cursor\scripts\php-docker.cmd -l admin\lib\Objects\Item\AdminItemController.php
```

## Ограничения
- Только Windows cmd.exe
- Зависит от `php-docker.js` (Node.js)
- Не делает трансляцию путей сам — делегирует в JS

## Связи
- Node.js версия: `php-docker.js` (основная логика)
- Bash: `php-docker.sh` (универсальная)
- PowerShell: `php-docker.ps1`
- Контейнер: `.tools/docker-dev/php-apache` / `.tools/docker-test`

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)