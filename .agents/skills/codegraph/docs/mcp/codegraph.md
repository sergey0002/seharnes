# MCP: codegraph

<!-- meta
type: config
status: actual
updated: 2026-11-10
related: [../../../../../.cursor/rules/mcp.mdc, ../../../../../.doc/harnes/state/04-mcp.md, ../../../../../.doc/harnes/state/15-mcp-stack.md]
tags: [harness, mcp, php, graph, codegraph]
-->

---

## Суть

Локальный граф кода CodeGraph: символы, вызовы, импорты и blast radius в SQLite.
Один инструмент `codegraph_explore` отвечает на структурный вопрос сразу
исходником, путем вызовов и списком зависимостей, без обхода файлов через grep.
Сервер написан на Node, индекс лежит в `.codegraph/`, наружу ничего не уходит.

---

## Замена Graphify

С 2026-11-02 CodeGraph заменил Graphify в активном маршруте. Запись `graphify`
удалена из `.cursor/mcp.json`, сервис `mcp-graphify.service` остановлен, правило
и документ Graphify оставлены как legacy. Активный контракт:
[правило codegraph](../../../../../.cursor/rules/mcp/codegraph.mdc).

Что стало лучше:

- один вызов `codegraph_explore` отдает исходник с номерами строк, путь вызовов и
  blast radius, тогда как Graphify отдавал только узлы;
- индекс обновляется сам за 1-2 секунды, не нужен ручной `graphify update`;
- нет Python, uv-кеша и ABI-проблемы `pydantic_core`, нет systemd-юнита и порта
  9130;
- `impact` учитывает тесты, `affected` подбирает тесты по измененным файлам;
- есть `context` для дешевого брифа и `ui` для локального просмотра графа.

Что не заменяется:

- сообщества по плотности (`get_community`);
- god nodes (`god_nodes`);
- shortest path между двумя символами (`shortest_path`);
- метки уверенности EXTRACTED, INFERRED и AMBIGUOUS;
- PR impact через GitHub, который в этом репозитории все равно не работал.

Для этих вопросов используется CBM `trace_path` и `search_graph`, а не возврат
legacy Graphify. Полный разбор отличий и бенчмарк ниже.

---

## Когда вызывать

Когда вопрос про структуру кода: где объявлен класс, как проходит поток, что
сломается при правке символа. Берут до `grep` и чтения файлов, после CBM, если
нужен быстрый обзор. Порядок вызова для агента:
[правило codegraph](../../../../../.cursor/rules/mcp/codegraph.mdc).

Не брать для документации `.doc/`, схемы БД, точных литералов в `.tpl` и правок
символов по LSP.

---

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | stdio |
| Запуск | `bash .agents/skills/codegraph/scripts/codegraph-mcp.sh` |
| Команда сервера | `codegraph serve --mcp --path <корень проекта>` |
| Канон | `.cursor/mcp.json`, ключ `codegraph` |
| Конфиг индекса | `codegraph.json` в корне проекта |
| Каталог индекса | `.codegraph/`, исключен локально через `.git/info/exclude` |
| Телеметрия | выключена |
| Окружение | секретов нет |

Обертка ищет `codegraph` в `PATH`, затем в `$HOME/.nvm/versions/node/*/bin`.
Корень проекта вычисляется от расположения скрипта, поэтому клиент может запускать
сервер из любого каталога.

---

## Текущие значения

| Параметр | Значение |
|---|---|
| Версия CLI | 1.6.2 |
| Статус | включен |
| Транспорт | stdio |
| Проект по умолчанию | корень репозитория через `--path` |
| Файлов в индексе | 1913 |
| Узлов и ребер | 17413 узлов, 44193 ребра |
| Размер БД | 60 МБ |
| Языки | PHP, JavaScript, Vue, XML, YAML |
| `pendingChanges` | добавлено 0, изменено 0, удалено 0 |

Значения сняты `codegraph status --json` 2026-11-02. Индекс пересобирается сам
после правок, числа растут вместе с кодом.

`codegraph.json` исключает сторонние библиотеки и понижает в ранжировании
генерируемые и служебные классы:

```json
{
  "exclude": [
    "scripts/tiny_mce/",
    "scripts/plugins/",
    "scripts/jscalendar-1.0/",
    "admin/scripts/plugins/",
    "dompdf/",
    "sql/",
    "backups/",
    "uploads/"
  ],
  "deprioritize": [
    "scripts/",
    "tools/",
    "lib/sdi/",
    "lib/wm-api/",
    "lib/meta-data/",
    "lib/Objects/Abstract/",
    "**/*Base*.php",
    "lib/CustomObject*.php"
  ]
}
```

`vendor/`, `node_modules/`, `.doc/`, `templates_c/`, `cache/` и `log/` исключаются
без настройки: первые два по встроенному списку, остальные через `.gitignore`.
`sql/` исключен намеренно: там 300 PHP-миграций и исторические DDL, около 2272
узлов, которые не участвуют в текущем рантайме и дают общие имена `up` и `down`.
Если задача про миграцию, ее текст ищется через `rg`, а не через граф.

`deprioritize` не убирает файлы из индекса, а понижает их в ранжировании.
`lib/sdi/` и `lib/wm-api/` - сторонний и инфраструктурный код. `**/*Base*.php`
и `lib/Objects/Abstract/` - сгенерированные и абстрактные классы с общими
`Load`, `Save`, `GetList`. `lib/CustomObject*.php` - общий каркас CRUD.
После настройки запрос `Load` перестал начинаться с `lib/sdi` и `*Base.php`,
в топ вышли продуктовые классы.

После правки `codegraph.json` нужен полный пересбор: `codegraph index --force`.

---

## Инструменты и аргументы

| Инструмент | Аргументы | Что возвращает |
|---|---|---|
| `codegraph_explore` | `query` обязателен, `maxFiles` по умолчанию 12, `projectPath` для другого проекта | Исходник найденных символов по файлам, путь вызовов, blast radius, отношения `extends`/`implements`/`calls` |

`codegraph_explore` включен в `alwaysAllow`. Остальные инструменты
(`codegraph_node`, `codegraph_search`, `codegraph_callers`, `codegraph_callees`,
`codegraph_impact`, `codegraph_files`, `codegraph_status`) в MCP не выводятся по
умолчанию. Включаются переменной `CODEGRAPH_MCP_TOOLS`: короткие имена через
запятую, без префикса `codegraph_`, читаются при старте сервера.

| Инструмент | Аргументы | Когда |
|---|---|---|
| `codegraph_search` | `query`, `kind`, `limit` 10 | точное или частичное имя символа; `kind` отделяет PHP `method` от JS `function` |
| `codegraph_callers` | `symbol`, `file`, `limit` 20 | прямые вызывающие, 1 hop; `file` снимает неоднозначность одноименных символов |
| `codegraph_impact` | `symbol`, `file`, `depth` 2 | транзитивный blast radius, включая тесты |
| `codegraph_node` | `symbol`, `file`, `includeCode`, `offset`, `limit`, `symbolsOnly` | один символ с телом или файл целиком с номерами строк и зависимостями |
| `codegraph_callees` | `symbol`, `file`, `limit` 20 | исходящие вызовы символа |
| `codegraph_files` / `codegraph_status` | каталог, шаблон, формат | структура индекса и состояние синка |

Рабочий набор для этого репозитория: `explore,search,callers,impact`.
`explore` остается основным для вопросов словами, остальные три дают точный
поиск, прямых вызывающих и blast radius без лишнего исходника. `codegraph_node`
в файловом режиме читает файл как Read и полезен там, где экстрактор не увидел
символ, например `Order.MakeReestr = function`. `codegraph_affected` в MCP нет,
только CLI.

Для узкого вопроса `maxFiles` стоит уменьшать до 5-6: по умолчанию 12 файлов
дают лишний контекст и размывают выдачу общими символами.

`codegraph affected` есть только в CLI: он ищет тесты по зависимостям измененных
файлов. В этом репозитории список получается широким, потому что общий
`tests/TestHelper.php` связан со многими тестами. Для выбора тестов задачи он
вспомогательный, основной маршрут остается у `test-task` и diff.

---

## Дополнительные возможности

Плагинов и отдельного plugin API у codegraph нет. Языки, парсеры и MCP-инструменты
встроены в бинарник. Дополнительные возможности идут командами CLI и настройками.

| Возможность | Что делает |
|---|---|
| `codegraph context <task>` | собирает контекст под задачу: точки входа, связанные символы и код; `--format json`, `--max-nodes`, `--no-code` |
| `codegraph affected <files>` | ищет тесты, затронутые изменениями; только CLI, в MCP не выводится |
| `codegraph ui` или `codegraph web` | локальный браузерный просмотрщик графа; в 1.6.2 скрыт за `CODEGRAPH_UI=1`, слушает `127.0.0.1:4747`, есть `--read-only` и `--no-open` |
| `CODEGRAPH_MCP_TOOLS` | расширяет набор MCP-инструментов, подробности выше |
| `codegraph.json` | `exclude`, `include`, `deprioritize`, `extensions` |
| Библиотека `@colbymchenry/codegraph` | встраивание графа в свой Node-процесс, нужен Node 22.5+ |

### `codegraph context`

Собирает контекст под задачу: точки входа, связанные символы и связи. Команда
только CLI, в MCP ее нет.

```bash
codegraph context "fix unpaid order tariff recalculation" --max-nodes 15 --no-code
codegraph context "fix unpaid order tariff recalculation" --format json
```

- `--no-code` оставляет только структуру, без исходников.
- `--format json` отдает точки входа, связи и код в JSON.
- `--max-nodes` ограничивает число символов.

Замер на нашей задаче про пересчет тарифа: `--no-code` дал 618 символов за 1.25 с,
JSON с 10 узлами дал 13.6 тыс. символов. Для брифа перед правкой это дешевле, чем
`explore` на 25 тыс. символов. После брифа детали добираются `explore` или чтением
файлов.

### `codegraph affected`

Ищет тесты, связанные с измененными файлами. Только CLI, в MCP не выводится.

```bash
git diff --name-only | codegraph affected --stdin --quiet
codegraph affected lib/Objects/Order/OrderService.php --json
codegraph affected src/auth.ts --filter "e2e/*"
```

Флаги: `--stdin`, `--depth` по умолчанию 5, `--filter` для шаблона тестов, `--json`,
`--quiet`.

На `lib/Objects/Order/OrderService.php` команда вернула 23 теста. В список попал
`tests/lib/Objects/Order/OrderServiceTest.php`, но из-за общего `tests/TestHelper.php`
связей много. Это подсказка для `test-task`, а не точный селектор: основной выбор
тестов остается за diff и матрицей задачи.

### Просмотрщик `ui` и `web`

В версии 1.6.2 команда скрыта за `CODEGRAPH_UI=1`:

```bash
CODEGRAPH_UI=1 codegraph ui --read-only
CODEGRAPH_UI=1 codegraph web --port 4750
```

Флаги:

| Флаг | Значение |
|---|---|
| `--port` | порт, по умолчанию 4747 или следующий свободный |
| `--no-open` | только напечатать URL, браузер не открывать |
| `--read-only` | запретить любые записи, включая сохранение trails |

Просмотрщик слушает только `127.0.0.1`, открывает уже готовый индекс и не меняет
граф или код. Основные экраны: символ с вызывающими и вызываемыми, Map по модулям,
Entry points, Flow между символами, Dead code, Screens и Steps для UI-приложений,
сохраненные trails и экспорт картинки или SVG. Trails пишутся в
`.codegraph/ui/trails/` и не попадают в git; `--read-only` отключает и это.

Проверка: `CODEGRAPH_UI=1 codegraph ui --no-open --read-only --port 4749` отдал
HTTP 200 и HTML на локальном порту. В обычном релизе команда пока отключена.

Для проекта есть обертка:

```bash
.agents/skills/codegraph/scripts/codegraph-ui.sh
.agents/skills/codegraph/scripts/codegraph-ui.sh --open --port 4750
```

Она включает `CODEGRAPH_UI=1`, ставит `--read-only` и порт 4747 или следующий
свободный. `--port N` фиксирует конкретный порт.

### Готовые правила и скилы

В репозитории codegraph есть официальное правило `.cursor/rules/codegraph.mdc`
с инструкцией для агента: начинать с `codegraph_explore`, доверять результату,
читать файл напрямую только при баннере устаревания. Официальных пользовательских
скилов для `context`, `affected` и `ui` нет. Каталог `.claude/skills` в репозитории
codegraph (`add-lang`, `agent-eval`) относится к разработке самого codegraph, не к
работе с ним.

В нашем проекте готовые файлы такие:

| Файл | Роль |
|---|---|
| `.cursor/rules/mcp/codegraph.mdc` | правило вызова MCP и CLI-сценариев |
| `.agents/skills/codegraph/SKILL.md` | скил: контекст, символы, тесты, просмотрщик |
| `.agents/skills/codegraph/README.md` | краткое описание скила |
| `.agents/skills/codegraph/skill.json` | манифест скила |
| `.doc/harnes/skills/codegraph.md` | карточка скила |
| `.agents/skills/codegraph/scripts/codegraph-ui.sh` | запуск просмотрщика с нужными флагами |

### Внешние образцы правил и скилов

Проверены официальные материалы и сторонние репозитории. Часть выдачи по слову
`codegraph` относится к другим одноименным проектам, их брать нельзя.

| Источник | Что дает | Как использовать |
|---|---|---|
| [Официальное правило codegraph](https://github.com/colbymchenry/codegraph/blob/main/.cursor/rules/codegraph.mdc) | минимальная инструкция: начинать с `codegraph_explore`, доверять результату, читать файл только при баннере устаревания | эталон для нашей копии правила |
| [Официальные docs: MCP server](https://colbymchenry.github.io/codegraph/reference/mcp-server/) | как агент должен вызывать инструменты, `CODEGRAPH_MCP_TOOLS`, границы | сверять поверхность вызова |
| [onsager-ai/dev-skills: codegraph](https://github.com/onsager-ai/dev-skills/blob/main/skills/codegraph/SKILL.md) | сильный разбор: граф tree-sitter неполный, grep обязателен для полноты, матрица выбора инструментов, замеры cold start | взять раздел про soundness и правило "grep - источник полноты" |
| [jaredshuai/understand-codebase](https://github.com/jaredshuai/understand-codebase) | скил связки codegraph + codebase-memory + fast-context, кросс-проверка, известные ложные результаты | взять идею сверки с CBM и проверки тестов через `rg` |
| [full-stack-skills/agent-skills: codegraph](https://github.com/full-stack-skills/agent-skills/blob/main/skills/codegraph/SKILL.md) | полный справочник: MCP-матрица, CLI, установка, gotchas, ссылки на официальные docs | использовать как шпаргалку по командам |
| [audichuang/codegraph-skill](https://github.com/audichuang/codegraph-skill) | минимальный скил только для CLI, без MCP, с trigger-eval | брать для субагентов и окружений без MCP |
| [itsarvinddev/agent-primer: codegraph-policy.md](https://github.com/itsarvinddev/agent-primer/blob/main/codegraph-policy.md) | политика на старте сессии: проверить индекс, свежесть, PATH, восстановление | взять чеклист, но не автоматическую индексацию без разрешения |
| [stark-ai-de/agent-skills: codegraph-ast-grep](https://github.com/stark-ai-de/agent-skills/blob/main/skills/engineering-workflows/codegraph-ast-grep/SKILL.md) | workflow setup/update/doctor, ast-grep как структурная проверка, оценки и контракты | брать для командной установки и диагностики, не для ежедневных задач |
| [skills.sh поиск codegraph](https://skills.sh/?q=codegraph) | каталог с числом установок, `npx skills add` | искать обновления и аналоги |

Что взять в наш скил из внешних источников:

- Codegraph это tree-sitter приближение. Для переименований, смены сигнатуры и
  полного списка вызывающих источник полноты - `rg`, граф только ранжирует.
- `codegraph_callers` может недосчитать тестовых вызывающих. Для влияния брать CBM
  `trace_path` с `include_tests` или проверять `rg`.
- Аннотации тестов в `codegraph_explore` могут быть ложноположительными, число
  тестов проверять `rg`.
- Для перегруженных имен (`run`, `execute`, `load`) вызывать `codegraph_node` на
  конкретный символ и файл, а не общий `callers`.
- После правки watcher отстает на 1-2 секунды. До разрешённого `codegraph sync`
  использовать актуальный файл напрямую.

Одноименные проекты, которые не относятся к colbymchenry CodeGraph:
`GoldDHacker/codegraph-explorer-skill` (локальный Python-парсер) и
`ipowa777/codegraph-studio-claude` (CodeGraph Studio с `npm run codegraph:*`).
Их правила и команды несовместимы с нашим MCP.

### Чего в экосистеме нет

- Плагинов, plugin API и маркетплейса расширений нет.
- Языки и парсеры встроены в бинарник, добавить язык плагином нельзя.
- Отдельного расширения для VS Code нет, интеграция только через MCP.
- В npm только основной пакет и платформенные сборки, без плагинов.
- Пакет UI-компонентов `@colbymchenry/codegraph-ui` готовится в исходниках, в npm
  на момент проверки его нет.
- Hosted-платформа getcodegraph.com находится в early beta и не является локальной
  надстройкой.
- `codegraph install --print-config` только печатает конфиг для агента, это не
  плагин.

---

## Правила использования

1. В этом проекте порядок по коду: CBM -> codegraph -> Serena. `codegraph_explore`
   собирает исходник и связи после первичного поиска CBM, до ручного обхода файлов.
2. Ответ считать прочитанным только в реально возвращённом объёме. Перед правкой
   и при P7 нужен целый актуальный файл: сниппет метода не заменяет whole-file Read.
   Если инструмент уже вернул весь актуальный файл, дублировать чтение не нужно.
3. При баннере об устаревшем файле читать напрямую, если исходник пропущен или
   свежесть не подтверждена. Полный CURRENT-исходник, возвращённый вместо старого
   сниппета, уже прочитан. При глобально отключённом синке читать текущие файлы напрямую.
4. Перед правкой публичного символа проверять blast radius из ответа и уточнять
   ссылки через Serena.
5. Не индексировать чужие проекты без просьбы; `projectPath` только для текущего
   репозитория или его подкаталога.
6. Markdown не индексируется. Документация ищется через
    [jdocmunch](../../../../../.cursor/rules/mcp/jdocmunch.mdc), не через codegraph.
7. Примеры `init`, `index --force`, `sync` и изменения конфигурации ниже относятся
   к обслуживанию индекса по разрешению пользователя. Поиск не разрешает запись.

---

## Сравнение с CBM и graphify

Замер 2026-11-02 на рабочем дереве, HEAD `306f918d0`. 12 задач по реальному PHP,
JS и Vue коду, документация в задания не входила. В ячейках: найдено/ожидалось,
время, размер ответа.

| Задача | codegraph | CBM | graphify |
|---|---|---|---|
| T1 PHP класс `OrderService` | 2/2, 0.5 с, 3.0k | 2/2, 0.10 с, 1.0k | 2/2, 0.06 с, 0.17k |
| T2 PHP метод `OauthController::Login` | 2/2, 0.6 с, 7.5k | 2/2, 0.14 с, 1.0k | 2/2, 0.17 с, 0.18k |
| T3 PHP метод `recalculatePayments` | 2/2, 0.5 с, 4.2k | 2/2, 0.10 с, 1.3k | 2/2, 0.06 с, 0.24k |
| T4 JS `MakeReestr`, два определения | 1/2, 0.5 с, 1.2k | 0/2, 0.13 с, 0.5k | 1/2, 0.04 с, 0.4k |
| T5 JS `normalizeOrderFilter` | 2/2, 0.6 с, 0.6k | 2/2, 0.08 с, 0.3k | 2/2, 0.04 с, 0.17k |
| T6 Vue `ProfilePersonData` | 2/2, 0.5 с, 3.1k | 2/2, 0.11 с, 0.3k | 2/2, 0.03 с, 0.22k |
| T7 вызывающие `newOrder` | 2/2, 0.5 с, 2.8k | 2/2, 0.04 с, 0.3k | 2/2, 0.04 с, 1.1k |
| T8 вызывающие `recalculatePayments` | 2/2, 0.5 с, 2.9k | 2/2, 0.04 с, 0.3k | 2/2, 0.03 с, 1.6k |
| T9 blast radius `newOrder` depth 2 и тест | 4/4, 0.5 с, 5.3k | 4/4, 0.03 с, 0.6k | n/a |
| T10 вопрос словами PHP: оплата и статус | 4/4, 1.4 с, 24.7k | 2/4, 0.16 с, 1.8k | 2/4, 0.25 с, 6.5k |
| T11 вопрос словами JS: registry и pay | 3/4, 1.5 с, 25.0k | 0/4, 0.14 с, 2.0k | 0/4, 0.27 с, 8.0k |
| T12 влияние на тесты `OrderService.php` | 1/1, 0.7 с, 1.4k | n/a | n/a |

| Итог | codegraph | CBM | graphify |
|---|---|---|---|
| Полных задач | 10/12 | 8/12 | 7/12 |
| Частичных | 2 | 3 | 3 |
| Нет прямого аналога | 0 | 1 | 2 |
| Медиана точного поиска | 0.53 с | 0.10 с | 0.04 с |
| Ответ словами | 1.4-1.5 с, 25k | 0.14-0.16 с, 2k | 0.25 с, 6.5-8k |
| Исходник в ответе | да | нет, только по запросу | нет |
| Вызовы и blast radius | да | да | только 1 hop |
| Тесты | `impact` и `affected` | `include_tests` по символу | нет |

Детали оценки:

- T4 и T11: у `MakeReestr` и `PayFromAccount` два живых определения, Vuex-действие
  в `frontend/entry/src/store/module/Order.js` и реализация в
  `frontend/entry/src/store/services/Order.js`. Codegraph нашел только module,
  graphify только services, CBM не нашел ни одного и вернул PHP
  `OrderXhrController`.
- T9: CBM с `include_tests` нашел тестовый метод и класс
  `OrderServiceTest`, но не строку пути с `.php`. Это засчитано как 4/4.
- T12: у CBM и graphify нет прямого аналога `affected` для файла, поэтому n/a.
- Время указано по одному прогону. У graphify холодный старт доходил до 7.5 с,
  теплые вызовы 0.03-0.27 с.

Выводы:

- codegraph лучший на flow-вопросах одним вызовом: исходник, путь вызовов и
  blast radius сразу. Цена - около 25 тыс. символов на ответ и обязательные точные
  имена для общих слов.
- CBM самый быстрый и точный на qualified name, строках и `trace_path`. Провал на
  JS-функциях вида `Order.MakeReestr = function`; ключевые слова лучше
  `semantic_query`.
- graphify силен точечно: `get_node`, `get_neighbors`, `shortest_path`,
  `god_nodes`, связи с confidence. Широкий `query_graph` на вопрос словами
  стартует не от тех узлов и обрезает BFS.
- Документация индексируется только jdocmunch; Markdown не разбирает ни один из
  трех графов.

---

## Установка и перенос

Установка на машину:

```bash
npm i -g @colbymchenry/codegraph@1.6.2
codegraph telemetry off
```

Индекс проекта:

```bash
cd /path/to/project
codegraph init --yes
codegraph status --json
```

После клонирования на другой машине индекс не переносится: `.codegraph/` лежит
локально. Нужно поставить CLI, выполнить `codegraph init --yes` и проверить
`status`. Обертка `.agents/skills/codegraph/scripts/codegraph-mcp.sh` и запись `codegraph` в
`.cursor/mcp.json` приходят с репозиторием; клиентские конфиги пересобираются
`sync-agent-views.sh`.

Проверка: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=codegraph` и
`codegraph status --json`.

---

## Несколько проектов

- Один индекс на проект, каталог `.codegraph/` в корне.
- Сервер запускается в каждом клиенте, но использует общий фоновый демон и один
  писатель на проект.
- По умолчанию отвечает по проекту из `--path` в обертке.
- Другой проект запрашивается параметром `projectPath` в `codegraph_explore`.
- Индекс одного проекта не виден другому: это отдельные SQLite-базы.

---

## Проверка

```bash
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=codegraph
codegraph status --json
codegraph query Order --limit 5
codegraph explore "How is an order paid"
```

Ожидаемо: smoke `OK`, `status` без `pendingChanges`, `query` и `explore` возвращают
символы из `lib/Objects`.

---

## Связи

- [Карта MCP](../../../../../.cursor/rules/mcp.mdc) - общий список серверов
- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - состав, порядок, Kilo-адаптация
- [MCP-стек](../../../../../.doc/harnes/state/15-mcp-stack.md) - общий HTTP-слой и проектная изоляция
- [codebase-memory-mcp](../../../codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md) - структурный граф и trace_path
- [История замены Graphify](#замена-graphify) - выведен из активного маршрута, не использовать
- [Правило codegraph](../../../../../.cursor/rules/mcp/codegraph.mdc) - поверхность вызова

---

## Известные проблемы и ограничения

### П-1: Индекс не найден

- Симптом: `codegraph_explore` предлагает обычные инструменты вместо ответа.
- Причина: в проекте нет `.codegraph/`.
- Решение: сообщить об отсутствии индекса и читать исходник напрямую.
  Только по разрешению выполнить `codegraph init --yes`, затем `codegraph status`.
- Файлы: `.codegraph/`

### П-2: Блокировка писателя

- Симптом: второй процесс `serve --mcp` завершается ошибкой блокировки.
- Причина: один живой писатель индекса на проект.
- Решение: оставить общий демон включенным; не запускать несколько прямых
  процессов с `CODEGRAPH_NO_DAEMON=1`.
- Файлы: `.codegraph/writer.pid`

### П-3: Smarty-шаблоны не в индексе

- Симптом: `.tpl` не находится через `explore`.
- Причина: расширение не входит в поддерживаемые, это шаблоны, а не PHP.
- Решение: искать шаблоны через `multi-search.sh` или `rg`; при необходимости
  сопоставить расширение в `codegraph.json`, но для Smarty это даст мусорные узлы.
- Файлы: `codegraph.json`

### П-4: Markdown и документация не в индексе

- Симптом: `codegraph_explore` не находит раздел или термин из `.md`.
- Причина: Markdown не входит в поддерживаемые языки, файл не попадает в индекс.
- Решение: документация ищется через jdocmunch; codegraph отвечает только по коду.
- Файлы: `.doc/`, `docs/`

### П-5: Миграции не в индексе

- Симптом: `codegraph_explore` не находит класс или метод миграции.
- Причина: каталог `sql/` исключен в `codegraph.json`, это исторический код.
- Решение: искать через `rg` по `sql/`; если миграции нужны в графе постоянно,
  убрать `sql/` из `exclude` и выполнить `codegraph index --force`.
- Файлы: `codegraph.json`, `sql/`

---

## История изменений

- 2026-11-10: локальный порядок CBM/codegraph/Serena и требование полного исходника согласованы с подготовкой плана; повторное чтение полного актуального файла не требуется.
- 2026-11-02: codegraph заменил graphify в активном маршруте: запись удалена из
  `.cursor/mcp.json`, сервис 9130 остановлен, legacy-файлы помечены; обновлены
  правила, скилы, state-доки и mcp-stack
- 2026-11-02: сервер установлен для теста: CLI 1.6.2, индекс 2214 файлов, правило и
  документ созданы, запись добавлена в канон `.cursor/mcp.json`
- 2026-11-02: все внешние источники скачаны в
  `.doc/temp/skil/codegraph-analysis`; подробный разбор в `analysis.md`, индекс
  источников в `README.md`, lookalikes вынесены отдельно
- 2026-11-02: найдены внешние образцы правил и скилов: официальное правило,
  `onsager-ai/dev-skills`, `jaredshuai/understand-codebase`,
  `full-stack-skills`, `audichuang/codegraph-skill`, `agent-primer`,
  `stark-ai-de`; в скил добавлены soundness-ограничения и проверка полноты через `rg`
- 2026-11-02: добавлены скил `codegraph`, карточка скила, обертка
  `.agents/skills/codegraph/scripts/codegraph-ui.sh`; подробно описаны `context`, `affected`,
  просмотрщик `ui`/`web`, готовые правила и отсутствие plugin API
- 2026-11-02: описаны дополнительные CLI-возможности: `context`, `affected`,
  браузерный `ui`/`web` за `CODEGRAPH_UI=1`, библиотека для встраивания;
  отдельного plugin API и маркетплейса плагинов нет
- 2026-11-02: описаны дополнительные MCP-инструменты через `CODEGRAPH_MCP_TOOLS`
  (`search`, `callers`, `impact`, `node`, `callees`, `files`, `status`);
  рекомендованный набор `explore,search,callers,impact`
- 2026-11-02: точность ранжирования: в `deprioritize` добавлены `lib/sdi`,
  `lib/wm-api`, `lib/meta-data`, `lib/Objects/Abstract`, `**/*Base*.php` и
  `lib/CustomObject*.php`; запрос `Load` теперь начинается с продуктовых классов,
  а не с `lib/sdi` и `*Base.php`
- 2026-11-02: детальный бенчмарк 12 задач по PHP, JS и Vue: codegraph 10/12
  полных, CBM 8/12, graphify 7/12; у всех трех выявлены разные дыры в JS-покрытии,
  CBM не нашел `Order.MakeReestr = function`, graphify не нашел Vuex-действия,
  codegraph не нашел реализацию в `services/Order.js`
- 2026-11-02: сравнение с CBM и graphify на 5 вопросах и 11 символах: покрытие
  символов 11/11 у всех, codegraph 4/5 на вопросы словами, точные имена обязательны
  для админских запросов, CBM быстрее и точнее по qualified name, graphify лучше
  точечными `get_node`/`get_neighbors`
- 2026-11-02: настройка под репозиторий: исключены `sql/` (300 PHP-миграций) и
  сторонние библиотеки, добавлен `deprioritize` для `scripts/` и `tools/`,
  пересборка `index --force` дала 1913 файлов, 17413 узлов и 44193 ребра;
  проверено отсутствие сторонних библиотек в индексе, автосинк нового файла 576 мс
