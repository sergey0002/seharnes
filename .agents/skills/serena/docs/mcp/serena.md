# MCP: serena

<!-- meta
type: config
status: actual
updated: 2026-11-10
related: [../../../../../.cursor/rules/mcp.mdc, ../../../../../.doc/harnes/state/04-mcp.md, ../../../../../.doc/harnes/state/15-mcp-stack.md]
tags: [harness, mcp, lsp, symbols, php]
-->

---

## Суть

LSP-слой по символам: объявления, ссылки, диагностика и точечные правки. Один
процесс на проект: testdeploydocker на `9121`, cms на `9122`. PHP обслуживает
Intelephense 1.14.4, настройки в `.serena/project.yml`. Берется после CBM и
codegraph: Serena подтверждает символ и blast radius, граф не заменяет.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/serena.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | HTTP |
| URL | `http://127.0.0.1:9121/mcp`, cms `:9122` |
| Служба | `mcp-serena-testdeploydocker.service` |
| Порты | один юнит на проект, порт из хеша корня, `SERENA_PORT` для переопределения |
| Language server | PHP, Intelephense 1.14.4 |
| Конфиг | `.serena/project.yml`, каталог исключен из git |
| Лимиты | клиент обрывает вызов на 60 с, сервер работает до 240 с |

Действующие значения `.serena/project.yml`:

```yaml
language_servers:
- php

ls_specific_settings:
  php:
    ignore_vendor: true

ignore_all_files_in_gitignore: false

ignored_paths:
  - ".kilo/worktrees/**"
  - ".doc/**"
  - "sourcegraph-local/**"
  - "node_modules/**"
  - "vendor/**"
  - "cache/**"
  - "templates_c/**"
  - "backups/**"
  - "log/**"

included_optional_tools:
  - restart_language_server
  - serena_info
  - replace_lines
  - insert_at_line
  - delete_lines
  - get_diagnostics_for_symbol

symbol_info_budget: 30
```

Почему так:

- `ignore_all_files_in_gitignore: false` - обход сотни `.gitignore` при старте
  занимал около 50 с, а `ignored_paths` закрывают тяжелые каталоги явно.
- `.doc/**` в игноре: 2.5 ГБ и 59 653 файла, для индекса кода это шум.
- `sourcegraph-local/**` - локальное зеркало, не исходники проекта.
- `symbol_info_budget: 30` - больше времени на сбор сведений в крупных классах.

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `url: http://127.0.0.1:9121/mcp` |
| Переменные окружения | нет |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

В `alwaysAllow`: `list_dir`, `read_file`, `find_file`, `find_symbol`,
`get_symbols_overview`, `search_for_pattern`, `find_referencing_symbols`,
`find_declaration`, `get_diagnostics_for_file`, `replace_content`.

Изменяющие структуру инструменты (`replace_symbol_body`, `insert_before_symbol`,
`insert_after_symbol`, `safe_delete_symbol`, `replace_in_files`,
`create_text_file`) в список не входят: они требуют подтверждения.
`get_type_hierarchy` доступен только в JetBrains-бэкенде, из списка убран.

`alwaysAllow` описывает разрешение клиента, а не право менять файл по задаче.
В режиме подготовки плана исходник не меняется, даже через `replace_content`.
Перед записью проверить scope запроса; настройки разрешений не менять для обхода
подтверждения. Выбор инструмента сначала задают инструкции текущей среды, затем
правило правки: PHP-символ с верным LSP-диапазоном, уникальный текстовый якорь,
линейные инструменты только как резерв при неверных диапазонах LS.

Проверено вызовами на этом проекте 2026-11-01. Типичное время: файловые операции
0.1-0.2 с, символьные 1-4 с при прогретом индексе.

Чтение и обзор:

| Инструмент | Результат | Замечание |
|---|---|---|
| `read_file` | работает | весь файл и диапазон `start_line` / `end_line` (от 0) |
| `list_dir` | работает | `recursive`, `skip_ignored_files` |
| `find_file` | работает | маска `*` / `?`, работает и по `.doc` |
| `get_symbols_overview` | работает | дерево символов файла |
| `find_symbol` | работает | `depth` для детей, `include_body`, `substring_matching` |

Символы и связи:

| Инструмент | Результат | Замечание |
|---|---|---|
| `find_referencing_symbols` | работает | файлы, символы и контекст вокруг ссылки |
| `find_declaration` | работает | regex с одной группой, `include_body` |
| `get_diagnostics_for_file` | работает | ошибки LSP с кодом и источником |
| `find_implementations` | не работает | всегда `[]`, функция Premium в Intelephense |

Правки:

| Инструмент | Результат | Замечание |
|---|---|---|
| `create_text_file` | работает | создает файл и родительские каталоги |
| `replace_content` | работает | `mode: literal` и `mode: regex`, `allow_multiple_occurrences` |
| `replace_symbol_body` | работает | только для корректных диапазонов от LS |
| `insert_before_symbol` | работает | вставка перед символом |
| `insert_after_symbol` | работает | вставка после символа |
| `safe_delete_symbol` | работает | со ссылками отказывает и перечисляет строки |
| `replace_in_files` | работает | `dry_run` возвращает diff с `occurrence_ids` |
| `rename_symbol` | не работает | `returned no rename edits`, Premium в Intelephense |

Поиск:

| Инструмент | Результат | Замечание |
|---|---|---|
| `search_for_pattern` | работает | regex, `paths_include_glob`, `context_lines_before/after` |

Память Serena (`write_memory`, `read_memory`, `list_memories`, `edit_memory`,
`rename_memory`, `delete_memory`) работает, хранится в `.serena/memories`.

Опциональные инструменты включены в `project.yml` и отдаются при старте:
`replace_lines`, `insert_at_line`, `delete_lines`, `restart_language_server`,
`serena_info`, `get_diagnostics_for_symbol`. Клиент держит список инструментов с
момента подключения, поэтому в уже открытой сессии их не видно до перезагрузки
окна. Линейные правки не зависят от LS и остаются резервом, если у бэкенда
испортятся диапазоны символов.

Проверка точности правок: прочитать тело через `find_symbol include_body`,
записать обратно тем же текстом и проверить `git diff`. Пустой diff означает
совпадение диапазона. Проверено на `lib/src/Client/ClientController.php`, метод
`search` (74 строки).

Поиск по документации (`serena/project.py:527-537`, пакет `serena-agent`):

| Путь | Поведение |
|---|---|
| `.doc` целиком | непригодно: обход 59 653 файлов и 2.5 ГБ, таймаут и лимит памяти |
| подкаталог `.doc`, например `.doc/harnes` | работает: 2 с на 32 файла |
| отдельный файл `.doc/...` | пустой результат: файл отбрасывается фильтром |

Для документации использовать [jdocmunch](../../../jdocmunch/docs/mcp/jdocmunch.md) и `multi-search.sh`.

Выбор PHP-бэкенда:

| Бэкенд | rename | implementations | references | диапазоны тел | Итог |
|---|---|---|---|---|---|
| `php` (Intelephense) | нет, Premium | нет, Premium | да | верные | выбран |
| `php_phpantom` | да | да | да | только имя символа | отклонен |
| `php_devsense` | да | нет | да | верные | отклонен: 30-111 с на операцию |
| `php_phpactor` | частично | нет | нет | верные | отклонен: пустые ссылки |

Компромисс выбранного бэкенда: `rename_symbol` и `find_implementations`
недоступны бесплатно, вместо них `replace_in_files` с `dry_run` и
`search_for_pattern` по `implements <Interface>`.

---

## Правила использования

1. Брать после CBM и codegraph: Serena подтверждает символы и blast radius.
2. Переименование: `replace_in_files` с `dry_run`, применение по `occurrence_ids`.
3. Поиск реализаций: `search_for_pattern` по `implements <Interface>`.
4. Массовый поиск по `.doc`: `multi-search.sh` или [jdocmunch](../../../jdocmunch/docs/mcp/jdocmunch.md).
5. Долгие операции: после обрыва на 60 с перечитывать файл, а не повторять правку
   вслепую.

---

## Эксплуатация

### Юнит и лимиты

| Параметр | Значение |
|---|---|
| Юнит | `mcp-serena-<slug>` |
| MemoryHigh | 2G |
| MemoryMax | 4G |
| CPUQuota | 200% |
| TasksMax | 512 |
| Restart | always |
| Порты | 9121-9199, порт по хешу корня |
| Лимиты в конфиге | `symbol_info_budget: 30` |

### Данные

| Что | Путь | Размер |
|---|---|---|
| Конфиг и память | `~/.serena/serena_config.yml`, `~/.serena/memories` | мало |
| LSP-бинари | `~/.serena/language_servers` | около 153 MB, не переносить |
| Состояние проекта | `<project>/.serena/{project.yml,memories}` | около 8 MB |

### Один процесс на проект

Инцидент 2026-10-21: каждый редактор запускал свою Serena по stdio, каждая копия
поднимала Intelephense на весь репозиторий. Три копии давали 4.9 ГБ RSS и около
400% CPU, load average до 34 при 8 ядрах.

Вторая причина зависания: в `sourcegraph-local/repos/testdeploydocker` лежал
симлинк на корень репозитория. Intelephense следовал симлинку, получал рекурсию,
держал 200-260% CPU больше 20 минут и не завершал индекс.

Решение:

- Serena вынесена в systemd-юнит на проект: `mcp-serena-testdeploydocker` на 9121,
  `mcp-serena-cms` на 9122; клиенты подключаются по HTTP.
- `serena-shared.sh` остался fallback для машин без systemd.
- Симлинк `sourcegraph-local/repos/testdeploydocker` удален, индексация 21 495
  файлов занимает 36 секунд.
- В `serena-shared.sh` перед `mcp-proxy` сбрасываются proxy-переменные.
- `/.dsh/` добавлен в `.cbmignore`, чтобы CBM не индексировал харнес.

Проверка, что копия одна:

```bash
ss -tln | grep -E '92[0-9][0-9]'
ps -eo pid,rss,cmd | grep intelephense
```

## Установка и перенос

- Установка: `uvx serena start-mcp-server --context desktop-app --project <root>` через `mcp-serena-<slug>.service`; LSP-бинари ставятся в `~/.serena/language_servers`.
- Перенос: скопировать unit/скрипт и запись `serena`, создать unit на новый корень, порт 9121-9199.
- Проверка: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=serena`.

## Несколько проектов

- Один процесс на проект: testdeploydocker 9121, cms 9122; клиенты подключаются по HTTP.
- Не запускать второй stdio-процесс на тот же проект: это дублирует Intelephense.
- Проекты не смешивать: символы и ссылки только своего корня.

## Связи

- [Карта MCP](../../../../../.cursor/rules/mcp.mdc) - общий список
- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - маршрут по коду
- [MCP-стек](../../../../../.doc/harnes/state/15-mcp-stack.md) - юниты, порты, лимиты
- [Правило test-task](../../../../../.cursor/rules/test-task.mdc) - прогоны и chromedriver
- [Правила документации](../../../../../.doc/harnes/doc_rules.md) - MCP-маршрут

---

## Известные проблемы и ограничения

### П-1: `rename_symbol` возвращает пустой результат

- Симптом: `returned no rename edits`.
- Причина: функция Premium в Intelephense.
- Ограничение или решение: `replace_in_files` с `dry_run`.
- Файлы: `.serena/project.yml`

### П-2: `find_implementations` пуст

- Симптом: всегда `[]`.
- Причина: функция Premium в Intelephense.
- Ограничение или решение: `search_for_pattern` по `implements <Interface>`.
- Файлы: `.serena/project.yml`

### П-3: Поиск по `.doc` целиком висит

- Симптом: вызов упирается в таймаут 240 с.
- Причина: обход 2.5 ГБ и 59 653 файлов при отключенном gitignore.
- Ограничение или решение: узкий подкаталог, jdocmunch или `multi-search.sh`.
- Файлы: `.serena/project.yml`

### П-4: Клиент обрывает вызов раньше сервера

- Симптом: ошибка `-32001` на 60 с, сервер продолжает работу.
- Причина: разные таймауты клиента и юнита.
- Ограничение или решение: перечитать файл после обрыва.
- Файлы: `.cursor/mcp.json`

---

## История изменений

- 2026-11-10: разрешение клиента отделено от scope задачи; уточнены ограничения записи при планировании и выбор инструмента правки.
- 2026-11-01: создан по данным `.cursor/mcp.json` и проверкам state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
