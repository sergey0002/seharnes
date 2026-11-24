<!-- generated from architecture:deepseek-harness-07-scenarios by doc_render.py; do not edit -->

# тест от 2026-10-20

task unknown - status unknown - branch unknown - release unknown

# Сценарии работы DSH: тест от 2026-10-20
<a id="сценарии-работы-dsh:-тест-от-2026-10-20"></a>
<!-- meta
type: flow
status: actual
updated: 2026-10-20
tags: [deepseek, scenarios, tests]
-->

---

## Суть
<a id="суть"></a>
Сценарии проверены "как будто выполняешь": четыре независимых прогона
(переход к задаче и план, аудит плана и тест, матрица MCP, доки и правила).
Каждый прогон смотрел, грузятся ли нужные скилы, работают ли скрипты, отвечают
ли MCP и совпадает ли документация с реальностью.

Итог: рабочий цикл в DSH проходит, но нашлось несколько расхождений, которые
ломали корректность, а не только текст. Критичное исправлено, остальное
перечислено ниже.

> **AI:** читай перед прогоном задачи, чтобы не наступить на известные грабли.
> **Сначала:** [03-workflow.md](./deepseek-harness-03-workflow.md) - шаги цикла.
> **Не читай целиком:** смотри "Находки" и "Осталось открытым".

---

## Как проверяли
<a id="как-проверяли"></a>
| Сценарий | Что делали | Чем подтверждали |
|---|---|---|
| SC-1 переход к задаче | `skill(gototask)`, `gototask.ps1 -Action inspect` на 2622 | JSON inspect, сверка с каноном скила |
| SC-2 план | `skill(prepare-plan)`, `jsondoc plan template/verify` | JSON модели, exit-коды |
| SC-3 аудит плана | разбор P7.4a в каноне, сверка с dsh-router | 17 шагов, проверяемость каждого |
| SC-4 тест | `skill(test-task)`, `gates.py`, контракт `verdict.json` | код скриптов, поля verdict |
| SC-5 MCP | по одному дешёвому вызову на 15 серверов | статусы green/red/SKIP |
| SC-6 доки и правила | `validate-docs.ps1`, сверка чисел, генератор | 0 ошибок, `cmp` |

---

## Результаты по сценариям
<a id="результаты-по-сценариям"></a>
| Сценарий | PASS | FAIL | WARN | Комментарий |
|---|---|---|---|---|
| SC-1 переход | 5 | 2 | 1 | inspect работает за 6 с; расходится трактовка `branchExists` |
| SC-2 план | 4 | 1 | 1 | `template` валиден; `verify` на 2622 даёт 2, а не 5 |
| SC-3 аудит плана | 3 | 0 | 2 | 17 шагов на месте; формулировка "структурная проверка" сужала канон |
| SC-4 тест | 4 | 2 | 3 | `verdict.json` согласован; G13 skipped проходит зелёным |
| SC-5 MCP | 6 | 4 | 0 | 6 green, jira-task без tools, часть серверов red по env |
| SC-6 доки | 6 | 1 | 1 | overlay_entries и битые ссылки в DSH-RULES |

---

## Находки и что сделано
<a id="находки-и-что-сделано"></a>

### N-1: branchExists считается по origin (исправлено в доках)
<a id="n-1:-branchexists-считается-по-origin-(исправлено-в-доках)"></a>
- Симптом: ветка `bugfixes/#2622` уже checkout, а inspect говорит
  `branchExists: false` и советует `create-branch`.
- Причина: `$branches.exact` собирается из `git ls-remote origin`; локальная
  ветка без origin в расчёт не входит.
- Решение: в `03-workflow.md` и `dsh-router` добавлено правило сверять
  `currentBranch` перед apply.
- Файлы: `.dsh/skills/dsh-router/SKILL.md`, `.doc/architecture/deepseek-harness-03-workflow.md`

### N-2: шкала exit в plan verify была неполной (исправлено)
<a id="n-2:-шкала-exit-в-plan-verify-была-неполной-(исправлено)"></a>
- Симптом: `plan verify --task 2622` даёт 2 `plan_model_missing`, хотя план
  (30 КБ, `status: implemented`) есть. Доки называли такой случай "legacy = 5".
- Причина: 5 возвращается только если в сторе есть plan-артефакт без
  JSON-модели; если артефакта нет вовсе, это 2.
- Решение: шкала расписана: 5 legacy, 2 plan_model_missing (сначала
  `template + plan write`), 3-4 чинить.
- Файлы: `.dsh/skills/dsh-router/SKILL.md`, `.doc/architecture/deepseek-harness-03-workflow.md`,
  `.dsh/adapters/prepare-plan-digest.md`

### N-3: digest противоречил оболочке (исправлено)
<a id="n-3:-digest-противоречил-оболочке-(исправлено)"></a>
- Симптом: digest звал `powershell.exe -File "<unc>..."` и `wsl -e python3`.
- Причина: файл писался до появления `run-ps1.sh`.
- Решение: команды переведены на `bash .dsh/scripts/run-ps1.sh` и голый
  `python3`.
- Файлы: `.dsh/adapters/prepare-plan-digest.md`

### N-4: P7.4a описан слишком мягко (исправлено)
<a id="n-4:-p7.4a-описан-слишком-мягко-(исправлено)"></a>
- Симптом: в router было "1 проход структурной проверки", канон требует
  mandatory rebuild.
- Решение: перечислены обязательные части rebuild, добавлено, что re-tick
  без шагов 1-17 невалиден.
- Файлы: `.dsh/skills/dsh-router/SKILL.md`, `.doc/architecture/deepseek-harness-03-workflow.md`

### N-5: G13 skipped проходит зелёным (задокументировано, код не меняли)
<a id="n-5:-g13-skipped-проходит-зелёным-(задокументировано,-код-не-меняли)"></a>
- Симптом: задача без `plan.md` и без таблицы веток проходит `gates.py` с
  exit 0.
- Причина: `skipped()` ставит `ok=True, blocking=False`, `ready` считается
  только по блокирующим.
- Решение: в доки добавлено правило проверять G13 вручную: plan.md есть, а
  таблицы нет = FAILED; нет plan.md = законно n/a.
- Файлы: `.dsh/skills/dsh-router/SKILL.md`, `.doc/architecture/deepseek-harness-03-workflow.md`
- Почему не правили код: `gates.py` принадлежит канону QA и используется
  Cursor/Codex; менять его без отдельного согласования нельзя.

### N-6: jira-task не регистрируется (задокументировано, обход есть)
<a id="n-6:-jira-task-не-регистрируется-(задокументировано,-обход-есть)"></a>
- Симптом: в патче клиент есть, tools нет.
- Причина: `.doc/skil_data/jira/server.php` ждёт LSP-фрейминг `Content-Length`, а
  DSH-клиент шлёт newline-JSON; сервер молча выходит.
- Решение: обход через `gototask.ps1` (он экспортирует `task.md` через
  docker/php). Записано в `.dsh/adapters/mcp-names.md`.
- Файлы: `.dsh/adapters/mcp-names.md`, `.doc/architecture/deepseek-harness-05-skripty.md`

### N-7: снятые MCP-серверы
<a id="n-7:-снятые-mcp-серверы"></a>
- Серверы из этого наблюдения удалены из канона.
- Решение: статусы в таблице, fallback "данные не выдумывать".
- Файлы: `.dsh/adapters/mcp-names.md`

### N-8: битые ссылки в DSH-RULES.md (исправлено)
<a id="n-8:-битые-ссылки-в-dsh-rules.md-(исправлено)"></a>
- Симптом: 12 относительных ссылок вели в несуществующие пути из корня.
- Причина: тела правил инлайнились из `.cursor/rules/` без перебазирования.
- Решение: генератор пересчитывает ссылки на путь от корня репо; после
  регенерации 0 битых.
- Файлы: `.agents/skills/harness-management/children/environment-sync/scripts/generate-dsh-config.py`, `DSH-RULES.md`

### N-9: устаревшие числа (исправлено)
<a id="n-9:-устаревшие-числа-(исправлено)"></a>
- `overlay_entries` 2 → 3 в `02` и `06`.
- `state/04-mcp.md`: "17 записей, 15 включённых, 2 отключённых".
- `AGENTS.md`: канон тестов `.doc/tests.md` → `.doc/harnes/tests.md`.

### N-10: в шаблоне плана нет `patches` (задокументировано)
<a id="n-10:-в-шаблоне-плана-нет-`patches`-(задокументировано)"></a>
- `plan template` даёт модель без ключа `patches`, хотя P5 и P7.0 требуют
  Patches и "N == число файлов".
- Решение: в digest добавлено, что форму Patches брать из канона, не угадывать.

---

## Осталось открытым
<a id="осталось-открытым"></a>
| # | Что | Почему не закрыто |
|---|---|---|
| 1 | jira-task фрейминг | нужен фикс MCP-клиента или сервера, это не .dsh |
| 3 | G13 skipped в `gates.py` | канон QA, нужно отдельное решение |
| 4 | `patches` в шаблоне jsondoc | канон JSONdoc |
| 5 | Разница test-task и 03-workflow (chromedriver, отчёт §8) | сознательное упрощение, отмечено |

---

## Как повторить
<a id="как-повторить"></a>
```bash
bash .dsh/scripts/smoke.sh --task 2622
bash .dsh/scripts/run-ps1.sh .agents/skills/project-doc/scripts/validate-docs.ps1 -Path .doc/architecture
python3 .doc/skil_data/task-doc/jsondoc.py --root . plan verify --task 2622 --require-syntax
bash .dsh/scripts/run-ps1.sh .agents/skills/gototask/scripts/gototask.ps1 -TaskNumber 2622 -Action inspect
```

Сценарии MCP проверяются вызовом инструментов в сессии: запись в патче не
гарантирует наличие tools.

---

## Связи
<a id="связи"></a>
- [Workflow](./deepseek-harness-03-workflow.md) - шаги, затронутые находками
- [Скрипты](./deepseek-harness-05-skripty.md) - оболочка и MCP
- [Модели](./deepseek-harness-04-modeli.md) - почему нет второго аудитора

---

## Известные проблемы и ограничения
<a id="известные-проблемы-и-ограничения"></a>
- Симптом: вывод про `branchExists` и `plan verify` привязан к этой задаче.
- Причина: один прогон, а не матрица задач.
- Ограничение или решение: повторить на задаче без локальных изменений и на
  задаче с планом в JSON-модели.


- Симптом: phpstan, semgrep, playwright, php-deps помечены SKIP.
- Причина: полный скан или браузерная навигация не входили в прогон.
- Ограничение или решение: отдельный прогон с известным дефектом в коде.

---

## История изменений
<a id="история-изменений"></a>
- 2026-10-20: сценарии прогнаны, находки N-1..N-10 зафиксированы, N-1..N-5,
  N-8, N-9 исправлены в доках и генераторе

#deepseek #scenarios #tests
