<!-- generated from architecture:sourcegraph-local by doc_render.py; do not edit -->

# Sourcegraph local (MCP-поиск по коду)

task unknown - status unknown - branch unknown - release unknown

# Sourcegraph local (MCP-поиск по коду)
<a id="sourcegraph-local-(mcp-поиск-по-коду)"></a>
<!-- meta
type: architecture
status: actual
updated: 2026-09-22
related: [cicd.md, architecture.md, local-dev-resources.md]
tags: [sourcegraph, mcp, gototask, zoekt, local-dev]
-->

---

## Суть
<a id="суть"></a>
Локальный Sourcegraph (Docker, UI `:7080`) даёт агентам полнотекстовый поиск по коду через MCP.
Индекс строится не по рабочей копии напрямую, а по bare-зеркалу в `sourcegraph-local/repos-mirror/`.
Поэтому после смены ветки (gototask apply) индекс может отставать, пока зеркало и Zoekt не обновлены.

> **AI:** читай этот doc при работе с MCP `sourcegraph`, устаревшим поиском после смены ветки, gototask sync-index.  
> **Сначала:** [§1](#1-как-устроено) → [§2](#2-gototask--автообновление-индекса).  
> **Операционка (запуск, токен, бэкап):** [`sourcegraph-local/README.md`](../../sourcegraph-local/README.md).  
> **MCP в IDE:** [`.cursor/sourcegraph-mcp.md`](../../.cursor/sourcegraph-mcp.md).

### Быстрая навигация
<a id="быстрая-навигация"></a>
| § | Тема |
|---|---|
| [§1 Как устроено](#1-как-устроено) | serve-git, зеркало, Zoekt, фильтр `repo:` |
| [§2 gototask](#2-gototask--автообновление-индекса) | когда и что обновляет индекс |
| [§3 Вручную](#3-ручная-синхронизация) | `sync-index.sh` |
| [П-N](#известные-проблемы-и-ограничения) | старый HEAD, `.doc/` вне индекса |

---

## 1. Как устроено
<a id="1.-как-устроено"></a>
```
worktree (текущая ветка задачи)
    │  sync-mirror / sync-index
    ▼
sourcegraph-local/repos-mirror/*.git   <- bare, HEAD = default branch для поиска
    │  src-serve-git :3434
    ▼
Sourcegraph gitserver → Zoekt index
    │
    ▼
MCP http://127.0.0.1:7080/.api/mcp/v1
```

| Элемент | Путь / значение |
|---|---|
| Стек и скрипты | `sourcegraph-local/` |
| Список репо | `sourcegraph-local/config/repos.conf` |
| Зеркало CopyTrust | `repos-mirror/testdeploydocker.git` |
| UI / MCP | `http://localhost:7080` |
| Фильтр в запросах | `repo:^src-serve-git-3434/repos/testdeploydocker$` |

Поиск без `rev:` идёт по **default branch** зеркала (symbolic-ref `HEAD`).  
Если HEAD зеркала указывает на старую ветку задачи, MCP отдаёт чужой код при живой рабочей копии на новой.

`.doc/` в git-зеркале нет: `task.md` / `doc.md` / `architecture/*` читать через **Read**, не Sourcegraph.

Место в MCP-маршруте агента: codebase-memory-mcp → **sourcegraph** → serena (см. [`.doc/doc_rules.md`](../harnes/doc_rules.md) § MCP-маршрут).

---

## 2. gototask: автообновление индекса
<a id="2.-gototask:-автообновление-индекса"></a>
После **apply** (когда файлы worktree реально сменились) скрипт gototask вызывает `sourcegraph-local/sync-index.sh`.

| Action | Индекс |
|---|---|
| `inspect` | не трогает |
| `export-task` | не трогает |
| `checkout` | да |
| `create-branch` | да |
| `merge-release` | да (в т.ч. при конфликтах после checkout ветки) |
| `sync` | да |

Реализация:

| Где | Что |
|---|---|
| `.cursor/skills/task-router/children/gototask/scripts/gototask.ps1` | `Invoke-SourcegraphIndexSync` → `Write-ApplyJson` |
| `.codex/skills/task-router/children/gototask/scripts/gototask.ps1` | то же (через `.codex/go-task.ps1`) |
| Env при вызове | `WORKTREE=<repo>`, `REPO_NAME=testdeploydocker.git` (только это зеркало) |

`sync-index.sh` делает:

1. `sync-mirror.sh` с `SYNC_HEAD_TO_WORKTREE=1` - fetch веток из worktree, `HEAD` зеркала → текущая ветка.
2. `sync-after-commit.sh` - `POST /.api/repos/.../-/refresh` (очередь reindex).

В JSON ответа apply: поле `sourcegraphIndex` (`ok` / `skipped` / ошибка). Падение Sourcegraph **не** валит gototask (best-effort).

Zoekt обычно догоняет за 1-3 минуты после refresh.

---

## 3. Ручная синхронизация
<a id="3.-ручная-синхронизация"></a>
```bash
cd sourcegraph-local
./sync-index.sh

# или только CopyTrust:
<a id="или-только-copytrust:"></a>
WORKTREE=/home/newuser/projects/copytrust/testdeploydocker REPO_NAME=testdeploydocker.git ./sync-index.sh
```

После коммитов без gototask: `./sync-mirror.sh` затем `./sync-after-commit.sh`  
(без смены HEAD, если не нужен поиск именно по текущей ветке).

Запуск стека: `./start.sh` / `./ensure-up.sh` - детали в README.

---

## Связи
<a id="связи"></a>
- [CI/CD §6a локальный git push](./cicd.md#6a-локальный-git-push) - remotes и правило push; gototask не пушит сам
- [architecture.md](./architecture.md) - карта кода продукта (не локальный MCP)
- [local-dev-resources.md](./local-dev-resources.md) - ОЗУ стека (~1.5 ГБ), stop при тормозах WSL
- Операционка: [`sourcegraph-local/README.md`](../../sourcegraph-local/README.md)
- MCP IDE: [`.cursor/sourcegraph-mcp.md`](../../.cursor/sourcegraph-mcp.md), [`.codex/sourcegraph-mcp.md`](../../.codex/sourcegraph-mcp.md)
- Скил gototask: [`.cursor/skills/task-router/children/gototask/SKILL.md`](../../.cursor/skills/task-router/children/gototask/SKILL.md)

---

## Известные проблемы и ограничения
<a id="известные-проблемы-и-ограничения"></a>
- **Симптом:** MCP находит код/пути с прошлой задачи, worktree уже на другой ветке.
- **Причина:** bare `HEAD` и/или Zoekt не обновлены после checkout.
- **Решение:** gototask apply вызывает `sync-index.sh`; иначе вручную §3. Подождать 1-3 мин после refresh.
- **Файлы:** `sourcegraph-local/sync-index.sh`, `sourcegraph-local/sync-mirror.sh`, gototask `Invoke-SourcegraphIndexSync`

- **Симптом:** поиск по `task.md` / architecture пустой.
- **Причина:** зеркало - только git worktree репозитория; `.doc/tasks` не зеркалится как продукт-код для SG.
- **Решение:** Read / task-doc; не Sourcegraph.

- **Симптом:** в JSON apply `sourcegraphIndex.ok=false` или `skipped`.
- **Решение:** `sourcegraph-local/ensure-up.sh` / `bootstrap.sh`; gototask при этом уже переключил ветку.

- **Симптом:** `VmmemWSL` 10+ ГБ; Disk 100%; Cursor Remote отваливается.
- **Причина:** ~18 контейнеров (несколько Postgres + search/index); плюс другие стеки на той же WSL.
- **Решение:** останавливать SG когда MCP-поиск не нужен; нативный install без Docker почти не легче. Разбор: [local-dev-resources.md](./local-dev-resources.md).
- **Файлы:** `sourcegraph-local/` compose

---

## История изменений
<a id="история-изменений"></a>
- 2026-09-22: П-4 + ссылка на [local-dev-resources.md](./local-dev-resources.md) (аудит ОЗУ/диска)
- 2026-07-30: документ создан; gototask apply → `sync-index.sh` (зеркало + HEAD + reindex)
