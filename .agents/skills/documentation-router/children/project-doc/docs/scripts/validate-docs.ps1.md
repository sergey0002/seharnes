# Скрипт: `.agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, validate-docs]
-->

## Суть
Валидация архитектурной документации: проверяет meta-блок (наличие полей type, status, updated; валидность значений), обязательные секции (## Суть, ## Связи — для всех; дополнительно ## Известные проблемы и ограничения, ## История изменений — для не-index), сломанные локальные ссылки (игнорирует кодовые блоки и инлайн-код). Поддерживает точечную проверку по пути/маске (`-Path`, `-Mask`) и режим `-Fix` (пока не реализован, зарезервирован). Выводит сводку: ошибки, предупреждения, OK. Exit code: 1 если есть ошибки, 0 если всё чисто.

## Когда запускать
- В CI/пре-коммите для документации.
- После генерации/правки архитектурных документов.
- При команде «валидируй доки» / «проверь архитектуру».
- Агент запускает после записи/обновления architecture/*.md.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| -Fix |  | switch | нет |  | (Зарезервировано) Автоисправление найденных проблем |
| -Path |  | string | нет | '' | Путь к файлу/папке для проверки (поддерживает wildcard) |
| -Mask |  | string | нет | '*.md' | Маска файлов при проверке папки |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Нет ошибок (warnings допускаются) | Успех |
| 1 | Есть ошибки (meta, секции, ссылки) | Исправить документы |

## Что читает и что пишет
**Читает:**
- `.doc/architecture/*.md` — архитектурные документы (фильтрует: не `_map/`, не `_*`, не служебные task/test/report/plan/readme/audit)
- Meta-блок (`Get-DocMeta`), H1 (`Get-DocFirstHeading`), ссылки (regex по markdown)

**Пишет:**
- Ничего (только stdout: таблица результатов).

## Побочные эффекты
- Нет побочных эффектов (read-only; `-Fix` не реализован).

## Окружение и зависимости
- Использует `_lib.ps1`: `Get-RelativePath`, `Read-TextFile`, `Get-DocMeta`, `Get-DocFirstHeading`, `Normalize-RelativePath`.
- `git` — не требуется.

## Примеры
```powershell
# Полная валидация всех architecture/*.md
powershell .agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1

# Проверить конкретный документ
powershell .agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1 -Path architecture/orders.md

# Проверить папку с маской
powershell .agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1 -Path architecture/payments -Mask "*.md"

# Режим исправления (пока не реализован)
powershell .agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1 -Fix
```

Вывод:
```
═══════════════════════════════════════
  РЕЗУЛЬТАТЫ ВАЛИДАЦИИ
═══════════════════════════════════════

❌ Ошибки (3)
  ❌ architecture/payments.md — meta: нет поля 'status:'
  ❌ architecture/api/webhooks.md — нет секции '## История изменений'
  ❌ architecture/orders.md — сломанная ссылка: ../architecture/payments.md

⚠️  Предупреждения (2)
  ⚠️  architecture/legacy.md — meta: неизвестный status 'deprecated'
  ⚠️  architecture/index.md — meta: неизвестный type 'navigation'

✅ OK (15)
  ✅ architecture/index.md
  ✅ architecture/orders.md
  ...

Итого: 20 файлов | ❌ 3 | ⚠️ 2 | ✅ 15
```

## Ограничения
- Проверяет только `.md` в `.doc/architecture/` (с исключениями для служебных файлов задач/тестов/планов).
- Валидные `status`: actual, outdated, draft, frozen.
- Валидные `type`: architecture, rules, api, model, flow, config, index.
- `updated` должен быть в формате `YYYY-MM-DD`.
- Ссылки проверяются только локальные (`./`, `../` к `.md`); внешние и якоря игнорируются.
- Кодовые блоки (```) и инлайн-код (` `) исключаются из проверки ссылок.
- `-Fix` не реализован — только отчёт.

## Связи
- Вызывается: CI, агент вручную, после генерации docs
- Зависит от: `_lib.ps1`, структуры `.doc/architecture/`
- Результат используется: блокировка коммита при ошибках, список для исправления

## История изменений
- 2026-11-07: полная документация на основе кода (status: actual)