# Миграция харнеса 2026-11-02

<!-- meta
type: architecture
status: actual
updated: 2026-11-02
related: [./01-canon-envs.md, ./02-skills.md, ./03-rules.md, ./13-agent-migration.md, ./14-project-migration.md, ../skill-format.md, ../component-install.md, ../../plan/harnesmigrations.md, ../../plan/harnesaudit-2026-11-02.md]
tags: [harness, migration, skills, rules, mcp, dsh]
-->

---

## Суть

Зафиксирован результат миграции харнеса: канон скилов перенесен в
`.agents/skills`, канон правил и MCP остался в `.cursor`, правила MCP собраны в
папку `mcp/`, добавлены манифесты скилов, документы 180 скриптов и валидаторы.
Документ описывает фактическое состояние после правок, чтобы не читать историю
плана и аудита как текущую инструкцию.

---

## 1. Текущая раскладка

```
.agents/
  skills/{name}/SKILL.md       26 скилов, канон скилов
  skills/{name}/README.md      краткое описание без ссылок
  skills/{name}/skill.json     манифест структуры
  skills/{name}/scripts/       собственные скрипты
  skills/{name}/references/    документы по требованию
  skills/{name}/assets/        шаблоны и схемы
  skills/{name}/tests/         тесты скила
  skills/{name}/children/      дочерние скилы, если есть
  rules/*.md                   36 плоских правил для Antigravity, генерируются
  mcp_config.json              19 MCP, вид Antigravity, генерируется
.cursor/
  rules/*.mdc                  36 правил, канон правил
  rules/mcp/{server}.mdc       19 правил MCP, канон
  scripts/                     общие скрипты
  mcp.json, mcp.env            канон MCP и имена секретов
  mcp-servers/                 php-toolchain
.codex/
  skills/                      26 скилов, копия для Codex
  rules/                       36 правил, представление
  config.toml, mcp.json        представление
.kilo/
  rules/                       36 правил, представление
  kilo.jsonc                   MCP и instructions, представление
.dsh/
  skills/dsh-router/           адаптерный скил
  adapters/, scripts/, tests/  kit
  DSH-RULES.md, project.patch.yml, генерируются
  kit.manifest.json            обязательные файлы kit
```

Правила остаются в `.cursor/rules`, потому что у Cursor, Kilo, Antigravity и DSH
нет общего корня правил. MCP остается в `.cursor/mcp.json`, потому что Cursor,
Kilo, Antigravity и DSH читают разные конфиги.

---

## 2. Что изменено

| Что | Было | Стало |
|---|---|---|
| Канон скилов | `.cursor/skills` | `.agents/skills` |
| Копия Kilo | `.kilo/skills` | удалена, Kilo читает `.agents` |
| Копия Codex | `.codex/skills` из `.cursor` | `.codex/skills` из `.agents` |
| Мертвые каталоги | `.antigravity`, `.gemini`, `.kilocode` | удалены |
| Правила MCP | `.cursor/rules/mcp-*.mdc` | `.cursor/rules/mcp/{server}.mdc` |
| Правила Antigravity | `.mdc` с `alwaysApply` | плоские `.md` с `trigger` |
| `comment-triage` | правило в `.cursor/rules` | `gototask/references/comment-triage.md` |
| Данные mirror | `harness-mirror/.data` | `.cursor/.state/harness-mirror` |
| Документы mirror | `harness-mirror/docs` | `harness-mirror/references` |
| Шаблоны отчета | `task-change-report/templates` | `task-change-report/assets` |
| Агент ревью | `task-code-review/agents` | `task-code-review/references` |
| Тесты скилов | `scripts/test_*.py` | `tests/test_*.py` |
| Однопользовательские скрипты | `.doc` | `scripts/` своего скила |
| Манифесты | не было | 26 `skill.json` |
| Документы скриптов | не было | 180 draft-документов |
| Валидаторы | частично | `validate_skills.py`, `validate_docs.py` |
| DSH kit | фиксированный список | `kit.manifest.json` |

---

## 3. Скилы и скрипты

Добавлен 26-й скил `ponytail`: README, `skill.json`, карточка, запись в реестре.
Текст `SKILL.md` сохранен оригинальным, на английском, из
`.doc/temp/skil/ponytail/skills/ponytail/SKILL.md`; `argument-hint` разрешен как
поле импортированного multi-client скила. Ссылки на скил стоят в
`prepare-plan` и `code-editing`.

Перенесены в скилы:

- `yadisk-fetch.ps1` в `yadisk-screenshot/scripts`;
- `new-task-test.py` в `prepare-task-test/scripts`.

Чужие вызовы скриптов заменены зависимостями скилов. Скрипт из папки другого
скила больше не запускается.

---

## 4. Как среды видят компоненты

| Среда | Скилы | Правила | MCP |
|---|---|---|---|
| Cursor | `.agents/skills` и `.codex/skills`, две копии | `.cursor/rules` | `.cursor/mcp.json` |
| Kilo | `.agents/skills`, одна копия | `.kilo/rules` | `.kilo/kilo.jsonc` |
| Antigravity | `.agents/skills`, одна копия | `.agents/rules/*.md`, `trigger` | `.agents/mcp_config.json` |
| DSH | `.agents/skills`, одна копия | `DSH-RULES.md` | `.dsh/project.patch.yml` |
| Codex | `.codex/skills`, одна копия | `.codex/rules` | `.codex/config.toml` |

Две копии в Cursor остаются из-за `.codex/skills`. Убрать их можно только если
Codex начнет читать `.agents/skills`; до подтверждения копия сохраняется.

---

## 5. Скрипты миграции

| Скрипт | Что делает | Проверка |
|---|---|---|
| `sync-agent-views.sh` | `.agents` канон, `.codex` копия, `.kilo` правила и MCP, parity | `PASS parity`, `PASS parity-fresh` |
| `generate-agent-configs.py` | Codex и Kilo views, рекурсивные правила, `.kilo/skills` удаляется | `PASS parity` |
| `generate-antigravity-rules.py` | 36 плоских `.md` с `trigger` | `--check` passed |
| `generate-dsh-config.py` | `DSH-RULES.md`, `project.patch.yml`, 15 MCP | `--check` passed |
| `verify_parity.py` | скилы, правила, MCP по относительным путям | `passed` |
| `copy-dsh-kit.ps1` | kit по `kit.manifest.json` | `test_dsh_kit.py` 6 passed |
| `rebase_project.ps1` | Full и Core, must-check | Full PASS, Core PASS |
| `validate_skills.py` | структура 26 скилов | 0 ошибок, 2 предупреждения |
| `validate_docs.py` | 180 документов, карточки, MCP | 0 ошибок |

---

## 6. Проверки на 2026-11-02

```bash
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selfcheck.sh
bash .dsh/scripts/smoke.sh
python3 .agents/skills/harness-router/children/improvement/scripts/validate_skills.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_docs.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py \
  --rules-dir .cursor/rules --skills-dir .agents/skills
```

Фактический результат:

- `sync`: parity, mcp-views и parity-fresh passed;
- `harness-selfcheck`: 14 passed, 0 failed;
- `smoke`: passed;
- `validate_skills`: 0 ошибок, 2 предупреждения;
- `validate_docs`: 0 ошибок, 0 предупреждений;
- `validate_registry`: passed;
- `validate_rules`: passed, 19 info;
- `harness_mirror check`: passed;
- Full export: must-check PASS;
- Core export: must-check PASS, 15 скилов.

---

## 6.1 Панели после миграции

- `http://127.0.0.1:8090/` - `harness-mirror.service`. После переноса данных в
  `.cursor/.state/harness-mirror` службу нужно перезапустить:
  `systemctl --user restart harness-mirror.service`.
- `http://127.0.0.1:8077/` - панель `.doc/web` в контейнере
  `web-web-panel-1`. Запуск: `bash .doc/web/start.sh`, состояние:
  `docker compose -f .doc/web/docker-compose.yml ps`.
- Проверка: `curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8090/`
  и то же для `8077`. Ожидается `200`.

После перезагрузки машины обе панели проверены: `8090` 200, `8077` 200.
Узел `ponytail` открывается по адресу
`/nodes/skill__ponytail__agents.json`.

---

## 7. Остаток

1. `prepare-plan/SKILL.md` 476 строк и `task-doc/SKILL.md` 465 строк. Это
   предупреждения, не ошибки.
2. 26 карточек скилов существуют, но не унифицированы под один шаблон секций.
3. 180 документов скриптов созданы скелетами, часть полей требует ревью.

---

## Связи

- [Канон и среды](./01-canon-envs.md) - фактическое дерево
- [Карта скилов](./02-skills.md) - 26 скилов и реестр
- [Правила](./03-rules.md) - 36 правил
- [Миграция между агентами](./13-agent-migration.md) - синк и parity
- [Миграция между проектами](./14-project-migration.md) - Full и Core
- [Формат скила](../skill-format.md) - нормативная структура
- [Установка компонента](../component-install.md) - новый скил, скрипт, MCP
- План миграции - фазы M0-M11
- Аудит плана - находки и решения

---

## История изменений

- 2026-11-02: зафиксировано итоговое состояние после перевода канона скилов в
  `.agents/skills`, переноса правил MCP, документов и DSH-кита
- 2026-11-02: ponytail сохранен оригинальным английским текстом, `argument-hint`
  разрешен для импортированного скила, ссылки добавлены в планирование и правку кода
