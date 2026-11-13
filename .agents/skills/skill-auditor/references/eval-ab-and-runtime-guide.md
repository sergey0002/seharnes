# Протокол разумного A/B-тестирования и оценки AI на этапе выполнения (v3.0)

Руководство для `scripts/eval_runner.py` и `agents/execution-evaluator.md`. Загружайте этот файл **только** при запуске живого бенчмаркинга или оценки трасс выполнения (`eval-ab` / runtime grading).

---

## 1. Зачем нужен AI Applicability Gate (отказ от слепого A/B)

Классическое парное сравнение `with_skill` vs `without_skill` имеет смысл **не всегда**:
- Если скил содержит **уникальную строгую валидацию документа, закрытую корпоративную схему, авторский JSON-контракт или локальные скрипты/CLI**, без которых задачу выполнить **физически невозможно**, прогон `without_skill` гарантированно даст `~0%` или галлюцинацию. Считать по таким кейсам `Impact Score` бессмысленно — это лишь тратит токены и создаёт ложное ощущение пользы.
- Поэтому **перед запуском** AI-оценщик (`agents/execution-evaluator.md`) присваивает каждому кейсу режим:
  1. **`AB_MEANINGFUL`** — модель способна осмысленно решить задачу и без скила (архитектура, код-ревью, SQL, рефакторинг, работа с публичными API). Запускаются оба рукава для поиска `Redundant` (`>=80%` без скила) и **`Regression`** (скил мешает сильной модели!).
  2. **`WITH_SKILL_ONLY`** — задача требует уникальной валидации/скриптов/формата скила. Прогон `without_skill` **пропускается** (`ab_skipped: true`), а все ресурсы уходят на глубокий **Runtime Execution Audit** (оценку поведения AI по трассе выполнения).
  3. **`HYBRID`** — открытая часть проверяется сравнительно, а уникальные детерминированные ворота — через runtime trace `with_skill`.

---

## 2. Пошаговый конвейер запуска

1. **Этап А — Инициализация и AI Gate**:
   Сначала `execution-evaluator` изучает скил и `evals/evals.json`, формируя `eval_applicability.json`:
   ```bash
   python3 <skill_auditor_dir>/scripts/eval_runner.py prepare \
     --evals <target_dir>/evals/evals.json \
     --workspace <eval_workspace> \
     --applicability <eval_workspace>/eval_applicability.json
   ```
   Скрипт создаёт изолированные каталоги `<eval_workspace>/runs/case_<id>/with_skill/` (и `without_skill/` только для `AB_MEANINGFUL` / `HYBRID`).

2. **Этап Б — Выполнение задач в изолированных сессиях**:
   Запустите каждый рукав в чистом контексте (субагент или изолированный прогон) и сохраните артефакты + трассу тулов (прочитанные файлы, команды, ошибки `stderr`, число ходов/токенов).

3. **Этап В — Оценка AI на этапе выполнения (Runtime Execution Grading)**:
   `execution-evaluator` проверяет не только итоговый текст, но и 5 осей трассы выполнения (`0–5` по каждой в `eval_judgments.json`):
   - `progressive_disclosure` — прочитаны только нужные `references/` по условию;
   - `script_and_tool_discipline` — вызваны реальные `scripts/`, не подделаны расчёты, обработаны ошибки;
   - `invariant_and_guardrail_compliance` — соблюдены запреты, HITL-подтверждения и границы недоверия без «отговорок» (`RL`);
   - `context_and_turn_economy` — нет зацикливаний (`FM-1.3`) и мусорного чтения всего каталога;
   - `output_spec_accuracy` — пройдены строгие валидаторы и ассерты результата.

4. **Этап Г — Детерминированный подсчёт метрик**:
   ```bash
   python3 <skill_auditor_dir>/scripts/eval_runner.py score \
     --judgments <eval_workspace>/eval_judgments.json \
     --output <eval_workspace>/eval_benchmark.json \
     --markdown-out <eval_workspace>/eval_benchmark.md
   ```
   Агрегатор классифицирует кейсы в **Four Buckets** (`WORKING`, `GAP`, `REDUNDANT`, `REGRESSION`) и **Runtime Buckets** (`RUNTIME_PASS`, `RUNTIME_GAP`), а **Impact Score** считает **строго по `AB_MEANINGFUL` кейсам**, чтобы `0%` невозможных задач не раздували дельту искусственно.
