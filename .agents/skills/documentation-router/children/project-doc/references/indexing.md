## ИНДЕКСАЦИЯ И ДОКУМЕНТИРОВАНИЕ (Batching)

Вместо подхода "1 файл = 1 док", мы описываем **бизнес-процессы** (фронт + бэк) и берем файлы из очереди пакетами.
Файлы автоматически отсортированы по директориям — один батч = один модуль.

### B0 — Проверь прогресс
```
powershell -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Status
```
Увидишь прогресс-бар покрытия. Если покрытие >90% — индексация завершена.

### B1 — Получи пакет файлов

```
powershell -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Count 15
```

Для CSS/TPL/SQL (тривиальные файлы) — батч можно увеличить:
```
powershell -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Count 30 -Kind css
```

Для параллельных агентов (разные порции):
```
# Агент 1:
powershell ... -Count 15 -Skip 0
# Агент 2:
powershell ... -Count 15 -Skip 15
```

### B2 — Анализируй файлы
1. Изучи содержимое выданных файлов.
2. Определи, к какому единому **бизнес-процессу** (например, `registration`, `payments`, `tariffs`) они относятся.
3. Помни: **не создавай документацию 1-к-1 к файлу**. Описывай процесс целиком.
4. **Фильтрация шума:** Если в пакете попался сторонний плагин, минифицированный файл или библиотека (например, `admin/scripts/tinymce.js`), которую не нужно документировать — **ОБЯЗАТЕЛЬНО ПОМЕТЬ ЕЕ КАК ШУМ**. 
   Запусти: `powershell .agents/skills/documentation-router/children/project-doc/scripts/mark-noise.ps1 -Paths "путь/к/файлу1.js", "путь/к/файлу2.js"`
   После этого файл навсегда будет исключен из Очереди.

### B3 — Создай или дополни документ
1. Найди существующий документ бизнес-процесса в `.doc/architecture/` или создай новый (обязательно проверив Index Gate!).
2. Обязательно впиши в него ссылки на обработанные файлы кода в бектиках (например, `` `admin/ident.php` ``). По этим ссылкам `map-project.ps1` обновит статус файлов на `indexed`!

### B4 — Завершение пакета
Запусти:
```
powershell -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1
powershell -ExecutionPolicy Bypass -File .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Status
```
Остановись и скажи:
«✅ Батч обработан: N файлов → [документ].md. Покрытие: X% (было Y%). Напишите "продолжи" для следующего батча.»

### B5 — Автономный режим (/goal)

В Antigravity пользователь может запустить автономную индексацию:
```
/goal Проиндексируй проект. Цикл: get-indexing-batch → анализ → запись в architecture/*.md
(бектики обязательны!) → map-project.ps1. Повторяй пока файлы не закончатся.
```

Агент будет работать автономно, не останавливаясь после каждого батча.

### S4.5 — Index Gate (ОБЯЗАТЕЛЬНО перед S5)

**Перед созданием или существенным дополнением architecture/*.md** выполни Index Gate
из [`.doc/harnes/doc_rules.md`](../../../../.doc/harnes/doc_rules.md) (раздел «Index Gate»):

```
1. Прочитай .doc/architecture/index.md целиком
2. Просмотри существующие *.md в .doc/architecture/ (glob, без _*.md и _map/)
3. Найди наиболее подходящий документ:
   - имя: order ↔ orders, payment ↔ payments (singular/plural)
   - строка в таблицах index.md
   - tags: / related: в meta
   - H1 и ## Суть существующих docs
4. Если найден → target = существующий файл, режим «дописать»
5. Если не найден → target = новый файл, AskQuestion перед созданием
```

Выведи отчёт перед записью:

```
📋 Index Gate — раздел [раздел]

Проверено в index.md: да
Кандидаты:
  • orders.md — «Система заказов» (блок 4. Бизнес-процессы) ← рекомендуется
  • payments.md — частичное пересечение (auto-pay)

Решение: дописать orders.md | создать новый [имя].md
Блок index.md: [если новый файл]
```

**Запрещено** создавать `order.md`, если в index уже есть `orders.md`, без явного решения пользователя.

### S4.6 — CBM Gate (ОБЯЗАТЕЛЬНО при доступном MCP)

**После Index Gate, перед S5.** CBM даёт **граф кода** (классы, routes, вызовы) — не путать с Index Gate (граф **docs**).

Правило вызова: [mcp-codebase-memory](../../../../../../.cursor/rules/mcp/codebase-memory-mcp.mdc), эксплуатация: [документация CBM](../../../../codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md)

#### Шаг 1 — Проект и индекс

```
list_projects          → project (логическое имя репо)
index_status           → если нет / stale: index_repository
  repo_path: абсолютный путь к корню git-репозитория
  mode: moderate       → full только по запросу пользователя
```

#### Шаг 2 — Обзор раздела

```
get_graph_schema       → один раз за сессию индексации, если ещё не вызывал
get_architecture       → aspects: routes, packages (hotspots модулей)
search_graph           → query: "[паттерн раздела]" (BM25)
                       → name_pattern: ".*Order.*" для точного поиска
                       → label: Route | Class | Function (по необходимости)
                       → file_pattern: "*.php" | "*.vue" при смешанном модуле
                       → limit: 20
```

Выбери **2–5 ключевых символов** (контроллер, сервис, route, vue store/component).

#### Шаг 2b — codegraph (после CBM, если MCP зелёный)

```
codegraph_explore → вопрос по модулю, maxFiles 5-6
codegraph_search  → точный символ по имени
codegraph_callers → кто вызывает
codegraph_impact  → blast radius с глубиной
codegraph_files   → структура индекса
```

Для другого проекта передать `projectPath=<абсолютный корень проекта>`.

Дополни CBM: исходник, вызывающие и blast radius по всему репо. Для литералов,
regex и `.js`/`.tpl` вне графа используй `.tools/scripts/multi-search.sh` или `rg`:
codegraph не полнотекстовый поиск. `.doc/` в граф не входит, читай через
`multi-search.sh` или `Read`. Сообщества, god nodes и shortest path из старого
graphify в codegraph не заменяются; для таких вопросов брать CBM `trace_path`.
См. [правило codegraph](../../../../.cursor/rules/mcp/codegraph.mdc) и
[документацию](../../../../codegraph/docs/mcp/codegraph.md).

#### Шаг 3 — Связи и impact (для ## Как устроено и ## Связи)

Для каждого ключевого символа (макс. **3** вызова `trace_path` на раздел):

```
trace_path
  function_name: qualified name из search_graph
  direction: both
  depth: 2                    → 3 только для 🔴A сложных модулей
  mode: calls                  → структура вызовов
  mode: cross_service          → front↔back, HTTP между PHP и API (обязательно для UI-модулей)
  risk_labels: true            → для ## Известные проблемы (shared / high coupling)
```

Дополнительно при необходимости:

```
search_graph  semantic_query: ["оплата","order","payment"]  → пересечения с другими доменами
search_code   → строковые ключи API во Vue/legacy JS
get_code_snippet → точные сигнатуры для doc (вместо Read целого файла)
query_graph   → сложные multi-hop (редко, только если trace_path недостаточно)
```

**Не используй** `manage_adr` — решения пиши в `.doc/architecture/`, не в ADR CBM.

#### Шаг 4 — Перенос в документ

Из результатов CBM **обязательно** отразить:

| Секция architecture/*.md | Что взять из CBM |
|--------------------------|------------------|
| `## Как устроено` | иерархия: Route → Controller → Service → listeners; entry points |
| `## Связи` | ссылки на **другие** `.doc/architecture/*.md`, если модули связаны через trace_path / cross_service |
| `related:` в meta | имена связанных arch-файлов |
| `## Известные проблемы` | shared-компоненты, high inbound degree, legacy+vue параллель |
| backticks в тексте | пути из `get_code_snippet` / search_graph (`lib/.../OrderService.php`) |

Правило **обратных ссылок** из `doc_rules.md`: если дописал в `orders.md` ссылку на `payments.md` —
проверь/дополни `## Связи` в `payments.md`.

#### Шаг 5 — CBM-отчёт перед записью

```
🕸️ CBM Gate — раздел [раздел]

project: [имя из list_projects]
Ключевые символы: OrderService, OrderControllerNew, /order/...
Связанные модули (docs): payments.md, routes.md, frontend.md
trace_path: inbound N / outbound N / cross_service: [да/нет]
Рекомендация ## Связи: +payments.md, +frontend.md

Читать файлы вручную: [список ≤5 или «не требуется»]
```

### S5 — Создай или дополни документ

**Если Index Gate выбрал существующий файл** — допиши секции в него, не создавай новый.

**Если Index Gate выбрал новый файл** — создай `.doc/architecture/[имя].md` по шаблону из `.doc/harnes/doc_rules.md`.

Обязательные секции: `## Суть`, `## Как устроено`, `## Связи`,
`## Известные проблемы и ограничения`, `## История изменений`.

**`## Связи` при индексации:** минимум одна ссылка на каждый **смежный домен**,
найденный CBM `trace_path` / `cross_service`, если для него уже есть architecture/*.md.
Формат: `- Название (./файл.md#якорь) — почему связано (вызов / route / shared service)`.

### S5.1 — SYNC: сверка docs ↔ код (CBM, опционально после больших разделов)

Если раздел 🔴A и MCP доступен — после S5:

```
detect_changes  scope: unstaged | branch  depth: 2
```

Если CBM показывает активные символы **не упомянутые** в doc — добавь в `## История изменений`
запись «CBM sync: добавлены …» или в `## Известные проблемы` gap.

### S6 — Обнови index.md (ОБЯЗАТЕЛЬНО)

**Не спрашивай «обновить index?»** — это часть индексации, не опциональный шаг.

После S5:

1. Открой `.doc/architecture/index.md`
2. Убедись, что целевой документ **есть в нужной таблице** (блок 1–5 CopyTrust)
3. Если строки нет — **добавь** `| файл.md | краткое описание |`
4. Если документ merge/rename — исправь или убери устаревшую строку
5. Обнови `_priority.md` → статус ✅ готово (спроси только если `_priority.md` не существует)
6. Проверь обратные ссылки

**Не вызывай `-Complete`**, пока документ не отражён в index.md.

Спроси через AskQuestion **только если**:
- непонятно, в какой тематический блок положить строку;
- нужен новый раздел index (редко).

### S7 — Зафиксируй завершение (чекпоинт)

Прогресс отслеживается автоматически через `file-registry.tsv`: бектики в документе
переводят файлы из `not_indexed` в `indexed` после `map-project.ps1`.

Скажи пользователю:

```
✅ Раздел "[раздел]" задокументирован.

Обнови карту и проверь прогресс:
  powershell .agents/skills/documentation-router/children/project-doc/scripts/map-project.ps1
  powershell .agents/skills/documentation-router/children/project-doc/scripts/get-indexing-batch.ps1 -Status

Следующий шаг:
  «продолжи индексацию» (выдаст следующий батч)
```

### S8 — Отчёт

```
✅ Раздел "[раздел]" задокументирован

Файл: .doc/architecture/[файл].md (создан | дополнен)
index.md: ✅ обновлён — блок [N], строка [файл.md]
Index Gate: [reuse orders.md | новый файл]
CBM: project=[имя] | символов N | trace_path N | связей docs +N
Читано файлов проекта: N (пропущено за счёт CBM: N)

Зафиксировано:
  📐 Решений: N  |  ⚠️ Проблем: N  |  🔗 Связей: N

Прогресс сессии: X/N разделов
Следующий: [из стейта]
```

---
