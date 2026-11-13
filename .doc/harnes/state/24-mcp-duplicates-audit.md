# Аудит дублей MCP по процессам (2026-11-06)

<!-- meta
type: architecture
status: actual
updated: 2026-11-07
related: [./15-mcp-stack.md, ./04-mcp.md, ./20-mcp-rules.md, ../mcp/README.md]
tags: [harness, mcp, memory, duplicates, systemd, audit]
-->

---

## Суть

При 2 открытых редакторах (VS Code/Kilo и dsh) и 2 проектах (`testdeploydocker`, `cms`) запущено 89 MCP-процессов на 6.5 ГБ RSS. Часть из них - обязательные копии по проекту, часть - дубли по клиенту. Этот документ фиксирует, что дублируется, почему, и какой перевод в общий процесс возможен.

Причина появления: каждый клиент запускает stdio-сервер сам. Один и тот же сервер работает N раз при N клиентах, даже если проектов меньше.

## Замер 2026-11-06

### Копии каждого сервера

| Сервер | Процессов | Транспорт | Хранение |
|---|---:|---|---|
| `php-toolchain/server` (phpstan + php-deps) | 9 | stdio | без индекса, читает файлы по вызову |
| `jdocmunch-mcp serve` | 6 | stdio | общий `~/.doc-index/` |
| `codegraph serve` | 5 | stdio | `.codegraph/` в каждом проекте |
| `codeprism_serve` | 5 | stdio | `~/.local/share/codeprism/<sha256(пут/проект)>.db` |
| `mysql-mcp-proxy` | 5 | stdio + relay на 3306 | одна БД 8031 |
| `codebase-memory-mcp` | 4 | HTTP 9131 | свой SQLite на проект |
| `serena start-mcp-server` | 4 | HTTP 9121/9122 | состояние на проект |

### Группы памяти

| Группа | RSS |
|---|---:|
| MCP-серверы всего | 6.5 ГБ |
| Контейнеры `copytrust-dev-mysql` + `copytrust-dev-php-apache` | 322 МБ |
| Остальное: редакторы, VS Code server, dsh, Kilo serve, Intelephense | ~2.2 ГБ сверх |

Docker-контейнеры из этого объёма занимают меньше 5 процентов. Основной расход - MCP и редакторы.

## Что дублируется законно

| Сервер | Правило | Почему нельзя свести |
|---|---|---|
| `serena` | один процесс на проект | активный проект глобальный, LSP держит один workspace |
| `Intelephense` | один на Serena | языковой сервер живёт внутри процесса Serena |
| `dsh` | один процесс на проект | отдельное приложение, не MCP |
| `playwright` | один на редактор | браузер и профиль принадлежат клиенту |

### dsh: два процесса - это два проекта

```
pid 1014  dsh web --patch projects/cms/.dsh/project.patch.yml               --port 3081
pid 1564  dsh web --patch copytrust/testdeploydocker/.dsh/project.patch.yml --port 3080
```

Оба запущены от оболочки входа, а не копией друг друга. Второй экземпляр появился потому, что открыт проект `cms`. Это штатное поведение, не утечка.

### Intelephense: два процесса - два проекта

```
pid 1509  Intelephense --stdio  (родитель - serena 9121, testdeploydocker)  586 МБ
pid 1492  Intelephense --stdio  (родитель - serena 9122, cms)               256 МБ
```

Тоже штатно: каждый Serena поднимает свой LSP под свой проект.

## Что дублируется без пользы

| Сервер | Копий | Причина | Потенциал |
|---|---:|---|---|
| `jdocmunch` | 6 | индекс уже общий, сервер читает `DOC_INDEX_PATH` при вызове | один процесс на машину |
| `mysql-mcp-proxy` | 5 | все копии идут в одну БД 8031 | один процесс на машину |
| `php-toolchain` | 9 | без состояния и без индекса | один-два процесса на машину |
| `codeprism` | 5 | база уже на проект, но путь фиксируется при старте | один процесс на проект |
| `codegraph` | 5 | индекс уже в проекте, но путь фиксируется при старте | один процесс на проект |

## Хранение: база на проект уже есть

Проверено по коду и каталогам:

| Сервер | Где база | Ключ разделения |
|---|---|---|
| `codeprism` | `~/.local/share/codeprism/<sha256(abs path)>.db` | `core/paths.py: get_db_path(project_path)` |
| `jdocmunch` | `~/.doc-index/<owner>/<name>.json` + `.related.json` + `.postings.jsonl` | `repo` в каждом вызове |
| `codegraph` | `<project>/.codegraph/` | путь проекта |
| `codebase-memory-mcp` | SQLite на проект в каталоге проекта | `project` в каждом вызове |
| `serena` | состояние на проект | один процесс на проект |

### Индексы jdocmunch в одном сервере

`doc_list_repos` на работающем сервере вернул 3 репозитория:

| Репозиторий | Документов | Секций |
|---|---:|---:|
| `local/testdeploy-arch` | 1971 | 29287 |
| `local/cms-arch` | 53 | 953 |
| `local/cms-manifest` | 54 | 1435 |

То есть `jdocmunch` уже мультипроектный по данным. Дубль возникает только на уровне клиентских процессов.

## Что реально выполнимо

| Сервер | Нужен HTTP-транспорт | Путь проекта в запросе | Итог |
|---|---|---|---|
| `jdocmunch` | да, `serve` сейчас только stdio | есть, параметр `repo` | один процесс на машину |
| `codeprism` | да, `--transport sse --port` | нет, задаётся `configure(path)` | один процесс на проект |
| `codegraph` | да, сейчас только `--mcp` stdio | нет, задаётся `--path` | один процесс на проект |
| `php-toolchain` | да, сейчас `StdioServerTransport` | нет, `MCP_WORKSPACE` из env | один процесс на машину с путём в запросе |

Проверка `codeprism serve --help`: транспорты `stdio | sse`, порт по умолчанию 8765, путь - позиционный аргумент. Проверка `codegraph serve --help`: только `--mcp` и `--path`, HTTP не предусмотрен.

## Плановый перевод

Порядок от простого к сложному. CodePrism для `testdeploydocker` переведен на
общий Streamable HTTP на 9201. Остальные пункты остаются планом и требуют
проверки актуального состояния перед выполнением.

1. `jdocmunch`: один HTTP-сервер на машину, `repo` в аргументах. Минус 5 процессов.
2. `codeprism`: выполнено для `testdeploydocker`, HTTP-сервер на проект, порт по проекту.
3. `codegraph`: сервер на проект с обёрткой. Минус 3 процесса.
4. `php-toolchain`: HTTP-обёртка с `MCP_WORKSPACE` в запросе. Минус 7 процессов.

Ожидаемый эффект: минус 18-25 процессов, 1.5-2 ГБ RSS.

## Как проверить дубли сейчас

```bash
ps -eo cmd | grep -oE "jdocmunch-mcp serve|php-toolchain/server|mysql-mcp-proxy|codebase-memory-mcp --ui=false|serena start-mcp-server|codeprism_serve|codegraph serve" | sort | uniq -c
ps -eo pid,ppid,rss,cmd | grep -E "dsh/lib/bin.js|intelephense|codeprism_serve" | grep -v grep
```

Норма: по одному `dsh` и одному `Intelephense` на открытый проект; по одному HTTP-процессу на сервер с общим транспортом.

## Что не относится к дублям

- `graphiti` был включён в каноне, но не работал: порт 8000 пуст, контейнеров нет. Исправлено постановкой юнита `graphiti-stack.service`; подробности в [15-mcp-stack](./15-mcp-stack.md#2-юниты-и-лимиты).
- `sourcegraph` отключён (`disabled: true`), контейнеров нет, порт 7080 свободен. В расчёте копий не участвует.

## Связи

- [MCP-стек](./15-mcp-stack.md) - юниты, порты, скрипты, перенос
- [MCP-серверы](./04-mcp.md) - состояние и порядок вызова
- [MCP-правила](./20-mcp-rules.md) - состав правил канона
- [Документы MCP](../archive/mcp/README.md) - конвенция серверов
- [codebase-memory-mcp](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md), [serena](../../../.agents/skills/serena/docs/mcp/serena.md), [codegraph](../../../.agents/skills/codegraph/docs/mcp/codegraph.md), [codeprism](../../../.agents/skills/codeprism/docs/mcp/codeprism.md) - ограничения каждого сервера

---

## История изменений

- 2026-11-07: отмечен переход CodePrism testdeploydocker на один HTTP-процесс для клиентов; исторический замер оставлен без изменений.
- 2026-11-06: документ создан по замеру после переезда Docker Desktop на Docker в Ubuntu. Зафиксированы 89 MCP-процессов и 6.5 ГБ, разбор законных и лишних дублей, проверка хранения на проект в коде codeprism и jdocmunch, план перевода на общий HTTP.
