# Эксплуатация MCP-платформы: память WSL2 и регламенты серверов

<!-- meta
type: architecture
status: actual
updated: 2026-11-01
related: [./04-mcp.md, ./01-canon-envs.md, ../mcp/README.md, ../../architecture/local-dev-resources.md, ../archive/mcp/sourcegraph-local.md]
tags: [harness, mcp, cbm, wsl, memory, runbook]
-->

---

## Суть

Текущая реализация общего HTTP-стека (systemd-юниты, порты, лимиты, перенос):
[15-mcp-stack.md](./15-mcp-stack.md).

> **Legacy (2026-10-29):** MCP `sourcegraph` выключен в каноне. Правила Zoekt ниже
> относятся к опциональному стеку; агентский маршрут - codegraph и `multi-search.sh`.

Операционный runbook dev-окружения MCP: системные настройки WSL2, профиль памяти и
причины падений. Регламенты отдельных серверов (CBM, Sourcegraph, Serena) перенесены
в `.doc/harnes/mcp/`, здесь остались ссылки.
Перенесен из `.doc/supermsp.md` 2026-10-02 без изменений содержания.
Пересечения (не дублируются, читать там): картина памяти и стек проектов -
`architecture/local-dev-resources.md`; устройство SG-стека -
`architecture/sourcegraph-local.md`; список MCP-серверов скилов - [04-mcp.md](./04-mcp.md).

Данный документ описывает причины падений WSL2 из-за перегрузки памяти, профиль потребления и системные настройки для стабильной работы контейнеров и серверов. Регламенты CBM, Sourcegraph и Serena перенесены в `.doc/harnes/mcp/` и здесь не дублируются.

---

## 1. Диагностика инцидента: почему падал WSL2

### Точная техническая причина сбоя
При анализе логов ядра Linux (`dmesg`) и состояния виртуальной машины Hyper-V были выявлены следующие ошибки:
```text
kworker/0:0: page allocation failure: order:7, mode:0xdc0(GFP_KERNEL|__GFP_ZERO)
Workqueue: hv_pri_chan vmbus_add_channel_work
...
WSL (SessionLeader) ERROR: UtilAcceptVsock:273: accept4 failed 110 (ETIMEDOUT)
systemd-journald: Under memory pressure, flushing caches.
```

1. **Исчерпание памяти WSL2**: процесс `vmmemWSL` в Windows был забит на **13.97 ГБ из 14.0 ГБ**. Внутри Ubuntu свободной памяти оставалось всего **121 МБ**.
2. **Фрагментация страниц памяти ядра**: драйвер шины Hyper-V (`vmbus_add_channel_work`) при сетевых операциях Docker-контейнеров и сессий VSCode/Cursor запросил непрерывный блок памяти порядка 7 (`order:7` = 128 страниц подряд = 512 КБ). Из-за сильнейшей фрагментации и нехватки страниц ядро выдало `page allocation failure`.
3. **Таймаут сокетов vsock**: внутренняя шина связи Windows и WSL2 зависла с ошибкой `110 (Connection timed out)`, что приводило к обрыву соединений, зависанию консоли и падению виртуальной машины.

---

## 2. Распределение памяти: До и После

| Компонент | До оптимизации | После оптимизации | Причина изменений |
|---|---|---|---|
| **`codebase-memory-mcp` (MCP)** | **6.35 ГБ RSS** (10.9 ГБ VSZ) | **~300-600 МБ** | Исключены ворктри `.kilo`, дампы `.doc`, тяжелые JS/CSS |
| **`cbm-ui` (веб-интерфейс в tmux)** | **~7.0 ГБ** (бюджет) | **0 МБ** (отключен) | Убран автозапуск дублирующего процесса |
| **База графа проекта (.db)** | **613 МБ** | **~40-70 МБ** | Очищена от мусора и пересоздана с `.cbmignore` |
| **Docker-стеки (~25 контейнеров)** | ~2.5-3.0 ГБ | ~2.5-3.0 ГБ | Sourcegraph, Assignment, Qdrant стабильны |
| **Доступная свободная память WSL** | **121 МБ** (критическая зона) | **7.5 ГБ** (стабильная зона) | Запас под сборку, тесты и сетевые операции |

---

## 3. Веб-интерфейс `cbm-ui` (порт 9749)

Перенесено в [mcp/codebase-memory-mcp.md](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md), раздел
Веб-интерфейс cbm-ui. Там причина отключения автозапуска, формула бюджета памяти,
команды включения и остановки.

Коротко: UI нужен только человеку, агенты работают по MCP. Автозапуск отключен,
потому что каждый экземпляр резервирует `budget_mb = total_ram / 2`.

---

## 4. Файл исключений `.cbmignore`

Перенесено в [mcp/codebase-memory-mcp.md](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md), раздел
Что попадает в индекс. Там причина проблемы, источники исключений и влияние на
бюджет памяти.

---

## 5. Чек-лист: Что делать при подключении нового проекта

Шаги по CBM (`.cbmignore`, скрытие файла от git, проверка лаунчера, очистка
старой базы) перенесены в
[mcp/codebase-memory-mcp.md](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md), раздел Установка и перенос.
Общая процедура подключения проекта к HTTP-стеку остается в
[15-mcp-stack.md](./15-mcp-stack.md), раздел 6.

---

## 6. Что насчет Sourcegraph?

MCP-сервер выключен, правила зеркала и `.gitattributes` перенесены в
[mcp/sourcegraph.md](../archive/mcp/sourcegraph.md), раздел Зеркало и индексация.
Устройство стека: [sourcegraph-local.md](../archive/mcp/sourcegraph-local.md).

---

## 7. Системные настройки Windows и WSL2 (применены глобально)

### 1. `C:\Users\NewUser\.wslconfig` (Windows)
```ini
[wsl2]
# 2026-10-21: снижено с 14GB, применяется после wsl --shutdown
memory=12GB
processors=8
swap=8GB

# Автоматический возврат свободной памяти в Windows
autoMemoryReclaim=gradual
pageReporting=true

# Сеть
networkingMode=mirrored
dnsTunneling=true
autoProxy=true

[experimental]
sparseVhd=true
```

### 2. `/etc/sysctl.d/99-wsl-memory.conf` (WSL Ubuntu)
Защита ядра от нехватки непрерывных блоков памяти (`order:7 page allocation failure`):
```ini
vm.min_free_kbytes = 131072
vm.vfs_cache_pressure = 150
```
- `vm.min_free_kbytes = 131072` (128 МБ) - гарантированный резерв для сетевых драйверов Hyper-V VMBus и Docker veth-мостов.
- `vm.vfs_cache_pressure = 150` - своевременный сброс кэшей структур файловой системы при активной дисковой работе.
---

## 8. Профиль потребления памяти при всех активных стеках (Sourcegraph + Assignment)

В боевом режиме, когда разработчик активно использует **Sourcegraph** и сопутствующие сервисы:

### Реальное распределение памяти (~7-9.5 ГБ в Диспетчере задач Windows):
1. **Чистая память процессов (~6.5-7.0 ГБ)**:
   - **Стек Sourcegraph (18 контейнеров)**: ~1.5-2.0 ГБ (Zoekt web/indexer, Syntect, Postgres, Gitserver, Frontend, Worker). В `docker-compose.override.yaml` уже отключена Observability (`prometheus`, `grafana`, `cadvisor`), что экономит 1.5-2 ГБ.
   - **5 серверов баз данных**: ~1.3 ГБ (2x MySQL 8.4 по ~450 МБ, 3x Postgres 16 по ~150 МБ, 3x Redis, Qdrant).
   - **Приложения и веб-серверы**: ~0.5 ГБ (Assignment PHP, Nginx, Caddy).
   - **Инфраструктура**: ~2.0 ГБ (VS Code / Cursor Remote сервер, демоны Docker Desktop, ядро Linux).
   - **codebase-memory-mcp**: ~0.3-0.5 ГБ (благодаря `.cbmignore` больше не раздувается).

2. **Дисковый кэш ядра Linux (`buff/cache`, ~2.0-2.5 ГБ)**:
   - При активных поисковых запросах Sourcegraph и работе Docker слои образов и файлы индексов оседают в page cache. Из-за этого `VmmemWSL` в Windows колеблется в районе **7.0-9.5 ГБ**.
   - Внутри WSL сохраняется стабильный гарантированный запас в **4.5-7.0 ГБ** (до потолка в 14 ГБ).

### Выбранная политика возврата памяти: `autoMemoryReclaim=gradual`
В `.wslconfig` оставлен режим:
```ini
autoMemoryReclaim=gradual
```
- **Почему именно gradual:** при этом режиме WSL мягко отдает неиспользуемые страницы обратно Windows во время пауз в работе, при этом **сохраняет кэши в оперативной памяти**, что обеспечивает мгновенный поиск в Sourcegraph и быстрый отклик баз данных без постоянного перечитывания диска.
- **Опция на будущее (если на хосте Windows экстренно понадобится еще 2-3 ГБ):**  
  Можно заменить на `autoMemoryReclaim=dropcache`. В этом режиме WSL будет агрессивно сбрасывать дисковый кэш, прижимая `VmmemWSL` строго к отметке ~6.5-7.0 ГБ.

---

## 9. Один Serena на проект (2026-10-21)

Разбор инцидента, причина рекурсии через симлинк, замеры CPU и памяти, команды
проверки перенесены в [mcp/serena.md](../../../.agents/skills/serena/docs/mcp/serena.md), раздел Эксплуатация.
Общая схема юнитов: [15-mcp-stack.md](./15-mcp-stack.md).

---

## Известные проблемы и ограничения

- **Симптом:** WSL2 падает, в dmesg `page allocation failure`, Cursor выдает `E_UNEXPECTED`.
- **Причина:** лимит памяти, `swap=0` или одновременная работа нескольких тяжелых стеков.
- **Решение:** §7, `memory=12GB` (с 2026-10-21, до этого 14 ГБ), `swap=8GB`, `vm.min_free_kbytes=131072`.
- **Файлы:** `%UserProfile%\.wslconfig`, `/etc/sysctl.d/99-wsl-memory.conf`

Проблемы отдельных серверов перенесены в их файлы:
[codebase-memory-mcp.md](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md),
[serena.md](../../../.agents/skills/serena/docs/mcp/serena.md), [sourcegraph.md](../archive/mcp/sourcegraph.md).

---

## Связи

- local-dev-resources.md (проект Target) - картина памяти, стеки Docker, §8 общий Serena, §12 зависания платформы и сбросы NVMe
- [01-canon-envs.md](./01-canon-envs.md) - канон `.cursor/` и адаптеры
- [04-mcp.md](./04-mcp.md) - список MCP-серверов и порядок вызовов
- [mcp/README.md](../archive/mcp/README.md) - документы по каждому серверу
- [mcp/codebase-memory-mcp.md](../../../.agents/skills/codebase-memory-mcp/docs/mcp/codebase-memory-mcp.md) - регламент CBM
- [mcp/serena.md](../../../.agents/skills/serena/docs/mcp/serena.md) - инцидент и один процесс на проект
- [sourcegraph-local.md](../archive/mcp/sourcegraph-local.md) - устройство Sourcegraph

---

## История изменений

- 2026-10-02: runbook перенесён из `.doc/supermsp.md`.
- 2026-10-21: разобран повторный перегруз WSL после установки DSH; Serena переведена на один HTTP-сервер на проект, `/.dsh/` добавлен в `.cbmignore`. Удалён самоссылающийся симлинк `sourcegraph-local/repos/testdeploydocker`, из-за которого Intelephense не завершал индексацию. Удалены старые образы Docker и build cache (38 ГБ), `git gc` сократил `.git` до 386 МБ, в `.wslconfig` записано `memory=12GB`. Добавлена разбивка памяти по редакторам и MCP: `local-dev-resources.md` §10.
- 2026-11-01: регламент CBM, правила Sourcegraph и инцидент Serena перенесены в `.doc/harnes/mcp/`, здесь остались WSL2 и общая картина памяти
- 2026-11-01: добавлена ссылка на `local-dev-resources.md` §12, где собраны зависания платформы, синхронные сбросы NVMe, USB, GPU и NDIS, внесённые правки питания и порядок дальнейшей проверки
