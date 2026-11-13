# Скрипт: `.tools/scripts/multi-search.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, .cursor/rules/batch-calls.mdc]
tags: [harness, script, multi-search, powershell, wrapper, wsl, rg]
-->

## Суть
Тонкая PowerShell-обёртка для `multi-search.sh` — форвардит аргументы в bash-скрипт под WSL/Git-Bash. Если bash/wsl недоступны — фоллбечит на прямой `rg` (ripgrep) с предупреждением, что поддерживается только single-pattern поиск. Обеспечивает единый вход для Windows-сред в пакетный поиск.

## Когда запускать
- Из Windows-сред (Cursor native, Codex, PowerShell) когда нужен `multi-search.sh`
- Автоматически вызывается агентами вместо прямого вызова bash

## Аргументы
| Аргумент | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|
| `-Args` (ValueFromRemainingArguments) | string[] | да | — | Все аргументы пробрасываются в `multi-search.sh` или `rg` |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Поиск завершён | Результаты в stdout |
| 1 | Ошибка поиска | Проверить аргументы |
| 2 | bash/wsl/rg не найдены | Установить WSL, Git-Bash или ripgrep |

## Что читает и что пишет
- **Читает**: ничего сам; делегирует `multi-search.sh` или `rg`
- **Пишет**: stdout/stderr от делегированной команды

## Побочные эффекты
- Запускает bash/wsl или rg процесс

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| `bash` или `wsl` | Для полнофункционального `multi-search.sh` |
| `rg` (ripgrep) | Фоллбек при отсутствии bash/wsl |

## Примеры
```powershell
# Пакетный поиск через multi-search.sh (предпочтительно)
.cursor\scripts\multi-search.ps1 --root .doc/tasks --pattern "2233" --pattern "Yandex" --include "task.md" --include "doc.md"

# Фоллбек на rg (только один паттерн)
.cursor\scripts\multi-search.ps1 "search-term"
```

## Ограничения
- Фоллбек на `rg` поддерживает только single-pattern поиск
- Полные фичи (multi-pattern, --include, --root) только через `multi-search.sh` в bash/wsl
- Не поддерживает прямые Windows-пути в паттернах (нужен bash/wsl)

## Связи
- Основной скрипт: `multi-search.sh` (canon)
- Документация: `.cursor/rules/batch-calls.mdc`, `.doc/harnes/plan/massgrep.md`
- Используется в: правиле `batch-calls` для пакетных поисков

## История изменений
- 2026-11-07: документация заполнена из кода (status: actual)

## Аргументы (аудит: 2 колонки)
| Аргумент | Описание |
|---|---|
| `-Args` | Все аргументы пробрасываются в `multi-search.sh` или `rg` (ValueFromRemainingArguments) |