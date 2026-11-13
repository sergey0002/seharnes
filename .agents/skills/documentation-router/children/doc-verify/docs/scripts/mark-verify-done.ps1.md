# Скрипт: `.agents/skills/documentation-router/children/doc-verify/scripts/mark-verify-done.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, mark-verify-done]
-->

## Суть
Помечает архитектурный документ как сверенный (status=verified) или пропущенный (status=skipped) в реестре `.doc/architecture/_map/verify-registry.tsv`. Записывает дату сверки, число исправленных issues и опциональную заметку. Используется на шаге 5 скила `doc-verify` после завершения сверки документа с кодом.

## Когда запускать
После ручной или агентской сверки документа из батча, полученного `get-verify-batch.ps1`. Обязателен для закрытия цикла doc-verify: без отметки документ останется в pending и будет выдаваться снова. Если документ не требует сверки (навигация, index.md) — использовать `-Skip`.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Path |  | string | да |  | Имя файла или относительный путь: `payments.md` / `orders.md` |
| -Issues |  | int | нет | 0 | Сколько несоответствий исправлено (число). 0 = расхождений не было |
| -Skip |  | switch | нет |  | Пропустить документ без сверки (status=skipped) |
| -Notes |  | string | нет | '' | Короткая заметка в реестр (например, причину skip) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех, документ отмечен | Продолжить работу |
| 1 | Реестр не найден или документ не найден в реестре | Запустить get-verify-batch.ps1 -Init, проверить имя |

## Что читает и что пишет
**Читает:**
- `.doc/architecture/_map/verify-registry.tsv` — реестр сверки

**Пишет:**
- `.doc/architecture/_map/verify-registry.tsv` — обновлённая строка документа (status, verified_at, issues_found, notes)

## Побочные эффекты
- Обновляет реестр сверки (TSV).

## Окружение и зависимости
- Использует `_lib.ps1` из `project-doc/scripts/`: `Normalize-RelativePath`, `Write-Utf8File`.
- Не требует внешних зависимостей.

## Примеры
```powershell
# Документ сверен, исправлено 2 несоответствия
powershell .agents/skills/documentation-router/children/doc-verify/scripts/mark-verify-done.ps1 -Path payments.md -Issues 2

# Документ пропущен (навигация), с заметкой
powershell .agents/skills/documentation-router/children/doc-verify/scripts/mark-verify-done.ps1 -Path index.md -Skip -Notes "nav only"
```

Вывод:
```
OK: payments.md -> verified (issues=2)
```

## Ограничения
- Не проверяет, действительно ли была выполнена сверка — доверяет вызывающему.
- Не создаёт запись, если документа нет в реестре (нужен предварительный `-Init`).
- Поиск в реестре нечёткий: совпадает по полному пути, имени файла или leaf имени.

## Связи
- Вызывается: `doc-verify` (шаг 5), агент вручную после сверки
- Зависит от: `get-verify-batch.ps1` (создаёт реестр и батч)
- Результат используется: прогресс-бар в `get-verify-batch.ps1 -Status`, отчётность doc-verify

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)