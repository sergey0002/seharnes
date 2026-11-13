---
name: triz-contradiction-resolution
description: Опциональный ТРИЗ-слой для неразрешимых противоречий, IFR, ресурсов и поиска неочевидных решений. Использовать когда обычное сравнение упирается в конфликт требований или когда нужно проверить психологическую инерцию. Не является обязательным gate для каждой задачи.
---

# triz-contradiction-resolution

Вход: `criteria.csv`, `contradictions.csv`, `gaps.csv`, `00-brief.md`.  
Выход: только `03-triz/**`: `contradictions.csv`, `ifr.md`, `resources.csv`, `resolution-ledger.csv`, `nine-windows.md`, `afd.md`, `super-effects.md`, `tese-check.md`, `business-adaptation.md`.

## 1. Когда запускать

Триггеры:

- `IF ... THEN ... BUT` конфликт: улучшение одного параметра ухудшает другой;
- два обоснованных требования к одному параметру;
- candidate union дал противоречивые признаки;
- нужно проверить, не изобретается ли велосипед из-за психологической инерции;
- есть `frontier` модель, которой полезен явный IFR.

Для рутинных выборов с закрытыми hard gates скилл можно не запускать: это зафиксировать в `deviation-request.md`.

## 2. Оговорка адаптации

Классическая матрица 39×39 построена для инженерных параметров. Для исследовательского процесса/документации/бизнес-задачи используется **явная адаптация**: `IF-THEN-BUT`, разделение principles, 40 principles как эвристики, business TRIZ. Не выдавать это за каноническую ячейку Алтшуллера.

## 3. Минимальные артефакты

```text
03-triz/contradictions.csv       # type, if/then/but, improving, worsening, adaptation: explicit, status
03-triz/ifr.md                   # IFR, benefits/costs/harms, no_new_harm
03-triz/resources.csv            # internal/external/supersystem, readily-available/derived
03-triz/resolution-ledger.csv    # separation principle, inventive principles, resource_ids, verification
03-triz/nine-windows.md          # subsystem/system/supersystem × past/present/future + anti-system
03-triz/afd.md                   # «как сделать неверным, не нарушив формальные gates»
03-triz/super-effects.md         # новые пользы/вреды, review triggers
03-triz/business-adaptation.md   # почему перенос ТРИЗ на процесс корректен
```

## 4. Stop

Если скилл запущен, `TRIZ_ADAPTATION` = PASS только при `adaptation: explicit`, отсутствии статуса `tradeoff`, наличии verification и super-effects. Если не запущен, gate помечается `n/a` с ссылкой на deviation/профиль.

## Запрещено

- Делать ТРИЗ обязательным для каждой задачи.
- Выдавать адаптацию за официальную матричную ячейку.
- Закрывать противоречие компромиссом без `resolution-ledger.csv`.
