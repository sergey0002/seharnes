---
name: existing-solution-scouting
description: Ищет существующие решения с подтверждённым опытом успешного применения до всякого изобретения нового подхода. Использовать когда нужна практическая рекомендация для любой задачи: выбрать технологию, стандарт, методику, железо, продукт, фреймворк, библиотеку, процесс или комбинацию. Не привязан к open source. Строит longlist, adoption evidence, shortlist и reuse decision.
---

# existing-solution-scouting

Вход: `00-brief.md`, `task-spec.md`, `research-protocol.md`, `method-registry.md`.  
Выход: `candidates.csv`, `adoption-evidence.csv`, `reuse-decision.md`, при необходимости `build-justification.md`.

## 1. Универсальность

`candidate_type` не ограничен open source:

```csv
oss, commercial, saas, managed, hardware, standard, methodology, process, framework, library, model, vendor, hybrid, internal_legacy
```

Примеры: для ИИ-задачи это может быть видеокарта, фреймворк, managed inference, готовая модель, quantization stack; для документации — Reversa, OpenSpec, Spec Kit, Kiro, внутренний стандарт; для пожара — IICRC S700 и локальные протоколы; для клиники — валидированные клинические рекомендации.

## 2. Два прохода поиска

1. **Longlist до насыщения.** Искать действующие, EOL, нишевые, коммерческие, open source, managed, self-hosted, «сделать самим», смежные домены, комбинации, ранее отвергнутые рынком. Число не ограничивается.
2. **Adoption evidence.** Для каждого shortlisted кандидата собрать независимые свидетельства успешного применения: production case study, benchmark, standard, docs/changelog, post-mortem, отзывы с датой/версией. Маркетинг без подтверждения получить tier `T3` и не пускать в decision-critical ячейки.

## 3. candidates.csv

```csv
candidate_id,candidate_type,name,version,proven_use,source_ids,method_ids,status
C001,framework,FrameworkA,2.4,"production case + independent benchmark",S001;S002,M001;M017,shortlisted
```

## 4. adoption-evidence.csv

```csv
candidate_id,evidence_type,source_ids,excerpt,date,version,independence_group,confidence
C001,production_case_study,S001,"used in production at ...",2026-03-11,2.4,CompanyA,high
```

## 5. Ранжированный shortlist

`candidates.csv`/status `shortlisted` не является потолком. Ранг строится после насыщения и capability census. Hard gates отсекают до MCDA: лицензия/регуляция/безопасность/совместимость/бюджет/юрисдикция. Высокий суммарный балл не перебивает veto.

## 6. reuse-decision.md

```markdown
decision: adopt | adapt | extend | compose | build
selected_candidates: [...]
reason: ...
proven_use_evidence: adoption-evidence.csv
extension_plan: ...
exit_strategy: ...
compose_map: ...
build_justification: build-justification.md | —
```

Приоритет: `adopt → adapt → extend → compose → build`. `build` разрешён только если `build-justification.md` доказывает, что готовые решения не закрывают требования и их разумная доработка/композиция дороже или рискованнее.

## 7. build-justification.md

```yaml
build_selected: yes | no
gap_proven: yes | no
uncovered_requirements: [...]
rejected_reuse_options: [...]
why_adapt_failed: ...
why_compose_failed: ...
cost_risk_compare: ...
human_approval: ...
```

## 8. Stop

`REUSE_FIRST = PASS` только если longlist закрыт до насыщения, adoption evidence есть у всех shortlisted, `reuse-decision.md` заполнен, а при `build` есть `gap_proven: yes`. Иначе `INCOMPLETE`.

## Запрещено

- Сразу предлагать новый формат/методику без reuse decision.
- Считать open source обязательным условием.
- Рекомендовать решение только по vendor claim.
- Ограничивать longlist «топ-5».
- Усреднять конфликтующие свидетельства об успешном внедрении.
