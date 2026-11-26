# Замена описаний верхнеуровневых скилов

<!-- meta
type: rules
status: actual
updated: 2026-11-24
related: [skill-format.md, index.md]
tags: [skills, omp, descriptions, routing, restore]
-->

---

## Суть

Документ фиксирует замену `description` у 28 верхнеуровневых скилов в `.agents/skills`. Замена нужна, чтобы omp не отправлял описания в LLM-сжатие и не терял триггеры маршрутизации. Здесь лежат исходный и новый текст каждого описания, поэтому любую замену можно откатить вручную. Затронут только YAML-ключ `description` в `SKILL.md`, тела скилов, имена и дочерние скилы не менялись.

---

## Почему заменяли описания

omp 19.1.1 читает скилы из `.agents/skills/<name>/SKILL.md` без рекурсии: 28 верхнеуровневых видит, 50 дочерних не видит. Описание длиннее 100 символов omp отправляет на сжатие в smol-модель по промпту `compress-description.md` и кэширует результат в `~/.omp/agent/skill-descriptions.db`.

Границы сжатия по коду omp:

| Параметр | Значение | Следствие |
|---|---|---|
| Порог сжатия | 100 символов после нормализации пробелов | до 100 сжатия нет, текст уходит дословно |
| Лимит результата | 160 символов, одна строка | лимит 12 слов не проверяется |
| Запасной вариант | первые 99 символов с обрезкой | триггеры из конца описания теряются |
| Ключ кэша | sha256(промпт + имя скила + описание) | правка текста меняет ключ и запускает сжатие заново |
| Отключение | настройки нет | выключить сжатие нельзя |

До замены все 28 описаний были длиннее 100 символов, поэтому сжимались все. Сжатые hints теряли русские триггеры и перечисления дочерних скилов. Новые описания короче 100 символов, поэтому сжатие для них не запускается.

---

## Что заменено

Длина считается по нормализованному тексту в единицах UTF-16, как в omp.

| Скил | Файл | Было | Стало | Причина |
|---|---|---:|---:|---|
| `code` | `.agents/skills/code/SKILL.md` | 326 | 88 | Триггеры root cause, diff и путь вызовов вынесены вперёд, добавлен явный запрет править код. |
| `codebase-memory-mcp` | `.agents/skills/codebase-memory-mcp/SKILL.md` | 230 | 98 | Оставлены CBM, search_graph, trace_path; отрицание уводит документы и схемы БД в другие скилы. |
| `codegraph` | `.agents/skills/codegraph/SKILL.md` | 217 | 93 | Сохранены context/affected/ui и blast radius, убрана вода про редактирование исходников. |
| `codeprism` | `.agents/skills/codeprism/SKILL.md` | 362 | 84 | Оставлены поток данных и security gate перед записью, убран длинный английский хвост. |
| `context7` | `.agents/skills/context7/SKILL.md` | 168 | 94 | Триггеры синтаксис, настройки, версии, миграции стоят в первых словах. |
| `copytrust` | `.agents/skills/copytrust/SKILL.md` | 465 | 88 | Сохранены UIN, email, taskId, локальный стенд и d8; перечень разговорных фраз заменён короткими триггерами. |
| `documentation-router` | `.agents/skills/documentation-router/SKILL.md` | 137 | 96 | Команды задокументируй, продолжи индексацию, сверь стоят впереди; дети не перечисляются. |
| `exhaustive-research-decision-v6` | `.agents/skills/exhaustive-research-decision-v6/SKILL.md` | 667 | 91 | Длинная цепочка этапов свёрнута в исследование, критерии, доказательства, reuse. |
| `git` | `.agents/skills/git/SKILL.md` | 206 | 91 | Сохранены status/diff/log/blame и запрет commit/push без просьбы. |
| `graphiti` | `.agents/skills/graphiti/SKILL.md` | 176 | 82 | Сохранены история решений, факты и эпизоды памяти проекта. |
| `harness-router` | `.agents/skills/harness-router/SKILL.md` | 342 | 96 | Сохранены синк сред, перенос kit, настройка проекта, mirror, аудит и улучшение; убран список детей. |
| `jdocmunch` | `.agents/skills/jdocmunch/SKILL.md` | 205 | 96 | Сохранены фраза найди в документации и корпуса architecture/tasks/harnes/web. |
| `login-as-user` | `.agents/skills/login-as-user/SKILL.md` | 385 | 75 | Сохранены clientId, имперсонейт, ограничение dev и запрет прода. |
| `mysql` | `.agents/skills/mysql/SKILL.md` | 156 | 96 | Сохранены describe_table и SELECT, добавлено условие записи только с разрешением. |
| `neiroslop` | `.agents/skills/neiroslop/SKILL.md` | 440 | 90 | Сохранены очеловечь, канцелярит, проверка стиля и запрет трогать код и цитаты. |
| `php-deps-mcp` | `.agents/skills/php-deps-mcp/SKILL.md` | 156 | 90 | Сохранены phpcallgraph и phpda, добавлено отрицание для JS. |
| `phpstan-mcp` | `.agents/skills/phpstan-mcp/SKILL.md` | 166 | 95 | Сохранены типы, аргументы, сигнатуры и запуск по задаче; добавлено отрицание браузерных тестов. |
| `playwright` | `.agents/skills/playwright/SKILL.md` | 167 | 91 | Сохранены DOM, клики, скриншоты и условие отсутствия Cest или PHPUnit. |
| `ponytail` | `.agents/skills/ponytail/SKILL.md` | 366 | 96 | Сохранены be lazy, YAGNI и минимальная полная правка; многострочный YAML заменён одной строкой. |
| `prepare-plan` | `.agents/skills/prepare-plan/SKILL.md` | 361 | 93 | Сохранены подготовь план, stage2 и запреты на реализацию, аудит и тесты. |
| `semgrep` | `.agents/skills/semgrep/SKILL.md` | 153 | 90 | Сохранены SQL, XSS, доступ, данные и AST; добавлено отрицание проверки типов PHP. |
| `send-to-git` | `.agents/skills/send-to-git/SKILL.md` | 287 | 96 | Сохранены отправь в гит, commit/push и требование сначала согласовать. |
| `serena` | `.agents/skills/serena/SKILL.md` | 158 | 87 | Сохранены find_symbol, references и LSP-диагностика; добавлено отрицание JS и Vue. |
| `skill-auditor` | `.agents/skills/skill-auditor/SKILL.md` | 548 | 96 | Сохранены аудит и оценка скила, переносимость, A/B; добавлено отрицание создания с нуля. |
| `skill-creator` | `.agents/skills/skill-creator/SKILL.md` | 394 | 84 | Сохранены создание скила, scripts/evals и упаковка .skill; добавлено отрицание аудита. |
| `task-router` | `.agents/skills/task-router/SKILL.md` | 468 | 95 | Сохранены постановка, переход, diff, аудит плана, ревью, тесты, Jira/Kaiten, отчёт, документация. |
| `todone` | `.agents/skills/todone/SKILL.md` | 115 | 92 | Сохранены очереди, JSON-записи, типы, потоки, доказательства и отчёты. |
| `yadisk-screenshot` | `.agents/skills/yadisk-screenshot/SKILL.md` | 481 | 87 | Сохранены все формы ссылок, скачивание скрина и условие публичной ссылки. |

---

## Новые описания

Значения применены в `SKILL.md` как однострочный YAML-скаляр в двойных кавычках.

```yaml
code: "Найди причину бага: бизнес-логика, diff, путь вызовов, root cause; без исправления кода."
codebase-memory-mcp: "Структура кода, кто вызывает, связи, влияние diff: CBM/search_graph/trace_path; не документы и БД."
codegraph: "Граф кода: символы, пути вызовов, blast radius, context/affected/ui; не документы и схема БД."
codeprism: "Связи и влияние правок, поток данных, security gate перед записью; не запуск тестов."
context7: "Документация библиотек, SDK, API, CLI: синтаксис, настройки, версии, миграции; не код проекта."
copytrust: "Логи площадки/заказа по UIN/email/taskId; проверь в браузере на локальном стенде или d8."
documentation-router: "Задокументируй проект/задачу, продолжи индексацию, сверь документацию с кодом; не поиск раздела."
exhaustive-research-decision-v6: "Сравни и выбери решение: исследование, критерии, доказательства, reuse; не быстрая справка."
git: "Прочитай status/diff/log/blame, проверь авторство изменений; без commit/push и смены ветки."
graphiti: "Найди историю решений, факты и эпизоды в памяти проекта; сохрани разрешённый факт."
harness-router: "Харнес: скилы/правила, MCP, синк сред, перенос kit, настройка проекта, mirror, аудит, улучшение."
jdocmunch: "Найди в документации, где описано, подтяни контекст: .doc/architecture/tasks/harnes/web; не код."
login-as-user: "Войди как клиент/clientId через админский имперсонейт на dev; никогда прод."
mysql: "Проверь схему БД, таблицы, колонки и данные: describe_table/SELECT; запись только с разрешением."
neiroslop: "Убери нейрослоп/канцелярит, очеловечь русский текст, проверь стиль; не код и чужие цитаты."
php-deps-mcp: "Зависимости PHP, граф вызовов phpcallgraph/phpda, влияние правки общих компонентов; не JS."
phpstan-mcp: "После правок PHP проверь типы, аргументы и сигнатуры по файлам или задаче; не браузерные тесты."
playwright: "Проверь DOM, клики, скриншоты в видимом браузере, если нет Cest/PHPUnit; иначе Codeception."
ponytail: "Пиши, исправляй, рефактори и ревьюй код минимальной полной правкой; be lazy, YAGNI; без лишнего."
prepare-plan: "Подготовь план, составь план, plan.md, stage2; без реализации, аудита плана и запуска тестов."
semgrep: "Проверь безопасность SQL/XSS/доступа/данных, AST и правила сканера; не проверка типов PHP."
send-to-git: "Отправь в гит, закоммить и запушь: согласуй файлы, сообщение и команды; исполняй после согласия."
serena: "Символы PHP, find_symbol, references, LSP-диагностика перед правкой; не JS/Vue-символы."
skill-auditor: "Проверь/оцени скил, SKILL.md, AGENTS.md: аудит качества, переносимости, A/B; не создание с нуля."
skill-creator: "Создай новый скил: SKILL.md, scripts/evals, упаковка .skill; не аудит существующего."
task-router: "Задача: постановка, переход, diff, аудит плана, ревью, тесты, Jira/Kaiten, отчёт, документация."
todone: "Управляй локальными очередями, JSON-записями, типами, потоками, доказательствами и отчётами."
yadisk-screenshot: "Скачай скрин/файл с Яндекс.Диска: disk.yandex.ru/i/, /d/, yadi.sk/i/; публичная ссылка."
```

---

## Оригиналы для восстановления

Ниже дословные блоки, которые стояли в `SKILL.md` до замены. Для отката замените текущий блок `description:` на соответствующий блок из этого раздела.

```yaml
# code
description: >-
  Расследование поведения кода CopyTrust: поиск истинной причины бага по
  описанию, дифам, связанным задачам, документации, бизнес-логике и графу
  вызовов. Дочерние: bug-cause. Use when the user says найди причину бага,
  почему баг, root cause, разбери баг по коду, исследуй диф, граф вызовов,
  бизнес-путь бага, code investigation.
```

```yaml
# codebase-memory-mcp
description: "Explore code structure, callers and diff impact: CBM, search_graph, trace_path, граф кода, кто вызывает. Not for documentation or database schemas; use jdocmunch or mysql. Uses only the current project's codebase-memory-mcp index."
```

```yaml
# codegraph
description: >-
  Codegraph, граф кода, контекст задачи, какие тесты затронуты, открыть граф.
  Use for codegraph context/affected/ui/explore, symbols, call paths and blast
  radius. Not for documentation, database schemas or source edits.
```

```yaml
# codeprism
description: Uses the CodePrism knowledge graph to give an agent structural context before reading files: symbols, callers, callees, impact, dependencies, data flow and a security gate before writes. Use when exploring an unfamiliar module, planning a refactor, tracing callers, checking blast radius, or scanning proposed code for secrets and vulnerabilities before writing.
```

```yaml
# context7
description: Документация внешних библиотек, SDK, фреймворков, CLI и API через MCP Context7. Применять для вопросов о синтаксисе API, конфигурации, версиях и миграциях зависимостей.
```

```yaml
# copytrust
description: >-
  Работа с площадкой CopyTrust: чтение логов по номеру заказа, UIN, e-mail
  клиента или taskId и браузерная проверка задачи на выбранной площадке,
  локальной или удалённой. Дочерние: platform-logs, platform-browser-test.
  Use when the user says логи площадки, логи заказа, что в логах по заказу,
  проверь задачу в браузере, браузерная проверка задачи, на какой площадке
  тестировать, локальный стенд, d8, зайди в админку, войди под клиентом,
  copytrust logs, platform logs.
```

```yaml
# documentation-router
description: Маршрутизатор документации: карта проекта, сверка документации с кодом, документация задачи. Дочерние: project-doc, doc-verify, task-doc.
```

```yaml
# exhaustive-research-decision-v6
description: Универсальный deep-research скилл: сырая мысль -> одобренный бриф -> поиск существующих решений с proven use -> единый criteria.csv (включая синтетические метрики) -> полная матрица candidate x criterion -> adopt/adapt/extend/compose, а build только при доказанном gap. Использовать для выбора СУБД, бекапов, библиотек, фреймворков, нейромоделей, видеокарт, стандартов документирования, методик, клинических досье, восстановления после пожара и любого сравнения или проектирования. Не привязан к open source; кандидатом может быть продукт, сервис, стандарт, железо, процесс или комбинация. High risk: досье + human gate, а не диагноз, назначение или разрешение работ.
```

```yaml
# git
description: Чтение статуса, diff, истории и blame через MCP git. Применять для проверки рабочей копии и принадлежности изменений; изменения веток и публикация проходят через профильные скилы с разрешением пользователя.
```

```yaml
# graphiti
description: "Retrieve project decisions and their temporal history with Graphiti MCP, or record an authorized durable episode. Use for graphiti, memory facts, episodes and decision history."
```

```yaml
# harness-router
description: Главный маршрутизатор харнеса: синхронизация сред, перенос kit, настройка проекта, аудит MCP, карта харнеса, улучшение харнеса. Дочерние: add-skill, copy-project, environment-sync, harness-core, improvement, index, mcp-audit, migration-review, mirror, new-project, project-setup, remove-skill, skill-authoring, doc-script, doc-skill, doc-mcp.
```

```yaml
# jdocmunch
description: "Find documentation sections: найди в документации, где описано, подтяни контекст; documentation, architecture, harness, reports and dashboards via jdocmunch MCP. Not for code structure or database schemas."
```

```yaml
# login-as-user
description: >-
  Вход под конкретным клиентом (по clientId) для воспроизведения бага или
  ручной QA-проверки в браузере, через механизм админского имперсонейта
  (client/login-by-client), а не через прямой пароль клиента. Только dev-стенд
  (.tools/docker-test), никогда прод. Use when the user says войди как клиент,
  зайди под пользователем, воспроизведи баг под клиентом N, login as user,
  login as client.
```

```yaml
# mysql
description: Чтение схемы и данных dev-стенда через MCP mysql. Применять для проверки таблиц, колонок и фактических данных; execute требует отдельного явного разрешения.
```

```yaml
# neiroslop
description: "Убирает нейрослоп и канцелярит из русского текста и пишет с нуля простым разговорным языком. Для отчётов к задачам, описаний PR, писем, постов и документации; новости, научный и юридический текст сохраняют свой регистр. Триггеры: без нейрослопа, очеловечь, почисти от AI, убери канцелярит, проверь текст, что выдаёт нейросеть, humanizer, slop, звучит как ChatGPT. Не использовать для кода, таблиц и чужого текста без явной просьбы о правке."
```

```yaml
# php-deps-mcp
description: Граф вызовов и зависимостей PHP через MCP php-deps-mcp. Применять для phpcallgraph, phpda и оценки влияния изменений общих PHP-компонентов после графа кода.
```

```yaml
# phpstan-mcp
description: Статический анализ измененных PHP-файлов через MCP phpstan-mcp. Применять после правок PHP для проверки типов, аргументов и сигнатур по номеру задачи или явным путям.
```

```yaml
# playwright
description: "Verify uncovered UI behavior in a visible browser using Playwright MCP. Use for DOM inspection, clicks and screenshots when the scenario has no Cest or PHPUnit method."
```

```yaml
# ponytail
description: >
  Lazy senior dev mode: the smallest change that fully solves the task, and a
  reply a busy human understands in one read. Use on any coding task (writing,
  fixing, refactoring, reviewing, choosing dependencies) and when the user says
  "ponytail", "be lazy", "simplest solution", "yagni", or complains about
  over-engineering or bloat. Levels: lite, full (default), ultra.
```

```yaml
# prepare-plan
description: >-
  Use when the user asks to prepare or write an implementation plan:
  подготовь план, составь план, prepare plan, plan.md, stage2 plan, план этапа.
  Produces an authored plan.md with per-file Before/After patches, sources of
  truth, AC and R/S scenarios, and a self-check. Do NOT use for plan audit,
  implementation, test execution, task documentation or code review.
```

```yaml
# semgrep
description: "Scan scoped workspace files for security risks with Semgrep MCP. Use for SQL, XSS, access-control and user-data changes, custom rules and AST inspection."
```

```yaml
# send-to-git
description: >-
  Согласование отправки в git: status, список файлов задачи, предупреждение если лишнее,
  текст подтверждения и команды commit/push. Выполняет только после явного «да».
  Use when: отправь в гит, отправь в git, закоммить и запушь, commit and push,
  send to git, предложи коммит, запушь задачу.
```

```yaml
# serena
description: "Inspect PHP symbols, references and diagnostics with Serena MCP before scoped source edits. Use for find_symbol, symbol bodies, references and PHP LSP checks."
```

```yaml
# skill-auditor
description: Audits, benchmarks, and iteratively improves AI skills, .skill archives, subagents, child skills, MCP setups, scripts, AGENTS.md, Cursor .mdc rules, and skill fleets across 17+ agents. Use when reviewing, grading, checking cross-agent portability, security/triggering/context bloat, running smart A/B + runtime evals, or refactoring skills (Claude Code, Codex, Cursor, Antigravity, Kilo, OpenCode, Pi, Qoder, Copilot, Windsurf) — включая «аудит скила», «проверь SKILL.md/AGENTS.md». Do NOT use for general code review or greenfield skill authoring.
```

```yaml
# skill-creator
description: "Designs, scaffolds, and packages portable 17-agent AI Skills from scratch or chat workflows (Claude, Codex, Cursor, OpenCode, Kilo, Antigravity, Pi, Qoder). Use when creating a new skill, building scripts/openai.yaml/evals, or packaging .skill archives — включая «создай скил», «подготовь SKILL.md». Do NOT use for standalone audits of existing skills (use skill-auditor) or general app coding."
```

```yaml
# task-router
description: Главный маршрутизатор задач: постановка задачи, сбор требований и формулировка задачи, переход к задаче, diff, заведение, code review, git-task-blame, Jira, Kaiten, аналитика, тестирование, отчеты, документация задачи. Дочерние: analytics, audit-plan, git-task-blame, gototask, jira, kaiten, reporting-router, task-report, task-change-report, task-code-review, task-core, task-diff, task-intake, task-spec, testing-router, test-task, prepare-task-test, browser-verify.
```

```yaml
# todone
description: Управляет локальными очередями, JSON-записями, типами, потоками, доказательствами и отчётами через три точки входа.
```

```yaml
# yadisk-screenshot
description: >-
  Скачивает скриншот/файл с публичной ссылки Яндекс.Диска
  (disk.yandex.ru/i/..., disk.yandex.ru/d/..., yadi.sk/i/...) в
  .doc/skil_data/yadisk-screenshot/imd/ и возвращает абсолютный путь. Имя файла —
  детерминированный SHA256-хеш URL: повторный запуск использует кеш и не
  обращается к сети. Use when the user shares a Yandex.Disk link, says
  загрузи скрин с яндекса, скачай картинку с яндекс диска,
  fetch yandex screenshot, или сообщение содержит ссылку вида
  https://disk.yandex.ru/i/.
```

---

## Восстановление

1. Откройте `SKILL.md` нужного скила.
2. Найдите блок, который начинается со строки `description:` и заканчивается последней вложенной строкой перед следующим ключом frontmatter.
3. Замените блок дословно на блок из раздела "Оригиналы для восстановления".
4. Проверьте YAML-парсером, что frontmatter читается.
5. Выполните синхронизацию представлений и parity.

Массовый откат: примените все 28 блоков из раздела оригиналов. Массовый повтор замены: примените все значения из раздела новых описаний.

---

## Известные проблемы и ограничения

- Короткое описание обходит сжатие, но не гарантирует, что модель выберет нужный скил. Выбор маршрута проверяется запросами вручную.
- omp не видит дочерние скилы. Триггеры детей должны попадать в описание верхнего роутера или в его тело.
- Лимит в 12 слов относится к промпту сжатия, а не к проверке результата. Реальный предел результата 160 символов и одна строка.
- Кэш `~/.omp/agent/skill-descriptions.db` для новых описаний не используется, потому что сжатие не запускается. Чистить его для этих 28 скилов не нужно.
- При откате описания к прежнему длинному тексту включится сжатие и вернётся потеря триггеров.
- Имена скилов, пути и тела `SKILL.md` не менялись.

---

## Связи

- [Формат скила](./skill-format.md) - структура `SKILL.md`, frontmatter, дети.
- [Карта харнеса](./index.md) - место скилов и правил в харнесе.
- [Правило улучшения харнеса](../../.cursor/rules/harness-improvement.mdc) - порядок правки и синхронизации.
- [Стиль текста](../../.cursor/rules/text-style.mdc) - требования к документации и отчётам.

---

## История изменений

- 2026-11-24: создан документ и заменены описания 28 верхнеуровневых скилов ради обхода LLM-сжатия omp; сохранены оригиналы для отката.

#skills #omp #descriptions #routing
