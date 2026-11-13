# Audit Report Template (`SKILL.md` & Agent Skill Artifacts v3.1)

Render all core sections below in the language specified by `config.json` (`default_output_language: "ru"` — Russian by default, overriding only if the user explicitly requests another language). Adapt detail depth naturally to the target's complexity rather than padding trivial skills or truncating huge systems.

```markdown
# Отчёт аудита скила / Skill Audit Report: `<skill-name>`

- **Цель и тип / Target & Type:** `<path>` (`<skill-package | .skill archive | agents-md | cursor-mdc | agent-profile | plugin-bundle | skill-fleet>`)
- **Класс сложности / Complexity Tier:** `<Tier 1 | Tier 2 | Tier 3>` (путь аудита: `<Light | Balanced | Full>`, политика: `<strict | balanced | permissive>`)
- **Итоговый балл / Final Score:** **`<final_score> / 100`** (Грейд **`<A|B|C|D|F>`**, без капов: `<uncapped_score>`)
- **Вердикт / Verdict:** `<PRODUCTION_READY | PASS_WITH_RECOMMENDATIONS | CONDITIONAL_PASS_IMPROVE_RELIABILITY | MANUAL_REVIEW_REQUIRED_INCOMPLETE_COVERAGE | NEEDS_REFACTORING_BEFORE_USE | BLOCKED_REMEDIATE_CRITICAL_ISSUES>`
- **Security Gate & Покрытие:** `<CLEAR | INCOMPLETE_COVERAGE | CAPPED_HIGH (<=69) | BLOCKED_CRITICAL (<=39)>` · Покрытие: `<COMPLETE | INCOMPLETE_COVERAGE>` *(+ waivers, если есть)*
- **Бюджет токенов пакета:** `SKILL.md` `<N>` tok · весь пакет `<N>` tok (`<X>%` от 200K)
- **Универсальная совместимость (17 агентов & auto-discovery):** **`<portability_score_pct>%`** (`<ready>/17 PASS`, `<warn> WARN`, `<fail> FAIL` · скоуп: `<detected_install_scope>`) — Core: `<PASS/FAIL>`, Claude Code / Codex / Cursor / Antigravity / Kilo / OpenCode / Pi / Qoder / Copilot / Windsurf / Cline / Roo / Gemini CLI / Kiro / Amp / OpenClaw *(указать проблемных агентов и советы по `npx skills add` / `.agents/skills/`)*

---

## 1. Резюме, смысловая чистота и свобода пути (Executive Summary & Frontier Fit)
[Кратко: главная сильная сторона, главный риск, наличие воды (`FLUFF`), устаревших костылей слабых моделей (`SCAR`), несамодостаточных тезисов (`AMBIG`), внутренних противоречий (`CONTRA`), утечки шагов в `description` (`CSO-LEAK`), чрезмерных скриптов (`SCRIPT-OVERREACH`), рамок `CAGE`/`SOC` и гигиены контекста субагентов (`D4.2` Input Diet + Output Isolation).]

---

## 2. Таблица оценок по 8 измерениям (Scorecard)

| ID | Измерение (Dimension) | Вес (Баз. → Эфф.) | Балл | Рейтинг | Ключевой вердикт |
|---|---|---:|---:|---|---|
| **D1** | Triggering & Discoverability | 14% → `<eff>%` | `<pts>` (`<pct>%`) | `<rating>` | ... |
| **D2** | Context Engineering & Progressive Disclosure | 16% → `<eff>%` | `<pts>` (`<pct>%`) | `<rating>` | ... |
| **D3** | Prompt & Procedural Engineering | 14% → `<eff>%` | `<pts>` (`<pct>%`) | `<rating>` | ... |
| **D4** | Multi-Agent, Sub-Skills & Orchestration | 16% → `<eff>%` | `<pts>` (`<pct>%`) | `<rating/N/A>` | ... |
| **D5** | Tools, MCP Integration & External Resources | 12% → `<eff>%` | `<pts>` (`<pct>%`) | `<rating/N/A>` | ... |
| **D6** | Verification, Guardrails & Reliability | 12% → `<eff>%` | `<pts>` (`<pct>%`) | `<rating>` | ... |
| **D7** | Security, Trust Boundaries & Supply-Chain | 10% (+Gate) | `<pts>` (`<pct>%`) | `<rating>` | ... |
| **D8** | Cross-Platform Portability & Maintainability | 6% → `<eff>%` | `<pts>` (`<pct>%`) | `<rating>` | ... |

---

## 3. Обнаруженные Skill Smells, MAST-риски и Security Findings

- **Skill Smells / Статические находки:** `<список кодов с file:line; рекомендательные пометки отдельно от ошибок>`
- **MAST / Cross-Skill Risks (если применимо):** `<FM-X.Y, SG09 Lethal Trifecta с обоснованием>`
- **Security Hard Gates & Coverage:** `<подтверждённые CRITICAL/HIGH, нечитаемые бинарники/байткод, либо CLEAR (+ cleared_static_findings если были ложные)>`

### 3.1. Анализ разумности каждого скрипта (Per-Script Review — если есть `scripts/`)
| Скрипт | Назначение | Вердикт (`JUSTIFIED` / `SCRIPT_OVERREACH` / `REDUNDANT`) | Обоснование (объём/валидация vs узурпация смысла LLM) | Что передать модели / как упростить |
|---|---|---|---|---|
| `scripts/...` | ... | ... | ... | ... |

---

## 4. Топ-ROI и детальный план улучшений (Quick Wins & Patches)

### Топ-улучшения по ROI (`roi_top_actions`)
| Приоритет | Локация | Действие | Оценка прироста |
|---|---|---|---|
| `P0/P1` | `file:line` | ... | `+X.X б.` |

### P0 — Блокеры (Исправить немедленно)
> [Локация `file:line` → Суть/код дефекта → Влияние → Готовый `Before / After` дифф.]

### P1 — Высокий эффект (Сильно поднимут надёжность, переносимость или контекст)
> [Локация → Дефект → Конкретный патч/шаблон.]

### P2 — Полировка, сжатие и освобождение пути
> [Что можно упростить, сжать или освободить от лишних рамок для роста качества на сильных моделях.]

---

## 5. Взгляд за рамки рубрики (Beyond the Rubric)
[Свободная экспертная критика: можно ли радикально упростить архитектуру, нет ли фундаментальных ошибок предметной области, которые не ловятся чеклистом.]

---

## 6. Тестовый пакет для верификации (Recommended Evals — адаптивный объём)

- **Should-Trigger (3–5+ промптов):** ...
- **Should-Not-Trigger Near-Misses (3–5+ промптов):** ...
- **Проверяемые Task Assertions (+ отметка `AB_MEANINGFUL` vs `WITH_SKILL_ONLY`):** ...

*(Опционально — включается при запуске `scripts/eval_runner.py` или цикла улучшения `references/improve-loop-protocol.md`)*
## 7. Живой бенчмарк выполнения и/или журнал улучшений (`eval_benchmark` / `round_comparison`)
[Сводка по `Four Buckets` (`WORKING`/`GAP`/`REDUNDANT`/`REGRESSION`) + `RUNTIME_PASS`/`RUNTIME_GAP`, честный `Impact Score` только по `AB_MEANINGFUL`, средний `Runtime Execution Score` по 5 осям выполнения и дельта по раундам улучшений.]
```
