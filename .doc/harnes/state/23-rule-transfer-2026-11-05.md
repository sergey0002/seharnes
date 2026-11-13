# Перенос правил по средам 2026-11-05

<!-- meta
type: architecture
status: actual
updated: 2026-11-05
related: [./01-canon-envs.md, ./03-rules.md, ./13-agent-migration.md, ./19-harness-mirror.md]
tags: [harness, rules, migration, parity, kilo, codex, antigravity]
-->

---

## Суть

Документ фиксирует правку механизма переноса правил из `.cursor/rules` в шесть сред.
Причина правки: Kilo загружал все 38 правил в стартовый промпт, Antigravity не читал
блочный `globs`, Codex не отличал обязательные правила от справочных. Введён один
классификатор `rule_model.py`, единый порядок видов правила и гейт
`verify_rule_triggers.py`. Текущее состояние сред описано в
[13-agent-migration.md](./13-agent-migration.md), канон и parity в
[01-canon-envs.md](./01-canon-envs.md).

---

## 1. Наблюдение и причина

| Наблюдение | Причина | Где видно |
|---|---|---|
| Kilo грузил 38 правил (186 874 байта) в каждый запрос | генератор игнорировал `alwaysApply` и перечислял все `.md` из `.kilo/rules` | `generate-agent-configs.py`, сессия Kilo 292 387 входных токенов |
| Два кэш-промаха стоили по 93k и 95k токенов | провайдер не попал в кэш, полный контекст ушёл повторно | `kilo.db`, сообщения `cache.read = 0` |
| `doc-verify` и `project-doc-indexing` в Antigravity получили `model_decision` | парсер читал `globs` как скаляр и не понимал блочный список | `generate-antigravity-rules.py` |
| Codex не имел списка обязательных правил | все 38 копий лежали в `.codex/rules`, но подключался только `AGENTS.md` | `.codex/` до правки |
| Qwen ставил `globs` выше `alwaysApply`, остальные наоборот | пять локальных классификаторов с разным порядком | генераторы Qoder, Qwen, DSH, Antigravity, Kilo |

История задач по компоненту `environment-sync`: `history: n/a`, в `.doc/tasks/*/doc.md`
подтверждённых случаев изменения этого генератора нет.

---

## 2. Решение

### 2.1 Один классификатор

`rule_model.py` в `environment-sync/scripts` выдаёт ровно один из четырёх видов:

| Вид | Условие | Приоритет |
|---|---|---|
| `always` | `alwaysApply: true` | 1 |
| `conditional` | есть `globs` или `paths` | 2 |
| `agent_requested` | есть `description` | 3 |
| `manual` | нет сигналов | 4 |

`always` важнее `globs`, это совпадает с Cursor: always-правило игнорирует свои globs.
Блочный и inline-список YAML разбираются одинаково.

### 2.2 Маппинг по средам

| Вид | Kilo | Codex | Qoder | Qwen | Antigravity | DSH |
|---|---|---|---|---|---|---|
| always | `instructions` | раздел обязательных в `rules-index` | `always_on` | baseline в `rules` | `always_on` | инлайн |
| conditional | строка в индексе с globs | on-demand строка | `glob` | `rules` с `paths` | `glob` | таблица |
| agent_requested | строка в индексе | on-demand строка | `model_decision` | `skills/rule-*` | `model_decision` | таблица |
| manual | строка в индексе | on-demand строка | `manual` | baseline | `manual` | таблица |

### 2.3 Гейт

`verify_rule_triggers.py` читает канон, классифицирует каждое правило и сверяет
фактический вид во всех шести вью. Он падает на пяти типах расхождений: always
правило вне обязательного списка, on-demand правило в стартовом промпте, неверный
trigger, conditional без globs, отсутствующая копия или строка индекса.
Шаг `rule-triggers` встроен в `sync-agent-views.sh` после проверок Qwen.

---

## 3. Изменённые файлы

| Файл | Роль изменения |
|---|---|
| `.agents/skills/.../environment-sync/scripts/rule_model.py` | новый общий классификатор и парсер frontmatter |
| `.agents/skills/.../environment-sync/scripts/verify_rule_triggers.py` | новый гейт паритета триггеров |
| `.agents/skills/.../environment-sync/scripts/generate-agent-configs.py` | Kilo и Codex собирают индекс, Codex получил `rules-index.md` |
| `.agents/skills/.../environment-sync/scripts/generate-antigravity-rules.py` | использует общий классификатор, читает блочный `globs` |
| `.agents/skills/.../environment-sync/scripts/generate-qoder-config.py` | `trigger_for` делегирует классификацию |
| `.agents/skills/.../environment-sync/scripts/generate-qwen-config.py` | `rule_shape` делегирует классификацию |
| `.agents/skills/.../environment-sync/scripts/generate-dsh-config.py` | `rule_row` делегирует классификацию |
| `.agents/skills/.../environment-sync/scripts/sync-agent-views.sh` | шаг `rule-triggers` |
| `.agents/skills/.../environment-sync/tests/test_sync_views.py` | тесты классификатора и блочного `globs` |
| `.codex/AGENTS.md` | ссылка на `.codex/rules-index.md` |
| `.kilo/kilo.jsonc`, `.kilo/rules-index.md` | сгенерированы |
| `.codex/rules-index.md` | сгенерирован |

Канон правил не менялся: frontmatter `.cursor/rules/*.mdc` остался прежним, поэтому
поведение Cursor не изменилось. Правка только в адаптерах и генераторах.

---

## 4. Проверки на 2026-11-05

```bash
python3 .agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_rule_triggers.py --root .
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .cursor/scripts/harness/verify_parity.py --canonical .agents/skills \
  --view .codex/skills --view .agents/skills --rules-canonical .cursor/rules \
  --rules-view .codex/rules --rules-view .kilo/rules --rules-view .agents/rules \
  --rules-view .qoder/rules
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py \
  --rules-dir .cursor/rules --skills-dir .agents/skills
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py rebuild
```

| Проверка | Результат |
|---|---|
| `test_sync_views.py` | 14/14 passed |
| `verify_rule_triggers.py` | passed, 38 правил, 7 always, 2 conditional, 29 agent_requested, 0 manual |
| `sync-agent-views.sh` | passed: dsh, parity, qoder, qwen, rule-triggers, mcp-views, parity-fresh |
| `verify_parity.py` | passed, errors 0 |
| `validate_rules.py` | passed, 38 правил, 7 alwaysApply, 23 info |
| mirror rebuild | drift 0, nodes 1573 |

Эффект по стартовому контексту:

| Среда | Было | Стало |
|---|---|---|
| Kilo | 38 правил, 186 874 байта | 7 правил плюс индекс, 59 592 байта (-43.9k токенов) |
| Codex | 38 копий без приоритета | `AGENTS.md` 16 438 байт плюс `rules-index.md` 9 726 байт |
| Antigravity | 7 always_on, 31 model_decision | 7 always_on, 2 glob, 29 model_decision |

---

## 5. Остаточные риски

- У Qoder, Qwen и DSH остались свои парсеры frontmatter для тела правила. Классификация
  общая, разбор YAML дублируется.
- Kilo и Codex не инжектят always-правила, а указывают их. Соблюдение зависит от того,
  прочитает ли агент индекс.
- Kilo не умеет привязку правила к файлу по globs. `conditional` правило попадает в
  индекс с перечнем globs, решение остаётся за агентом.
- Гейт `verify_rule_triggers.py` не имеет изолированного unit-теста, проверяется на
  реальном дереве в синке.
- Счётчик скриптов в scripts/README.md остаётся снимком
  2026-11-02 и требует пересборки после переноса скриптов синка в скилы.

---

## 6. Откат

1. Вернуть предыдущие версии `generate-*.py`, `sync-agent-views.sh` и удалить
   `rule_model.py`, `verify_rule_triggers.py`.
2. Запустить `sync-agent-views.sh`: представления пересоберутся из неизменённого канона.
3. Удалить `.kilo/rules-index.md` и `.codex/rules-index.md`, затем вернуть прежний
   `generate-agent-configs.py`.
4. Канон правил и frontmatter не затрагивались, поэтому откат не требует правок
   `.cursor/rules`.

---

## Связи

- [Канон и parity](./01-canon-envs.md) - порядок чтения, зеркала, проверки
- [Рулесы канона](./03-rules.md) - состав 38 правил и их назначение
- [Миграция между агентами](./13-agent-migration.md) - текущее состояние шести сред
- [Зеркало харнеса](./19-harness-mirror.md) - граф и drift после правки
- `rule_model.py` - единый классификатор правил

---

## Известные проблемы и ограничения

### П-1: Индекс вместо принудительной загрузки
- Симптом: always-правило не попало в ответ, хотя помечено обязательным.
- Причина: Kilo и Codex не имеют движка always-apply, индекс читает агент.
- Ограничение: гарантирует только Cursor; для остальных проверяется наличие в индексе.
- Файлы: `.kilo/rules-index.md`, `.codex/rules-index.md`

### П-2: Дублирование парсеров frontmatter
- Симптом: новый YAML-формат читается по-разному в разных адаптерах.
- Причина: Qoder, Qwen и DSH сохранили локальные парсеры для тела правила.
- Решение: следующий шаг - перевести их на `rule_model.split_frontmatter`.
- Файлы: `generate-qoder-config.py`, `generate-qwen-config.py`, `generate-dsh-config.py`

---

## История изменений

- 2026-11-05: создан после правки переноса правил: общий `rule_model.py`, гейт
  `verify_rule_triggers.py`, индекс Codex, исправление блочного `globs` у Antigravity

#harness #rules #migration #parity
