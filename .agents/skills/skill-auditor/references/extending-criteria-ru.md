# Расширение критериев, запахов и весов (`skill-auditor`)

Руководство для владельцев пакета `skill-auditor`: куда и как добавлять новые критерии оценки, статические детекторы и измерения без поломки детерминированной математики.

---

## Куда прописывать изменения: быстрая навигация

| Что нужно добавить | Куда прописывать (файлы) | Нужна ли правка Python-кода? |
|---|---|---|
| **Новый подкритерий** внутри `D1–D8` (например, `D5.6` или `D7.5`) | 1. [references/rubric-criteria.md](rubric-criteria.md)<br>2. Соответствующий агент в `agents/*-auditor.md` | **Нет.** `scripts/score_aggregator.py` автоматически суммирует любые `criterion_scores` внутри `D1..D8`. |
| **Новый детерминированный парсерный/структурный запах** (лимиты, поля YAML/TOML, ссылки, AST-сигналы) или правило безопасности `SEC-*` *(не пытайтесь парсить смысл в коде — см. `SCRIPT-OVERREACH`)* | 1. [references/mast-and-smells-catalog.md](mast-and-smells-catalog.md)<br>2. [scripts/static_audit.py](../scripts/static_audit.py) (`static_smells` / `SECURITY_PATTERNS`)<br>3. [scripts/self_test.py](../scripts/self_test.py) | **Да** (1 структурная проверка + 1 регрессионный тест). |
| **Новое верхнеуровневое измерение `D9+`** или **перебалансировка весов `D1–D8`** | 1. [config.json](../config.json) (`dimension_weights` / `custom_dimensions`, сумма весов = `100.0`)<br>2. [references/rubric-criteria.md](rubric-criteria.md)<br>3. Назначить измерение одному из `agents/*.md` или создать нового агента + обновить [SKILL.md](../SKILL.md) | **Нет** для `score_aggregator.py` (он читает `config.json` напрямую). |
| **Язык вывода и политика** | [config.json](../config.json) (`"default_output_language": "ru"`, `"default_policy_profile": "balanced"`) | **Нет.** |
| **Режим A/B + Runtime Eval** | [references/eval-ab-and-runtime-guide.md](eval-ab-and-runtime-guide.md) + [scripts/eval_runner.py](../scripts/eval_runner.py) | **Нет** (для добавления кейсов в `evals/evals.json`). |

---

## Сценарий 1. Добавить семантический подкритерий внутрь `D1–D8`

1. Откройте [references/rubric-criteria.md](rubric-criteria.md) и добавьте пункт вида `- **D5.6 <Название>**: <конкретный объект, условие и проверяемый порог>` (без размытых фраз вроде *"должен быть качественным"* — соблюдайте принцип `AMBIG`).
2. Откройте профильного аудитора в `agents/`:
   - `D1`, `D2` → `agents/trigger-context-auditor.md`
   - `D3`, `D6` → `agents/workflow-reliability-auditor.md`
   - `D4` → `agents/orchestration-subagent-auditor.md`
   - `D5`, `D8` → `agents/tools-mcp-resources-auditor.md`
   - `D7` → `agents/security-safety-auditor.md`
3. Добавьте одноимённый пункт проверки в `## Key Checks` выбранного агента. Агрегатор подхватит новый `criterion_id` при следующем запуске.

## Сценарий 2. Добавить детерминированную структурную проверку (`static_audit.py`)

Добавляйте в скрипт только объективные проверки (размеры, поля конфигурации, граф ссылок, AST/regex-счётчики, security-сигнатуры). Семантический анализ текста (вода `FLUFF`, костыли `SCAR`, автономность `AMBIG`, противоречия смысла `CONTRA`) доверяйте только LLM-агентам из `agents/`.

1. Впишите код запаха, уровень серьёзности и правило срабатывания в [references/mast-and-smells-catalog.md](mast-and-smells-catalog.md).
2. В `scripts/static_audit.py` добавьте объективный сбор данных или парсерную проверку в `audit_skill_package` (и при необходимости в `audit_agents_md` / `audit_cursor_mdc`).
3. Добавьте фикстуру в `scripts/self_test.py` и выполните:
   ```bash
   python3 skill-auditor/scripts/self_test.py
   python3 skill-auditor/scripts/static_audit.py skill-auditor --self-audit-safe --fail-on-critical
   ```

## Сценарий 3. Добавить новое измерение `D9` через `config.json`

1. В `config.json` скорректируйте `dimension_weights` и добавьте запись в `custom_dimensions` так, чтобы суммарный вес всех измерений строго равнялся `100.0`:
   ```json
   "dimension_weights": {
     "D1": 12.0, "D2": 15.0, "D3": 14.0, "D4": 15.0,
     "D5": 11.0, "D6": 12.0, "D7": 10.0, "D8": 5.0
   },
   "custom_dimensions": [
     { "id": "D9", "name": "Domain Compliance & Licensing", "weight": 6.0 }
   ]
   ```
2. Добавьте описание `D9` в [references/rubric-criteria.md](rubric-criteria.md) и включите `"D9"` в `evaluated_dimensions` ответственного агента в `agents/` и в таблицу `SKILL.md`.
