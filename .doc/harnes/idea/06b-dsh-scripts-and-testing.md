# Дополнение к плану 07: скрипты, оболочка, тестирование харнеса

<!-- meta
type: plan-amendment
status: draft
updated: 2026-10-31
related: [07-dsh-final.md, ../state/01-canon-envs.md, ../state/05-scripts.md]
tags: [harness, dsh, scripts, testing, adaptation]
-->

---

## Суть

Ответ на вопросы: как используются скрипты канона в DSH, как скилы вызывают
скрипты, копирование или единый источник, как тестировать сам харнес. Дополняет
раздел 9 плана 07.

**Главный вывод**: скрипты НЕ копируются в `.dsh/`. Единственный источник -
`.agents/skills/*/scripts/`. DSH вызывает их через WSL-обёртку. Адаптация
сводится к замене оболочки, не к копированию.

---

## 1. Инвентаризация: сколько скриптов и где

Проверено по коду 2026-10-31.

### 1.1 Скрипты скилов канона (34 файла)

```
.agents/skills/
  gototask/scripts/            2 (ps1): gototask, find-task-branch (legacy)
  harness-improvement/scripts/ 4 (py): runtime_registration, validate_registry,
                                    validate_rules, test_harness_improvement
  jira-report/scripts/         1 (py): collect-shots
  prepare-plan/scripts/        3 (py): research_ledger, validate_plan,
                                    test_validate_plan
  task-change-report/scripts/  2 (py) + tests/ 3
  task-diff/scripts/           1 (ps1)
  page-content/scripts/        1 (ps1)
  serp-study/scripts/          2 (ps1, py)
  serpanalise-report/scripts/  2 (ps1)
  xmlriver/scripts/            2 (ps1, py)
```

### 1.2 Скрипты харнеса (16 файлов)

```
.cursor/scripts/
  codebase-memory-mcp-launch.{cmd,sh}
  codebase-memory-mcp-ui.sh
  multi-exec.{ps1,sh}      <- batch-calls правило
  multi-search.{ps1,sh}    <- batch-calls правило
  mysql-mcp-proxy.mjs
  node-mcp.{cmd,sh}
  php-docker.{cmd,js,ps1,sh}
  run-with-mcp-env.sh      <- подстановка mcp.env
  test-mcp-servers.mjs
```

### 1.3 Скрипты документации (17 файлов в `.agents/skills/documentation-router/children/project-doc/scripts/`)

```
build-tasks-index, find-related-tasks, generate-doc-index,
generate-file-registry, get-indexing-batch, get-verify-batch,
map-project, mark-noise, mark-verify-done, sync-docs,
validate-docs, audit-docs, export-rebase-project, _lib
```

### 1.4 QA-скрипты (28 файлов в `.agents/skills/task-router/children/testing-router/children/test-task/scripts/`)

```
gates.py, task-test.sh, run-phpunit.py, check-ac-matrix.py,
check-selectors.py, make-verdict.py, doctor.py, ... 
```

### 1.5 JSONdoc скрипты (в `.doc/skil_data/task-doc/`)

```
jsondoc.py - единый CLI для plan verify (P7.0), get, search, apply
```

**Итого: ~95+ скриптов**, из них 34 внутри скилов, остальные общие.

---

## 2. Решение: единый источник, не копирование

### 2.1 Принцип

```
.agents/skills/<name>/scripts/*    <- канон, единственный источник
.cursor/scripts/*                  <- канон, общие скрипты
.agents/skills/documentation-router/children/project-doc/scripts/*                  <- канон, документация
.agents/skills/task-router/children/testing-router/children/test-task/scripts/*                  <- канон, QA
.doc/skil_data/task-doc/*             <- канон, JSONdoc
```

Никакой из этих каталогов не копируется в `.dsh/`.

DSH видит:
- `.agents/skills/<name>/scripts/` — зеркало синка (уже есть, проверено)
- `.agents/skills/<name>/scripts/` — оригинал, доступен напрямую по пути

**Мы вызываем канонический путь `.agents/skills/...`, а не зеркало**, потому что:
1. Зеркало может отставать до следующего синка.
2. Канон всегда правее.
3. Путь в скиле dsh-task явный — разработчик видит, что читает канон.

### 2.2 Почему не копировать в .dsh/

Если скопировать скрипты в `.dsh/skills/dsh-task/scripts/`:
- Появится **второй источник** — рано или поздно разъедется с каноном.
- Правки в `.agents/skills/.../scripts/` не подхватятся без перекопирования.
- Паритет не проверяется (синк не знает про `.dsh/`).
- Нарушение правила проекта "не дублировать".

**Решение**: копирование запрещено. Только вызов по каноническому пути.

### 2.3 Почему не симлинк

Симлинки в WSL/Windows-границе работают нестабильно. Синк проекта
использует копии, а не симлинки (README: «Зеркала - реальные копии, а не
симлинки»). Для `.dsh/` тоже не исключение.

---

## 3. Как скил вызывает скрипт

### 3.1 Общая схема

```
Агент (DSH)
  |
  |-- skill("gototask")            -> читает .agents/skills/task-router/children/gototask/SKILL.md
  |                                   (зеркало канона, синкается)
  |
  |-- видит в SKILL.md команду:
  |     powershell -File .agents/skills/task-router/children/gototask/scripts/gototask.ps1 ...
  |
  |-- применил адаптер оболочки (раздел 4):
  |     wsl -e pwsh -File /home/newuser/projects/.../.agents/skills/...
  |
  |-- выполняет через pwsh tool или wsl -e
  |
  |-- получает JSON, интерпретирует
  |
  v
Результат
```

**Ключевое**: SKILL.md в скиле не переписывается. Агент читает канонический
текст, видит `powershell -File .cursor/...`, применяет адаптер оболочки и
выполняет через WSL. Это называется **адаптация на лету**, а не копирование.

### 3.2 Адаптер оболочки: точные правила

Записывается в `.dsh/adapters/shell.md`:

```markdown
# Оболочка в DSH

## Правило 1: PowerShell скрипты

Канон: `powershell -NoProfile -ExecutionPolicy Bypass -File .agents/skills/<name>/scripts/<script>.ps1 <args>`

DSH (порядок попытки):
1. wsl -e pwsh -NoProfile -ExecutionPolicy Bypass -File .agents/skills/<name>/scripts/<script>.ps1 <args>
2. Если pwsh в WSL нет: powershell.exe -NoProfile -ExecutionPolicy Bypass -File <winpath> <args>
3. Если оба нет: НЕ пытаться вручную, остановиться и спросить

Проба: `.agents/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 2538 -Action inspect`
Успех: JSON с полем needsUserInput. Записать факт.

## Правило 2: Python скрипты

Канон: `python3 .agents/skills/<name>/scripts/<script>.py <args>`

DSH: `wsl -e python3 .agents/skills/<name>/scripts/<script>.py <args>`

Python должен быть 3.9+. Проверить: `wsl -e python3 --version`.

## Правило 3: Shell скрипты

Канон: `bash .cursor/scripts/<script>.sh <args>`

DSH: `wsl -e bash .cursor/scripts/<script>.sh <args>`

Перед вызовом: `wsl -e chmod +x .cursor/scripts/<script>.sh` (один раз).

## Правило 4: Git

Канон: `git <subcommand>`

DSH: `wsl -e git <subcommand>`

Рабочий каталог автоматически = cwd WSL.

## Правило 5: Node.js скрипты

Канон: `node .cursor/scripts/<script>.mjs <args>`

DSH: `wsl -e node .cursor/scripts/<script>.mjs <args>`

Требуется node в WSL. Проверить: `wsl -e node --version`.
```

### 3.3 Что делать, если скрипт не запускается

Если все три оболочки провалились:
1. Проверить, существует ли файл: `wsl -e test -f .agents/skills/<name>/scripts/<script>.ps1`.
2. Проверить, что правильный cwd (корень репозитория с `.git`).
3. Если файл есть, но не работает — **записать как известную проблему**
   в `.dsh/adapters/shell.md` и в harness incident.
4. Не изобретать обход (ручной git вместо gototask запрещён).

### 3.4 Как скил dsh-task направляет вызов

dsh-task содержит **только карту маршрутизации**, не сами скрипты:

```markdown
## Вызов скриптов

Все скрипты находятся в `.agents/skills/<name>/scripts/` (канон) и
`.agents/skills/documentation-router/children/project-doc/scripts/`, `.agents/skills/task-router/children/testing-router/children/test-task/scripts/`, `.doc/skil_data/task-doc/` (общие).
НЕ копировать, НЕ дублировать.

Оболочка:
- ps1: `wsl -e pwsh -NoProfile -ExecutionPolicy Bypass -File <path> <args>`
- py:  `wsl -e python3 <path> <args>`
- sh:  `wsl -e bash <path> <args>`
- git: `wsl -e git <args>`

Например:
- gototask inspect: `wsl -e pwsh ... .agents/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber N -Action inspect`
- P7.0 verify: `wsl -e python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . plan verify --task N`
- find-related-tasks: `wsl -e pwsh .agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc <path> -Json`
- gates: `wsl -e python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py N`
```

Полная карта — в разделе 5 этого дополнения.

---

## 4. Карта скриптов по этапам workflow

### 4.1 Переход к задаче

| Скрипт | Вызов | Когда |
|---|---|---|
| gototask.ps1 | `wsl -e pwsh .agents/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber N -Action inspect` | всегда первым |
| gototask.ps1 create | `... -Action create-branch` | ветки нет |
| gototask.ps1 merge | `... -Action merge-release` | ветка есть |
| find-task-branch.ps1 | не вызывается, legacy; поиск веток живет в gototask.ps1 | n/a |

### 4.2 План (Medium/Large)

| Скрипт | Вызов | Когда |
|---|---|---|
| jsondoc.py | `wsl -e python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . plan verify --task N` | P7.0, **обязательно** |
| validate_plan.py | `wsl -e python3 .agents/skills/prepare-plan/scripts/validate_plan.py .doc/tasks/N/plan.md` | P7.8 fallback |
| research_ledger.py | `wsl -e python3 .agents/skills/prepare-plan/scripts/research_ledger.py` | ledger |
| find-related-tasks.ps1 | `wsl -e pwsh .agents/skills/documentation-router/children/doc-verify/scripts/find-related-tasks.ps1 -Doc <arch.md> -Json` | P0.5a |
| git-task-blame (внутри SKILL) | `wsl -e pwsh .agents/skills/task-router/children/git-task-blame/scripts/...` | P0.5b, файлы патча |

### 4.3 Реализация и тест

| Скрипт | Вызов | Когда |
|---|---|---|
| task-diff.ps1 | `wsl -e pwsh .agents/skills/task-router/children/task-diff/scripts/task-diff.ps1 -TaskNumber N` | после правок |
| task-test.sh | `wsl -e bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh N` | полный тест |
| gates.py | `wsl -e python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py N` | финал |
| check-ac-matrix.py | `wsl -e python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-ac-matrix.py N` | проверка AC |
| make-verdict.py | `wsl -e python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/make-verdict.py N` | вердикт |
| run-phpunit.py | `wsl -e python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/run-phpunit.py` | один тест |
| browser-verify (playwright MCP) | `mcp__playwright__*` | UI-флоу |
| login-as-user (MCP) | `mcp__playwright__*` | вход |

### 4.4 Отправка в git

| Действие | Вызов | Когда |
|---|---|---|
| send-to-git (вручную) | `wsl -e git status`, `wsl -e git add`, `wsl -e git commit`, `wsl -e git push` | после "да" |
| task-doc B (индекс) | `wsl -e pwsh .agents/skills/documentation-router/children/project-doc/scripts/build-tasks-index.ps1 -AlsoTsv` | после push |

### 4.5 Самоулучшение

| Скрипт | Вызов | Когда |
|---|---|---|
| validate_registry.py | `wsl -e python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py` | после правки харнеса |
| validate_rules.py | `wsl -e python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py --rules-dir .cursor/rules --skills-dir .agents/skills` | после правки |
| verify_parity.py | `wsl -e python3 .cursor/scripts/harness/verify_parity.py --canonical .agents/skills --view .agents/skills ...` | после синка |

### 4.6 Харнес-скрипты

| Скрипт | Вызов | Зачем |
|---|---|---|
| multi-search.ps1/sh | `wsl -e pwsh .cursor/scripts/multi-search.ps1 -Patterns 'a','b'` | batch-calls правило |
| multi-exec.ps1/sh | `wsl -e pwsh .cursor/scripts/multi-exec.ps1 -Commands 'a','b'` | batch-calls правило |
| test-mcp-servers.mjs | `wsl -e node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs` | проверка MCP |
| php-docker.sh | `wsl -e bash .cursor/scripts/php-docker.sh <args>` | PHP в Docker |

---

## 5. Тестирование харнеса (не задачи, а адаптера)

Это отдельный контур. Тестирование задачи (T1-T18 в плане 07) проверяет, что
задача проходит. Тестирование харнеса проверяет, что **адаптер работает**:
скилы видны, скрипты запускаются, MCP отвечают, оболочка правильная.

### 5.1 H-тесты: адаптер и инфраструктура

| ID | Проверка | Как | Критерий |
|---|---|---|---|
| H1 | Скил dsh-task виден | Новая сессия DSH, каталог скилов | `dsh-task` с source=project-dsh |
| H2 | Канонические скилы видны | Каталог содержит все 22 | 22 скила с source=project-agents |
| H3 | Инструкции активны | Новый чат | `AGENTS.md` + `DSH-RULES.md` в контексте |
| H4 | Патч загружен | Процесс запущен с `--patch` | Конфиг содержит `mcp-client-*` |
| H5 | MCP отвечает | `mcp__codebase_memory_mcp__*` дешевый вызов | Не red |
| H6 | Оболочка ps1 | gototask inspect | JSON с needsUserInput |
| H7 | Оболочка py | `wsl -e python3 --version` | >= 3.9 |
| H8 | Оболочка git | `wsl -e git --version` | Работает |
| H9 | Все скрипты доступны | `wsl -e test -f <path>` для каждого | Все файлы существуют |
| H10 | Скрипты не скопированы | `find .dsh -name '*.ps1'` | Пусто |
| H11 | Канон не изменён | `git diff .cursor/ .agents/ .codex/ .kilo/` | Пусто |
| H12 | dsh-task не дублирует | `wc -l .dsh/skills/dsh-task/SKILL.md` | < 200 строк (маршрутизация, не копия) |

### 5.2 Тест оболочки (главный, пошагово)

**Шаг 1: ps1 в WSL**
```bash
wsl -e pwsh -NoProfile -Command "Write-Output 'ok'"
# Ожидается: ok
```
Если fail — записать. Пробовать `powershell.exe`:
```powershell
powershell.exe -NoProfile -Command "Write-Output 'ok'"
```

**Шаг 2: реальный скрипт канона**
```bash
wsl -e pwsh -NoProfile -ExecutionPolicy Bypass -File .agents/skills/task-router/children/gototask/scripts/gototask.ps1 -TaskNumber 2538 -Action inspect
```
Ожидается JSON. Если pass — оболочка ps1 подтверждена.

**Шаг 3: python**
```bash
wsl -e python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . --version
```
Ожидается версия.

**Шаг 4: git**
```bash
wsl -e git status --short
```
Ожидается список.

**Шаг 5: sh**
```bash
wsl -e bash .cursor/scripts/multi-search.sh --help
```
Ожидается help (или корректная ошибка аргументов).

**Шаг 6: node**
```bash
wsl -e node --version
```
Ожидается версия.

Все шесть пасс — оболочка готова. Записать результат в `.dsh/adapters/shell.md`
(уже с фактическими командами).

### 5.3 Тест скила dsh-task

**Шаг 1: скил читается**
```
skill("dsh-task")
```
Ожидается: содержимое SKILL.md.

**Шаг 2: маршрутизация работает**
```
В чате: "перейди к задаче 2538"
```
Ожидается: агент называет gototask, запускает inspect через правильную оболочку.

**Шаг 3: классификация размера**
```
В чате: задача без явного размера
```
Ожидается: агент запрашивает task.md, определяет размер, пишет route.json.

**Шаг 4: trivial без плана**
```
В чате: trivial-задача
```
Ожидается: агент НЕ запускает prepare-plan, только правку и проверку.

### 5.4 Тест MCP-диагностики

**Шаг 1: зеленый сервер**
```
mcp__codebase_memory_mcp__search_graph(...)
```
Ожидается результат.

**Шаг 2: красный сервер (симуляция)**
Если сервер упадёт, агент должен:
1. Записать в рабочие заметки: «CBM red».
2. Переключиться на Sourcegraph.
3. Если Sourcegraph red → Serena → grep.
4. Не выдумывать факты БД.

**Шаг 3: полный коллстек**
1. CBM green → Sourcegraph green → Serena green → MCP-диагностика работает.

### 5.5 Тест паритета харнеса

```bash
wsl -e python3 .cursor/scripts/harness/verify_parity.py \
  --canonical .agents/skills \
  --view .agents/skills --view .codex/skills --view .kilo/skills \
  --view .antigravity/skills --view .gemini/skills
```
Ожидается: passed 5 views. Это подтверждает, что зеркала (включая `.agents`,
откуда DSH читает) синхронны с каноном.

**Важно**: `.dsh/skills/dsh-task` в паритете НЕ участвует, потому что это не
зеркало канона, а наш собственный скил. Это правильно — харнес касается только DSH.

### 5.6 Тест харнеса в целом

Полный прогон (после всех этапов внедрения):

```bash
# 1. Проверки харнеса
wsl -e python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
wsl -e python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py --rules-dir .cursor/rules --skills-dir .agents/skills
wsl -e python3 .cursor/scripts/harness/verify_parity.py --canonical .agents/skills --view .agents/skills ...
wsl -e python3 .agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py --canonical .cursor/mcp.json --codex-toml .codex/config.toml
wsl -e python3 .agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py

# 2. Тесты адаптера
wsl -e python3 .agents/skills/harness-router/children/improvement/tests/test_harness_improvement.py

# 3. Реальная задача-репетиция
# Проходит полный цикл без ошибок
```

**Критерий**: все тесты exit 0 И репетиционная задача прошла.

---

## 6. Обновления в план 07

### Раздел 9 заменяется на:

```markdown
## 9. Оболочка и скрипты

Скрипты НЕ копируются в `.dsh/`. Единственный источник — канон:
`.agents/skills/*/scripts/`, `.cursor/scripts/`, `.agents/skills/documentation-router/children/project-doc/scripts/`,
`.agents/skills/task-router/children/testing-router/children/test-task/scripts/`, `.doc/skil_data/task-doc/`.

DSH вызывает их через WSL-обёртку:
- ps1: `wsl -e pwsh -NoProfile -ExecutionPolicy Bypass -File <path> <args>`
- py:  `wsl -e python3 <path> <args>`
- sh:  `wsl -e bash <path> <args>`
- git: `wsl -e git <args>`

Полная карта скриптов по этапам — в 06b-dsh-scripts-and-testing.md.
Адаптер оболочки записывается в `.dsh/adapters/shell.md` после первого
успешного прогона gototask inspect.
```

### Добавляется раздел 10 (было 10, станет 11):

```markdown
## 10. Тестирование харнеса

Отдельно от тестирования задачи (T1-T18). Проверяет, что адаптер работает:
скилы видны, скрипты запускаются, MCP отвечают, оболочка правильная.

H1-H12 (см. 06b-dsh-scripts-and-testing.md раздел 5.1):
- H1 dsh-task виден
- H2 26 канонических скилов видны
- H3 инструкции активны
- H4 патч загружен
- H5 MCP отвечает
- H6-H9 оболочка ps1/py/git/sh работает
- H10 скрипты НЕ скопированы
- H11 канон не изменён
- H12 dsh-task не дублирует (маршрутизация < 200 строк)

Полный прогон — 06b-dsh-scripts-and-testing.md раздел 5.6.
```

### Новая таблица в разделе 12 приемочных тестов:

| ID | Проверка | Критерий |
|---|---|---|
| T19 | Скрипты не скопированы | `find .dsh -name '*.ps1' -o -name '*.py'` пусто |
| T20 | Канон не изменён | `git diff .cursor/ .agents/ .codex/ .kilo/` пусто |
| T21 | dsh-task < 200 строк | wc -l |
| T22 | Оболочка ps1 | gototask inspect вернул JSON |
| T23 | Оболочка py | jsondoc --version |
| T24 | Харнес-тесты | validate_registry, validate_rules, parity, verify_mcp, test_sync_views - exit 0 |

---

## 7. Файловая структура после внедрения

```
.dsh/                                  (не в git)
├── project.patch.yml                  (генерируется + модели вручную)
├── skills/
│   └── dsh-task/
│       └── SKILL.md                   (~150 строк, только маршрутизация)
├── adapters/
│   ├── shell.md                       (оболочка: ps1/py/sh/git)
│   ├── mcp-names.md                   (serverName -> mcp__server__tool)
│   ├── models.md                      (роль -> provider/model)
│   └── scripts.md                     (карта скриптов по этапам)
└── cache/                             (кэш архитектуры, blast radius)
    ├── architecture/
    └── blast/

Скрипты остаются в каноне:
.agents/skills/*/scripts/               (34 файла)
.cursor/scripts/                        (16 файлов)
.agents/skills/documentation-router/children/project-doc/scripts/                        (17 файлов)
.agents/skills/task-router/children/testing-router/children/test-task/scripts/                        (28 файлов)
.doc/skil_data/task-doc/                   (JSONdoc CLI)
```

Нет копий, нет дублей, единственный источник.

---

## 8. Ответы на прямые вопросы

### Вопрос: скрипты курсора и других сред будут использоваться?

**Да**, но только канонический источник `.cursor/`. Зеркала других сред
(`.codex/scripts`, `.kilo/scripts` и т.д.) **не используются** — они для
самой Cursor/Codex/Kilo, не для DSH.

### Вопрос: как из скилов вызываются?

Скил читается через `skill(name)`. В SKILL.md указана команда
`powershell -File .agents/skills/...`. Агент применяет адаптер оболочки
(замена на `wsl -e pwsh -File ...`) и выполняет.

### Вопрос: копирование или единый источник?

**Единый источник**. Копирование запрещено. Причины:
1. Два источника разъедутся.
2. Синк не знает про `.dsh/`.
3. Паритет не проверяется.
4. Нарушение правила проекта.

### Вопрос: адаптация будет включена в план?

**Да**, в этом дополнении (раздел 2-4) и в плане 07 раздел 9 (заменен).

### Вопрос: тестирование харнеса?

**Да**, в этом дополнении (раздел 5), 12 H-тестов + 6 T-тестов в приемке.

---

## Связи

- [Основной план 07-dsh-final.md](./07-dsh-final.md)
- [Скрипты канона](../state/05-scripts.md)
- [Канон и среды](../state/01-canon-envs.md)
- [Синк зеркал](../state/01-canon-envs.md#2-зеркала-сред)
- `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` - синк

---

## История изменений

- 2026-10-20: создано. Ответ на вопросы скриптов, оболочки, тестирования.
  Дополняет план 07 раздел 9 (оболочка) новым разделом о скриптах и H-тестами.
