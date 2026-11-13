# Скрипт: `.tools/scripts/multi-exec.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .doc/harnes/plan/massgrep.md]
tags: [harness, script, multi-exec, powershell, wrapper, wsl]
-->

## Суть
Тонкая PowerShell-обёртка для `multi-exec.sh` — форвардит все аргументы в bash-скрипт под WSL или Git-Bash. Обеспечивает единый вход для Windows-сред (Cursor native, Codex, Kilo) в пакетный исполнитель команд и чтений.

## Когда запускать
- Из Windows-сред (Cursor native, Codex, PowerShell) когда нужен `multi-exec.sh`
- Автоматически вызывается агентами вместо прямого вызова bash

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `-Args` (ValueFromRemainingArguments) | string[] | да | — | Все аргументы пробрасываются в `multi-exec.sh` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (все команды/чтения ok) | Результат в JSON-lines на stdout |
| 1 | Хотя бы одна команда упала | JSON содержит exit codes |
| 2 | bash/wsl не найден | Установить WSL или Git-Bash |

## Что читает и что пишет
- **Читает**: ничего сам; делегирует `multi-exec.sh`
- **Пишет**: stdout/stderr от `multi-exec.sh` (JSON-lines)

## Побочные эффекты
- Запускает bash/wsl процесс
- Пробрасывает все побочные эффекты `multi-exec.sh`

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `bash` или `wsl` | Должен быть в PATH (WSL предпочтительнее) |

## Примеры
```powershell
# Пакетное чтение 4 файлов задачи
.cursor\scripts\multi-exec.ps1 --read "id=a :: .doc/tasks/123/task.md +1 100" --read "id=b :: .doc/tasks/123/doc.md +1 100" --read "id=c :: .doc/tasks/123/diff.files.md +1 50" --read "id=d :: .doc/tasks/123/plan.md +1 200"

# Пакетные команды
.cursor\scripts\multi-exec.ps1 --cmd "id=x :: php -l file1.php" --cmd "id=y :: php -l file2.php" --mode parallel
```

## Ограничения
- Только форвардер — вся логика в `multi-exec.sh`
- Требует WSL (`bash` через `wsl`) или Git-Bash (`bash.exe`)
- Не поддерживает прямые Windows-команды (только через bash)

## Связи
- Основной скрипт: `multi-exec.sh` (canon)
- Документация: `.doc/harnes/plan/massgrep.md` раздел 5, `.doc/harnes/state/15-mcp-stack.md`
- Используется в: `batch-calls.mdc` правило пакетных вызовов

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)

## Аргументы (аудит: 2 колонки)
| Аргумент | Описание |
|---|---|
| `-Args` | Все аргументы пробрасываются в `multi-exec.sh` (ValueFromRemainingArguments) |