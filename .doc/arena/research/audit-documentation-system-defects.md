# Система документации — критичный аудит (дефекты, где работает криво)

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** система документации — правила, планирование, разработка, CLI, документация задач и архитектуры, индексирование.
**Метод:** не описание, а **экспертный аудит** — каждый пункт проверен на деле (прогон CLI, проверка путей, сравнение контракта и реальности).
**Итог:** архитектура документации **продумана, но в текущем состоянии работает криво** — хрупкая, часть функционала не реализована, контракты не совпадают с кодом, индекс-поток заперт на PowerShell, 163 сломанных ссылки.

---

## 0. Короткий вердикт

| Критерий | Оценка |
|---|---|
| Концепция / стандарт | ✅ продуман, единый стандарт `doc_rules.md` |
| JSONdoc-ядро (store/render/CAS/tests) | ✅ зрелое — 181 тест OK, чистая компиляция |
| **Контракт vs реальность** | ❌ **CRITICAL** — документированные команды (`tags search`) отсутствуют; плановая часть (`index refresh/check`) не реализована |
| **Индексация (project-doc)** | ❌ **CRITICAL** — весь batch-pipeline заперт на **PowerShell**, не запускается на Linux; зависит от gitignored `.doc/architecture/` |
| **Качество ссылок** | ❌ **HIGH** — **163 сломанных ссылки**, цели реально отсутствуют |
| **Переносимость / дрейф** | ❌ **HIGH** — hardcoded Windows-путе + CopyTrust в production-скриптах |
| **Дрейф названия** | ⚠️ MEDIUM — CopyTrust в doc_rules/jsondoc/build-tasks-index (проект — seharnes) |
| **MCP-зависимость** | ⚠️ MEDIUM — Reuse/Impact/Verify Gates обязательны при ready; без MCP система не идёт |
| **Общая оценка** | **4 из 10** — хорошая концептуальная модель, плохое исполнение |

---

## 1. D1 — CRITICAL: контурный дрифт — контракт документирует команды, которых нет в CLI

**Факт (подтверждён на деле):**
- `jsondoc.md` (§6.1, строка 455) документирует:
  ```bash
  python3 .../jsondoc.py --root . tags search --text "отмена" --fields label,description,aliases
  ```
- Реальный CLI **не имеет** подкоманды `tags`:
  ```
  $ jsondoc.py --root . tags search --text "x"
  jsondoc.py: error: argument command: invalid choice: 'tags'
  (choose from 'selftest','execution','baseline','get','search','related','apply',
   'render','validate','batch','ingest-tracker','ingest-git','recover')
  exit=2
  ```
- `jsondoc.md` §6.3 явно: "`index refresh` и `index check` относятся к плану J12-J13 и **в текущем CLI отсутствуют**".
- Также §6.3 упоминает `template` — в реальном CLI нет.

**Почему криво:** 208 КБ-документ (`jsondoc.md`) — это **смешанный документ**: часть — контракт, часть — **план реализации** (§10, R1–R6, «Пока только fixture»). Агент, читая документ, пробует `tags search`, получает hard-error. **Документ лжёт коду.**

**Причина:** JSONdoc склеивается стадиями (R1–R6), но `jsondoc.md` не разделен на «implemented» и «planned»; документировано больше, чем реально есть.

---

## 2. D2 — CRITICAL: индексационный pipeline заперт на PowerShell (не переносится)

**Факт (подтверждён):** в среде аудита **`pwsh`/`powershell` отсутствуют**:
```
$ command -v pwsh powershell
pwsh/powershell НЕ доступны
```
А **все ключевые index-скрипты — PowerShell**:
- `map-project.ps1` — карта проекта (tree, hot-files, метрики)
- `get-indexing-batch.ps1` — выдача батчей (жетловодель всего batch-цикла)
- `mark-noise.ps1`, `audit-docs.ps1`, `validate-docs.ps1`, `sync-docs.ps1`
- `generate-doc-index.ps1`, `generate-file-registry.ps1`, `build-tasks-index.ps1`

**Почему криво:** **индексирование — нерв система документации — не запускается на Linux/macOS без PowerShell.** JSONdoc (Python) с одной стороны платформонезависимый, а вся индексация с другой — Windows-locked. **Два движка на разных платформах в одной системе.**

**Дополнительно:** index-скрипты читают **gitignored** `.doc/architecture/` (`validate-docs.ps1`: `$archDir = .doc\architecture`). На новом чистом клоне это директриса не существует — система не может индексировать «с нуля» в repo.

---

## 3. D3 — HIGH: 163 сломанные ссылки в `.doc`

**Факт (подтверждён на деле):**
```
$ python3 .../check-links.py --root .
...
.doc/mcp.index.md -> harnes/mcp/codebase-memory-mcp.md
.doc/mcp.index.md -> ../.cursor/graphify-mcp.md
.doc/rebase_project.md -> ../sourcegraph-local/README.md
.doc/rebase_project.md -> ../tools/docker-dev/compose.yaml
...
TOTAL broken links: 163
exit=1
```
Цели **реально отсутствуют**:
```
BROK .doc/harnes/mcp/          (директории нет)
MISSING .cursor/graphify-mcp.md
MISSING sourcegraph-local/
MISSING tools/docker-dev/compose.yaml
MISSING tools/docker-test/compose.yaml
MISSING leantime/docker
```

**Почему криво:** система с built-in `check-links.py` (и правилами ссылок в `doc_rules.md`), но **163 dead-ссылки в собственной документации**. То есть валидатор есть, а docs в нём не живут. **Контроль есть, соблюдение нет.** Распределение — концентрировано в `mcp.index.md`, `rebase_project.md`, referencing убранные/перенесённые ветки (sourcegraph-local, tools/docker-*, leantime, .cursor/graphify-mcp).

### D3.1 — Почему контроль не сработал (корень)

Есть **два** контрольных CLI, но ни один не перекрыл 163 брека:

| Инструмент | Роль | Охват | Исправление | В миграции? |
|---|---|---|---|---|
| `check-links.py` | прямой проверяльщик ссылок | весь `.doc` (163) | **нет** (read-only) | **нет** |
| `validate_docs.py` | контроль doc-покрытия + D07 (вызывает check-links) | **только `.doc/harnes`** | нет | **нет** |

1. **Охват `validate_docs.py` слишком узкий (главное).** Он сканирует **только `.doc/harnes`** (`harness = root/".doc/harnes"`, `harness.rglob("*.md")`). 163 брека живут **вне** `.doc/harnes` (`mcp.index.md`, `rebase_project.md`, `qa`, `harnes/idea`) — не видны. Реально он нашёл **1** брек:
   ```
   $ validate_docs.py
   ERROR D07 .doc/harnes/readmy_doc.md: битых ссылок: 1: ../architecture/index.md
   errors: 1, warnings: 0, exit=1
   ```
2. **Миграционный движок не знает о контроле.** `harness_transfer.py` (inventory/plan/verify/apply/export…) **не содержит** `validate_docs`/`check-links`/`D07` (grep пуст). «Контроль при миграции в папку» **не реализовано** — перенос файлов без link-check.
3. **Нет hook/CI.** `validate_docs.py` упомянут только в SKILL.md как гейт до `verified`, **никем не вызван** (`.github` отсутствует, hooks не вызывают его). Запуск — только ручной и для `.doc/harnes`.
4. **Цели структурно gitignored.** `architecture/index.md`, `sourcegraph-local/`, `tools/docker-dev/` — локальное состояние или удалено; на чистом клоне ссылки заведомо битые, и проверяльщик их не «починит», пока доки не сгенерированы.

**Суть:** инструмент корректен для своей зоны, но **не вписан в миграционный pipeline** и **ограничен `.doc/harnes`** — поэтому 163 брека в других частях `.doc` его обошли.

---

## 4. D4 — HIGH: hardcoded Windows-путе и CopyTrust в production-скриптах

**Факт (подтверждён):**
```
.agents/.../project-doc/scripts/_restore_cicd_from_transcript.py:5
    r"C:\Users\NewUser\.cursor\projects\c-projects-copytrust-testdeploydocker\...\....jsonl"

.agents/.../project-doc/scripts/audit-docs.ps1:11
    cd C:\projects\copytrust\testdeploydocker

.agents/.../project-doc/scripts/build-tasks-index.ps1:136
    [void]$sb.AppendLine('# Индекс задач CopyTrust')
```
- Эти путе — **machine-specific, не переносятся**. `_restore_cicd_from_transcript.py` — one-off скрипт с захардкоженным абсолютным путём и CopyTrust в пути.
- **CopyTrust** (проект — `seharnes`) встречается: `doc_rules.md` (2), `jsondoc.md` (1), `build-tasks-index.ps1:136`, `audit-docs.ps1`, `_restore_cicd_from_transcript.py`, и docs-копии `audit-docs.ps1.md`, `build-tasks-index.ps1.md`, `references/indexing.md`.

**Почему криво:** **production-скрипты содержат чужие пути и старое название.** При переносе в другую машину/проект они **не работают**. Это прямой переносочный дефект — не паттерн, а захардкоженный мусор.

---

## 5. D5 — MEDIUM: два «стандарта», один из которых наполовину план

- `doc_rules.md` — 44 КБ, живой стандарт (читать первым). ✅
- `jsondoc.md` — **208 КБ**, из которых §10 — это **план реализации** (R1–R6, «Before/After», «Expected»). Это **не стандарт, а stage-план**, смешанный с контрактом.
**Почему криво:** агент не может определить, что **дано наличие**, а что **предписано**. Указание «before/after» и «expected» в «стандарте» — это спек, а не канон; читатель ошибётся в интерпретации.

---

## 6. D6 — MEDIUM: MCP hard-contract (система не идёт без MCP)

**Факт:** `task-doc` (B2.5 Reuse Gate, B2.6 Impact Gate) и `doc-verify` (V3 MCP Gate) **обязательны при доступном MCP**:
- codebase-memory-mcp, codegraph, serena; Sourcegraph выключен (legacy).
**Почему криво:** если MCP не ready (частый случай), обязательные гейты не выполнимы → `task-doc`/`doc-verify` **блокированы**. Система не имеет graceful-fallback: либо MCP-ready, либо документировать нельзя. Правила не предусматривают деградацию (для task-diff/gototask, например, есть local-fallback, здесь — нет).

---

## 7. D7 — MEDIUM: дрейф пути тестов (контракт vs reality)

**Факт:**
- `jsondoc.md` §R1: тесты запускаются из `.doc/skil_data/task-doc/tests` (gitignored, **отсутствует**).
- Реальные тесты — в `.agents/skills/documentation-router/children/task-doc/tests/` (15 файлов, **181 тест OK**).
**Почему криво:** документ учит запускать тесты с несуществующего пути. Это ещё один пример **контракта, оторванного от реальности** (D1).

---

## 8. D8 — LOW: дробление валидации и мелкие нестыковки

- **`type`-валидация wart:** `doc_rules.md` даёт список `architecture | rules | api | model | flow | config | index`; для `doc.md` задачи — `flow`, но **`task` и `task-doc` валидатор считает неизвестными** (task-doc SKILL оговаривает это, но сам скил-название попадает в «неизвестное»).
- **`check-doc-text.py`** не работает без `--task`/`--file` (exit 2): валидация текста — частичная.
- **`jsondoc.py selftest`** требует `--run`/`--stage` и **сразу hard-ошибается** (`selector_required, exit 2`) — интерфейс неочевиден.
- **`jsondoc.md` §6.5** batch-лимит `MAX_CALLS=20` — есть в коде, но опциональный; без задачи batch выдаёт NOT_FOUND-по-пустому (корректно, но «успешно» со стопкой).

---

## 9. Что не криво (чтобы не ломать)

- **JSONdoc-ядро зрелое:** 181 тест OK, чистая компиляция пакета, CAS/store/render/ingest раздельны и корректны.
- **Концепция единой канонии** (`doc_rules.md`) — формат, ссылки, индекс-гейт, маркеры статуса чётки.
- **Index Gate / правило обратных ссылок** — защита от дублирования doc-разделов.
- **Batch-очередь с стейтом** (`file-registry.tsv`) — resume-able индексация (хотя на PowerShell, D2).
- **store/render разделение** — `doc.md` view, не источник.

---

## 10. Причина, почему «работает криво» — суть

1. **System не переносим:** индекс-pipeline (PowerShell) ≠ knowledge-engine (Python). На Linux doc-система не индексирует.
2. **Контракты не синхронизированы с кодом:** `jsondoc.md` (208 КБ) документирует больше, чем существует (`tags`, `index refresh/check`, путь тестов). Документ и код живут в разных временных плоскостях (план R1–R6 vs reality).
3. **Нет контроля соблюдения и контроля при миграции:** есть `check-links.py` (full `.doc`), но он read-only и не вызывается; есть `validate_docs.py`, но он **только для `.doc/harnes`** и **не вписан в `harness_transfer.py`**. 163 dead-ссылки в других поддеревьях `.doc` прошли мимо. **Инструменты есть, вписать их в pipeline и расширить охват — нет.**
4. **Hardcoded мусор:** чужие Windows-путе + CopyTrust в production-скриптах — переносится только тяжело.
5. **MCP-hard-contract без деградации:** без MCP документирование системно заблокировано.
6. **Локальное состояние:** `.doc/architecture/` gitignored — система работоспособна только на «сгенерированной» машине.

---

## 11. Рекомендации по упорядочению (прямые, по приоритету)

1. **D1 (CRITICAL):** разделить `jsondoc.md` на **контракт (implemented)** и **план (planned)**; либо реализовать `tags search` + `index refresh/check`. Убрать из документации команды, которых нет.
2. **D2 (CRITICAL):** либо port index-pipeline в Python (jsondoc уже есть), либо явно задокументировать PowerShell как mandatory-prereq. **Не оставлять два движка на разных платформах.**
3. **D3 (HIGH):** исправить 163 dead-ссылки; расширить охват `validate_docs.py` (с `.doc/harnes` до всего `.doc`); **вписать link-check в `harness_transfer.py`** (verify/apply) + CI/pre-commit gate.
4. **D4 (HIGH):** удалить hardcoded Windows-путе (`audit-docs.ps1`, `_restore_cicd_from_transcript.py`); вернуть `build-tasks-index.ps1` на `seharnes`; убрать CopyTrust из всех doc-artifacts.
5. **D6 (MEDIUM):** добавить graceful-fallback для Reuse/Impact/Verify Gates без MCP (чётко «деградированный режим»).
6. **D7 (MEDIUM):** выровнять путь тестов в `jsondoc.md` с реальностью.
7. **D5 (MEDIUM):** сократить `jsondoc.md`; вынести план §10 в отдельный документ.
8. **D8:** задокументировать `type`-список; сделать `check-doc-text`/`selftest` очевидными.

**Важно:** код не правился — это аудит с выявленными дефектами. Правки требуют согласования плана.

---

## 12. Доказательства (commands + выводы)

```bash
# D1: контурный дрифт
$ jsondoc.py --root . tags search --text "x"          → invalid choice: 'tags' (exit 2)
$ jsondoc.py --help                                    → 13 команд, без 'tags'/'index'/'template'
# D3: сломанные ссылки
$ python3 .../check-links.py --root .                  → TOTAL broken links: 163 (exit 1)
# D2: PowerShell отсутствует
$ command -v pwsh powershell                          → НЕ доступны
# D4: hardcoded пути / CopyTrust
$ git grep 'copytrust|C:\\Users' .../project-doc/scripts  → 3+ нахождения
# Ядро здорово
$ python3 -m unittest discover -s .../task-doc/tests  → Ran 181 tests, OK (skipped=1)
```

## 13. Связи
- overview: `.doc/arena/research/audit-documentation-system.md`
- стандарты: `.doc/harnes/doc_rules.md`, `.doc/harnes/jsondoc.md`
- скилы: `.agents/skills/documentation-router/children/{task-doc,project-doc,doc-verify}`
- CLI-справочник: `.doc/arena/research/cli-reference-all-commands.md`
