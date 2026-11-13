# exhaustive-research-decision-v6

Готовый drop-in пакет скилла: один компактный корень `SKILL.md` + отдельные дочерние `skills/*/SKILL.md` + агенты, шаблоны, схемы и валидатор. Всё лежит внутри этой папки.

## Установка

Скопируй **всю папку** в `.cursor/skills/`, `.agents/skills/` или `.claude/skills/` — имя `exhaustive-research-decision-v6` менять нельзя. Внутри уже всё: дочерние скиллы, скрипты, шаблоны, схемы, примеры и спецификации агентов. **Больше ничего создавать не надо.** Полная матрица путей и нюансы по субагентам: **[INSTALL.md](INSTALL.md)**.

Кратко:

```bash
mkdir -p .cursor/skills
cp -r exhaustive-research-decision-v6 .cursor/skills/
```

Работает сразу. Опционально: `cp agents/*.md .cursor/agents/` ради нативных `/candidate-scout`, `readonly` и `is_background` — без этого шага роли инлайнятся в промпт обычного subagent.

## Структура

```text
SKILL.md                         # компактный корень, 180 строк (<500)
INSTALL.md                       # куда копировать и что подхватывается
COMPATIBILITY.md                 # 40+ агентов: матрица, ограничения, fallback
README.md
DESIGN-NOTES-v6.md
skills/                          # 10 отдельных дочерних SKILL.md
agents/                          # 8 спецификаций ролей (не нативные subagents)
references/                      # методики, источники, compliance, freedom
assets/templates/                # 28 канонических промежуточных файлов
assets/AGENTS.md.snippet         # fallback для агентов без Agent Skills
schemas/                         # 5 JSON Schema
scripts/check_gates.py           # --init-v6 + check_v6()
examples/minimal-passing-run/    # регрессионный PASS fixture
```

## Стандарт: что есть что

| Вопрос | Ответ |
|---|---|
| Можно ли всё в одну папку? | Да, уже так. `scripts/`, `references/`, `assets/` — каноничные папки стандарта; остальные — дополнительные ресурсы. |
| Дочерние скиллы в `child/`? | Имя групповой папки не регламентировано. У нас `skills/`; подошло бы и `child/`. Главное — свой `SKILL.md` в каждой папке и `name` == имени папки. |
| Ссылаться из основного? | Да. Корень ссылается на все 10 напрямую, одним уровнем; `disable-model-invocation: true` не даёт им триггериться самим. |
| Агенты внутри скилла? | Как спецификации — да. Как нативные Cursor subagents — нет, им нужен `.cursor/agents/`. Fallback описан в `research-assignment`. |
| `paths` или `globs`? | Ни то, ни другое: это расширения клиентов, не спецификация. Мы их убрали ради переносимости. |
| Kilo / Codex / Gemini / Copilot? | Да: корень совместим со всеми; вложенные скиллы там читаются корнем, а не регистрируются отдельно. См. [COMPATIBILITY.md](COMPATIBILITY.md). |

## Быстрый старт

```bash
python scripts/check_gates.py --init-v6 research/<task-id> --force
python scripts/check_gates.py research/<task-id>
```

Свежий `--init-v6` ожидаемо даёт `FAIL/INCOMPLETE`: шаблоны содержат placeholders. `examples/minimal-passing-run/` демонстрирует `PASS`.

## Ключевые отличия от v5

1. Existing-solutions-first: готовые решения любого типа ищутся до изобретения.
2. `criteria.csv` — единый реестр из brief/domain/candidate_union/synthetic.
3. Двухпроходный union признаков и дозаполнение матрицы.
4. Синтетические метрики отделены от фактов формулой и sensitivity.
5. Настоящие промежуточные файлы со ссылками `path + hash + ID`.
6. Risk-adaptive freedom: `frontier | balanced | regulated`.
7. G- guardrails жёсткие, P- процедуры заменяемы через `deviation-request.md`.
8. Дочерние скиллы физически разнесены и связаны из корня.
9. Валидатор исполняет гейты, а не оставляет их прозой.
10. Не привязано к open source; reuse ladder `adopt → adapt → extend → compose → build`.

## Validation status

- `python3 -m py_compile scripts/check_gates.py examples/minimal-passing-run/generate.py` — OK.
- `python3 scripts/check_gates.py examples/minimal-passing-run` — `PASS errors=0 warnings=0`.
- Fresh `--init-v6 /tmp/...` — `FAIL errors=124 warnings=2` (expected: placeholders are not a passing run).
- Root `SKILL.md` — 193 lines, `description` ≤ 1024, все локальные ссылки существуют.
- CJK/внедрённые иероглифы — 0.
- `references/05-source-dossier.md` — 38 unique citation IDs, 0 ID conflicts, 0 duplicate URLs.
- Machine-checkable schemas: 5; templates: 28; agents: 8 focused roles.

Design-readiness self-score: **9.0/10**. Не обещается абсолютная безошибочность: живой прогон на реальной задаче всё ещё требуется, а `residual_unknowns` обязателен.
