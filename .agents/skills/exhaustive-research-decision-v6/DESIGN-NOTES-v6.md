# DESIGN NOTES v6: что исправлено после замечаний

## Содержание

1. Брифинг и промежуточные файлы
2. Защита от изобретения велосипеда
3. Универсальный candidate → criteria конвейер
4. Синтетические метрики
5. Research protocol, а не SDD
6. Risk-adaptive freedom
7. Реальные interim-файлы и path+hash
8. Критики и выходной контракт
9. Оценка качества
10. Validation evidence
11. Drop-in packaging audit
12. Cross-client compatibility audit

## 1. Брифинг и промежуточные файлы

Проблема v5/test: сырая задача была показана как секции одного `.md`, физических `00-brief/*` не было, ссылки шли на `§0`, а не на пути.

v6:

- один версионируемый `00-brief.md` с Raw/Pre-brief/Clarified/Approval+freeze;
- отдельный `task-spec.md`;
- `research-protocol.md` как аналог PRISMA-P/OSF preregistration, а не «SDD для исследований»;
- `00-state.md` ссылается на `path + hash + stable_id`;
- `99-handoff.md` читает файлы, а не историю чата;
- структура сокращена: не 8 бриф-файлов, а компактное ядро.

## 2. Защита от изобретения велосипеда

Добавлен `existing-solution-scouting` и gate `REUSE_FIRST`. Для любой задачи сначала ищутся существующие решения с proven successful use. Open source — только `candidate_type`, не обязательство. Решение оформляется в `reuse-decision.md`; `build` требует `build-justification.md` с `gap_proven: yes`.

## 3. Универсальный candidate → criteria конвейер

Реализована мысль пользователя:

```text
кандидаты → субагент по каждому → все характеристики
→ union уникальных признаков → второй проход по пропускам
→ domain/technology research → единый criteria.csv
→ synthetic layer → полная candidate × criterion матрица
→ MCDA/sensitivity → практическая рекомендация
```

`criteria-synthesis` не даёт сравнивать кандидатов по разным наборам колонок. Если у Framework A 50 характеристик, у Framework B 30, union применяется ко всем: `native | extension | none | unknown | n/a`, а отсутствие не превращается в ноль.

## 4. Синтетические критерии

Выделены в отдельный тип `origin: synthetic` и `synthetic-scores.csv`. «Скорость в попугаях», «бюджет-фит в процентах», «насколько подходит проекту» обязаны иметь formula, input_feature_ids, normalization, method_ids, sensitivity_status. Факт, доменный gate, взвешенный критерий и синтетика больше не смешиваются.

## 5. SDD в исследованиях

SDD остаётся software-engineering подходом. Для research введён `research-protocol.md`: question format, eligibility, search plan, synthesis plan, analysis plan, criteria plan, reuse policy, amendment log, registration id. Это ближе к PRISMA-P/OSF preregistration/Registered Reports, чем к Spec Kit.

## 6. Строгость и сильные модели

Убрана иллюзия «без лимитов при 82 гейтах». Введены:

- `freedom_profile: frontier | balanced | regulated`;
- `model_class: frontier | standard | small`;
- `risk_class`;
- типы правил `G/C/P/H`;
- `deviation-request.md`.

Для `frontier` проверяется результат и guardrails, а не каждый процедурный шаг. Для `regulated` сохраняется low freedom и human signoff. Это соответствует официальной рекомендации calibrating degrees of freedom и предостережению от over-prescribing сильных моделей.

## 7. Дочерние скиллы

Физически созданы 10 `SKILL.md`:

```text
briefing-intake
existing-solution-scouting
criteria-synthesis
research-assignment
evidence-provenance
variant-feature-evaluation
triz-contradiction-resolution  # опционально
cursor-state-handoff
domain-safety-verification
output-contract-and-format-compliance
```

Корневой `SKILL.md` ссылается на них прямыми относительными ссылками. Ссылки одного уровня.

## 8. Оптимальность

«Идеально» здесь означает сбалансированно, не «абсолютно без ошибок». Ограничения:

- нет живого прогона во всех моделях;
- нет реального проекта для полного rebuild;
- схемы и валидатор нужно подключить в CI;
- доменные adapters требуют наполнения под конкретные юрисдикции;
- `frontier` deviations требуют честного audit trail.

Оценка design-readiness: **9.0/10**. Не 10, потому что эмпирические evals на нескольких моделях и реальных задачах ещё не исполнены.

## 10. Validation evidence

Исполняемая проверка, а не только декларация:

| check | result |
|---|---|
| `py_compile` validator + fixture generator | OK |
| demo fixture `check_gates.py` | `PASS errors=0 warnings=0` |
| fresh `--init-v6` | `FAIL errors=124 warnings=2` — ожидаемо |
| root line count | 180 (<500) |
| root local links | 27, missing 0 |
| CJK scan | 0 |
| citation ID conflicts / duplicate URLs | 0 / 0 |
| schemas / templates / agents | 5 / 28 / 8 |

Итог: сбалансированный design-readiness **9.0/10**. «Идеально» трактуется как максимальная готовность дизайна при явном отказе от обещания абсолютной полноты; в реальном прогоне остаются `residual_unknowns`, human gate для high-risk и verification command.

## 11. Drop-in packaging audit

Сверено с [Cursor Agent Skills](https://cursor.com/docs/skills), [Cursor Subagents](https://cursor.com/docs/subagents) и [Claude Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices).

| Требование стандарта | Статус пакета |
|---|---|
| Одна папка с `SKILL.md`; `name` == имени папки | ✅ `exhaustive-research-decision-v6` |
| Обязательный триггерный `description` | ✅ |
| `SKILL.md` < 500 строк | ✅ 180 |
| Ссылки одним уровнем от корня | ✅ §10 перечисляет child/reference/agent/скрипты напрямую |
| `scripts/`, `references/`, `assets/` | ✅ каноничные папки на месте |
| Рекурсивное обнаружение вложенных `SKILL.md` | ✅ `children/*/SKILL.md`, `name` == своей папке |
| Имя групповой папки `child/` не обязательно | ✅ используется `children/` (требование формата харнеса) |
| Дочерние скиллы не срабатывают автономно | ✅ маршрутизация из родительского скилла, поле `disable-model-invocation` убрано |
| Актуальное поле скоупа `paths`, не `globs` | ✅ |
| Нативные subagents | ⚠️ только `.cursor/agents/`; внутри скилла это спецификации + inline fallback |
| TOC у длинных reference-файлов | ✅ добавлено |

Вывод: пакет работает при копировании одной папки. Единственный необязательный шаг — `cp references/agents/*.md .cursor/agents/` ради `/name`, `readonly` и `is_background`; без него `research-assignment` инлайнит роль в обычный `Task`.

## 12. Cross-client compatibility audit

Проверено по [спецификации Agent Skills](https://agentskills.io/specification), [Client Showcase](https://agentskills.io/clients) и официальным докам Cursor / Claude Code / Codex / Kilo Code / Gemini CLI / GitHub Copilot / VS Code.

| Изменение | Причина |
|---|---|
| Убраны `paths:` из 10 дочерних скиллов | Поле отсутствует в спецификации; это расширение Cursor/Claude Code |
| Убран glob `.cursor/research/**` | Привязка к одному клиенту |
| `description` корня сокращён 869 → ~600 | Codex ограничивает стартовый список скиллов 2% контекста / 8000 символов и урезает длинные описания |
| Добавлены `compatibility` и `metadata` | Стандартные опциональные поля; явно декларируют Python 3.9+ и версию |
| Добавлен `assets/AGENTS.md.snippet` | Fallback для агентов без поддержки Agent Skills |
| Добавлен `COMPATIBILITY.md` | Матрица 40+ клиентов, глубина discovery, нативные субагенты, чек-лист |

Ключевой honesty-пункт: **рекурсивное обнаружение вложенных `SKILL.md` есть только у Cursor**. Kilo Code, Gemini CLI, Codex, Copilot и Claude Code ищут скилл на один уровень вглубь. Поэтому в одном пакете 10 дочерних файлов у них не становятся отдельными slash-скиллами — они остаются процедурными reference-файлами, которые корень читает по прямым ссылкам. Функция не теряется, меняется лишь способ регистрации. Это лучше, чем разносить пакет по нескольким папкам ради `/name` у каждого клиента.

Итог: корневой скилл переносим без правок; единственная runtime-зависимость — Python 3 для валидатора, объявленная в `compatibility`.
