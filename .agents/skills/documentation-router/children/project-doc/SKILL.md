---
name: project-doc
description: >-
  Документирование проекта: инициализация, анализ карты, документирование
  разделов с продолжением с места остановки, аудит, валидация, синхронизация.
  Экономия токенов через скрипты-коллекторы. Use when the user says
  задокументируй проект, проанализируй карту проекта, задокументируй раздел,
  проанализируй аудит, продолжи индексацию, продолжи документирование,
  resume indexing, bootstrap documentation, document section,
  исправь ошибки валидации, обнови устаревшие документы.
---

# Project Doc — Документирование проекта

---

## Шаг P0 — Обязательное чтение

Прочитай [`.doc/harnes/doc_rules.md`](../../../.doc/harnes/doc_rules.md) перед любой записью в `.doc/`.

---

## Шаг P1 — ПРОВЕРКА ОЧЕРЕДИ

Новая система использует единую Очередь `file-registry.tsv`. 
Чтобы начать или продолжить индексацию, переходи к секции "ИНДЕКСАЦИЯ И ДОКУМЕНТИРОВАНИЕ (Batching)".

---

## Активация

| Команда | Режим |
|---------|-------|
| «задокументируй проект» / «bootstrap documentation» | → [INIT](#init) |
| «проанализируй карту проекта» + вывод скрипта | → [MAP](#map) |
| «задокументируй раздел [name]» | → [SECTION](#section) |
| «продолжи индексацию» / «продолжи документирование» | → [P1 → SECTION](#шаг-p1--проверка-состояния) |
| «проанализируй аудит» + вывод | → [AUDIT](#audit) |
| «исправь ошибки валидации» + вывод | → [VALIDATE](#validate) |
| «обнови устаревшие документы» + вывод | → [SYNC](#sync) |
| «сверка документации» / «продолжи сверку» | → скил [doc-verify](../doc-verify/SKILL.md) |

**При MAP и SECTION** — обязательно используй [codebase-memory-mcp (CBM)](#codebase-memory-mcp-cbm-при-индексации), если MCP доступен.

---

## INIT

Используется для новых проектов (нет `index.md` и `_priority.md`).

### I1 — Задай вопросы

```
📋 Создаю систему документации. Ответь:

1. Название проекта?
2. Стек: backend / frontend / БД / деплой?
3. Главные папки и их назначение?
4. Самые сложные или часто меняемые части?
5. Есть готовая документация? Где?
```

### I2 — Создай структуру

1. `.doc/architecture/index.md` — с callout `> ⚠️ Правила: [doc_rules.md](../../../.doc/harnes/doc_rules.md)`
2. `.doc/architecture/_context-base.md` — стек, соглашения, структура
3. `.doc/architecture/_priority.md` — матрица приоритетов (пустая)

### I3 — Инструкция

```
✅ Готово.

Следующий шаг:
  powershell .agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1

Скинь вывод → "проанализируй карту проекта"
```

---

## MAP

Когда пользователь скидывает вывод `map-project.ps1`.

### M1 — Анализируй ТОЛЬКО по выводу скрипта

Не читай файлы проекта самостоятельно.

**Дополнение через CBM (если MCP доступен):** после M1 вызови [CBM — обзор перед MAP](#cbm--обзор-перед-map) —
hotspots и routes из графа **уточняют** приоритеты из hot-files.txt, не заменяют скрипт.

```
Используй:
  hot-files.txt              → активные модули (кандидаты 🔴A)
  tree.txt                   → структура папок
  file-registry.tsv          → путь, kind, domain, ссылки на architecture-доки
  procedural-php-files.txt   → PHP без классов: entrypoints, cron, admin, legacy
  php-metrics.txt            → loc/classes/functions по PHP
  js-metrics.txt             → loc/functions по JS/TS
  tpl-metrics.txt            → loc по шаблонам
  css-metrics.txt            → loc/classes по стилям
  js-files.txt               → полный список JS/TS
  vue-files.txt              → список Vue-компонентов
  tpl-files.txt              → Smarty / шаблоны
  css-files.txt              → стили
```

`procedural-php-files.txt` содержит PHP-файлы с нулём объявлений `class`, `interface` и `trait`. Метрики считаются по объявлениям в начале строки: методы класса попадают в `functions` того же файла.

Во всех метриках есть колонка `scope`: `app` или `vendor`. `vendor` ставится по пути из [M1.1](#m11--правило-отделения-app-кода-от-vendorminified-шума), а также для `dompdf/`, `*.min.js`, `*.min.css` и `*/phone-codes/*`. Сортировка сначала по `scope`, затем по `loc` по убыванию: первыми идут крупные файлы app-кода.

### M1.1 — Правило отделения app-кода от vendor/minified шума

Для legacy JS агент ОБЯЗАН сначала классифицировать файлы по путям и только потом делать выводы по модулю.

Приоритет классификации:
1. `vendor` по пути:
   - `scripts/plugins/`
   - `admin/scripts/plugins/`
   - `vendor/`
   - `node_modules/`
2. `app` по пути:
   - `scripts/module/`
   - `scripts/services/`
   - `scripts/stores/`
   - `frontend/entry/src/`
   - `admin/scripts/`, кроме `admin/scripts/plugins/`
3. `minified/noise` по имени:
   - `*.min.js`
   - `*.bundle.js`
   - сжатые файлы библиотек
4. Всё спорное — `unknown`, не смешивать автоматически с app-кодом.

Правила интерпретации:
- Не предлагай документировать vendor/minified как бизнес-модуль.
- Не повышай приоритет раздела только из-за активности vendor-файлов.
- В отчёте отдельно указывай:
  - `legacy-js app`
  - `legacy-js vendor`
  - `legacy-js unknown`
- Если карта ещё не разделила файлы физически, агент всё равно обязан мысленно отфильтровать vendor по путям.

### M2 — Заполни `_priority.md`

```
Активное + Сложное  → 🔴 A  (документировать подробно)
Редкое + Сложное    → 🔴 A  (архитектурные решения)
Активное + Простое  → 🟡 Б  (кратко)
Редкое + Простое    → 🟢 В  (пропустить)
```

Спроси перед записью: «Записать `_priority.md`? (да / нет)»

При добавлении заглушек в `index.md` (M4) — для каждого раздела **сначала Index Gate**:
не добавляй строку на `order.md`, если уже есть `orders.md`; используй каноническое имя из index.

### M3 — Стартуй batch-индексацию

После подтверждения `_priority.md` скажи пользователю:

```
Готово к индексации.

  1. Проверь прогресс:    powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Status
  2. Получи первый батч:  powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Count 15
  3. Скажи: «продолжи индексацию»
```

### M4 — Отчёт

```
✅ Карта проанализирована

Модулей найдено: N
🔴A (документировать подробно): payments, auth, orders
🟡Б (кратко): tariffs, s3, email

_priority.md записан.
index.md обновлён (заглушки).

Далее:
  1. powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Status
  2. powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Count 15
  3. «продолжи индексацию»
```

---

## ИНДЕКСАЦИЯ И ДОКУМЕНТИРОВАНИЕ (Batching)

См. [references/indexing.md](references/indexing.md).

## AUDIT

Когда пользователь скидывает вывод `audit-docs.ps1`:

### A1 — Исправь сломанные ссылки сразу (без вопросов)

### A2 — Сформируй план

```
📊 Аудит проанализирован

🔴 Исправлено сразу: сломанных ссылок N
🟡 Требует внимания:
  • Устаревших документов: N
  • Файлов без документации: N
  • Документов без meta: N

Предлагаю:
  1. [файл/раздел] — N изм. за 30 дней
  2. [файл/раздел]

Начать с первого? (да / нет / выбери)
```

---

## VALIDATE

Когда пользователь скидывает вывод `validate-docs.ps1`:

1. **Ошибки (❌)** — исправь, предварительно спросив подтверждение одним AskQuestion со списком
2. **Предупреждения (⚠️)** — предложи план, не исправляй без запроса
3. После исправлений скажи: «Запусти `validate-docs.ps1` снова для проверки»

---

## SYNC

Когда пользователь скидывает вывод `sync-docs.ps1`:

Для каждого устаревшего документа:
1. Читай **только** изменившиеся секции (по именам файлов из вывода скрипта)
2. Прочитай только соответствующие части `.md` документа (не целиком)
3. Обнови секцию, добавь `<!-- updated: {date}, sync -->` к изменённой секции
4. Обнови `updated:` в meta и `## История изменений`
5. Спрашивай подтверждение перед каждым документом

```
🔄 Обновляю payments.md

Изменился: PaymentService.php (3 изм. после 2025-01-01)
Буду читать: только PaymentService.php секцию логики оплаты
Затронутая секция: ## Как устроено → Оплата с баланса

Обновить? (да / нет / пропустить всё)
```

---

## Codebase-memory-mcp (CBM) при индексации

См. [references/cbm.md](references/cbm.md).

## Правила экономии токенов

```
✓ Скрипты дают структуру — не сканируй папки сам
✓ Читай только сигнатуры, не тела методов
✓ Один батч = один модуль = один документ (auto-grouping в get-indexing-batch)
✓ file-registry.tsv хранит прогресс между сессиями
✓ Index Gate перед каждым новым architecture/*.md — не плодить order vs orders
✓ CBM Gate (S4.6) при доступном MCP — связи и структура из графа, не mass Read
✓ index.md обновляется в том же проходе SECTION — не опционально
✓ get-indexing-batch.ps1 -Status — лёгкая проверка прогресса (без чтения кода)
✓ SYNC читает только изменившиеся файлы, не перечитывает весь раздел

✗ Не читай все файлы раздела подряд
✗ Не документируй CRUD без бизнес-логики
✗ Не сканируй vendor/ node_modules/ cache/
✗ Не смешивай project legacy JS с vendor/minified JS при анализе карты
✗ Не пересоздавай уже indexed файлы
✗ Не создавай architecture/*.md без Index Gate и без записи в index.md
✗ Не пропускай CBM Gate при зелёном MCP без причины (укажи в отчёте)
✗ Не читай doc_rules.md дважды за сессию
```

---

## Сводка скриптов

| Скрипт | Когда | Что даёт агенту |
|--------|-------|-----------------|
| `map-project.ps1` | Первый запуск / после батча | tree, hot-files, метрики и списки файлов, регенерация registry+doc-index |
| `get-indexing-batch.ps1 -Status` | Начало нового диалога | Прогресс-бар покрытия |
| `get-indexing-batch.ps1 -Count N` | Перед каждым батчем | N файлов из очереди, сгруппированы по директориям |
| `get-indexing-batch.ps1 -Skip N` | Параллельные агенты | Пропускает N файлов (для второго/третьего агента) |
| `get-indexing-batch.ps1 -Kind css` | Тривиальные типы | Фильтрация по типу (css/tpl/sql/php/js/vue) |
| `mark-noise.ps1 -Paths "..."` | При виде плагина | Исключает из очереди навсегда |
| `audit-docs.ps1` | Периодически | Gaps, устаревшие, сломанные |
| `validate-docs.ps1` | После правок | Ошибки структуры |
| `sync-docs.ps1` | При изменениях кода | Список устаревших доков |

---

## Связи

- [`.doc/harnes/doc_rules.md`](../../../.doc/harnes/doc_rules.md) — стандарт (читать первым)
- [`.doc/architecture/index.md`](../../../.doc/architecture/index.md) — оглавление
- [`.doc/architecture/_map/file-registry.tsv`](../../../.doc/architecture/_map/file-registry.tsv) — Реестр-Очередь (стейт прогресса)
- [`.doc/architecture/_map/doc-index.tsv`](../../../.doc/architecture/_map/doc-index.tsv) — индекс docs (для Index Gate)
- [`.agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1`](../../../.agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1) — карта проекта
- [`.agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1`](../../../.agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1) — выдача батчей
- [`.agents/skills/documentation-router/children/project-doc/scripts/mark-noise.ps1`](../../../.agents/skills/documentation-router/children/project-doc/scripts/mark-noise.ps1) — фильтрация шума
- [`.agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1`](../../../.agents/skills/documentation-router/children/project-doc/scripts/validate-docs.ps1) — валидация
- [`.agents/skills/documentation-router/children/project-doc/scripts/sync-docs.ps1`](../../../.agents/skills/documentation-router/children/project-doc/scripts/sync-docs.ps1) — синхронизация
- [`.agents/skills/documentation-router/children/doc-verify/SKILL.md`](../doc-verify/SKILL.md) — сверка architecture/*.md с кодом (очередь)
- [`.agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1`](../../../.agents/skills/documentation-router/children/doc-verify/scripts/get-verify-batch.ps1) — батчи сверки
- [`.cursor/rules/mcp/codebase-memory-mcp.mdc`](../../../.cursor/rules/mcp/codebase-memory-mcp.mdc) — CBM при индексации
- [`.cursor/rules/mcp/codegraph.mdc`](../../../.cursor/rules/mcp/codegraph.mdc) — codegraph при индексации
- [`codegraph`](../../../codegraph/docs/mcp/codegraph.md) — установка, инструменты и ограничения codegraph
- `.cursor/rules/project-doc.mdc` — триггер Cursor
- `.cursor/rules/project-doc-indexing.mdc` — пакетный цикл индексации (Cursor)
- `.cursor/rules/doc-verify.mdc` — пакетный цикл сверки docs↔код
