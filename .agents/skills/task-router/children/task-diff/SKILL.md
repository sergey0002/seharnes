---
name: task-diff
description: >-
  Генерирует diff.md для задачи по коммитам с номером в subject (полный диф по
  умолчанию), плюс незакоммиченные правки. Use when the user says обнови диф
  задачи, собери диф, update task diff, task diff, diff задачи, или упоминает
  diff.md с номером задачи.
---

# Task Diff (task-diff)

Генерация `.doc/tasks/{N}/diff.md` — диф **только по задаче** (коммиты с номером в subject).

Канонический скрипт (один для Cursor и Codex):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .codex/task-diff.ps1 -TaskNumber {N}
```

Или напрямую:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .codex/skills/task-router/children/task-diff/scripts/task-diff.ps1 -TaskNumber {N}
```

| Action | Когда |
|--------|-------|
| `generate` | По умолчанию — создать/перезаписать diff.md |
| `inspect` | Посмотреть состояние, какие ветки найдены |

Параметры:
- `-Mode full` (default) - все коммиты с номером задачи, даже уже влитые в релиз
- `-Mode ahead` / `-AheadOnly` - только коммиты, которых ещё нет в релизе
- `-StrictMatch` - subject строго начинается с номера
- `-NoReleaseBase` - без метаданных релиза
- `-SkipFetch` - не ходить в origin, брать только локальные refs
- `-ForkCommit` - якорь диапазона вместо merge-base с релизом

## Origin / SSH

Скрипт **не должен падать**, если `git fetch` / `ls-remote` ломаются из-за SSH (смена host key GitVerse, sandbox без ключа, сеть).

Порядок:
1. Попытка `git fetch origin` (если нет `-SkipFetch`)
2. При ошибке транспорта/SSH - локальные `refs/heads` и `refs/remotes/origin|bitbucket`
3. В JSON: `originSync` = `fetched` | `ls-remote` | `local-fallback` | `skipped`
4. Если host key сменился, `originHint` содержит команду для `known_hosts`. Скрипт **сам known_hosts не правит**.

Агенту не нужно чинить SSH, чтобы собрать диф: достаточно локальной ветки задачи и релиза. После починки ключа следующий запуск без `-SkipFetch` снова синхронизирует origin.

## Workflow

```
TaskDiff:
- [ ] 1. inspect (если ветка неочевидна)
- [ ] 2. AskQuestion (ветка / релиз — при необходимости)
- [ ] 3. generate
- [ ] 4. отчёт (commitCount, alreadyInRelease, aheadOfRelease)
```

## Как считается diff

**Источник истины — коммиты с номером задачи**, не `release..task`.

1. Tip ветки с origin (`features/#N` / `bugfixes/#N`); локальный HEAD — только если потомок origin tip
2. Фильтр subject: `N`, `#N`, `CT-N`, legacy из `task.md`
3. Mode `full` — полный диф задачи (default для «собери/обнови диф»)
4. Mode `ahead` — остаток до релиза
5. Релиз для метаданных: `-ReleaseBranch` → суффикс → Jira Version из `task.md` → config
6. В метаданных: `alreadyInRelease`, `aheadOfRelease`
7. Незакоммиченные — `git diff HEAD` на ветке задачи
8. Ветки задачи нет — режим `any-ref`: коммиты ищутся по номеру во всех локальных
   refs (`--all`), в `diff.md` пишется `Branch mode: any-ref`, в JSON приходят
   `branchMode`, `alreadyInRelease`, `aheadOfRelease`. Так собирается диф старой
   задачи, ветку которой удалили после merge.

Пустой `release..task` **не** значит, что дифа нет — задача могла быть уже влита.

**Legacy Bitbucket.** Для задач, импортированных из Bitbucket, в `task.md` есть
`Imported from https://bitbucket.org/…/issues/1642/…` или поле `| Bitbucket | 1642 |`.
Старые ветки и коммиты используют этот номер: `bugfixes/#1642`, subject `1642 …`.
Скрипт читает номер из `task.md` и принимает его наравне с номером Jira: ветки
попадают в `taskBranches.legacyExact`, коммиты в диф, в шапке появляется
`Legacy numbers`, в JSON `legacyNumbers`. Ссылка на Bitbucket без `Imported from`
не считается legacy, это может быть упоминание чужой задачи.

`any-ref` не доказывает принадлежность всех найденных коммитов задаче: subject
мог упомянуть номер в другом контексте. Спорные коммиты проверяются по subject и
файлам перед записью в `doc.md`.

## Результат

- `.doc/tasks/{N}/diff.md`
- `.doc/tasks/{N}/diff.files.md`

## Ограничения

- Не push, не commit.
- Не вызывать MCP jira-task — diff только из git.
