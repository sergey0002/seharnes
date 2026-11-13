---
name: gototask
description: >-
  Переход к ветке задачи Jira по номеру: обновляет task.md из Jira, ищет ветку на
  origin, создаёт от релизной ветки или вмерживает релиз в существующую, синхронизирует
  рабочую копию. Use when the user says перейди к задаче, go to task, gototask,
  открыть задачу, переключись на задачу, or mentions a task number like #1612 or CT-2538.
---

# Go To Task (gototask)

Переключение на ветку задачи. **Всё через один PS1-скрипт** - не вызывать MCP `jira-task` и не дублировать git-команды вручную.

Экспорт `task.md`: [`.doc/skil_data/jira/README.md`](../../../.doc/skil_data/jira/README.md) (Jira `CT-{N}` → папка `.doc/tasks/{N}/`).

## Скрипт

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber {N} -Action {action} [параметры]
```

| Action | Когда |
|--------|-------|
| `inspect` | Первый шаг - JSON со всем состоянием |
| `export-task` | Только выгрузить `task.md`, `_jsondoc/work/tracker.json` и обновить `task.json`; ветка не меняется |
| `create-branch` | Ветки нет - создать от релиза из Jira |
| `merge-release` | Ветка есть - **всегда** вмержить релиз из Jira |
| `checkout` | Только если явно нужен checkout без merge (не штатный путь) |
| `sync` | Checkout ветки и fast-forward до origin без merge релиза |

Параметры и коды выхода:

| Параметр | По умолчанию | Роль |
|---|---|---|
| `-ReleaseBranch` | из Jira Version | релиз для `create-branch` / `merge-release` |
| `-TaskBranch` | `exact` или `suggestedBranch` | ветка задачи |
| `-LocalChanges` | `keep` | `keep` оставляет правки и добавляет вопрос `local_changes`; `stash` прячет; `discard` требует `-ConfirmDiscard` |
| `-SkipTaskExport` | выключен | не обращаться в Jira, читать локальный `task.md` |
| `-ConfirmCreateBranch` | выключен | обязателен для `create-branch` |
| `-ConfirmMerge` | выключен | обязателен для `merge-release`, если есть другие открытые вопросы |
| `-ConfirmDiscard` | выключен | обязателен для `-LocalChanges discard` |
| `-RepoPath` | корень репозитория | переопределение пути |
| `-ConfigPath` | `.cursor/skills/task-router/children/gototask/config.json` | переопределение конфига |

Коды выхода: `0` успех; `2` merge с конфликтами (`needsConflictResolution: true`); `3` apply заблокирован открытым вопросом (`apply_blocked_pending_user_input`, `discard_requires_confirm`); `1` необработанная ошибка скрипта.

После успешного **apply** (`checkout` / `create-branch` / `merge-release` / `sync`) скрипт best-effort обновляет индекс codegraph (`codegraph sync`, таймаут 60 с, без LLM). В JSON ответа поле `codegraphIndex`. `inspect` / `export-task` индекс не трогают. Отключить: `CODEGRAPH_AUTO_UPDATE=0`.

**Номер задачи:** только цифры (`2538`). URL Jira (`…/browse/CT-2538`) и ключ `CT-2538` понимает экспортёр `.agents/skills/task-router/children/jira/scripts/server.php`, gototask передаёт `{N}`.

**Импортированные из Bitbucket задачи.** В `task.md` встречается строка
`Imported from https://bitbucket.org/…/issues/1642/…`, а старые ветки названы по
этому номеру: `features/#1642` или `bugfixes/#1642`. Скрипт читает такой номер из
`task.md` (строка `| Bitbucket | 1642 |` или текст `Imported from`) и ищет
legacy-ветки наравне с ветками Jira. В JSON появляются `task.bitbucket`,
`taskBranches.legacyExact`, `legacyNumbers`. Обычные ссылки на Bitbucket без
`Imported from` не считаются: это может быть упоминание чужой задачи.

## Автоправила (без AskQuestion)

1. **Релиз всегда из Jira** - брать `defaultReleaseBranch` из Fix Version (`defaultReleaseSource: jira`). Не спрашивать `select_release_branch`.
2. **Ветка есть → всегда `merge-release`** - не спрашивать `confirm_merge_release`, не делать голый `checkout` вместо merge.

Исключение: Jira Version пуст или ветка релиза не найдена на origin → тогда спросить релиз (`select_release_branch` в `needsUserInput`) или остановиться с ошибкой.

## Workflow

```
GoToTask:
- [ ] 1. inspect
- [ ] 2. AskQuestion только по needsUserInput (префикс / какая ветка / создать / локальные правки)
- [ ] 3. apply: нет ветки → create-branch; есть ветка → merge-release (релиз из Jira)
- [ ] 4. конфликты (если есть)
- [ ] 5. отчёт
- [ ] 5b. якорь для аналитики диалогов (после успешного apply)
- [ ] 6. comment triage (если есть свежие комментарии)
- [ ] 7. MCP smoke test (после успешного apply)
```

### Шаг 1. inspect (всегда первым)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .cursor/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 2538 -Action inspect
```

Скрипт автоматически:
- выгружает `task.md` из Jira через PHP/Docker (`.agents/skills/task-router/children/jira/scripts/server.php`) и передает снимок в `jsondoc ingest-tracker`;
- делает `git fetch origin`;
- возвращает JSON: `task` (`title`, `kind`, `jiraVersion`, `bitbucket`, `suggestedPrefix`, `suggestedBranch`), `releaseBranches`, `defaultReleaseBranch`, `defaultReleaseSource`, `taskBranches` (`exact`, `jiraExact`, `legacyExact`, `variants`), `branchExists`, `branchExistsLocally`, `localAheadCount`, `hasLocalChanges`, `originState`, `currentBranch`, `recommendedAction`, `needsUserInput`;
- при недоступной сети не падает: `originState` принимает значение `fetch_failed` или `ls_remote_failed`, список веток собирается из локальных remote-tracking refs `origin/*`.

**Не читать task.md и не вызывать MCP** - данные уже в JSON.

### Шаг 2. AskQuestion (только если есть в needsUserInput)

**Без ответа по этим пунктам - не выполнять apply.** Не спрашивать релиз и merge, если их нет в `needsUserInput`.

#### select_task_branch

Если несколько (`bugfixes/#2538`, `bugfixes/#2538_for5606`) - спросить какую.

#### select_branch_prefix

Если в заголовке нет «доработка»/«ошибка» - спросить: `features` или `bugfixes`.

| Слово в заголовке / Kind | Префикс |
|--------------------------|---------|
| `доработка` | `features` |
| `ошибка` | `bugfixes` |
| Kind `Баг` / `bug` | `bugfixes` |

Шаблон ветки: `{prefix}/#{N}`.

#### confirm_create_branch

«Ветка `{branch}` не найдена. Создать от `{releaseBranch}` (Jira Version)?» → Да / Нет.

#### select_release_branch (только исключение)

Только если `defaultReleaseSource` не `jira` или `defaultReleaseBranch` пуст. Показать `releaseBranches`, спросить релиз.

#### local_changes

«Есть незакоммиченные изменения» → Затереть / Stash / Отмена.

### Шаг 3. apply

Релиз: `-ReleaseBranch` = `defaultReleaseBranch` из inspect (Jira), если не сработал exception выше.

**Новая ветка** (после «Да» на create):

```powershell
... -Action create-branch -ReleaseBranch "releases/5.7.4" -TaskBranch "features/#2538" -LocalChanges discard -ConfirmCreateBranch -ConfirmDiscard
```

**Существующая ветка** (всегда merge, без вопроса):

```powershell
... -Action merge-release -ReleaseBranch "releases/5.7.4" -TaskBranch "bugfixes/#2538" -LocalChanges discard -ConfirmDiscard
```

Если в `needsUserInput` остались другие пункты, к `merge-release` добавляется `-ConfirmMerge`. Без соответствующего `-Confirm*` скрипт возвращает exit 3 и ничего не меняет.

Поле `recommendedAction` в inspect: `create-branch` | `merge-release` | `null` (нужен выбор ветки/префикса).

### Шаг 4. Конфликты merge

Если `merge-release` вернул exit 2 или `needsConflictResolution: true`:

1. Прочитать `conflicts` из JSON.
2. Прочитать `.doc/tasks/{N}/task.md` и `.doc/tasks/*/task.md` связанных задач (номера из комментариев/веток в конфликтных файлах).
3. Разрешить конфликты с учётом контекста задач.
4. **Согласовать с пользователем** спорные места через AskQuestion.
5. `git add` + `git commit` (сообщение: `gototask: merge {release} into {branch}`).
6. **Не push** без явной просьбы («пуш» / «запушь» / «push»). Как пушить: `.doc/architecture/cicd.md` §6a.

### Шаг 5. Отчёт

```
✓ Задача #{N}: {title}
✓ task.md: обновлён из Jira ({method})
✓ Ветка: {branch}
✓ Релиз: {releaseBranch} (jira | config-fallback | user)
✓ Действие: {создана | merge-release}
✓ Merge: {выполнен | конфликты разрешены}
✓ Локальные правки: {нет | сброшены | stash}
✓ codegraph index: {ok | skipped | fail} (codegraph sync)
```

После apply скрипт best-effort запускает `codegraph sync` (таймаут 60 с,
CODEGRAPH_AUTO_UPDATE=0 отключает). Статус в codegraphIndex не валит переход.

### Шаг 5b. Якорь для аналитики диалогов

После успешного apply один раз запиши якорь задачи. Он связывает этот диалог с
задачей точно, без угадывания по путям и номерам в тексте.

```bash
python3 .agents/skills/task-router/children/analytics/scripts/task-analytics.py anchor \
  --task {N} --branch "{branch}" \
  --quote "<первые 80 символов первого сообщения пользователя в этом диалоге>"
```

Файл `.doc/tasks/{N}/_dialogs/anchor.json` создаётся один раз; повторный вызов с
теми же значениями возвращает `duplicate`. Шаг best-effort: при ошибке запиши
`anchor: fail` в отчёт, но не блокируй apply и не чини инструмент в рамках
gototask.

### Шаг 6. Comment triage (если есть комментарии)

После успешного apply, если в `task.md` есть ## Comments с непустыми записями моложе 7 дней:

Следовать шагу [references/comment-triage.md](references/comment-triage.md):

1. Прочитать последний комментарий из task.md.
2. Классифицировать: QUESTION | BUG | REQUIREMENT | DECISION | AMBIGUOUS.
3. Проверить evidence в коде (обязательно для BUG/REQUIREMENT).
4. Вывести triage-блок с типом, проверкой, действием.
5. Предложить следующую команду, не запускать автоматически.

Если комментариев нет или последний старше 7 дней - пропустить, сообщить "комментариев для triage нет".

### Шаг 7. MCP smoke test (после успешного apply)

После успешного перехода (apply без конфликтов или с разрешенными конфликтами) прогнать smoke-тест MCP и вывести отчет. Цель: зафиксировать какие инструменты реально зеленые до начала работы, чтобы последующие скилы (prepare-plan, doc-verify) не строили предположений о доступности.

```bash
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs
```

Скрипт проверяет серверы в две фазы: Phase 1 - запуск процесса (`tools/list`), Phase 2 - функциональная проба (`tools/call` read-only операцией: CBM `list_projects`, serena `get_symbols_overview`, mysql `list_tables`, git `git_status`, codegraph `codegraph_explore`). Сервер с живым процессом, но проваленной пробой, помечается `OK→DEGRADED` или `OK→TIMEOUT` - это не зеленый тир, а повод для компенсации. Скрипт сам пропускает серверы вне скоупа харнеса (xdebug) и отключенные в `mcp.json` (deepwiki, bitbucket-task, sourcegraph), проверяет остальные параллельно и возвращает exit 1 при FAIL/TIMEOUT/DEGRADED. `codegraph` падает, если нет `.codegraph/`; это значит, что индекс не построен, а не что сервер сломан.

В отчет gototask добавить блок:

```
MCP smoke: OK {n} / FAIL {n} / SKIP {n} (+ список FAIL с причиной)
```

При FAIL/TIMEOUT/DEGRADED любого нужного сервера: зафиксировать в отчете строкой `MCP {name}: {status} - {detail}`, продолжить работу с учетом недоступности (компенсация Grep/Read), не блокировать переход к задаче. Не чинить серверы в рамках gototask.

## Конфигурация

[config.json](config.json): `releaseBranch` + `releaseBranchFallbacks` - **только fallback**, если Jira Version пуст или ветка релиза не найдена на origin. В этом случае агент спрашивает релиз, а не молча берёт config.

Порядок выбора релиза:

1. Fix Version из Jira, список через запятую: для каждой версии проверяются `releases/{v}`, затем `release/{v}`, затем любая ветка релиза с окончанием `/{v}`. Источник `jira`.
2. Бэкпорт-суффикс ветки задачи (`bugfixes/#N_for5606`, `bugfixes/#N_for_5.6.0.6`) перекрывает Fix Version и подставляет релиз своей версии. Источник `backport_suffix`.
3. `config.json` - только если Jira Version пуст или ветка не найдена на origin. Источник `config`, при этом в `needsUserInput` есть `select_release_branch`.

## Ограничения

- Не push без явной просьбы («пуш» / «запушь» / «push»). Обход SSH: `.doc/architecture/cicd.md` §6a.
- Не спрашивать релиз и merge в штатном сценарии (Jira Version есть, ветка релиза на origin).
- Не пропускать AskQuestion для создания ветки, выбора среди нескольких веток, префикса и локальных правок.
- Не вызывать MCP `jira-task` - только PS1 (скрипт сам вызывает `.agents/skills/task-router/children/jira/scripts/server.php`).
- Не commit кроме завершения merge с конфликтами.
- Exit 3 при открытом вопросе - нормальная защита, а не сбой задачи: либо закрыть вопрос ответом, либо передать соответствующий `-Confirm*`.
- Локальная ветка при checkout не сбрасывается: если она опережает upstream, скрипт падает, а не теряет коммиты; reset (`checkout -b`) только для ветки, которой еще нет локально.
- `scripts/find-task-branch.ps1` лежит в каталоге как legacy и не вызывается: поиск веток (Jira, legacy Bitbucket, варианты, бэкпорт) живет в `gototask.ps1`.

## Зависимости

- PHP в PATH или Docker `copytrust-dev-php-apache-1`
- `.doc/skil_data/jira/config.env` настроен (`read:jira-work`)
- Git remote `origin` = GitVerse (`git@gitverse.ru:realant/copytrust.ru.git`); запасной `bitbucket`
