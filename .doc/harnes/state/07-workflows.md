# Схемы взаимодействия

<!-- meta
type: architecture
status: actual
updated: 2026-11-10
related: [../index.md, ./02-skills.md, ./02-skills.md, ./02-skills.md]
tags: [harness, workflows, lifecycle]
-->

---

## Суть

Пять контуров соединения скилов: жизненный цикл задачи, документация, мета-контур
самосовершенствования, синхронизация сред, отчетный контур после push. Каждая
стрелка - реальный переход с артефактом. Текстовая версия схем (бывший harnes.html раздел 10).

---

## 1. Жизненный цикл задачи

Сквозной проход от постановки до аудита диалога.

```
task-spec (сбор требований и скриншотов, task.md в .doc/skil_data/task-spec/{id})
 -> gototask (экспорт task.md, ветка)
 -> gototask шаг 6: references/comment-triage.md (разбор последнего комментария: вопрос, баг, требование, решение)
 -> task-doc A (погружение: task.md плюс doc.md плюс diff плюс архитектура по ссылкам)
 -> prepare-plan (авторский plan.md, P7 аудит) : входит git-task-blame, find-related-tasks
 -> реализация (правки кода по плану, проверка этапа R через его S)
 -> task-diff (diff.md плюс diff.files.md)
 -> test-task : входит prepare-task-test (если нет Cest), browser-verify, отчет 8, gates.py
 stage-priority: сначала stage-only прогон правок стейджа, потом full задачи
 -> task-change-report (HTML) -> jira-report (текст в Jira)
 -> send-to-git (согласование, commit плюс push по явному да, без авто-аудита)
 -> task-doc B (doc.md, аудит архитектуры B3, индекс задач B4.5)
```

Автоматический `auto` бизнес-анализа запускается в shadow по умолчанию. Публикация
из `auto` требует `--publish` или `AUTO_PROMOTE=1`; `auto --all` ограничивается
положительным `--max-tasks`. Явные `promote` и `analysis-complete` сохраняют
проверки сверки, верификации и актуальности входов. Дата правила происходит из
источника с пометкой fallback, дата публикации не заменяет дату задачи.

Входит в prepare-plan:

```
find-related-tasks (задачи по докам и файлам, score>=20)
плюс git-task-blame (история строк, открытые ветки, риск конфликта)
плюс blast radius (graph, call-graph, LSP, fulltext, git, DB, security, types, runtime)
плюс ponytail P4.0 (нужно ли, есть ли в коде, stdlib, зависимость, одна строка, минимум)
```

Ponytail в реализации:

```
prepare-plan P4.0 (минимальный полный патч)
-> code-editing (лестница перед правкой, без потери валидации и безопасности)
-> task-code-review (lens на переусложнение после проверки ownership)
-> test-task (тестовый контракт задачи важнее правила про один маленький тест)
```

Канон ponytail: `.agents/skills/ponytail/SKILL.md`.

Входит в test-task:

```
prepare-task-test (нет Cest - собрать из Page и Step слоев)
-> browser-verify (Codeception -g task-N, Playwright для строк без метода)
-> gates.py (G0-G13: AC-матрица, lint, PHPUnit, DB, hash)
```

Git и Jira:

```
Jira CT-N -> экспорт task.md через .agents/skills/task-router/children/jira/scripts/server.php
-> ветка: доработка в features/N, ошибка в bugfixes/N
-> бэкпорт bugfixes/N_for5606 и N_for_5.6.0.6, проверка ls-remote обоих имен
-> commit с subject на N, иначе не попадет в diff задачи
-> push: origin GitVerse, запасной bitbucket, только по явной просьбе
```

Проверка ветки: `git fetch origin`, затем
`git ls-remote origin "refs/heads/bugfixes/*N*"`, затем
`git log --all --grep "#N"`. Локальный список remote-веток не доказывает отсутствие ветки.

---

## 1a. Business analyst (снят)

С 2026-11-10 бизнес-аналитик удалён из харнеса: нет хука `analysis-prepare`,
скилов `business-analyst`/`task-business-analysis` и план-гейта `plan-check`.
Требования берутся из `task.md`, комментариев и диффа.

Историческое описание: [бизнес-анализ](./17-business-analyst.md#суть).

## 2. Документация: индексация и сверка

Индексация:

```
project-doc INIT, MAP, SECTION: батч 15 файлов (CSS до 30)
-> get-indexing-batch (current-batch.txt, приоритет hot-files)
-> анализ плюс CBM Gate (search_graph, trace_path - факт в текст)
-> Index Gate (найти подходящий док, дописать, не плодить дубли)
-> index.md (оглавление плюс _map реестры)
```

Сверка:

```
doc-verify: get-verify-batch -Count 1, один документ
-> сверка F, L, T, O (код, связи, задачи V6, Obsidian)
-> mark-verify-done (закрыть шаг в verify-registry.tsv)
-> повтор до конца очереди по команде "продолжи сверку"
```

Сводка очередей: `audit-docs.ps1`, `validate-docs.ps1`, `sync-docs.ps1`.

---

## 3. Мета-контур: самосовершенствование

```
harness-improvement (наблюдения, минимальная правка канона плюс тест)
-> sync-agent-views.sh (зеркала 3 сред плюс parity-report)
```

Наблюдения - доказательства, а не разрешение. Изменения идут через
harness-improvement и проверяются паритетом сред.

---

## 4. Синхронизация сред

```
.cursor/ (канон: rules 39, skills 28, mcp.json 21 сервер, mcp.env)
 через generate-agent-configs.py в .codex/ и .kilo/ (skills, rules, AGENTS, kilo.jsonc плюс permissions fragment)
 через generate-mcp-config.py в mcp.json и mcp_config.json с раскрытыми путями (Antigravity через .agents)
 LF-нормализация текстов везде (P1)
 parity-report.json: passed 3 вью плюс generated_at плюс canon_hash, stale означает fail синка (P2)
```

---

## 5. Отчетный контур после push

Единый `workflow-context.json`: scope, evidence, SHA-256, permissions. Цепочка
`send-to-git`, task-doc, task-change-report, jira-report делит один контекст.

```
workflow-context.json (единый контекст: scope, evidence, SHA-256, permissions)
-> task-change-report (report-model.json в report.html, было, изменение, стало, почему)
-> jira-report (комментарий в стиле команды, последняя строка релиз)
```

Детали контракта передачи: `synh_harnes/report-workflow-plan.md`.

---

## Связи

- [Точка входа](../index.md) - карта каталога
- [Скилы задач](./02-skills.md) - участники цикла
- [Скилы документации](./02-skills.md) - участники сверки
- [Мета-харнес](./02-skills.md) - участники мета-контура
- [Канон и среды](./01-canon-envs.md) - синк и parity
- [JSONdoc](./06-jsondoc.md) - batch пачки по скилам
- Схемы существуют только текстом здесь (визуальная harnes.html удалена 2026-10-02)

---

## История изменений

- 2026-11-10: по аудиту скилов уточнены shadow и разрешение автоматической публикации, лимит пакета и происхождение даты; скил ponytail исключён из изменений по запросу пользователя.
- 2026-11-09: схема бизнес-анализа приведена к атомарному скилу и драйверу; показаны кэш, агентская сверка и закрепление требований в плане вместо автопубликации из gototask.
- 2026-11-09: workflow обновлён по publication journal, recovery и границе semantic matching; analysis теперь публикуется в том же согласованном наборе.

- 2026-10-01: вынесено из `readmy.md` в `.doc/harnes/`
- 2026-10-30: добавлен контур business-analyst и gototask hook (shadow по умолчанию).
- 2026-11-06: жизненный цикл начинается с `task-spec`: сбор требований и вложений до перехода к задаче Jira.
- 2026-10-29: factual audit: rules 16, scripts 18, mcp.json 18 серверов
