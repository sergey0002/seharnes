<!-- generated from architecture:deepseek-harness-03-workflow by doc_render.py; do not edit -->

# Workflow задачи в DeepSeek Harness

task unknown - status unknown - branch unknown - release unknown

# Workflow задачи в DeepSeek Harness
<a id="workflow-задачи-в-deepseek-harness"></a>
<!-- meta
type: flow
status: actual
updated: 2026-10-31
tags: [deepseek, workflow, task]
-->

---

## Суть
<a id="суть"></a>
Цикл работы с задачей: переход, классификация размера, план, аудит плана,
реализация, тест, ручная отправка в git. Отличие от Cursor только в оболочке:
PowerShell-скрипты идут через `run-ps1.sh`, вопросы через tool
`ask_user_question`, моделей пока одна.

Маршрутизатор - скил `dsh-router` (`.dsh/skills/dsh-router/SKILL.md`).
Канонические скилы синк кладет в `.agents/skills`, DSH читает их через tool
`skill(name)`. В `.dsh/skills` лежит только `dsh-router`.

> **AI:** читай этот doc при выполнении задачи в DSH.
> **Сначала:** `skill(dsh-router)`.
> **Не читай целиком:** детали P0-P7 в `.dsh/adapters/prepare-plan-digest.md`.
> **См. также:** [../harnes/state/07-workflows.md../state/07-workflows.md) - схемы канона.

---

## Маршрут по размеру задачи
<a id="маршрут-по-размеру-задачи"></a>

### Ступень A - pre-классификация
<a id="ступень-a---pre-классификация"></a>
После gototask прочитать `task.md` и определить `size_pre`:

| size_pre | Сигналы |
|---|---|
| trivial | <=1 AC; 1 файл; нет money/auth/DB; риск Low |
| small | <=2 файла; один UI/HTTP-контур |
| medium | 3+ файла, или 2+ AC, или свежий комментарий с требованием |
| large | Critical, shared default, money/auth mutation, multi-domain |

Не можешь доказать trivial - ставь small. Результат в `.doc/tasks/{N}/route.json`.

### Что выполняется по размерам
<a id="что-выполняется-по-размерам"></a>
| Этап | trivial | small | medium | large |
|---|---|---|---|---|
| gototask | да | да | да | да |
| план | digest | digest | канон | канон |
| P7.0 plan verify | да | да | да | да |
| P7.8 zero-ambiguity | да | да | да | да |
| P7.9 task-closure | да | да | да | да |
| G13 ветки | да | да | да | да |
| P0.5a find-related-tasks | skip | да | да | да |

Механические гейты не масштабируются.

---

## Шаги
<a id="шаги"></a>

### 1. Переход к задаче
<a id="1.-переход-к-задаче"></a>
```bash
bash .dsh/scripts/run-ps1.sh .agents/skills/task-router/children/gototask/scripts/gototask.ps1 \
  -TaskNumber {N} -Action inspect
```

Разобрать JSON: `needsUserInput`, `recommendedAction`, `defaultReleaseBranch`.
Важно: `branchExists` считается по origin. Локальная ветка без origin даёт
`false` и `recommendedAction: create-branch`, даже если она уже checkout
(так на задаче 2622). Сверять `currentBranch` до apply.
Вопросы по `needsUserInput` задавать через `ask_user_question` с вариантами,
не текстом. Apply с флагами канона:

```bash
-Action create-branch -ReleaseBranch "<релиз>" -TaskBranch "<ветка>" -LocalChanges discard
-Action merge-release -ReleaseBranch "<релиз>" -TaskBranch "<ветка>" -LocalChanges discard
```

Для `merge-release` проверить конфликты и отразить их в отчёте. Свежие
комментарии - правило `comment-triage`. MCP smoke один раз на сервер, кеш в
`.doc/tasks/{N}/mcp-status.json`; красные серверы брать из
`.dsh/adapters/mcp-names.md`. Отчёт пользователю: ветка, релиз, что применено.

### 2. План
<a id="2.-план"></a>
```
skill(prepare-plan)
прочитать .dsh/adapters/prepare-plan-digest.md
jsondoc plan template --task {N} -> заполнить -> plan write -> plan verify
```

Subagent вызывать можно, но без `provider`/`model`: наследуется текущая модель.

### 3. Аудит плана (P7.4a)
<a id="3.-аудит-плана-(p7.4a)"></a>
Полный rebuild по 17 шагам канона, ведущим: blast radius, git-task-blame по
каждому Patches, свежий P7.9, IN/OUT, docs!=code, инварианты, симуляция,
уникальность Before, покрытие R->S, sources of truth, риск, scope_size.
Канон запрещает re-tick без шагов 1-17.
Независимого второго мнения на другой модели нет, пока не включён `llm-pi-ai`
(см. [04-модели.md](./deepseek-harness-04-modeli.md)).
Агрегация: common = обязательно, unique = проверить по коду.

### 4. Реализация
<a id="4.-реализация"></a>
```
1. Читать модель плана: jsondoc get --task {N}.
2. Before -> After через edit tool.
3. После каждого R: plan verify --task {N} до запуска S.
4. "Проверь этап R": только S этого R.
```

### 5. Тест
<a id="5.-тест"></a>
```
проверь этап R:   один метод или сценарий этого R.
тестируй задачу N:
  0. task-diff свежий.
  1. Таблица веток G13.
  2. Нет Cest -> prepare-task-test.
  3. preflight: check-tests.sh + task-test.sh --phase preflight.
  4. browser-verify: Codeception -g task-N, Playwright только строки без метода.
  5. Вердикт из verdict.json.
  6. gates.py N - G0..G13, skipped G13 = failed.
```

### 6. Отправка в git
<a id="6.-отправка-в-git"></a>
```
1. skill(send-to-git).
2. verdict.json зелёный.
3. Согласовать файлы через ask_user_question.
4. После "да": git add/commit/push.
5. skill(task-doc) режим B после push.
```

## Гейты
<a id="гейты"></a>
```
P7.0: python3 .agents/skills/documentation-router/children/task-doc/scripts/jsondoc.py --root . plan verify --task {N} --require-syntax
      0 green / 1 warnings / 5 legacy (артефакт есть, JSON-модели нет)
      2 plan_model_missing (модели нет: template + plan write) / 3-4 чини план.
P7.8: Before grep count=1; After полный; expected литерал.
P7.9: каждый AC закрыт R; 100% для FULL.
G13:  таблица веток без open/partial. gates.py считает skipped как ok,
      поэтому проверять вручную: plan.md есть, а таблицы нет = FAILED.
      Нет plan.md - G13 законно n/a.
```

---

## Связи
<a id="связи"></a>
- [Устройство](./deepseek-harness-01-ustroystvo.md) - слои
- [Модели](./deepseek-harness-04-modeli.md) - что доступно
- [Скрипты](./deepseek-harness-05-skripty.md) - команды
- [План 07../plan/07-dsh-final.md) - детальные гейты

---

## Известные проблемы и ограничения
<a id="известные-проблемы-и-ограничения"></a>
- Симптом: `subagent(provider=xai, model=grok-4.7)` возвращает null.
- Причина: `llm-pi-ai` выключен, провайдеров нет.
- Решение: не передавать provider/model; для тяжёлых моделей сначала
  [04-модели.md](./deepseek-harness-04-modeli.md).


- Симптом: subagent не видит transcript родителя и фабрикует incidents.
- Причина: spawn/fork не наследуют текущий транскрипт.
- Решение: только ведущий в своём контексте.


- Симптом: `inspect` висит больше 90 с.
- Причина: внутри `git fetch origin`.
- Решение: давать `timeoutMs` 60000 и повторять; fetch докачивается.

---

## История изменений
<a id="история-изменений"></a>
- 2026-10-20: создан
- 2026-10-20: команды переведены на `run-ps1.sh`, вопросы на `ask_user_question`,
  добавлен факт об одной модели

#deepseek #workflow #task
- 2026-10-31: уточнено, что канонические скилы приходят из .agents/skills, DSH kit переносится copy-dsh-kit.ps1
