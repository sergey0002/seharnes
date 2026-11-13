---
name: domain-safety-verification
description: Определяет класс риска, доменные hard gates, human gate и исполняемую верификацию. Использовать для любого финального решения и обязательно для медицины, пожара/строительства, права, финансов и AI-моделей. Не ставит диагноз и не разрешает работы.
---

# domain-safety-verification

Вход: `00-brief.md`, `00-state.md`, `criteria.csv`, `decision-matrix.csv`, `reuse-decision.md`, domain adapters.  
Выход: `verification.md`, обновление `safety`-полей в `00-state.md` при необходимости.

## 1. Risk class

`low | medium | high | critical`. Для `high|critical` обязательны:

```yaml
human_gate: yes
licensed_professional: ...
signoff_owner: ...
signoff_date: ...
emergency_escalation: yes
review_triggers: [...]
```

## 2. Domain adapters, а не жёсткие playbooks

Адаптер выбирается по `domain` из `00-brief.md`:

| Домен | Пример gate |
|---|---|
| Клиника | PICO, GRADE/AMSTAR/RoB, EtD, human gate, «не диагноз» |
| Пожар/дым | ANSI/IICRC S700, локальные нормы, лицензированный осмотр |
| BCDR/бекапы | RPO/RTO, restore rehearsal, 3-2-1-1-0 |
| Нейромодели | NIST AI RMF, golden dataset, bias/safety, cost/latency |
| Библиотеки/фреймворки | лицензия, CVE, Scorecard/SBOM, reproducible build |
| Стандарт документирования | clean-room rebuild + executable acceptance scenarios |
| Железо/видеокарты | VRAM/bandwidth/TDP/driver/compat/PoC benchmark |

Адаптер добавляет критерии в `criteria.csv` с `origin: domain_standard`, а не создаёт отдельную таблицу.

## 3. verification.md

```markdown
command: "python scripts/verify.py --profile ..."
expected: ...
actual: ...
date: 2026-11-10
version: ...
environment: ...
Status: PASS | FAIL | INCOMPLETE
method_ids: [...]
source_ids: [...]
```

Исполняемая проверка обязательна до финального `PASS`. Для `frontier` профиля можно предложить альтернативную проверку через `deviation-request.md`, но `Status: PASS` без факта прогона запрещён.

## 4. Stop

`VERIFICATION`, `HUMAN_GATE` = PASS только если риск-класс определён, доменные hard gates проверены, human gate подписан где требуется, verification исполнена, super-effects не содержат нового немитигированного harm.

## Запрещено

- Ставить диагноз, назначать дозировки, разрешать заселение после пожара.
- Давать юридически обязывающее заключение без специалиста.
- Заявлять «без ошибок».
- Подменять проверку уверенным тоном.
