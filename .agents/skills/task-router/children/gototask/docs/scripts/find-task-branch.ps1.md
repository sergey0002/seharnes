# Скрипт: `.agents/skills/task-router/children/gototask/scripts/find-task-branch.ps1`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, ../config.json]
tags: [harness, script, gototask, git, branch-discovery]
-->

## Суть
Поиск git-веток задачи на `origin` (GitVerse). Выполняет `git fetch origin`, затем `git ls-remote --heads origin` для получения актуального списка удалённых веток. Проверяет точное совпадение с ожидаемыми именами (`features/#N`, `bugfixes/#N`), ищет варианты с номером задачи в имени (backport-ветки), и определяет релизную ветку из конфига (`release/5.6.0.6` + фолбэки). Возвращает JSON с полным набором найденных веток. Не делает checkout — только информирует.

## Когда запускать
Вызывается из `gototask.ps1` перед решением о создании/переключении ветки. Можно вызвать вручную для диагностики: «есть ли ветка задачи на origin?». Если не запустить — `gototask` не узнает о существующих ветках и может создать дубликат или не вмержить релиз.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `-TaskNumber` | | string | **да** | | Номер задачи (например `2538` или `CT-2538`) |
| `-RepoPath` | | string | нет | `(Get-Location).Path` | Путь к корню git-репозитория |
| `-ConfigPath` | | string | нет | `<RepoPath>/.cursor/skills/task-router/children/gototask/config.json` | Путь к конфигу с релизными ветками |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: JSON на stdout | Разобрать JSON, использовать `branchExists`, `exactBranches`, `variantBranches`, `releaseBranch` |
| 1 | Ошибка PowerShell (strict mode, fetch failed, config not found) | Прочитать stderr, проверить сеть/конфиг/путь |

PowerShell не задаёт явные коды выхода — ошибки прерывают выполнение (`$ErrorActionPreference = "Stop"`).

## Что читает и что пишет
**Читает:**
- `.cursor/skills/task-router/children/gototask/config.json` — `releaseBranch` и `releaseBranchFallbacks`
- Git remote `origin` — через `git fetch origin` + `git ls-remote --heads origin`

**Пишет:**
- JSON на stdout (только вывод, файлы не создаёт)

**Пример вывода:**
```json
{
  "taskNumber": "2538",
  "releaseBranch": "release/5.6.0.6",
  "releaseBranchCandidates": ["release/5.6.0.6", "releases/5.6.0.6"],
  "exactBranches": ["bugfixes/#2538"],
  "variantBranches": ["bugfixes/#2538_for5606", "bugfixes/#2538_for_5.6.0.6"],
  "branchExists": true
}
```

## Побочные эффекты
- `git fetch origin` — сетевой запрос к GitVerse (обновляет локальные remote-tracking refs)
- Не меняет рабочую копию, не делает checkout, не коммитит

## Окружение и зависимости
- PowerShell 5.1+ / PowerShell 7+
- `git` в PATH
- Доступ к `origin` (GitVerse) по сети
- Конфиг `.cursor/skills/task-router/children/gototask/config.json` должен существовать

## Примеры
```powershell
# Базовый вызов (из корня репо)
powershell -File .agents/skills/task-router/children/gototask/scripts/find-task-branch.ps1 -TaskNumber 2538

# Явный путь к репо и конфигу
powershell -File .agents/skills/task-router/children/gototask/scripts/find-task-branch.ps1 -TaskNumber 2538 -RepoPath "C:\projects\copytrust" -ConfigPath "C:\projects\copytrust\.cursor\skills\task-router\children\gototask\config.json"

# Использование из gototask.ps1 (внутри скрипта)
$branchInfo = powershell -File find-task-branch.ps1 -TaskNumber $TaskNumber | ConvertFrom-Json
```

## Ограничения
- Не проверяет локальные ветки (`git branch`) — только `origin` через `ls-remote` (по правилу bitbucket-tasks.mdc)
- Не различает типы задач (feature/bugfix) — возвращает обе точные ветки если есть
- Backport-ветки ищутся по паттерну `#N` в имени, могут дать ложные срабатывания (например, `#25380`)
- Не валидирует, что найденная ветка актуальна (может быть удалена после merge) — только наличие ref на origin
- Требует сети — без доступа к origin вернёт пустые массивы

## Связи
- Вызывается: `gototask.ps1` (основной потребитель), вручную для диагностики
- Зависит от: `config.json` (релизные ветки), git remote `origin`
- Результат потребляет: `gototask.ps1` (решение о create/merge/checkout)
- Связанные скрипты: `gototask.ps1`, `task-diff.ps1`, `send-to-git`

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода