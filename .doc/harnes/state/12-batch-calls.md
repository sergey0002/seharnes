# Пакетные вызовы: правило batch-calls и скрипты multi-search / multi-exec

<!-- meta
type: architecture
status: actual
updated: 2026-10-02
related: [../index.md, ./03-rules.md, ./05-scripts.md, ./04-mcp.md, ./08-plan-contour.md, ./07-workflows.md, ../doc_rules.md]
tags: [harness, batch, tokens, scripts, rules]
-->

---

## Суть

Каждый вызов инструмента заново шлет весь накопленный контекст. Серия из N вызовов подряд стоит N пересылок, пачка тех же операций - 1 вызов. Встроенные `grep`/`read` не идут через CodeMode `execute` (только MCP-инструменты), флаг `experimental.batch_tool` лишь разрешает модели слать несколько вызовов в одном блоке, но не заставляет. Поэтому пачки закрыты двумя скриптами в каноне `.tools/scripts/` и одним правилом `.cursor/rules/batch-calls.mdc`. Код в git ищут Serena/codegraph/CBM (уже пакуются через `execute` + `Promise.all`), документацию и задачи в `.doc/` - `multi-search.sh`, любые независимые команды и чтения - `multi-exec.sh`. Внедрено 2026-10-02 через `harness-improvement`. Реестр: 29 компонентов (новое правило `rule-batch-calls`), рулесов 15, скриптов `.tools/scripts` 14 файлов.

> **AI:** читай этот doc если задача требует 2+ независимых поиска, чтения файлов задачи, git-тройку, линт-серию или массовый поиск по `.doc/`. Триггер: 3+ независимых вызова - обертка обязательна. Правки (`edit`/`apply_patch`/`write`), зависимые цепочки и долгие команды не паковать.

---

## 1. Проблема и evidence

Сессия `ses_f029452d` ("Актуализация входа по Yandex ID"): `read` 60, `grep` 55, `bash` 30, `execute` 0. Скрин пользователя: 15 строк `Grep` / `Чтение` по одному результату - последовательные вызовы, не пакет. Паузы между вызовами 20-300 секунд. CodeMode (`execute`) в базе: 110 вызовов, пакетных только 18, покрывает только MCP.

Полная картина пачек из `kilo.db` (127 сессий, 13534 вызовов):

| Пара подряд | Пар | Что внутри |
|---|---|---|
| `bash -> bash` | 3842 | `grep` через bash 716, `cd` 627, `python3 -c` 260+, `sed` 193, `jsondoc.py` 190, `git status` 147, аудит-запросы 114, `powershell` 100 |
| `read -> read` | 2159 | `tasks/*` 832, `*.php` 781, `*.md` 627, `architecture/*` 167 |
| `read <-> grep` | 347 + 343 | Чтение затем уточняющий поиск и наоборот |
| `read -> bash` / `bash -> read` | 628 + 627 | Чтение затем команда и наоборот |
| `grep -> grep` | 334 | Поиск по `.doc/` и `lib/` |
| `edit -> edit` | 515 | Правки, multi-file серий 39 против same-file 25 |
| `apply_patch -> apply_patch` | 166 | Аналогично edit |
| `glob -> read` | 128 | Найти файл затем прочитать |
| `bash -> todowrite` | 219 | Команда затем фиксация статуса |
| `edit -> bash` / `bash -> edit` | 243 / 166 | Правка затем проверка и наоборот |
| `read -> edit` | 122 | Чтение затем правка |

Вывод: паковать нужно не только grep. Кандидаты: независимые чтения, git-тройки, `php -l` серии, `jsondoc get` серии, `glob+read`. Не паковать: правки (зависят от прочитанного), зависимые цепочки (второй шаг читает вывод первого), долгие команды (стенд, тесты, вотчеры). Внешний MCP под батч не создавался: свой каталог в контексте и лишний хоп дороже выгоды.

---

## 2. Правило batch-calls

Канон: [`.cursor/rules/batch-calls.mdc`](../../../.cursor/rules/batch-calls.mdc). Зеркала в 3 средах через `sync-agent-views.sh`. Permissions не меняются, только софт-инструкция, без `deny`.

Триггеры: 2+ независимых поиска или чтения. 2+ независимых read-only команд.

Пакуй:

- 3+ поисков по `.doc/` или задачам: один вызов `multi-search.sh`.
- Открытие задачи (`task.md` + `doc.md` + `diff.files.md` + `plan.md`): один вызов `multi-exec.sh` с четырьмя `--read`.
- Чтения с офсетом (2+ файла): один вызов `multi-exec.sh` через `--read "id=x :: path +offset limit"`. Срезы считает скрипт.
- Git-тройка (`status` + `log` + `diff --stat`): один вызов `multi-exec.sh`.
- Линт-серия (`php -l` по N файлам): один `for` в `multi-exec.sh`.
- 3+ поисков по коду в git: один `execute` с `Promise.all` по `serena`/`codegraph` или один `bash` с `rg --json`.
- MCP-вызовы без зависимости: несколько в одном блоке ответа.

Не пакуй: правки (`edit`, `apply_patch`, `write`); зависимые цепочки (`grep->read`, `read->edit`, `glob->read` с неизвестным именем); долгие команды и необратимые записи (`push`, миграции `down()`).

Пороги: 1-2 независимых вызова - обычные инструменты; 3+ - обертка обязательна; dependent приоритетнее batch.

Точки интеграции (внесены по одной строке, без рерайта скилов): `prepare-plan` P1.1 (лестница blast-radius), `task-doc` B2.5/B2.6 (Reuse/Impact Gate), `bitbucket-tasks` порядок чтения (пункты 2-5 одной пачкой), `test-priority` режим этапа (`php -l` одной пачкой).

---

## 3. Скрипт multi-search.sh

Канон: [`.tools/scripts/multi-search.sh`](../../../.tools/scripts/multi-search.sh) (+ `.ps1` обертка для Windows). Один проход `rg` с alternation, наружу JSON-lines. Вызов через существующий `bash`, новый MCP не нужен. Зависимости: `rg` 14.1.1 в `~/.local/bin` (поставлен без sudo статическим musl-бинарником), fallback на `grep -rn` с пометкой в stderr при отсутствии `rg`.

CLI:

```bash
.tools/scripts/multi-search.sh \
  --root .doc/tasks \
  --pattern "2233" --pattern "Yandex" \
  --include "task.md" --include "doc.md" --include "plan.md" \
  --max-per-file 5 --max-total 100 --context 0 --truncate 300
```

| Параметр | Дефолт | Назначение |
|---|---|---|
| `--root` | обязательный | Корень поиска. Корень репо без `--include` запрещен (защита от `vendor/` и стенда) |
| `--pattern` | 1+, обязательный | Повторяемый, внутри один проход с alternation |
| `--include` | `*` | Повторяемый glob, маппится в `-g` флаги `rg` |
| `--max-per-file` | 5 | Совпадений на файл |
| `--max-total` | 100 | Общий лимит строк |
| `--context` | 0 | Строк контекста (`-C`) |
| `--truncate` | 300 | Обрезка строки с маркером `...[cut]` |

Исключения: уважать `.gitignore`, пропуск бинарников, пропуск `.tools/codeception/` при широком корне.

Выходной контракт: одна строка - один JSON `{"file","line","match"}`, в конце `_meta` (`patterns`, `files`, `shown`, `skipped`, `truncated`). Только JSON-lines в stdout, диагностика в stderr. Пути относительные от корня репо. Exit: 0 есть совпадения, 1 нет, 2 ошибка аргументов. Сортировка по файлу и строке.

Примеры:

```bash
# Поиск по архитектуре
.tools/scripts/multi-search.sh --root .doc/architecture \
  --pattern "oauth" --pattern "remember_me" --include "*.md" --max-per-file 3

# Поиск по задачам (то чего нет в SG-зеркале)
.tools/scripts/multi-search.sh --root .doc/tasks \
  --pattern "2233" --pattern "Yandex" --include "task.md" --include "doc.md" --include "plan.md"
```

---

## 4. Скрипт multi-exec.sh

Канон: [`.tools/scripts/multi-exec.sh`](../../../.tools/scripts/multi-exec.sh) (+ `.ps1` обертка). Пакетный запуск N команд и чтений одним вызовом bash. Зависимости: `bash` + `timeout` (coreutils) + `python3` (сборка JSON). Authority не расширяется: `bash` и так умеет все, скрипт только упаковывает вывод.

CLI:

```bash
.tools/scripts/multi-exec.sh \
  --cmd "id=lint1 :: php -l lib/Objects/Oauth/OauthController.php" \
  --cmd "id=git1 :: git log --oneline -5 -- lib/Objects/Oauth/" \
  --read "id=a :: lib/Objects/Oauth/OauthController.php +445 25" \
  --mode sequential --timeout 60 --max-output 20000 --truncate 2000
```

| Параметр | Дефолт | Назначение |
|---|---|---|
| `--input` | - | JSON-файл: массив `{id, cmd, cwd?, timeout?}` или `{id, file, offset?, limit?}`, смешивать можно |
| `--cmd` | - | Повторяемый `id=xxx :: команда`, для коротких пачек без файла |
| `--read` | - | Повторяемый `id=xxx :: path [+offset] [limit]`. Срез считает скрипт (`wc -l` + `sed -n`), модель арифметику не делает |
| `--mode` | `sequential` | `parallel` только для read-only allowlist: rg, grep без `-r/-R`, `git log/diff/show/blame/status`, `php -l/-m/--version`, `ls/cat/head/tail/wc/file/stat`, `jsondoc.py get/batch`, read-only `python3 -c`. Запрещены: edit, write, `git commit/push`, `docker exec` |
| `--timeout` | 60 | Секунд на команду через `timeout`; превышение - `{exit: 124, timeout: true}`, батч продолжается |
| `--max-output` | 20000 | Байт на весь stdout батча, дальше срез с `_meta.truncated: true` |
| `--truncate` | 2000 | Байт на stdout/stderr одной команды с маркером `...[cut]` |

Валидация (exit 2): пустой `cmd`, дубли `id`, `--mode parallel` вне allowlist.

Выходной контракт. Команда: `{"id","exit","ms","stdout","stderr","truncated","timeout"}`. Чтение: `{"id","exit","ms","file","offset","limit","total_lines","lines":[{"n","t"}],"eof"}`. Дефолты чтения: offset=1, limit=100. Whole-file чтение (offset=1, срез до конца) добавляет `content_hash` (`sha256:`) - prepare-plan сверяет с `research-ledger.json` и пропускает повторный Read на re-audit. Ошибки чтения в JSON команды, батч продолжается: нет файла - `{exit: 1, error: "not found"}`, offset за EOF - `{exit: 1, error: "offset beyond EOF", total_lines}`. Финальная строка: `{"_meta":{"total","failed","timeout","ms","truncated"}}`. Exit скрипта: 0 все ok, 1 хотя бы одна команда упала (JSON полный), 2 ошибка батча. Порядок детерминированный, как в input.

Готовые пачки:

| Пачка | Состав | Выгода |
|---|---|---|
| Открытие задачи | 4 файла через `--read` | 4 round-trip в 1 |
| Git-тройка | `status` + `log` + `diff --stat` | 3 вызова в 1 |
| Линт-серия | `for f in ...; do php -l $f; done` | N вызовов в 1 |
| jsondoc-серия | предпочитать встроенный `jsondoc.py batch --input`; `multi-exec` только в смеси с git/lint | N `get` в 1 |
| glob+read | `for f in pattern; do head` | Пара `glob->read` закрыта |
| Чтения с офсетом | N файлов через `--read` | N `read` в 1 |
| Whole-file чтения | N файлов до 300 строк через `--read` без offset | Содержимое не режется, экономия round-trip |

Примеры:

```bash
# Открытие задачи
.tools/scripts/multi-exec.sh \
  --read "id=task :: .doc/tasks/2233/task.md" \
  --read "id=doc :: .doc/tasks/2233/doc.md" \
  --read "id=files :: .doc/tasks/2233/diff.files.md" \
  --read "id=plan :: .doc/tasks/2233/plan.md"

# Чтения с офсетом (кейс со скрина: 15 отдельных Grep/Чтение)
.tools/scripts/multi-exec.sh \
  --read "id=a :: lib/Objects/Oauth/OauthController.php +445 25" \
  --read "id=b :: templates/m_login_redirect.tpl +1 100" \
  --read "id=c :: lib/Objects/PersonProfile.php +1 100" \
  --truncate 2000

# Git-тройка
.tools/scripts/multi-exec.sh \
  --cmd "id=st :: git status --short" \
  --cmd "id=log :: git log --oneline -5 -- lib/Objects/Oauth/" \
  --cmd "id=stat :: git diff --stat" --truncate 3000
```

---

## 5. Карта инструментов: что чем искать

| Зона | Инструмент | Почему |
|---|---|---|
| Код в git (`lib/`, `app/`, `admin/`, `scripts/`) | `serena`, затем `codegraph`, затем CBM; литералы через `multi-search.sh` | Символы и индекс; эти вызовы уже пакуются через `execute` + `Promise.all` |
| Документация `.doc/architecture/`, `.doc/harnes/`, `.doc/qa/` | `multi-search.sh` | Нет в SG-зеркале полностью, Serena покрытие слабое |
| Задачи `.doc/tasks/{N}/` | `multi-search.sh` (полнотекст), `find-related-tasks.ps1` (связь файл-задачи) | `.doc/tasks/` вне графа, только файловый поиск |
| Точечный поиск (1 паттерн, 1 файл) | Обычный `grep` / `read` | Обертка не окупается |
| Массовый поиск по коду (5+ паттернов) | `execute` + `Promise.all` по `serena`/`codegraph` или `bash` с `rg --json` | Встроенный `grep` не пакуется |

Гейт: 1-2 независимых поиска - обычные инструменты; 3+ по `.doc/` - `multi-search.sh`; 3+ по коду - `execute` пачкой; зависимые поиски - последовательно.

---

## 6. Экономика: точный расчет по истории

Источник: `/home/newuser/.local/share/kilo/kilo.db`, таблицы `session` (131 сессия) и `part` (196097 записей). Расчет 2026-10-02.

База: всего input 175728083 токенов, tool-запросов (distinct message_id) 9743, средний input на запрос 18036 токенов. Топ-сессия `ses_f029452d`: input 20118329 / output 23367 (ratio 861x) - почти весь input это пересылка контекста. Доля топ-5 сессий 34.3%.

Модель: каждый tool-запрос несет весь контекст. Серия длиной L стоит L пересылок, пачка - 1 вызов + 1 ответ. Экономия серии: `(L - 1) * средний_контекст - накладные` (вызов bash ~200 токенов + ~10% JSON-обертка, для серий 3+ пренебрежимо).

Серии длиной 3+: read 413 (1686 операций, средняя 4.1), grep 42 (146, 3.5), bash 128 (436, 3.4), glob 20 (69, 3.5). Итого 2337 операций в 603 сериях. Снятых пересылок 1734. Экономия: 1734 * 18036 = 31274424 токена, 17.8% общего input (верхняя граница). Консервативно с поправкой 0.5: 8-9%.

Тариф пользователя: cache_read 0.5 от input, input равен output. Средний запрос: input 18051 + cache 179160 + output 483, стоимость 108114 условных единиц, доля cache 82.9%. Экономия в деньгах совпадает с экономией в токенах (17.8%): cache доминирует везде одинаково, вес 0.5 сокращает числитель и знаменатель пропорционально.

Важно: 1 вызов НЕ в 10 раз экономнее чем 10 по отдельности. Серия длиной 10 стоит 10 пересылок растущего контекста, пачка снимает 9 пересылок (самые дорогие хвостовые). Экономия серии длиной 10: 60-70% ее стоимости, не 90% - первый запрос и возврат всех результатов платятся в обоих вариантах.

Топ-сессия при полных пачках: снято ~52 пересылки из 165 messages (31% шагов, 6.3M токенов, 31.5% ее input).

Итог: батчинг закрывает 8-18% общего input и до 31% в тяжелых сериях.

---

## 7. Дополнительные резервы (вне батчинга)

Все цифры - точные подсчеты по базе 2026-10-02, не оценки.

| Резерв | Факт | Оценка input | Статус |
|---|---|---|---|
| S1 повторные чтения | 931 лишняя read из 3730 (25.0%). 931 * 18036 = 16791516 токенов пересылок | до 9.6% | Частично закрыт: `content_hash` в контракте 5.3, правило сверки с ledger. Остаток: строка в prepare-plan P2.2 "файл с тем же хешем не читать" |
| S2 skill-контекст | 218 вызовов, средний 17591 символов (~4400 токенов). Топ: prepare-plan 30, gototask 23 | 3-5% ориентир | Не внедрен: нужен отдельный замер вклада в топ-5 сессий, затем разбивка крупных SKILL.md на lazy-секции (отдельный план) |
| S3 git-однострочники | 191 одиночный git из 5605 bash (без `;` и `&&`). 191 * 18036 = 3444876 токенов | ~1% остаток | Частично закрыт git-тройкой этого документа. Остаток: правило "одиночный git read-only всегда в пачке" |
| S4 grep-переполнение | 161 вывод больше 5K из 964 grep (16.7%), средний grep 1388 символов | 1-2% | Частично закрыт лимитами по умолчанию. Остаток: запрет голого grep по корню без `--include` уже в скрипте, добавить AC12 в будущие прогоны |
| S5 мелкие правки | 757 правок меньше 200 символов из 1358 (55.7%). Паковать нельзя (зависимости, раздел 4) | косвенно | Наблюдение для prepare-plan: edit-серии 3+ по одному файлу - признак неточного плана |

Суммарный потенциал всех резервов: 25-35% общего input. Приоритет: батчинг (внедрен здесь), затем S1 (дешево, content_hash готов), затем S4 (одна строка в правиле), затем S2 (дорого, отдельный план).

---

## 8. Внедрение: что сделано

Внедрено 2026-10-02 через `harness-improvement` (preflight: `batch-calls` новый, история пустая - expected; архив partial, 1 legacy MD-only).

Создано в каноне: `multi-search.sh` + `.ps1`, `multi-exec.sh` + `.ps1` (chmod +x, LF), `batch-calls.mdc`, запись `rule-batch-calls` в `component_registry.json` (29 компонентов). По ходу внедрения: поставлен `rg` 14.1.1 в `~/.local/bin` без sudo (статический musl-бинарник, grep fallback оставлен), починен `validate_rules.py` (не резолвил `.tools/scripts/`, `missing_script_reference` 5 - 0), внесены точечные строки в 4 файла (`prepare-plan` P1.1, `task-doc` B2.5/B2.6, `bitbucket-tasks` порядок чтения, `test-priority` режим этапа).

Проверки: `validate_registry.py` passed, `validate_rules.py` passed (36 rules, 26 skills, issues только info), `sync-agent-views.sh` passed (3 зеркала, свежий canon_hash), `verify_parity.py` passed 3 вью без ошибок. Ручные прогоны AC1-AC7 passed: 5 паттернов одним вызовом, срез `_meta`, exit 1/2, открытие задачи 4 файла, 5 чтений с верными номерами строк, дубли id и parallel вне allowlist отклонены, упавшая команда дает exit 1 батча при полном JSON.

Продукт, чужие правки, commit/push не затрагивались.

Известные ограничения: софт-правило не гарантирует поведение модели, жесткий `deny` ломает базовый контур; `rg` вне PATH шторки без `~/.local/bin`; повторные чтения S1 и разбивка скилов S2 - отдельные работы.

---

## Связи

- Канон правила: [`.cursor/rules/batch-calls.mdc`](../../../.cursor/rules/batch-calls.mdc) - единственный источник текста правила
- Канон скриптов: [`.tools/scripts/multi-search.sh`](../../../.tools/scripts/multi-search.sh), [`multi-exec.sh`](../../../.tools/scripts/multi-exec.sh) - единственный источник реализации
- [Точка входа](../index.md) - таблицы state/ и plan/
- [Рулесы канона](./03-rules.md) - строка `batch-calls` в составе 15
- [Скрипты контуров](./05-scripts.md) - строки `multi-search` / `multi-exec` в составе 16
- [MCP](./04-mcp.md) - массовый поиск по `.doc/` идет скриптом, не MCP
- [Контур планирования](./08-plan-contour.md) - P1.1 пачки Tier-поисков
- [Схемы взаимодействия](./07-workflows.md) - где пачки встают в жизненный цикл
- [Правила документации](../doc_rules.md) - стандарт `.doc/`

---

## История изменений

- 2026-10-02: внедрено через harness-improvement (скрипты, правило, реестр 29, синк 5 зеркал, parity passed, AC1-AC7 passed). Предшественники: `plan/massgrep.md` (спецификация, экономика разделы 9-10), `plan/massgrep-audit.md` (gaps G1-G12), `plan/massgrep-audit-summary.md` (сводка) - консолидированы в этот документ, файлы планов удалены.
