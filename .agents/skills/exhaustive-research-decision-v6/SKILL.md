---
name: exhaustive-research-decision-v6
description: Универсальный deep-research скилл: сырая мысль -> одобренный бриф -> поиск существующих решений с proven use -> единый criteria.csv (включая синтетические метрики) -> полная матрица candidate x criterion -> adopt/adapt/extend/compose, а build только при доказанном gap. Использовать для выбора СУБД, бекапов, библиотек, фреймворков, нейромоделей, видеокарт, стандартов документирования, методик, клинических досье, восстановления после пожара и любого сравнения или проектирования. Не привязан к open source; кандидатом может быть продукт, сервис, стандарт, железо, процесс или комбинация. High risk: досье + human gate, а не диагноз, назначение или разрешение работ.
compatibility: Requires Python 3.9+ only for scripts/check_gates.py; all other content is Markdown, CSV and JSON. Portable across any Agent Skills-compatible client.
metadata:
  version: "6.1"
  scope: "universal-deep-research"
---

# exhaustive-research-decision-v6

Миссия: превратить сырую мысль в **одобренную задачу**, найти **уже существующие подходящие решения**, доказательно исследовать их возможности, построить **единое пространство критериев**, получить практическую рекомендацию и внедряемую проверку. Абсолютная полнота не обещается; фиксируются `residual_unknowns`.

Канонический источник: этот `SKILL.md`. Дочерние скиллы физически лежат в `children/*/SKILL.md` и связаны относительными ссылками ниже. Cursor обнаруживает вложенные `SKILL.md` рекурсивно; имя скилла совпадает с именем папки.

**Установка одной папкой:** скопировать весь пакет в `.cursor/skills/`, `.agents/skills/` или `.claude/skills/`, не переименовывая (`name` должен совпадать с папкой). Матрица путей и нюансы субагентов — [INSTALL.md](INSTALL.md). Всё необходимое уже внутри; нативные subagents — опциональный шаг, без него роли читаются из `references/agents/` и инлайнятся в обычный `Task`.

## 1. Принцип «сначала готовое»

Никакого «изобрести новую методику/формат» до `reuse-decision.md`.

```text
ADOPT     готовое решение прямо подходит
ADAPT     подходит после конфигурации/обёртки
EXTEND    нужен патч, плагин или форк с exit-стратегией
COMPOSE   разумно связать 2–3 готовых решения
BUILD     только если build-justification.md доказывает gap
```

Кандидаты не ограничиваются open source. `candidate_type` может быть `oss | commercial | saas | managed | hardware | standard | methodology | process | framework | library | model | vendor | hybrid | internal_legacy`. open source — лишь один тип кандидата, а не обязательный gate.

## 2. Строгость риск-адаптивная, а не одинаковая для всех

В `00-state.md` фиксируются:

```yaml
freedom_profile: frontier | balanced | regulated
model_class: frontier | standard | small
risk_class: low | medium | high | critical
```

| Профиль | Когда | Как работает |
|---|---|---|
| `frontier` | сильная модель, low/medium risk | Цель, границы, evidence contract и safety guardrails обязательны; фазы, число агентов, точный набор interim-файлов и лимиты суммаризации можно заменить через `deviation-request.md`. Проверяется результат, а не каждый шаг. |
| `balanced` | default | Рекомендованный чеклист, гейты как warnings, критика по триггеру. |
| `regulated` | high/critical, необратимые решения, regulated домены | Low freedom: точные scripts, hard gates, human signoff, без импровизации. |

Типы правил:

- **G — guardrail**: не нарушается никогда;
- **C — criterion**: проверяется по результату;
- **P — procedure**: можно заменить с обоснованием в `deviation-request.md`;
- **H — heuristic**: по умолчанию, но сильная модель вправе предложить лучше.

Это убирает главный дефект v5: скилл заявлял «без искусственных лимитов», но навязывал десятки процедурных рамок. Теперь жёсткими остаются безопасность, доказательность и честность, а не количество волн/агентов/файлов.

## 3. G- guardrails

1. **G1 Reuse-first.** Без `reuse-decision.md` и, при выборе `build`, без `build-justification.md` финальный ответ запрещён.
2. **G2 Fact–Source–Method.** Каждое решение-критичное утверждение: `CL/F → S → M`, дословный excerpt, URL, дата/версия, location, independence group.
3. **G3 Criteria transparency.** Один `criteria.csv`; у каждого критерия `origin`, `type`, `unit`, `applies_to_all`, `na_policy`; синтетика имеет `formula`, `input_feature_ids`, `method_ids`, `sensitivity_status`.
4. **G4 Complete matrix.** Каждый candidate оценивается по каждому `applies_to_all` критерию. `unknown`, `n/a`, `not_supported` и `0` различаются.
5. **G5 No fake evidence.** Нельзя усреднять конфликтующие источники; нельзя выдавать маркетинг без подтверждения за факт.
6. **G6 Executable verification.** `verification.md` содержит команду/процедуру, expected/actual, дату, версию, окружение и `Status`.
7. **G7 Human gate.** Медицина, пожар/строительство, право, финансово-необратимые решения: досье + подпись специалиста, а не диагноз/назначение/разрешение.
8. **G8 Honest incompleteness.** `residual_unknowns`, `INCOMPLETE` при незакрытых гейтах, запрет «абсолютно полно» и «ошибок не будет».
9. **G9 No fake PASS.** `gates.json PASS` только после `scripts/check_gates.py`.

## 4. Дочерние скиллы — отдельные `.md` файлы

| Скилл | Файл | Владеет |
|---|---|---|
| `briefing-intake` | [children/briefing-intake/SKILL.md](children/briefing-intake/SKILL.md) | `00-brief.md`, `task-spec.md`, `research-protocol.md` |
| `existing-solution-scouting` | [children/existing-solution-scouting/SKILL.md](children/existing-solution-scouting/SKILL.md) | `candidates.csv`, `adoption-evidence.csv`, `reuse-decision.md`, `build-justification.md` |
| `criteria-synthesis` | [children/criteria-synthesis/SKILL.md](children/criteria-synthesis/SKILL.md) | `feature-dictionary.csv`, `feature-evidence.csv`, `criteria.csv`, `synthetic-scores.csv`, `gaps.csv` |
| `research-assignment` | [children/research-assignment/SKILL.md](children/research-assignment/SKILL.md) | `research-assignments.csv`, волны субагентов |
| `evidence-provenance` | [children/evidence-provenance/SKILL.md](children/evidence-provenance/SKILL.md) | `sources.csv`, `claims.csv`, `method-registry.md`, `contradictions.csv` |
| `variant-feature-evaluation` | [children/variant-feature-evaluation/SKILL.md](children/variant-feature-evaluation/SKILL.md) | `decision-matrix.csv`, sensitivity, exclusions |
| `triz-contradiction-resolution` | [children/triz-contradiction-resolution/SKILL.md](children/triz-contradiction-resolution/SKILL.md) | `03-triz/` — опционально по триггеру, не обязательный gate |
| `cursor-state-handoff` | [children/cursor-state-handoff/SKILL.md](children/cursor-state-handoff/SKILL.md) | `00-state.md`, `99-handoff.md`, `context-budget.md`, checkpoints |
| `domain-safety-verification` | [children/domain-safety-verification/SKILL.md](children/domain-safety-verification/SKILL.md) | `verification.md`, human gate, доменные adapters |
| `output-contract-and-format-compliance` | [children/output-contract-and-format-compliance/SKILL.md](children/output-contract-and-format-compliance/SKILL.md) | `compliance-matrix.csv`, `gates.json`, schemas, final report |

Ссылки от корневого `SKILL.md` **одного уровня**; вложенных цепочек «ссылка на ссылку на ссылку» нет.

`children/` — групповая папка дочерних скиллов харнеса. Каждый вложенный `SKILL.md` имеет свой `name`, совпадающий с папкой, и объявлен в `children` манифеста `skill.json`. Родительский скилл сам собирает триггеры дочерних и маршрутизирует запрос по тексту.

**Переносимость:** только Cursor обходит skills root рекурсивно и регистрирует эти 10 файлов как отдельные скиллы. Kilo Code, Codex, Gemini CLI, Copilot/VS Code и большинство остальных клиентов обнаруживают `SKILL.md` лишь на один уровень вглубь, поэтому внутри одного пакета вложенные скиллы остаются **процедурными reference-файлами**, которые корень читает по относительным ссылкам — работоспособность от этого не зависит. Полная матрица: [COMPATIBILITY.md](COMPATIBILITY.md).

## 5. Конвейер

| Фаза | Действие | Артефакт |
|---|---|---|
| -1 Brief | Сырой текст → pre-brief research → вопросы без лимита → одобренный/замороженный бриф | `00-brief.md`, `task-spec.md`, `research-protocol.md` |
| 0 Existing solutions | Поиск готовых решений любого типа с proven use, longlist до насыщения | `candidates.csv`, `adoption-evidence.csv` |
| 1 Capability census | Субагент по каждому shortlisted кандидату; извлечение всех характеристик | `feature-dictionary.csv`, `feature-evidence.csv` |
| 2 Union + gap filling | Объединение уникальных признаков, второй проход по недостающим ячейкам | `feature-evidence.csv`, `gaps.csv` |
| 3 Criteria synthesis | `brief + domain + candidate_union + synthetic` → один реестр | `criteria.csv`, `synthetic-scores.csv` |
| 4 Assignments | Каждый вопрос/критерий/ось/gap → задание с владельцем и stop condition | `research-assignments.csv` |
| 5 Evidence | Источники, claims, contradiction ledger, method registry | `sources.csv`, `claims.csv`, `contradictions.csv` |
| 6 Optional TRIZ | Только если есть неразрешимое противоречие или нужен IFR | `03-triz/**` |
| 7 Decide | Hard gates → полная матрица → MCDA → sensitivity → rank | `decision-matrix.csv` |
| 8 Reuse decision | adopt/adapt/extend/compose/build | `reuse-decision.md`, `build-justification.md` |
| 9 Verify + output | Исполняемая проверка, compliance, gates | `verification.md`, `compliance-matrix.csv`, `gates.json` |

Для `frontier` профиля фазы можно сжать, но G1–G9 и итоговые артефакты остаются.

## 6. Промежуточные файлы

Каноническое ядро `research/<task-id>/`:

```text
00-brief.md               # raw + clarified + approval + freeze hash, один версионируемый файл
00-state.md               # фаза, freedom_profile, loaded_files с path+hash, next_action
99-handoff.md             # что читать первым в новой сессии
task-spec.md              # goal/current/target/problems/constraints/DoD/assumptions/unknowns
research-protocol.md      # аналог PRISMA-P/OSF preregistration: план, amendments, analysis plan
candidates.csv
adoption-evidence.csv
feature-dictionary.csv
feature-evidence.csv
criteria.csv
synthetic-scores.csv
gaps.csv
decision-matrix.csv
research-assignments.csv
sources.csv
claims.csv
method-registry.md
contradictions.csv
critique-log.csv
reuse-decision.md
build-justification.md
deviation-request.md
context-budget.md
verification.md
compliance-matrix.csv
gates.json
```

Ссылки в `00-state.md` и `99-handoff.md` идут на `path + hash + stable_id`, а не на номера секций чата. Шаблоны — в `assets/templates/`, схемы — в `assets/schemas/`.

## 7. Быстрый старт

```bash
python scripts/check_gates.py --init-v6 research/<task-id> --force
```

1. Прочитать `00-brief.md`, `00-state.md`, `99-handoff.md`.
2. Запустить [briefing-intake](children/briefing-intake/SKILL.md) до поиска.
3. Запустить [existing-solution-scouting](children/existing-solution-scouting/SKILL.md) **до** всякого синтеза нового решения.
4. Запустить [criteria-synthesis](children/criteria-synthesis/SKILL.md): union features → второй проход → synthetic layer.
5. Запустить [research-assignment](children/research-assignment/SKILL.md).
6. Волны субагентов по незакрытым assignment'ам: спецификации ролей лежат в `references/agents/` от корня пакета. Если нативные Cursor subagents не зарегистрированы, [research-assignment](children/research-assignment/SKILL.md) инлайнит `references/agents/<name>.md` в промпт обычного `Task`; старт с 2–3 фокусных ролей, далее по триггеру. Опциональная регистрация — [INSTALL.md](INSTALL.md).
7. [variant-feature-evaluation](children/variant-feature-evaluation/SKILL.md), [domain-safety-verification](children/domain-safety-verification/SKILL.md), [output-contract-and-format-compliance](children/output-contract-and-format-compliance/SKILL.md).
8. `python scripts/check_gates.py research/<task-id>` → `gates.json`.

## 8. Гейты

Обязательные: `BRIEF`, `REUSE_FIRST`, `CANDIDATE_ADOPTION`, `UNION_COMPLETE`, `GAP_FILLING`, `CRITERIA_TRANSPARENCY`, `SYNTHETIC_TRANSPARENCY`, `MATRIX_COMPLETE`, `ASSIGNMENT`, `PROVENANCE`, `CONTRADICTION`, `CRITIQUE`, `SENSITIVITY`, `VERIFICATION`, `HUMAN_GATE`, `OUTPUT_CONTRACT`, `CONTEXT_BUDGET`, `RESIDUAL_UNKNOWNS`, `NO_FAKE_PASS`.

Процедурные гейты в `frontier` профиле могут быть заменены через `deviation-request.md`; G1–G9 — нет.

## 9. Контракт финального ответа

Выдавать не «рекомендацию в чате», а пакет:

- одобренная формулировка задачи;
- ранжированный список существующих решений с proven use;
- `reuse-decision.md`: adopt/adapt/extend/compose/build и почему;
- единый `criteria.csv` с `origin` и `synthetic`;
- полную `decision-matrix.csv` и `synthetic-scores.csv`;
- противоречия и их статус;
- sensitivity / rank reversal;
- исполняемую верификацию;
- compliance matrix;
- `gates.json`;
- `residual_unknowns`, human gate, review triggers.

## 10. Навигация

- Методики и источники: [references/00-method-registry.md](references/00-method-registry.md), [references/05-source-dossier.md](references/05-source-dossier.md)
- Existing solutions: [references/01-existing-solutions.md](references/01-existing-solutions.md)
- Критерии и синтетика: [references/02-criteria-and-synthetic-scores.md](references/02-criteria-and-synthetic-scores.md)
- Freedom/context engineering: [references/03-context-engineering-and-freedom.md](references/03-context-engineering-and-freedom.md)
- Output compliance: [references/04-output-compliance.md](references/04-output-compliance.md)
- Совместимость агентов: [COMPATIBILITY.md](COMPATIBILITY.md); fallback без Skills: [assets/AGENTS.md.snippet](assets/AGENTS.md.snippet)
- Установка: [INSTALL.md](INSTALL.md), [README.md](README.md)
- Агенты (папка): [references/agents/](references/agents/); спецификации ролей: [pre-brief-scout](references/agents/pre-brief-scout.md), [candidate-scout](references/agents/candidate-scout.md), [feature-gap-scout](references/agents/feature-gap-scout.md), [brief-critic](references/agents/brief-critic.md), [criteria-critic](references/agents/criteria-critic.md), [reuse-critic](references/agents/reuse-critic.md), [state-curator](references/agents/state-curator.md), [gate-verifier](references/agents/gate-verifier.md)
- Шаблоны: [assets/templates/](assets/templates/)
- Схемы: [assets/schemas/](assets/schemas/); пример прогона: [assets/examples/minimal-passing-run/](assets/examples/minimal-passing-run/)
- Валидатор: [scripts/check_gates.py](scripts/check_gates.py)
- Обоснование v6: [DESIGN-NOTES-v6.md](DESIGN-NOTES-v6.md)
