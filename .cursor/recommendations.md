# Рекомендации: работа агента с MCP-kit на большом legacy PHP + Vue.js

Документ для **Cursor** (`.cursor/recommendations.md`, rules) и **Codex** (`.codex/AGENTS.md`, `.codex/recommendations.md`): задаёт порядок инструментов, границы риска и типичные сценарии монолита **Laravel/Symfony/чистый PHP backend + Vue 2/3 SPA или mixed templates**.

---

## 1. Цели и ограничения

**Цель:** менять код предсказуемо в большом репозитории, не «угадывая» схему БД, не ломая контракт API между PHP и фронтом, не раздувая контекст чтением тысяч файлов.

**Ограничения legacy:**

- Дублирование логики (контроллер + сервис + «god class»).
- Смешение слоёв (SQL в контроллере, бизнес-логика во Vuex/Pinia и в PHP).
- Неочевидные entry points (cron, queue workers, `artisan`, legacy `.php` в `public/`).
- Vue: Options API + Composition API, глобальные компоненты, legacy build (Webpack/Vite).

**Принцип:** сначала **карта** (граф + архитектура), потом **узкий срез** (символ/файл), потом **правка**, потом **проверка** (PHPStan / Semgrep / UI).

---

## 2. Иерархия инструментов (обязательный порядок)

### Фаза A — ориентация (без правок кода)

1. **codebase-memory-mcp**
   - Новый проект / давно не индексировали: `index_repository` с абсолютным `repo_path` или дождаться `auto_index`.
   - Всегда при незнакомой задаче: `list_projects` → убедиться в имени `project`.
   - `get_graph_schema` → затем `get_architecture`.
   - Поиск сущностей: `search_graph` (`query` или `name_pattern`), не массовый Grep по всему репо.
   - Связи: `trace_path` (calls / data_flow), `query_graph` для multi-hop.
   - Перед чтением тела: `get_code_snippet` только после точного qualified name из `search_graph`.

2. **sourcegraph** (если MCP зелёный) — **сразу после CBM**, до Serena:
   - Фильтр репо: `repo:^src-serve-git-3434/repos/testdeploydocker$`
   - `sg_keyword_search` — точные строки/классы по путям из CBM; `file:.*\\.(vue|js|tpl)$` для фронта
   - `sg_nls_search` — если нужен размытый поиск по модулю после `search_graph`
   - `sg_read_file` — только если CBM snippet недостаточен; **не** дублировать тот же файл
   - `.doc/` — **не** Sourcegraph (Read). После коммитов: `sourcegraph-local/sync-mirror.sh`

3. **mysql** — любые вопросы про таблицы, колонки, FK, примеры строк:
   - `list_tables` → `describe_table` → `query` (SELECT only).
   - **Запрещено** придумывать имена колонок без `describe_table`.

4. **context7** — только для внешних API (Laravel, Vue, PHPUnit, пакеты):
   - `resolve-library-id` → `query-docs`.
   - Не использовать для кода **этого** репозитория.

5. **git** — контекст изменений: `git_status`, `git_log`, `git_diff`, `git_blame`.
   - Дополнительно CBM: `detect_changes` для blast radius по символам.
   - Если правка попадает в план (`prepare-plan`) — blast radius по своему **фиксированному
     порядку** (не общему из этого раздела): скил `prepare-plan` §P1.1 и таблица
     `BLAST_RADIUS_LADDER` в `.cursor/skills/prepare-plan/ADAPTERS.local.md`.
   - Кто раньше правил именно эти строки (номера задач, открытые ветки) — скил
     [`git-task-blame`](skills/git-task-blame/SKILL.md), обязателен в `prepare-plan` (P0.5b, P7.4a).

### Фаза B — точечное исследование

5. **serena** (PHP) — когда нужен LSP-точный символ или правка:
   - `get_symbols_overview` по файлу → `find_symbol` → `find_referencing_symbols` перед rename/delete.
   - `search_for_pattern` — только если CBM/Sourcegraph/Serena не дали результат (legacy строки, конфиги).

6. **playwright** (Vue/UI) — после понимания маршрута, всегда headed (видимый браузер):
   - `browser_navigate` → `browser_snapshot` → действия.
   - Не скриншот вместо snapshot для кликов/форм.

### Фаза C — правки

7. **PHP правки:** предпочитать **serena** (`replace_symbol_body`, `replace_content`, `rename_symbol`) для классов/методов; для небольших правок вне символов — обычный Edit с предварительным `read_file` (Serena).

8. **Vue/JS/TS:** обычный Read/Edit; для навигации — CBM `search_graph` или Sourcegraph `sg_keyword_search` с `file:.*\\.(vue|js)$`.

9. **mysql `execute`:** только с явного разрешения пользователя; для проверки гипотез — `query`.

### Фаза D — верификация

10. **phpstan-mcp** — после существенных PHP-изменений (`phpstan_analyze` на затронутые пути).
11. **semgrep** — security/quality, особенно перед PR с auth/SQL/XXE.
12. **test-task** / **browser-verify** — UI по задаче: оркестратор «тестируй задачу»
    (prepare-task-test при отсутствии Cest → Codeception → Playwright). Всегда headed.
    Канон: [`.doc/harnes/tests.md`](../.doc/harnes/tests.md), реестр: [`.doc/qa/index.md`](../.doc/qa/index.md).
13. **xdebug** — только если баг **рантайм** и статика не объясняет (не заменяет PHPStan).

---

## 3. Разделение ролей: CBM vs Sourcegraph vs Serena

| Ситуация | Инструмент |
|----------|------------|
| «Кто вызывает этот endpoint / сервис?» | CBM `trace_path`, `search_graph` (Route, Function) |
| «Где класс `OrderService`?» | CBM `search_graph` → `get_code_snippet`; уточнение строк — Sourcegraph `sg_keyword_search` |
| «Есть ли ещё вхождения строки в .js/.tpl?» | Sourcegraph `sg_keyword_search` с `repo:` + `file:` |
| «Поменять сигнатуру метода и все вызовы в PHP» | Serena `rename_symbol` / find references |
| «Найти строку в .vue без символа» | Sourcegraph `sg_nls_search` или CBM `search_code` |
| «Обзор файла перед правкой» | Serena `get_symbols_overview` |
| «Дока Vue 3 `defineProps`» | context7 |
| «task.md / doc.md задачи» | Read (не Sourcegraph) |

**Не делать:** читать подряд десятки файлов; не дублировать CBM и Sourcegraph на один и тот же файл.

---

## 4. Типичные сценарии PHP + Vue

### 4.1 Новый REST endpoint + Vue-форма

1. CBM: найти существующие `Route` / контроллеры в том же модуле (`search_graph`, `get_architecture`).
2. Sourcegraph: `sg_keyword_search` по именам из CBM + `file:.*\\.(vue|js)$` для фронта.
3. mysql: таблицы, с которыми связан домен (`describe_table`).
4. PHP: Serena — добавить метод в контроллер/сервис по образцу соседнего символа.
5. Vue: CBM/Sourcegraph по компоненту/API client → правка `.vue` / `api/*.js`.
6. PHPStan на изменённые PHP-пути.
7. Playwright: happy path формы (если есть staging URL в задаче).

### 4.2 Баг «данные не те на экране»

1. Playwright: snapshot + network (какой API дергается).
2. CBM: от Route/контроллера к сервису (`trace_path`).
3. mysql: `query` для проверки данных (read-only).
4. xdebug — если расхождение только в рантайме (ветвления, кэш).

### 4.3 Рефакторинг god class

1. CBM: `get_architecture`, `trace_path` inbound/outbound, `detect_changes` если уже есть локальные правки.
2. phpda / `phpcallgraph_generate` — понять циклы (опционально, тяжёлые на огромных `src/`).
3. Мелкие шаги: Serena `safe_delete_symbol` только после нулевых references.
4. PHPStan после каждого логического шага.

### 4.4 Поиск мёртвого кода

1. CBM: степень узлов, `trace_path` inbound, architecture hotspots.
2. Подтвердить Serena `find_referencing_symbols` перед удалением.
3. Не удалять: entry points artisan, `routes/*.php`, публичные API, Vue routes, динамические вызовы `call_user_func`.

### 4.5 Зависимость PHP ↔ Vue (контракт)

- Источник истины: DTO/Resource/Array shape в PHP + фактический JSON (playwright network или тест).
- При изменении поля: CBM найти **все** HTTP consumers (`HTTP_CALLS` / routes) + grep по строковым ключам в `.vue`.
- Зафиксировать решение: CBM `manage_adr` для нетривиальных контрактов.

---

## 5. Управление контекстом и токенами

- Один запрос CBM `get_architecture` лучше, чем 20× `Read` случайных файлов.
- `get_code_snippet` только для **подтверждённых** имён из `search_graph`.
- Serena: `include_body: false` при обзоре; `true` только перед правкой.
- Память Serena (`write_memory`): только устойчивые факты (имя dev-БД, URL staging, «модуль X deprecated»), не дублировать то, что есть в ADR/CBM.

---

## 6. Безопасность и данные

- **mysql `execute`:** по умолчанию запрещён без явного OK пользователя.
- Не коммитить `.cursor/mcp.env`, дампы БД, токены.
- Semgrep на изменениях в auth, upload, `eval`, raw SQL.
- CBM и mysql работают **локально**; не отправлять прод-пароли в чат.

---

## 7. Индекс и производительность

- Первый `index_repository` на монолите может занять минуты — сообщить пользователю, не прерывать.
- Режим `fast` — только структура; для семантики нужен `moderate`/`full`.
- Артефакт `.codebase-memory/graph.db.zst` — опционально в git для команды; иначе `.gitignore`.
- После крупного merge: `index_repository` или дождаться watcher.

---

## 8. Чеклист перед завершением задачи

- [ ] Затронутые PHP-пути прошли `phpstan_analyze` (или объяснён известный legacy baseline).
- [ ] Контракт API PHP↔Vue проверен (network / тест / ручное описание).
- [ ] Нет выдуманных колонок БД (были `describe_table` / `query`).
- [ ] Критичные security-пути — `semgrep_scan` при необходимости.
- [ ] UI-сценарий из тикета — playwright snapshot/click path (если применимо).
- [ ] Изменения согласованы с `git diff`; для крупного рефакторинга — краткая заметка в ADR (`manage_adr`).

---

## 9. Антипаттерны (запреты для агента)

- Массовый `Read`/`Glob` всего `app/` или `resources/js/` «на всякий случай».
- Правка PHP без поиска references (риск сломанных вызовов из Vue API client).
- `execute` в MySQL для «проверки» вместо `query`.
- Игнорирование queue/cron/event listeners при изменении «одного метода».
- Удаление кода только по «0 results» в grep без CBM/Serena (динамические вызовы).
- Дублирование документации framework из context7 вместо чтения **этого** проекта.

---

## 10. Краткая шпаргалка одной строкой

**CBM — карта → Sourcegraph — полнотекст → mysql — БД → Serena — правки PHP → context7 — внешняя дока → Playwright — UI → PHPStan/Semgrep — качество.**
