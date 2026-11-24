# План: несколько источников задач и локальные задачи с префиксом 0_

<!-- meta
type: plan
status: draft
updated: 2026-11-03
related: [../audit/summ.md, ../10.md, ../state/02-skills.md, ../state/07-workflows.md, ../skill-format.md, ../index.md]
tags: [harness, tasks, local-task, providers, json-doc, panel, task-diff, task-doc]
-->

---

## Суть

План описывает, как добавить локальные задачи с идентификатором `0_N` и сохранить текущий workflow. Jira остаётся источником по умолчанию для чисто числового номера. Локальная задача создаётся вручную, получает уникальный номер с префиксом `0_` и проходит те же этапы планирования, реализации, тестирования, документирования и diff.

Главный инвариант: идентификатор задачи всегда номер, а не заголовок и не slug. Jira использует номер `2538`. Локальная задача использует номер `0_1`. Полный `task_id` уникален. Скилы `task-diff`, `task-doc`, `send-to-git` и переход к задаче работают с полным `task_id`, поэтому источник задачи для них не важен.

План не меняет продуктовый код и не внедряет новые скилы. Он фиксирует находки, контракты, точные правки по файлам, порядок внедрения и проверки.

---

## 1. Зафиксированные решения

| Решение | Значение |
|---|---|
| Основной источник | Jira |
| Переход по умолчанию | Чисто числовой номер `2538` или `CT-2538` идёт в Jira |
| Локальные задачи | Номер `0_1`, `0_2`, `0_3` |
| Идентификатор | Полный `task_id`: `2538` или `0_1` |
| Числовая часть | Обязательна у каждой задачи |
| Заголовок | Не является идентификатором |
| Уникальность | Полный `task_id` уникален; числовая часть уникальна внутри своего префикса |
| Комментарий | Пишется в задачу; для Jira может публиковаться через адаптер |
| Ветка локальной задачи | Не обязательна; при наличии `features/#0_1` или `bugfixes/#0_1` |
| Коммит | Начинается с `0_1` или `#0_1` для локальной задачи |

Если позже потребуется одна глобальная числовая последовательность для всех источников, локальный номер станет `0_<global_number>`. Это меняет только генератор номера, не контракт `task_id`.

---

## 2. Находки

### F1. JSONdoc требует только цифры

**Симптом:** задача `0_1` не может быть сохранена и прочитана через JSONdoc.

**Причина:** ключ задачи проверяется как `[0-9]+` в нескольких местах.

**Файлы:**

- `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/store.py:113` - `task_key_digits`;
- `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/contract.py:203` - `task_id_required`;
- `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/search.py:27` - `invalid_task_key`;
- `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/review.py:123` - `key.isdigit()`.

**Следствие:** без общей правки локальная задача существует только как папка с Markdown, но не как полноценная задача JSONdoc, панели и индекса.

### F2. Проверка идентичности ожидает CT-номер

**Симптом:** `task-identity.py` не находит локальную папку и сравнивает ключ с `CT-0_1`.

**Причина:** `task_dirs()` фильтрует `path.name.isdigit()`, а `expected_key` всегда равен `CT-{number}`.

**Файлы:**

- `.agents/skills/documentation-router/children/project-doc/scripts/task-identity.py:112-118`;
- `.agents/skills/documentation-router/children/project-doc/scripts/task-identity.py:147-152`.

**Следствие:** локальная задача не проходит identity gate, а проверка ветки требует номер внутри ветки без учёта префикса.

### F3. Индекс задач пропускает локальные папки

**Симптом:** задача `0_1` не появляется в `.doc/tasks/index.md` и `_map/file-to-tasks.tsv`.

**Причина:** фильтр `^\d+$` и заголовок `# Issue #\d+:`.

**Файлы:**

- `.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1:45` - заголовок;
- `.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1:84` - фильтр папок;
- `.agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1:111,149,163` - ссылки и фильтры.

**Следствие:** `prepare-plan` не увидит локальную задачу через индекс и `find-related-tasks`.

### F4. Панель принимает только цифровой ID

**Симптом:** локальная задача не видна в списке и не открывается по ссылке.

**Причина:** `valid_task_id` проверяет `^\d+$`, а страница задачи жёстко строит ссылку `CT-{id}` и блоки Jira.

**Файлы:**

- `.doc/web/app/lib.php:66-68` - `valid_task_id`;
- `.doc/web/app/lib.php:109-112` - `list_tasks`;
- `.doc/web/public/index.php:919` - ссылка Jira;
- `.doc/web/public/index.php:923-931` - строки Jira;
- `.doc/web/public/index.php:1193` - разбор `task:(\d+)`.

**Следствие:** панель не показывает локальные задачи и не может отличить источник.

### F5. `task-diff` ищет коммиты по номеру

**Симптом:** `task-diff` не соберёт diff для `0_1`.

**Причина:** совпадение subject строится через `#N`, `CT-N` и `N`, а `0_1` не покрыт.

**Файлы:**

- `.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1:378-389` - matcher;
- `.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1:219,306` - заголовок задачи;
- `.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1:847` - папка задачи.

**Следствие:** локальная задача не получает `diff.md` и `diff.files.md`, а без них не работают impact mapping, тесты и аудит реализации.

### F6. `task-doc` и `send-to-git` почти готовы

**Симптом:** явной числовой проверки в них нет, но есть упоминания `{N}` и `CT-`.

**Причина:** скилы работают с путём `.doc/tasks/{ID}/`, но документация и команды написаны в числовом формате.

**Файлы:**

- `.agents/skills/documentation-router/children/task-doc/SKILL.md:48,77,98,120,298-302`;
- `.agents/skills/send-to-git/SKILL.md:137-138,171`.

**Следствие:** логика готова, но без обновления примеров и парсеров агент может снова угадывать числовой формат.

### F7. `jira-report` привязан к Jira

**Симптом:** комментарий и отчёт нельзя записать в локальную задачу.

**Причина:** скил называется `jira-report`, триггеры содержат «для жиры», факты берутся из Jira-полей `Version` и `CT-N`.

**Файлы:**

- `.agents/skills/jira-report/SKILL.md:1-11`;
- `.agents/skills/jira-report/SKILL.md:17-30`.

**Следствие:** локальная задача не получает комментарий, а формулировка скила противоречит идее нескольких источников.

### F8. `business-analyst` синхронизируется с Jira

**Симптом:** локальная задача не имеет Jira JSON и не может пройти `jira_sync.py`.

**Причина:** источник правил жёстко задан как Jira.

**Файлы:**

- `.agents/skills/business-analyst/SKILL.md`;
- `.agents/skills/business-analyst/scripts/jira_sync.py`.

**Следствие:** для локальных задач бизнес-анализ нужно либо отключить, либо перевести на `task.md` как источник.

### F9. Схема JSONdoc не содержит нейтральных комментариев

**Симптом:** комментарий к локальной задаче некуда записать, кроме `tracker.snapshot`, который относится к Jira.

**Причина:** `document.schema.json` не имеет коллекции `comments`, а `tracker` допускает `null` или объект Jira-снимка.

**Файлы:**

- `.agents/skills/documentation-router/children/task-doc/scripts/schemas/document.schema.json`;
- `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/render.py`.

**Следствие:** панель и документация не получают единый источник комментариев.

### F10. Смысловой слой зеркала не описывает локальный источник

**Симптом:** после добавления скилов `task-create`, `task-open`, `task-comment` граф харнеса не покажет связи с Jira и local.

**Причина:** зеркало строит только литеральные связи, а `.doc` вне его области.

**Файлы:**

- `.agents/skills/harness-router/children/mirror/ADAPTERS.local.md`;
- `.cursor/.state/harness-mirror/nodes/`.

**Следствие:** аудит следующего изменения не увидит цепочку источников без ручного чтения.

---

## 3. Целевая модель идентификатора

```text
task_id = 2538        provider = jira
task_id = 0_1         provider = local
task_id = gh_42       provider = github   (будущее)
task_id = gl_42       provider = gitlab   (будущее)
```

Правила:

1. `task_id` это строка.
2. Числовая часть обязательна.
3. Заголовок и slug не используются как ID.
4. Полный `task_id` уникален.
5. Числовая часть уникальна внутри префикса.
6. Чистое число и `CT-N` резолвятся как Jira.
7. `0_N` резолвится как local.
8. Неизвестный префикс даёт ошибку, а не догадку.

Резолвер:

```text
^\d+$       -> jira
^CT-\d+$    -> jira
^0_\d+$     -> local
```

Резолвер находится в одном месте. Скилы не дублируют регулярные выражения.

---

## 4. Контракт провайдера

Минимальный интерфейс:

```text
resolve(task_id)       -> {task_id, provider, dir, title, number, branch, status}
create(input)          -> {task_id, dir}
comment(task_id, text) -> {stored, published}
status(task_id)        -> {status, source_status}
list(filter)           -> [{task_id, provider, title, status}]
```

Провайдер `jira`:

- `resolve` читает `task.md` и tracker snapshot;
- `comment` может публиковать в Jira только по явной команде;
- `status` читает `tracker.snapshot.status`.

Провайдер `local`:

- `resolve` читает `.doc/tasks/0_N/task.md` и `task.json`;
- `create` создаёт папку, `task.md` и `task.json`;
- `comment` пишет в `comments[]` в `task.json`;
- `status` читает `metadata.status`.

Будущий провайдер реализует тот же интерфейс. Ядро не знает его API.

---

## 5. Контракт артефактов

| Артефакт | Владелец | Jira | Local |
|---|---|---|---|
| `task.md` | gototask | экспорт Jira | авторский текст |
| `task.json` | JSONdoc | экспорт и tracker snapshot | локальная инициализация |
| `doc.md` | task-doc | render | render |
| `plan.md` | prepare-plan | одинаково | одинаково |
| `test.md` | prepare-task-test | одинаково | одинаково |
| `diff.md` | task-diff | одинаково | одинаково |
| `comments[]` | task-comment | запись в Jira и зеркало | локальная запись |

`task.md` для локальной задачи содержит исходную постановку. Комментарии не дублируются в `task.md`. Они живут в `task.json` и попадают в `doc.md` через render. Это исключает два источника правды.

---

## 6. Изменения по компонентам

### 6.1. Общий валидатор task_id

**Файл:** `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/contract.py`.

**Правка:** добавить один шаблон:

```python
TASK_ID_RE = re.compile(r"^(?:[0-9]+|0_[0-9]+)$")
```

Заменить проверку `metadata.task_id` на этот шаблон. Проверку `doc.id == f"task:{task_id}"` сохранить.

**Обоснование:** один шаблон не даёт расходиться store, search, review и contract.

### 6.2. JSONdoc store

**Файл:** `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/store.py:113-118`.

**Правка:** заменить `[0-9]+` на `TASK_ID_RE`. Код ошибки сохранить для совместимости тестов, сообщение дополнить допустимым примером `0_1`.

**Проверка:** `jsondoc get --task 0_1` и `jsondoc get --task 2538` работают.

### 6.3. JSONdoc search и review

**Файлы:** `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/search.py:27`, `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc/review.py:123`.

**Правка:** заменить числовые проверки на `TASK_ID_RE`. Поиск задач по каталогу принимает папки `0_N`.

**Проверка:** `jsondoc search --task 0_1` и общий поиск видят локальную задачу.

### 6.4. Схема документа

**Файл:** `.agents/skills/documentation-router/children/task-doc/scripts/schemas/document.schema.json`.

**Правка:**

- в `metadata.properties` добавить `task_number` (integer или null), `source` (`jira|local`), `source_prefix` (string или null);
- в корень добавить `comments` как массив объектов:

```json
{
  "id": "c1",
  "at": "2026-11-03T00:00:00Z",
  "author": "user",
  "text": "...",
  "source_ids": []
}
```

- `comments` не включать в `required`, чтобы старые документы остались валидными;
- `tracker` уже допускает `null`, для локальной задачи использовать `null`.

**Проверка:** старый `task.json` проходит валидацию, новый локальный тоже.

### 6.5. Команда локальной инициализации

**Файл:** `.agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py`.

**Правка:** добавить команду `init-task`:

```text
python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . init-task \
  --task 0_1 \
  --input .doc/tasks/0_1/_jsondoc/work/local-init.json
```

Вход:

```json
{
  "title": "Название",
  "task_type": "feature",
  "summary": "Короткое описание",
  "sections": [],
  "acceptance_criteria": []
}
```

Команда создаёт полный документ со всеми обязательными полями, `id: task:0_1`, `revision: 1`, `tracker: null`, пустыми массивами и `metadata.source: local`.

**Почему не `ingest-tracker`:** он описывает Jira-снимок и не должен создавать локальные задачи.

### 6.6. Проверка идентичности

**Файл:** `.agents/skills/documentation-router/children/project-doc/scripts/task-identity.py`.

**Правки:**

- `task_dirs()` принимает `^\d+$` и `^0_\d+$`;
- `check()` для Jira ожидает `CT-N`, для local пропускает `issue_key` или ожидает `LOCAL-0_1`;
- ветка проверяется только если `metadata.branch` не пустой;
- заголовок local распознаётся как `# Задача 0_1: ...`;
- добавить проверку уникальности полного `task_id`.

**Проверка:** `python3 .agents/skills/documentation-router/children/project-doc/scripts/task-identity.py 0_1` возвращает `ok`, `--all` не ломается на Jira-задачах.

### 6.7. Индекс задач

**Файлы:** `.agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1:45,84`, `.agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1:111,149,163`.

**Правки:**

- принимать `^(?:\d+|0_\d+)$`;
- заголовок разбирать как `# Issue #N:` и `# Задача 0_N:`;
- сортировать Jira и local раздельно, внутри каждого по числу;
- ссылки `../tasks/0_1/` обрабатывать наравне с `../tasks/2538/`.

**Проверка:** после `build-tasks-index.ps1 -AlsoTsv` локальная задача есть в `index.md` и `file-to-tasks.tsv`.

### 6.8. Панель

**Файлы:** `.doc/web/app/lib.php`, `.doc/web/public/index.php`.

**Правки:**

- `valid_task_id` принимает `^(?:\d+|0_\d+)$`;
- `list_tasks` не пропускает `0_N`;
- `task_meta_summary` читает `metadata.source` и `metadata.task_number`;
- для `source=local` ссылка `CT-{id}` не выводится;
- блоки Jira created, updated, status, assignee скрываются;
- лента активности читает `comments[]`, для Jira оставляет fallback на `tracker.snapshot`;
- разбор ссылок `task:(\d+)` расширяется до `task:([0-9]+|0_[0-9]+)`;
- сортировка: Jira по `tracker.snapshot.updated_at`, local по mtime.

**Проверка:** локальная задача открывается по `?id=0_1`, Jira-задача по `?id=2538` выглядит как раньше.

### 6.9. `task-diff`

**Файл:** `.agents/skills/task-router/children/task-diff/scripts/task-diff.ps1`.

**Правки:**

- параметр `-TaskNumber` сохранить как alias, добавить `-TaskId`;
- matcher строить по литеральному `task_id`, а не по числу;
- для локальной задачи не требовать Jira-релиз;
- если ветки нет, искать коммиты по subject среди всех refs;
- заголовок локальной задачи читать как `# Задача 0_1:`;
- поля вывода дополнить `taskId` и `provider`;
- `Join-Path ".doc/tasks/$TaskId"` уже работает со строкой.

**Проверка:** `task-diff.ps1 -TaskNumber 0_1 -Action generate` создаёт `diff.md` и `diff.files.md`; старый вызов `-TaskNumber 2538` работает без изменений.

### 6.10. `task-doc`

**Файл:** `.agents/skills/documentation-router/children/task-doc/SKILL.md`.

**Правки:**

- примеры `{N}` заменить на `{TASK_ID}`;
- ссылки `[#0_1](../tasks/0_1/task.md)` считать допустимыми;
- команды `jsondoc` передают строковый `0_1`;
- `build-tasks-index.ps1` вызывать после локальной задачи так же, как после Jira.

**Проверка:** `задокументируй задачу 0_1` обновляет `task.json`, `doc.md`, индекс и не обращается к Jira.

### 6.11. `send-to-git`

**Файл:** `.agents/skills/send-to-git/SKILL.md`.

**Правки:**

- subject для локальной задачи начинается с `0_1` или `#0_1`;
- `jsondoc ingest-git --task 0_1` принимает строку;
- вместо `jira-report` вызывать `task-comment`;
- ветка локальной задачи не обязательна.

**Проверка:** пробный commit с subject `0_1 ...` попадает в diff задачи; Jira-задача `2538` работает как раньше.

### 6.12. Переход к задаче

**Новый скил:** `task-open`.

**Триггеры:** «перейди к задаче», «открой задачу», «переключись на задачу».

**Поведение:**

- `2538` или `CT-2538` идёт в Jira, как сейчас;
- `0_1` идёт в local;
- неизвестный префикс даёт ошибку без догадки;
- возвращает единый отчёт: ID, источник, ветка, папка, следующий шаг.

`gototask` остаётся Jira-скилом. Для `0_1` он не должен вызывать Jira API. Допустимый вариант: `gototask` видит префикс `0_` и возвращает `provider=local`, после чего `task-open` ведёт задачу дальше.

**Проверка:** «перейди к задаче 0_1» не вызывает `jira-task`; «перейди к задаче 2538» вызывает Jira как раньше.

### 6.13. Создание локальной задачи

**Новый скил:** `task-create`.

**Триггеры:** «добавь задачу», «создай локальную задачу», «заведи задачу вручную».

**Поведение:**

1. Разбирает сообщение: заголовок, контекст, критерии приёмки, ограничения, тип.
2. Сканирует `.doc/tasks/0_*` и берёт следующий свободный номер.
3. Создаёт `.doc/tasks/0_1/task.md` с заголовком `# Задача 0_1: ...`.
4. Вызывает `jsondoc init-task`.
5. Выполняет `render` и обновляет индекс.
6. По умолчанию не создаёт ветку.

**Проверка:** после команды в чате появляется папка, задача видна в панели и индексе, JSONdoc читает её без Jira.

### 6.14. Комментарий к задаче

**Новый скил:** `task-comment`, замена `jira-report`.

**Триггеры:**

- «добавь комментарий к задаче»;
- «напиши отчёт по задаче»;
- «зафиксируй результат в задаче».

**Поведение:**

- для local пишет в `comments[]` в `task.json`, затем `render` обновляет `doc.md`;
- для Jira готовит тот же текст и публикует только по явной команде;
- `jira-report` остаётся alias для старых фраз «напиши отчет для жиры» и вызывает `task-comment` с провайдером `jira`.

**Проверка:** комментарий к `0_1` виден в `doc.md` и панели; Jira-задача не получает скрытую публикацию без подтверждения.

### 6.15. Бизнес-анализ

**Файл:** `.agents/skills/business-analyst/SKILL.md`.

**Правка:** для `source=local` не вызывать `jira_sync.py`. Источником считать `task.md` и сообщения пользователя. Автоматическое извлечение правил для локальных задач включать только по явной команде.

**Проверка:** создание локальной задачи не требует Jira-конфига и не падает на `needs_llm`.

---

## 7. Правила и документация

### 7.1. Новое правило источников

**Файл:** `.cursor/rules/task-sources.mdc`.

Содержание:

- Jira по умолчанию для числового номера;
- local для `0_N`;
- полный `task_id` уникален;
- заголовок не является ID;
- коммит начинается с `task_id`;
- переход, diff и документация работают с любым провайдером.

Правило добавляется в `AGENTS.md`.

### 7.2. Обновление существующих правил

| Файл | Правка |
|---|---|
| `.cursor/rules/bitbucket-tasks.mdc` | Раздел о локальных задачах, номере `0_N`, коммитах и отсутствии Jira |
| `.cursor/rules/task-doc.mdc` | Примеры `{TASK_ID}` вместо `{N}` |
| `.cursor/rules/test-task.mdc` | Группа тестов для `0_1`, если Codeception требует другой формат |
| `.doc/harnes/doc_rules.md` | Владельцы `task.md` и `task.json` для local |
| `.doc/harnes/state/02-skills.md` | Добавить `task-open`, `task-create`, `task-comment` |
| `.doc/harnes/state/07-workflows.md` | Показать локальную ветку workflow |

### 7.3. Синхронизация

После правки канона:

```bash
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .cursor/skills/harness-mirror/scripts/harness_mirror.py scan --include-mirrors
python3 .cursor/skills/harness-mirror/scripts/harness_mirror.py build
python3 .cursor/skills/harness-mirror/scripts/harness_mirror.py check
python3 .cursor/scripts/harness/verify_parity.py
```

---

## 8. Тесты

### 8.1. Юнит-тесты JSONdoc

| Тест | Ожидание |
|---|---|
| `task_id 2538` | проходит |
| `task_id 0_1` | проходит |
| `task_id task-1` | ошибка |
| `task_id 0_` | ошибка |
| `task_id 0_1_2` | ошибка |
| старый документ без `comments` | проходит |
| новый документ с `comments` | проходит |

Файлы тестов: `.doc/skil_data/task-doc/tests/`.

### 8.2. Тесты идентичности и индексов

| Тест | Ожидание |
|---|---|
| `task-identity.py 0_1` | `ok` |
| `task-identity.py 2538` | `ok` |
| `task-identity.py --all` | локальные и Jira вместе |
| `build-tasks-index.ps1 -AlsoTsv` | `0_1` в индексе и TSV |
| `find-related-tasks.ps1` | находит `0_1` по ссылке |

### 8.3. Тесты панели

| Сценарий | Ожидание |
|---|---|
| Открыть `?id=0_1` | задача видна, нет ссылки `CT-0_1` |
| Открыть `?id=2538` | блоки Jira как раньше |
| Список задач | содержит `0_1` |
| Комментарий | виден в ленте локальной задачи |

### 8.4. Тесты diff и документации

| Сценарий | Ожидание |
|---|---|
| `task-diff.ps1 -TaskNumber 0_1` | `diff.md` и `diff.files.md` созданы |
| commit `0_1 test` | попадает в diff |
| commit `#2538 test` | попадает в diff Jira-задачи |
| `task-doc 0_1` | `doc.md` и индекс обновлены |
| `send-to-git` | subject с `0_1` принимается |

### 8.5. Сквозной сценарий

1. Пользователь пишет «добавь задачу ...».
2. Появляется `.doc/tasks/0_1/`.
3. Задача видна в панели.
4. `prepare-plan` создаёт план.
5. `prepare-task-test` создаёт `test.md`.
6. Реализация и тесты проходят.
7. `task-diff` собирает diff.
8. `task-doc` обновляет документацию.
9. `send-to-git` принимает commit с `0_1`.
10. Повторный прогон Jira-задачи `2538` не меняет поведение.

---

## 9. Порядок внедрения

1. Добавить `TASK_ID_RE` и тесты. Это разблокирует всё остальное.
2. Обновить JSONdoc store, search, review, contract.
3. Добавить `comments` и `init-task` в JSONdoc.
4. Обновить `task-identity.py`, индексы и `find-related-tasks`.
5. Обновить панель.
6. Добавить `task-open` и `task-create`.
7. Добавить `task-comment`, оставить `jira-report` alias.
8. Обновить `task-diff` и `send-to-git`.
9. Обновить правила, состояние харнеса и документацию.
10. Прогнать сквозной сценарий и регрессию Jira.
11. Только после этого добавлять третий провайдер.

Приоритет: пункты 1-5 дают работающую локальную задачу. Пункты 6-8 дают полный workflow. Пункт 11 проверяет универсальность.

---

## 10. Риски и откат

| Риск | Причина | Мера |
|---|---|---|
| Числовые приведения падают | `int(task_id)` в скриптах | Заменить на строку, тест `0_1` |
| Дубли ID | Нет проверки уникальности | `task-identity --all` и отдельный uniqueness check |
| Панель ломает Jira-задачи | Условные блоки Jira | Регрессия `2538` |
| Комментарии расходятся | Две записи в `task.md` и `task.json` | Один источник `comments[]` |
| Codeception не принимает group `task-0_1` | Ограничение имени группы | Проверить; при необходимости group alias `task-0-1` |
| Старые документы ломаются | Новые поля схемы | Поля не обязательные, старый JSON проходит |
| `task-diff` ловит лишние коммиты | Слишком широкий matcher | Матчить полный `task_id` с границей слова |
| Зеркало не видит новые скилы | `.doc` вне области | Заполнить H2 для новых узлов, не расширять область |

Откат:

1. Вернуть канонические файлы через git.
2. Выполнить `sync-agent-views.sh`.
3. Повторить `scan`, `build`, `check`.
4. Локальные папки задач не удалять, они не мешают Jira-задачам.

---

## 11. Открытые решения

1. Глобальная уникальность номера: сейчас предлагается уникальность полного `task_id` и числовой части внутри префикса. Если нужна одна общая последовательность, генератор local будет брать следующий свободный номер среди всех задач.
2. Формат ветки local: `features/#0_1` или `bugfixes/#0_1`. По умолчанию ветка не создаётся.
3. Публикация комментария в Jira: по умолчанию только текст в задаче, публикация отдельной командой.
4. Судьба `jira-report`: оставить alias или удалить после синхронизации представлений. Alias безопаснее.
5. Бизнес-анализ local: отключить автоматический Jira sync, включать извлечение правил только по явной команде.

---

## 12. Связи

- [Итоговый аудит харнеса](../audit/summ.md) - находки по workflow и владельцам этапов.
- [Аудит 10](../10.md) - предыдущая сводная рекомендация.
- [Скилы харнеса](../state/02-skills.md) - реестр владельцев.
- [Схемы взаимодействия](../state/07-workflows.md) - текущий workflow.
- [Формат скила](../skill-format.md) - обязательные файлы нового скила.
- [Правила документации](../doc_rules.md) - формат этого плана и правила `.doc`.
- [`task-diff`](../../../.agents/skills/task-router/children/task-diff/SKILL.md) - сбор diff по задаче.
- [`task-doc`](../../../.agents/skills/documentation-router/children/task-doc/SKILL.md) - документирование задачи.
- [`gototask`](../../../.agents/skills/task-router/children/gototask/SKILL.md) - текущий Jira-переход.

---

## История изменений

- 2026-11-03: создан план нескольких источников задач. Зафиксированы инвариант числового ID, локальный префикс `0_`, изменения JSONdoc, панели, индексов, `task-diff`, `task-doc`, `send-to-git` и новых скилов.
