# Сервис панели и харнес-миррора (copytrust-tools)

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [../index.md, ../../web/README.md, ../../web/changelog.md, ../../rebase_project.md, ../component-install.md, ./16-task-analytics.md, ./19-harness-mirror.md]
tags: [harness, panel, service, jobs, pricing, providers, transfer]
-->

---

## Суть

`copytrust-tools` это один PHP-сервис на `http://127.0.0.1:8077`. Он отдаёт панель задач, документацию, аналитику диалогов, просмотрщик харнес-миррора и запускает разрешённые консольные скрипты по кнопкам. Отдельный Python-сервер на 8090 и `harness-mirror.service` больше не используются.

Код сервиса лежит в `.doc/web` и переносится вместе с kit. Состояние, локальные адаптеры и образ создаются на целевой машине. Данные задач, диалогов и графа харнеса не переписываются при переносе.

---

## 1. Состав и рантайм

| Объект | Значение |
|---|---|
| Порт | `127.0.0.1:8077`, только loopback |
| Образ | `copytrust-tools:local` из `.doc/web/Dockerfile.tools` |
| База образа | `php:8.4-cli` |
| Интерпретаторы | `python3`, `bash`, `pwsh`, `git` |
| Без чего работает | без node, CBM, CodeGraph и второго веб-сервера |
| Исходники | `.doc/web` |
| Рабочая область | корень проекта, монтируется в контейнер по тому же абсолютному пути |
| Состояние | `.doc/web/state` |
| Граф харнеса | `.cursor/.state/harness-mirror` |
| Kilo DB | `/host-kilo/kilo.db`, только чтение |
| Старый просмотрщик | 8090 остановлен, `harness-mirror.service` отключён |

Файлы запуска: [compose.tools.yml](../../web/compose.tools.yml), [start.sh](../../web/start.sh), [stop.sh](../../web/stop.sh), [service.json](../../web/config/service.json).

`install.sh --project` создаёт `state`, `.env`, `ADAPTERS.local.md` и выставляет профиль `core` или `full`. `.env` хранит `SERVICE_WORKSPACE`, `HOST_UID`, `HOST_GID`, `KILO_DATA_DIR`, `WEB_PANEL_PORT`.

---

## 2. Маршруты

| Маршрут | Назначение |
|---|---|
| `/` | список задач и правое меню |
| `/task/{N}` | страница задачи |
| `/docs` | архитектурная документация |
| `/analytics` и `?tab=analytics` | аналитика диалогов |
| `/files/...` | статика `.doc`, только чтение |
| `/harness/` | просмотрщик харнес-миррора |
| `/harness/graph.json` | граф |
| `/harness/nodes/*.json` | узлы |
| `/harness/api/health` | статус и `writable` |
| `/harness/api/node?id=...` | `GET` узла, `PUT` сохранения |
| `/harness/api/rebuild` | пересборка графа |
| `/jobs` | `POST` запуск, `GET` последние задания |
| `/jobs/status?id=...` | статус, прогресс, хвост лога |
| `/jobs/cancel` | отмена задания |

Внутренние каталоги `/bin/` и `/config/` наружу не отдаются. Пути статики проверяются через `realpath` и containment.

---

## 3. Действия и задания

Реестр: [actions.json](../../web/config/actions.json), схема: [actions.schema.json](../../web/config/actions.schema.json). Локальные дополнения: `config/actions.local.json`, не переносятся.

| Действие | Команда | Пишет |
|---|---|---|
| `analytics_scan` | `task-analytics.py scan --allow-partial` | `.doc/tasks/*/dialogs`, `.doc/task-analytics/out` |
| `harness_build` | `harness_mirror.py rebuild` | `.doc/skil_data/mirror` |
| `harness_check` | `harness_mirror.py check` | ничего |
| `sync_views` | `sync-agent-views.sh` | `.codex`, `.kilo`, `.agents` |
| `task_diff` | `task-diff.ps1 -Task {task}` | `.doc/tasks/{N}` |

Правила запуска:

- argv собирается массивом, shell не используется;
- `cwd` по умолчанию корень проекта;
- окружение минимальное: `PROJECT_ROOT`, `TASK_ID`, `PATH`, `HOME`, `LANG`;
- на действие один lock, повторный запуск получает 409;
- задание выполняется отсоединённо, родительский запрос отвечает 202;
- лог ограничен 5 МБ и 200 строками в API, токены и пароли маскируются;
- таймаут завершает процесс, отмена пишет `cancelled`;
- прогресс берётся из маркеров `PROGRESS`, `[n/m]`, `шаг N из M` или `progress_regex`; без маркеров полоса неопределённая;
- `build-actions.py` собирает черновик реестра из `skill.json`, скрипты не изменяются.

Файлы: [jobs.php](../../web/app/jobs.php), [job-runner.php](../../web/bin/job-runner.php), [build-actions.py](../../web/bin/build-actions.py), [app.js](../../web/public/assets/app.js).

---

## 4. Харнес-миррор

Просмотрщик читает `.cursor/.state/harness-mirror`. Адреса `graph.json`, `nodes/`, `api/health`, `api/node` относительные, поэтому работают под `/harness/`.

Сохранение:

1. PHP проверяет `node_id`, каноничность и тип `rule` или `skill`.
2. `raw_file` пишется во временный файл в `state/tmp`.
3. Вызывается `harness_mirror.py set --node ID --file --content FILE`.
4. Затем `build` и `check`.
5. При ошибке возвращается 500, файл остаётся в истории `nodes/.history`.

Скрипты и зеркала через сохранение не редактируются. Прямая запись файлов из PHP запрещена.

Файлы: [harness.php](../../web/app/harness.php), [router.php](../../web/router.php).

---

## 5. Цены и провайдеры

Конфиг: [prices.json](../../web/config/prices.json). Локальные цены: `config/prices.local.json`, не переносятся. Шаблон: [prices.local.example.json](../../web/config/prices.local.example.json).

Для `ai-starimg-ru`:

- 30 000 000 внутренних токенов стоят 823.90 RUB;
- 1M внутренних токенов стоит 27.463333 RUB;
- коэффициент модели умножает вход, кэш и выход;
- кэш тарифицируется без скидки, `cached_discount: 1`;
- заполнено 44 модели;
- `codex-sale` и `kilo` описаны без цен: сессии видны, стоимость 0, ошибки нет.

Формула:

```text
стоимость = (вход + кэш + выход) * коэффициент * 0.000027463333
```

Примеры:

| Модель | Коэффициент | Цена за 1M, RUB |
|---|---:|---:|
| `deepseek-v4.1-flash` | 0.1 | 2.746333 |
| `gpt-6.1-sol` | 3 | 82.39 |
| `claude-opus-5-5` | 4 | 109.853333 |
| `glm-5.3` | 1.5 | 41.195 |
| `kimi-k2.8-preview` | 0.9 | 24.717 |

Провайдер берётся из `session.model.providerID` в `kilo.db`. База открывается через PDO только на чтение, `PRAGMA query_only`. Провайдер показывается в таблице сессий, в блоке `Провайдеры` и на странице диалога без задачи. Это провайдер последней модели сессии.

Если провайдер или модель не описаны, стоимость равна 0, ошибки нет.

Файлы: [pricing.php](../../web/app/pricing.php), [providers.php](../../web/app/providers.php).

---

## 6. Интерфейс и стоимость

| Элемент | Поведение |
|---|---|
| Таблица `Инструменты` | строка `bash` раскрывается, показывает CLI, токены и стоимость |
| Таблица `MCP` | строка сервера раскрывается, показывает инструменты, вызовы и стоимость |
| Стоимость MCP-инструмента | распределяется по числу вызовов внутри сервера |
| Блок `Bash` | удалён как дубль, команды остались в строке `bash` |
| Карточка задачи | стоимость выделена бейджем `.tcost` под токенами |
| Карточка диалога без задачи | стоимость в строке метрик |
| Таблица сессий | колонки `Провайдер` и `Стоимость` |
| Таблица моделей | стоимость в RUB |
| Таблица провайдеров | сессии, токены и стоимость в валюте провайдера |

Раскрытие работает мышью и клавиатурой (`Enter`, `Space`). Маркер строки меняется с `+` на `-`.

Файлы: [lib.php](../../web/app/lib.php), [index.php](../../web/public/index.php), [style.css](../../web/public/assets/style.css).

---

## 7. Переносимость

| Область | Full | Core | Примечание |
|---|---|---|---|
| `.doc/web` код | да | да | `web` в `$docDirs` |
| `.agents/skills/task-router/children/analytics` код | да | да | данные в `.doc/task-analytics/out` не переносятся |
| `actions.json` | да | да | task-группа скрыта в Core |
| `actions.local.json` | нет | нет | локальные дополнения |
| `prices.local.json` | нет | нет | локальные цены |
| `.doc/web/state` | нет | нет | задания и логи |
| `.env`, `ADAPTERS.local.md`, `*.log` | нет | нет | локальные значения |
| скрипты скилов | да | да | не изменяются, sha256 сверяется |
| python, php, pwsh | нет | нет | ставятся на Target |
| CBM, CodeGraph, node | нет | нет | вне сервиса |

Установка:

```bash
cd .doc/web
./install.sh --check
./install.sh --project
./start.sh
./verify.sh
```

`rebase_project.ps1 -RunSetup` вызывает `install.ps1 -Check` и `-Project`. Если проверка не прошла, компонент не считается установленным.

Канон переноса: [rebase_project.md](../../rebase_project.md), установка компонента: [component-install.md](../component-install.md).

---

## 8. Данные и проверки

Бэкап перед правками: `.doc/.backup/panel-service-2026-11-03/` с копиями `harness`, `task-analytics-out`, `web`, `tasks/{N}/dialogs`, манифестами `data.sha256`, `scripts.sha256`, `scripts-only.sha256` и `metrics.txt`.

Текущее состояние:

| Проверка | Результат |
|---|---|
| Сессии | 184, из них 91 в задачах, 93 без задачи |
| `task-analytics.py validate` | 0 ошибок |
| Граф харнеса | 795 узлов, 2222 связи |
| `harness_mirror.py check` | 775 узлов, 0 ошибок |
| Страницы панели | 200, предупреждений PHP 0 |
| AJAX `harness_check` | `ok`, прогресс и лог видны |
| Отмена задания | `cancelled`, следующий запуск проходит |
| Сохранение узла без изменения | sha256 совпал, история записана |
| `verify.sh` | 0 |
| `install.sh --check` | 0 |
| `selfcheck.py` | ok |
| `harness-selfcheck.sh` | 15 passed, 0 failed |
| Ссылки `.doc` | 0 ошибок |

Стоимость проверенной сессии `ses_e610e85adffetyEzpIP9A1Bvob`: 430.30 RUB, из них `gpt-6.1-sol` 418.2496 RUB и `deepseek-v4.1-flash` 12.0510 RUB. Задача 2612: 76.63 RUB, задача 2618: 129.19 RUB.

---

## Известные проблемы и ограничения

### П-1: Стоимость это оценка по локальным токенам

Панель считает по токенам из артефактов `task-analytics` и цене провайдера. Провайдерский лог может группировать запросы иначе, поэтому точная сумма для сессии может отличаться. Импорта экспорта логов провайдера пока нет.

### П-2: Пакет токенов задан как 30 000 000

В конфиге `balance.tokens: 30000000`, потому что при 300 000 сессия выходит около 42 973 RUB и не сходится с балансом. Если в кабинете провайдера 300 000, поменяйте `balance.tokens` на `300000`; цены пересчитаются.

### П-3: Провайдер сессии один

Провайдер берётся из последней модели сессии. При смене провайдера внутри диалога панель покажет последний, без разбивки по сообщениям.

### П-4: Один экземпляр на проект

Сервис обслуживает один `WORKSPACE_ROOT`. Несколько проектов требуют нескольких экземпляров или отдельного реестра рабочих областей.

### П-5: `php -S` не production

Встроенный сервер работает с воркерами, но задания запускаются отсоединённо. При росте нагрузки нужен PHP-FPM или Apache.

---

## Связи

- [Операционное описание панели](../../web/README.md) - маршруты, запуск, безопасность
- [Журнал изменений панели](../../web/changelog.md) - полный список правок
- [Перенос харнеса](../../rebase_project.md) - профили, исключения, must-check
- [Установка компонента](../component-install.md) - обязательные проверки
- [Анализ диалогов](./16-task-analytics.md) - источник токенов и метрик
- [Харнес-миррор](./19-harness-mirror.md) - устройство графа и зеркал
- [Цены](../../web/config/prices.json) - коэффициенты и стоимость

---

## История изменений

- 2026-11-11: пути действий приведены к `actions.json`: `analytics_scan` пишет в `.doc/task-analytics/out`, `harness_build` запускает `harness_mirror.py rebuild` и пишет в `.doc/skil_data/mirror`.
- 2026-11-03: документ перенесён в `state/22-panel-service.md` и переписан как описание реализованного сервиса. Зафиксированы один порт 8077, харнес-миррор без 8090, задания с AJAX, цены и провайдеры, стоимость сессий и задач, переносимость и проверки.
