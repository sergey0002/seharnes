# Набор скилов `skill-creator` + `skill-auditor` (`v3.1.0`) — Создание, аудит, 17-агентная переносимость и бенчмарк AI-скилов

В workspace размещены два взаимодополняющих братских скила, спроектированных по исследованиям лучших 2026 фреймворков (`agentskills.io`, `anthropics/skills`, `mattpocock/skills`, `openai/skills`, `obra/superpowers`, `vercel-labs/skills`):
1. **`skill-creator/`** — проектирование, извлечение из диалога, детерминированный скаффолдинг, ревью в чистом контексте, генерация `evals`/`agents/openai.yaml` и упаковка `.skill`-архивов с **100% (`17/17`) кросс-агентной переносимостью из коробки** и автоинтеграцией со `skill-auditor`.
2. **`skill-auditor/` (`v3.1.0`)** — независимый многоагентный аудит существующих `SKILL.md`-пакетов, `.skill`/`.zip`-архивов, субагентов, `AGENTS.md`/`CLAUDE.md`/`GEMINI.md`, `.cursor/rules/*.mdc` и целых флитов (`--target-type fleet`) по 8 измерениям, 40 критериям, безопасности и 17-агентной совместимости.

> **Принцип разделения «Код vs Модель»:** `scripts/static_audit.py` и `scripts/eval_runner.py` выполняют только объективные детерминированные операции (парсинг, лимиты, 17-агентную матрицу формата и авто-подхватывания, графы ссылок, symlinks, покрытие, `.pyc`/PNG chunks/PEP 723 typosquatting, AST-паспорта и taint-потоки, математика ROI, SARIF 2.1.0 и метрики трасс). Семантический анализ текста (`FLUFF`, `AMBIG`, `CAGE`, `SCAR`, `CSO-LEAK`, `UNREQ-ESCALATION`, смысловые `CONTRA`), **по-скриптовый разбор `SCRIPT-OVERREACH` (`D5.6`)**, **решение об уместности A/B-теста (`AB_MEANINGFUL` vs `WITH_SKILL_ONLY`)** и **оценка поведения AI на этапе выполнения** всегда принадлежат LLM-аудиторам!

> **Примечание о расположении `README.md`:** согласно рекомендациям по упаковке скилов (критерий `D8.3` / запах `README-IN-SKILL`), этот файл размещается рядом с папкой скила, а внутри [`skill-auditor/`](skill-auditor/) документация по расширению критериев лежит в [`skill-auditor/references/extending-criteria-ru.md`](skill-auditor/references/extending-criteria-ru.md).

---

## 1. Что нового в `v3.1.0` и `v3.0.0`

1. **Движок кросс-агентной переносимости и универсального авто-подхватывания (`v3.1.0` — 17 таргетов + `vercel-labs/skills` экосистема 75+ клиентов):**
   - **Матрица совместимости по 17 таргетам (`platform_compatibility.agents` + `universal_portability`):** детерминированно проверяет формат и особенности загрузчика для **Core (`agentskills.io`), Claude Code, OpenAI Codex, Cursor, Google Antigravity, Kilo Code, OpenCode, Pi Agent (`pi-coding-agent`), Qoder, GitHub Copilot, Windsurf (Cascade), Cline, Roo Code, Gemini CLI, AWS Kiro, Sourcegraph Amp и OpenClaw**.
   - **Детекция ловушек несовместимости (без `SCRIPT-OVERREACH`):** строгий `name == dir` и обязательность `description` (Pi молча отбрасывает скил без `description`!), строгий 5-ключевой/string-metadata парсер **OpenCode**, не-принуждение `allowed-tools` (Cursor / Pi / OpenCode / Gemini CLI / Kiro), отсутствие эквивалентов `disable-model-invocation` (`agents/openai.yaml` для Codex / `metadata.opencode/autoinvoke` для OpenCode), `context: fork`, не-канонические подпапки (`resources/`/`docs/`/`examples/` → `PORT-NONCANONICAL-DIR`), а также синтаксические вендор-локи (`!`command``, unguarded `${CLAUDE_SKILL_DIR}`, жёсткие пути и эксклюзивные имена тулов вроде `MultiEdit`/`grep_search`/`execute_command` → `PORT-VENDOR-LOCK`).
   - **Анализ реальной области авто-подхвата (`detected_install_scope` + `auto_discovered_from_current_path`):** показывает, какие из 16 агентов автоматически увидят скил прямо из текущей папки (13 агентов нативно читают `.agents/skills/`, тогда как Claude Code `.claude/skills/`, Qoder `.qoder/skills/` и Kiro `.kiro/skills/` требуют отдельной установки/симлинка через `npx skills add <source> --all`).
2. **Умный A/B + Runtime Execution Evaluator (`scripts/eval_runner.py` + `agents/execution-evaluator.md`):**
   - **AI Applicability Gate перед запуском A/B:** если скил задаёт уникальную строгую валидацию документа, закрытую корпоративную схему или локальный скрипт, которые **без скила сделать невозможно**, режим `WITH_SKILL_ONLY` осознанно **пропускает бессмысленный `without_skill` прогон** (`ab_skipped`), не тратит на него токены и не искажает `Impact Score`.
   - **Оценка AI на этапе выполнения (5 осей runtime-трассы):** проверка `progressive_disclosure`, `script_and_tool_discipline`, `invariant_and_guardrail_compliance`, `context_and_turn_economy` и `output_spec_accuracy`.
   - **Four Buckets + Runtime Buckets:** автоматическая детекция `WORKING`, `GAP`, `REDUNDANT` (голая модель уже даёт `>=80%`!), **`REGRESSION`** (скил ухудшает сильную модель!), `RUNTIME_PASS` и `RUNTIME_GAP`.
2. **Углублённый детерминированный скан безопасности и структуры (`scripts/static_audit.py`):**
   - **Symlink Escape (`SEC-SYMLINK-ESCAPE`)** & защита от **Zip-Slip / Zip-Bomb** для `.skill`/`.zip`.
   - **Coverage Confidence:** учёт нечитаемых/бинарных файлов — при неполном покрытии статус `CLEAR` запрещён (`INCOMPLETE_COVERAGE`).
   - **Скрытые векторы:** `.pyc` байткод (`SEC-PYC-BYTECODE`), инструкции в PNG `tEXt`/`iTXt`/`zTXt` (`SEC-IMG-METADATA`), `!command` и frontmatter `hooks:` (`SEC-LOADTIME-EXEC`), `conftest.py`/автотесты вне `evals/` (`SEC-AUTO-EXEC-TEST`), npm `postinstall` (`SEC-PKG-LIFECYCLE`), **PEP 723 / PyPI / npm typosquatting (`SG10`)** и внутрипроцедурный **AST `source → sink` taint-анализ**.
   - **Cross-Skill Privilege Chaining (`SG09` / «Lethal Trifecta»):** обнаружение опасного сочетания *недоверенный ввод + чтение чувствительных файлов + сетевой egress* между дочерними/флотовыми скилами.
   - **Полный Package Token Budget**, незакрытые code fences (`MD-UNCLOSED-FENCE`), `+x` ловушка (`SCRIPT-EXEC-BIT-TRAP`) и валидация `agents/openai.yaml` / `.mcp.json` / `hooks.json` / `plugin.json`.
4. **Энтерпрайз-вывод, политика, ROI и безопасный цикл доработки (`scripts/score_aggregator.py`):**
   - **Quick-Win ROI (`roi_top_actions`):** детерминированный расчёт `+баллов` за закрытие каждой рекомендации.
   - **SARIF 2.1.0 (`--sarif-out`)** для GitHub Code Scanning / IDE и **профили политик (`--policy strict | balanced | permissive`)**.
   - **Bounded Improve Loop (`references/improve-loop-protocol.md` + `--compare-prev`):** итеративные правки только с одобрения человека, с журналом раундов, scope guard, остановкой при не-сходимости и детекцией **Guarantee Weakening**.
5. **Точечные доработки критериев LLM:** `CSO-LEAK` (запрет утечки шагов в `description`), `UNREQ-ESCALATION` (`D1.4`), `Anti-Rationalization` (`D3.5`), `Over-Generalization` в `SCAR` (`D3.6`) и `SG07` Manifest-vs-Code Alignment (`D5.5`).

---

## 2. Конфигурация скила (`skill-auditor/config.json`)

```json
{
  "schema_version": "3.1.0",
  "default_output_language": "ru",
  "language_override_policy": "Always render audit reports and summaries in default_output_language unless the user explicitly writes or asks for another language.",
  "preserve_technical_identifiers": true,
  "default_self_audit_safe": false,
  "default_policy_profile": "balanced",
  "dimension_weights": {},
  "custom_dimensions": []
}
```

- **`default_output_language: "ru"`** — отчёты и сводки по умолчанию строятся на русском (переключение — запросом пользователя или `--lang en`).
- **`default_policy_profile: "balanced"`** — профиль строгости (`strict`, `balanced`, `permissive`).
- **`dimension_weights` и `custom_dimensions`** — декларативное переопределение весов и подключение `D9+` (сумма весов строго `100.0`).

---

## 3. Таблица 8 измерений и 40 подкритериев (`D1–D8`)

| Измерение (Вес) | ID | Критерий | Что проверяется | Способ проверки |
|---|---|---|---|---|
| **D1. Triggering & Discoverability** (`14%`) | `D1.1` | Spec & Naming Validity | `name` (1–64, `[a-z0-9-]`, равен имени папки), `description` (1–1024), 0 XML (`XID`), валидный YAML | **Статика** |
| | `D1.2` | Trigger Triad & Front-Loading | `[Что] + [Когда] + [Ключи]` в `description_first_250` (Claude / Codex 2% / 8KB) | **Статика + Семантика** |
| | `D1.3` | Point-of-View, CSO & Clarity | 3-е лицо/императив (`NTPD`), запрет **CSO Workflow-Leak** (утечки шагов в `description`) | **Семантика** |
| | `D1.4` | Boundaries, Collisions & Containment | `Do NOT use for...`, коллизии `--fleet` (`>=0.42`), защита от **Unrequested Escalation** | **Статика + Семантика** |
| | `D1.5` | Ecosystem Discovery, Paths & Multilingual | Ссылка из `AGENTS.md`/`CLAUDE.md` (56% miss), универсальный деплой `.agents/skills/` + `.claude/.qoder/.kiro`, RU/EN синонимы | **Статика + Семантика** |
| **D2. Context Engineering & Progressive Disclosure** (`16%`) | `D2.1` | Density, Package Budget & Syntax | `SKILL.md` плотный, без потолка строк; `token_budget` пакета как метрика, 0 незакрытых fences (`MD-UNCLOSED-FENCE`) | **Статика + Семантика** |
| | `D2.2` | One-Level-Deep Link Discipline | Прямые `/` ссылки из `SKILL.md` (`BP`), условия загрузки, 0 битых/сирот, глубина 1 | **Статика + Семантика** |
| | `D2.3` | Signal-to-Noise & Zero `FLUFF` | **Zero-Gain Deletion Test**: 0 «воды», банальностей и дублирования между файлами | **Семантика** |
| | `D2.4` | KV-Cache, Prefix & Thinking Stability | Append-only префикс (0 timestamp/random ID), стабильность списка тулов и `thinking`-блоков | **Статика + Семантика** |
| | `D2.5` | Long-Horizon Window Ladder & Memory | Выгрузка тулов `>25K` → сброс фаз → compaction; гигиена `/memories` (`exclude_tools`) | **Семантика** |
| **D3. Prompt & Procedural Engineering** (`14%`) | `D3.1` | Path Freedom vs Fragility (`CAGE`/`SOC`) | Максимум доменного контекста и инвариантов при свободе стратегии сильной модели | **Семантика** |
| | `D3.2` | Thesis Autonomy & Coherence (`AMBIG`/`CONTRA`) | Автономность тезиса без чата (`AMBIG`), 0 противоречий (`CONTRA`) между YAML/кодом/агентами | **Статика + Семантика** |
| | `D3.3` | Decision Criteria & Sane Defaults | Критерии выбора и рекомендованный дефолт (`TOB` avoidance) | **Семантика** |
| | `D3.4` | Output Contracts & Examples | Строгие шаблоны (`MT`) только там, где нужен парсинг; примеры при реальной неоднозначности | **Семантика** |
| | `D3.5` | Rationale, Traps & Anti-Rationalization | Причины ограничений (`why`), ловушки (`Gotchas`) и закрытие отговорок для high-stakes шагов (`RL`) | **Семантика** |
| | `D3.6` | Scar Tissue & Over-Generalization (`SCAR`) | Удаление костылей слабых моделей + запрет возводить единичный баг в `ALWAYS/MUST` | **Семантика** |
| **D4. Multi-Agent & Orchestration** (`16%` / `N/A`) | `D4.1` | Pattern Fit & Anti-Overengineering | Минимально достаточная топология без лишнего распараллеливания | **Семантика** |
| | `D4.2` | Bidirectional Context Hygiene | **Вход:** ролевой срез + 4-частный бриф + scoped tools/`skills:`. **Выход:** изолированное окно + сжатый результат | **Статика + Семантика** |
| | `D4.3` | Child-Skill Mechanics & Preloading | Ацикличность `skills/*/SKILL.md`, явный `skills:` в субагентах | **Статика + Семантика** |
| | `D4.4` | Typed Contracts, MAST & `SG09` | Защита от 14 сбоев MAST (`FM-1.1..3.3`) и кросс-скиловых цепочек (`SG09` Lethal Trifecta) | **Статика + Семантика** |
| | `D4.5` | Concurrency Safety & Fallback | Защита от гонок записи (`readonly: true`, `worktree`) + последовательный fallback | **Статика + Семантика** |
| **D5. Tools, MCP & Scripts** (`12%` / `N/A`) | `D5.1` | MCP Context Efficiency | Tool Search / deferred loading, >25K spill, tool masking | **Семантика** |
| | `D5.2` | Least-Privilege Scoping & Fallback | Узкий `allowed-tools` / `disallowedTools` + деградация при недоступном MCP | **Статика + Семантика** |
| | `D5.3` | Tool Consolidation & Deterministic Offload | Консолидация тулов и вынос точных расчётов/парсинга в `scripts/` (`MUS`) | **Статика + Семантика** |
| | `D5.4` | Script Ergonomics, `+x` & Error Affordance | Синтаксис, PEP 723, 0 TTY, `--help`, JSON, `--dry-run`, явный интерпретатор (`SCRIPT-EXEC-BIT-TRAP`), `stderr` подсказки | **Статика + Семантика** |
| | `D5.5` | Data Trustworthiness & `SG07` Alignment | Свежесть источников (`TSS`), соответствие `description`/`allowed-tools` реальному AST/taint скриптов (`SG07`), `model:` override | **Статика + Семантика** |
| | `D5.6` | Per-Script Rationality (`SCRIPT-OVERREACH`) | Обязательный разбор **каждого** скрипта: оправдан ли он или узурпирует смысловую работу LLM регулярками | **Статика (AST) + Семантика** |
| **D6. Verification & Reliability** (`12%`) | `D6.1` | Verification Loops | Валидация/линтер/тесты перед завершением (`NVS`/`EWP`) | **Семантика** |
| | `D6.2` | Failure Recovery & Bounded Retries | Документированные сбои, сохранение ошибок, лимит ретраев | **Семантика** |
| | `D6.3` | Complexity Contract & Fast-Path | Быстрый путь для простых входов (против деградации SkillsBench) | **Семантика** |
| | `D6.4` | Guardrails & HITL | Отказы вне области (`NG`) и подтверждения перед необратимыми действиями (`NAH`) | **Семантика** |
| | `D6.5` | Smart A/B Gate & Runtime Execution Eval | Разделение `AB_MEANINGFUL` и `WITH_SKILL_ONLY` (если без скила невозможно), оценка трассы выполнения и anti-bias | **Статика + AI Execution** |
| **D7. Security & Supply-Chain** (`10%` + Gates) | `D7.1` | Injection, PNG Metadata & Untrusted Data | 0 скрытых Unicode/HTML-инъекций, PNG `tEXt`/`iTXt` (`SEC-IMG-METADATA`), граница недоверенных данных | **Статика + Семантика** |
| | `D7.2` | Execution, Load-Time & Symlink Safety | 0 `curl\|bash`, `eval/shell=True`, `SEC-SYMLINK-ESCAPE`, `.pyc`, `conftest.py`, `!command`/frontmatter `hooks:` | **Статика + Семантика** |
| | `D7.3` | Secrets, AST Taint & Lethal Trifecta | 0 ключей, AST `taint_flows` (`environ -> net`), кросс-скиловый `SG09` | **Статика + Семантика** |
| | `D7.4` | Supply-Chain, Coverage Confidence & Persistence | Фиксированные версии, анти-typosquatting (`SG10`), `postinstall`, защита `MEMORY.md`, правило `INCOMPLETE_COVERAGE` | **Статика + Семантика** |
| **D8. Portability & Maintainability** (`6%`) | `D8.1` | Core Standard & 17-Agent Format Compliance | Чистая структура `<name>/SKILL.md` (`scripts/`, `references/`, `assets/` без плоских `.md` и `resources/`), `name == dir`, обязательный `description`, string-`metadata` (OpenCode), проверка всех 17 агентов (`Antigravity`, `Kilo`, `OpenCode`, `Pi`, `Qoder` и др.) | **Статика + Семантика** |
| | `D8.2` | Extensions, Vendor Locks & Auto-Discovery | Деградация `context: fork`, `allowed-tools` (Cursor/Pi/OpenCode/Gemini/Kiro), `disable-model-invocation` ↔ `openai.yaml`/`opencode`, `PORT-VENDOR-LOCK` (`!command`, `${CLAUDE_SKILL_DIR}`, тулы), `PORT-PATH-SILO`, symlink trap | **Статика + Семантика** |
| | `D8.3` | Terminology & Hygiene | Единые имена, нет `README.md` внутри корня скила, актуальные метаданные | **Статика + Семантика** |

---

## 4. Куда добавлять новые критерии

См. подробную инструкцию в [`skill-auditor/references/extending-criteria-ru.md`](skill-auditor/references/extending-criteria-ru.md):
- Новый семантический подкритерий в `D1–D8`: впишите в `references/rubric-criteria.md` + профильный `agents/*-auditor.md` (код Python менять не нужно).
- Новую детерминированную проверку (только объективные факты/AST/безопасность): `references/mast-and-smells-catalog.md` + `scripts/static_audit.py` + `scripts/self_test.py`.
- Новое измерение `D9+` или веса: задайте прямо в `skill-auditor/config.json` (`dimension_weights` + `custom_dimensions`, сумма = `100.0`).

---

## 5. Быстрый запуск и команды CLI

```bash
# 1. Полный регрессионный сьют v3.1 (включая тест 17-агентной матрицы совместимости)
python3 skill-auditor/scripts/self_test.py

# 2. Детерминированный пре-аудит (папка, .skill/.zip архив, AGENTS.md, .mdc или --target-type fleet)
python3 skill-auditor/scripts/static_audit.py path/to/target --fail-on-critical -o /tmp/static.json

# 3. Агрегация с политикой, Quick-Win ROI, SARIF 2.1.0 и сравнением раундов
python3 skill-auditor/scripts/score_aggregator.py \
  --static /tmp/static.json --findings /tmp/finding_*.json \
  --policy balanced --sarif-out /tmp/audit.sarif.json --markdown-out /tmp/summary.md -o /tmp/summary.json

# 4. Умный A/B + Runtime Execution бенчмарк (с AI Applicability Gate)
python3 skill-auditor/scripts/eval_runner.py prepare --evals path/to/evals.json --workspace /tmp/eval_ws --applicability /tmp/eval_app.json
python3 skill-auditor/scripts/eval_runner.py score --judgments /tmp/eval_judgments.json --markdown-out /tmp/eval_bench.md -o /tmp/eval_bench.json

# 5. Самоаудит самого skill-auditor
python3 skill-auditor/scripts/static_audit.py skill-auditor --self-audit-safe --fail-on-critical
```

---

## 6. Братский скил `skill-creator/` — подготовка новых 17-агентных скилов

[`skill-creator/`](skill-creator/) объединяет лучшие практики ведущих 2026 создателей скилов и встроенные стандарты качества `skill-auditor v3.1.0`:
- **Извлечение намерения и ветвлений (`anthropics/skills` + `mattpocock/grill-me`):** переиспользование наблюдаемого контекста диалога и точечные вопросы только по неразрешённым развилкам (*Red Baseline*, режим вызова, входы/выходы).
- **Инженерия для frontier-моделей (`mattpocock/writing-for-agents` + `obra/superpowers`):** баланс **Context Load vs Cognitive Load** (model-invoked vs `disable-model-invocation` vs router skill), **Context Pointers** на глубине 1, проверяемые **Completion Criteria** на каждом шаге (против преждевременного завершения), позитивные формулировки с объяснением причины (`why`), удаление no-op строк и анти-паттернов `FLUFF`/`CAGE`/`SCAR`/`CSO-LEAK`.
- **Чистое разделение «Код vs LLM» (`D5.6`):** скрипты `scripts/` выполняют только детерминированный скаффолдинг, генерацию `agents/openai.yaml`, безопасную ZIP-упаковку `.skill` и проверку инвариантов — никакой подмены LLM-семантики регулярками.
- **Универсальность на 17+ агентов из коробки:** строгие 6 ключей frontmatter, строковые значения `metadata` (OpenCode), опциональное зеркалирование `.agents/skills/` + `.claude/.qoder/.kiro`, и автоматическая проверка через соседний `skill-auditor`, если он присутствует.

### Структура `skill-creator/`
- [`skill-creator/SKILL.md`](skill-creator/SKILL.md) — компактный оркестратор (`66` строк / `934` токена; весь пакет `3,928` токенов = `1.96%` окна 200K).
- [`skill-creator/agents/skill-reviewer.md`](skill-creator/agents/skill-reviewer.md) + [`agents/openai.yaml`](skill-creator/agents/openai.yaml) — независимый `readonly: true` критик черновика и UI-метаданные OpenAI Codex.
- [`skill-creator/references/`](skill-creator/references/) — `authoring-methodology.md`, `portability-and-packaging-17.md`, `evals-and-trigger-guide.md`.
- [`skill-creator/assets/skill-md-blueprints.md`](skill-creator/assets/skill-md-blueprints.md) — эталоны 4 архетипов (`atomic`, `script`, `multi-agent`, `user-invoked`).
- [`skill-creator/scripts/`](skill-creator/scripts/) — `scaffold_skill.py`, `package_and_verify.py`, `self_test.py`.
- [`skill-creator/evals/`](skill-creator/evals/) — `evals.json` (5 кейсов с разметкой `AB_MEANINGFUL` / `WITH_SKILL_ONLY`) и `trigger_evals.json` (20 RU/EN запросов без пересечения со `skill-auditor`).

### Быстрые команды `skill-creator`
```bash
# 1. Регрессионный самотест (5/5, включая авто-интеграцию со skill-auditor)
python3 skill-creator/scripts/self_test.py

# 2. Детерминированный скаффолдинг нового 17-агентного скила (с зеркалированием в .claude/.qoder/.kiro)
python3 skill-creator/scripts/scaffold_skill.py "my-new-skill" \
  --output-dir .agents/skills \
  --archetype script \
  --resources scripts,references,evals \
  --description "What it does. Use when <triggers>. Do NOT use for <exclusions>." \
  --mirror-project . \
  --json

# 3. 17-агентный префлайт, авто-аудит через skill-auditor и сборка .skill архива
python3 skill-creator/scripts/package_and_verify.py .agents/skills/my-new-skill --json
```

