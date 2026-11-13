# Скрипт: `.agents/skills/harness-router/children/environment-sync/scripts/verify_rule_triggers.py`

<!-- meta
type: script
status: actual
updated: 2026-11-09
related: [../../SKILL.md]
tags: [harness, script, verify_rule_triggers, parity, verification]
-->

## Суть
Кросс-средая проверка парности классификации и visibility-контракта правил. Канон `.cursor/rules/**/*.mdc` классифицируется `rule_model.classify` на 4 вида; отдельно проверяются `gate: true` и `attach: glob`:
- `always` — `alwaysApply: true`
- `conditional` — `globs` или `paths`
- `agent_requested` — только `description`
- `manual` — никаких сигналов

Каждый адаптер должен отобразить этот вид в свой trigger. Дополнительно `gate: true` требует always/inline размещение, а `attach: glob` проверяет автоматический glob-trigger или generated glob-блок:
- Kilo: `instructions` list (always) / `rules-index.md` (остальные)
- Qoder: `always_on` / `glob` / `model_decision` / `manual`
- Qwen: baseline rule (always) / rule с `paths:` (conditional) / `rule-*` skill (agent_requested) / baseline (manual)
- Antigravity: `always_on` / `glob` / `model_decision` / `manual`
- DSH: инлайн `(always)` в `DSH-RULES.md` / on-demand таблица (остальные)
- Codex: только копия файла, нет trigger engine — always в `rules-index.md` head, остальные в tail

Скрипт читает все сгенерированные views и сверяет trigger и размещение каждого правила во всех средах. Дополнительно проверяет, что `gate: true` правила остаются inline, а `attach: glob` правила имеют автоматический trigger или generated glob-блок. JSON содержит `status`, `rules`, `kinds`, `gates`, `attach_globs` и `errors`.

## Когда запускать
- После запуска `sync-agent-views.sh` — верификация что генерация прошла корректно.
- В CI — гарантия что все адаптеры в синхронизации с каноном.
- После ручных правок в `.kilo/`, `.qoder/`, `.qwen/`, `.agents/rules/`, `.codex/rules/`, `DSH-RULES.md` — проверка что не сломана парность.
- При добавлении нового адаптера — чтобы убедиться что маппинг triggers реализован верно.

Если не запускать: расхождения между каноном и views будут накапливаться, агенты в разных IDE будут видеть разные правила.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --root |  | string | нет | . | Корень проекта |
| --canonical |  | string | нет | .cursor/rules | Путь к каноническим правилам |
| --kilo |  | string | нет | .kilo/kilo.jsonc | Путь к Kilo конфигу |
| --kilo-index |  | string | нет | .kilo/rules-index.md | Путь к Kilo rules-index |
| --qoder |  | string | нет | .qoder/rules | Путь к Qoder правилам |
| --qwen |  | string | нет | .qwen/rules | Путь к Qwen правилам |
| --qwen-skills |  | string | нет | .qwen/skills | Путь к Qwen скилам (rule-*) |
| --antigravity |  | string | нет | .agents/rules | Путь к Antigravity правилам |
| --dsh |  | string | нет | DSH-RULES.md | Путь к DSH правилам |
| --codex |  | string | нет | .codex/rules | Путь к Codex правилам |
| --codex-index |  | string | нет | .codex/rules-index.md | Путь к Codex rules-index |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все среды согласуются с каноном (status: passed) | Продолжить |
| 1 | Найдены расхождения (status: failed) | Исправить генерацию или ручные правки в views |
| 2 | Не найден канонический `.cursor/rules` | Указать верный `--root` / `--canonical` |

## Что читает и что пишет
**Читает:**
- `.cursor/rules/**/*.mdc` — канон (frontmatter для классификации)
- `.kilo/kilo.jsonc` — `instructions` массив
- `.kilo/rules-index.md` — текст индекса
- `.qoder/rules/*.md` — frontmatter `trigger`, `glob`
- `.qwen/rules/*.md` — frontmatter `paths`
- `.qwen/skills/rule-*/SKILL.md` — наличие файла
- `.agents/rules/*.md` — frontmatter `trigger`, `globs`
- `DSH-RULES.md` — текст (head = always inlined, tail = on-demand таблица)
- `.codex/rules/**/*.md` — наличие копий
- `.codex/rules-index.md` — head (always) / tail (on-demand)

**Пишет:**
- stdout: JSON:
  ```json
  {
    "status": "passed|failed",
    "rules": 42,
    "kinds": {"always": 10, "conditional": 15, "agent_requested": 12, "manual": 5},
    "gates": 1,
    "attach_globs": 2,
    "errors": [
      "kilo code-editing: always rule missing from instructions",
      "qwen mcp-server: conditional rule without paths",
      "dsh bitbucket-tasks: agent_requested rule missing from on-demand table"
    ]
  }
  ```

## Побочные эффекты
- stdout: JSON отчёт
- Нет файловых записей (read-only)

## Окружение и зависимости
- Python 3.8+
- `rule_model` (локальный: `classify`, `rule_frontmatter`, `rule_paths`, `is_gate`, `needs_glob`, `visibility_contract`, `as_list`, `split_frontmatter`)
- Все сгенерированные views должны существовать (после `sync-agent-views.sh`)

## Примеры
```bash
# Полная верификация всех сред
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_rule_triggers.py --root .

# С кастомными путями (если views не в стандартных местах)
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_rule_triggers.py --root /home/user/project --kilo /custom/.kilo/kilo.jsonc
```

## Ограничения
- Только проверяет, не исправляет. Для исправления нужно перезапустить `sync-agent-views.sh` или соответствующий генератор.
- Не оценивает смысловую достаточность gate-текста; проверяет только frontmatter-контракт, trigger и размещение.
- Требует наличия всех views. Если какой-то адаптер не настроен — ошибки будут для него.
- DSH: парсит по маркерам `<!-- rule: <name> (always) -->` в head и `.cursor/rules/<rel>` в tail таблице.
- Codex: парсит `rules-index.md` по разделителю `## По требованию` (на русском, как генерирует `generate-agent-configs.py`).
- Kilo: парсит `kilo.jsonc` как JSONC (пропускает `//` комментарии), берёт `instructions` массив.

## Связи
- Вызывается: `sync-agent-views.sh` (после генерации), CI pipeline, ручной запуск.
- Зависит от: `rule_model.py`, всех сгенерированных views.
- Верифицирует выходы: `generate-agent-configs.py` (Kilo, Codex), `generate-qoder-config.py`, `generate-qwen-config.py`, `generate-antigravity-rules.py`, `generate-dsh-config.py`.
- Связанные документы: `.doc/harnes/state/03-rules.md`, `.doc/harnes/state/01-canon-envs.md`.

## История изменений
- 2026-11-07: полная документация на основе анализа кода
- 2026-11-09: добавлена проверка visibility-контрактов гейтов и glob-триггеров