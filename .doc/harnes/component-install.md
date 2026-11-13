# Установка скила, скрипта и MCP

> Актуализация 2026-11-13: текущие профили называются Core, Developer и Project. Имена Full и Core ниже исторические; legacy Full отображается в Developer. Основной перенос выполняет `harness_transfer.py`, а не старый `rebase_project.ps1`.

<!-- meta
type: rules
status: actual
version: 1.0
updated: 2026-11-11
related: [./index.md, ./skill-format.md, ./component-docs.md, ./mcp/README.md, ./mcp/rules-placement.md, ./state/13-agent-migration.md, ./state/14-project-migration.md, ../plan/harnesmigrations.md, ../plan/harnesaudit-2026-11-02.md]
tags: [harness, install, skills, scripts, mcp, migration, dsh]
-->

---

## Суть

Документ описывает, как добавить новый скил, скрипт или MCP так, чтобы он
появился во всех средах и перенесся в другой проект. Один компонент проходит
цепочку: канон, документация, индекс, синхронизация, проверка, перенос.

Документ обязателен при внедрении плана миграции. Без записи в индексах и без
проверки переноса компонент считается не установленным.

Корень скилов: `.agents/skills`.

Ниже используется `{SKILLS_ROOT}`. Фактическое значение берется из
`state/13-agent-migration.md`.

---

## 1. Общий порядок

1. Создать компонент в каноне.
2. Создать документ компонента.
3. Обновить индексы и реестр.
4. Обновить DSH-адаптеры, если компонент виден в DSH.
5. Выполнить синхронизацию сред.
6. Проверить parity, MCP views, DSH smoke и видимость правил через harness mirror.
7. Проверить перенос Full и Core.
8. Записать результат в `doc.md` задачи или в `state/`.

Запрещено:

- править генерируемые зеркала `.codex`, `.kilo`, `.agents/rules`, `.qoder`, `.qwen` и `.dsh` вручную; `.agents/skills` остаётся каноном скилов;
- добавлять компонент без документа;
- добавлять MCP без правила и без строки в главной карте;
- добавлять скрипт без записи в `skill.json` или в `dependencies.project`;
- оставлять новые файлы DSH вне `kit.manifest.json`.

---

## 2. Установка скила

### 2.1 Файлы

```
{SKILLS_ROOT}/{name}/
├── SKILL.md
├── README.md
├── skill.json
├── scripts/        если есть свои скрипты
├── references/     если есть подробности
├── assets/         если есть шаблоны
├── tests/          если есть тесты
└── children/       если есть дочерние скилы
```

Требования к содержимому: [skill-format.md](./skill-format.md).

### 2.2 Шаги

1. Создать папку и три обязательных файла.
2. Заполнить `description` триггерами, по которым агент выбирает скил.
3. Добавить свои скрипты в `scripts/`, общие оставить в проекте и объявить в
   `dependencies.project`.
4. Добавить компонент в `component_registry.json`.
5. Обновить `state/02-skills.md` и, если нужно, `state/07-workflows.md`.
6. Если скил участвует в DSH-цикле, обновить `.dsh/skills/dsh-router/SKILL.md`:
   маршрут, счетчик скилов, ссылки на новые пути.
7. Выполнить проверки из раздела 6.

### 2.3 DSH

DSH читает канонические скилы через `skill(name)` из `{SKILLS_ROOT}`. Новый скил
не нужно копировать в `.dsh`. Нужно:

- обновить счетчик и маршрут в `dsh-router`, если скил входит в рабочий цикл;
- проверить, что `skill(name)` видит скил после перезапуска DSH;
- добавить проверку в `smoke.sh`, если скил критичен для цикла.

---

## 3. Установка скрипта

### 3.1 Владелец

| Потребителей | Где лежит | Объявление |
|---|---|---|
| один скил | `{SKILLS_ROOT}/{skill}/scripts/` | `skill.json.resources.scripts` |
| два и более скила | общая область `.tools/scripts/` или проектный контур | `dependencies.project` у каждого |
| DSH-обвязка | `.dsh/scripts/` | `.dsh/kit.manifest.json` |

Запуск скрипта из папки другого скила запрещен. Общий скрипт не копируется в
скилы.

### 3.2 Шаги

1. Положить файл по правилу владельца.
2. Создать документ `.doc/harnes/scripts/{id}.md` по шаблону
   [component-docs.md](./component-docs.md), раздел 3.
3. Указать все аргументы, значения по умолчанию, коды выхода, чтение, запись и
   побочные эффекты.
4. Обновить `skill.json` или `dependencies.project`.
5. Обновить вызовы в `SKILL.md` и документах.
6. Если скрипт запускается в DSH, обновить `.dsh/adapters/shell.md`,
   `.dsh/scripts/run-ps1.sh` (примеры) и `.dsh/kit.manifest.json`.
7. Если скрипт нужен на новом проекте, добавить путь в `$must` или в
   `copy-dsh-kit.ps1 -Check`.
8. Выполнить проверки из раздела 6.

### 3.3 Перенос

Перенос не меняет поведение. Содержимое файла сохраняется, `sha256` до и после
совпадает, меняются только путь и ссылки. После переноса запускается smoke или
`--help` по новому пути.

---

### 3.4 Установка сервиса панели

Сервис `copytrust-tools` объединяет панель `.doc/web` и просмотрщик харнеса. Код едет в kit, состояние и рантайм создаются на Target.

| Что | Где |
|---|---|
| Код | `.doc/web` целиком, `task-analytics` без `out` |
| Реестр кнопок | `.doc/web/config/actions.json` |
| Локальные дополнения | `.doc/web/config/actions.local.json`, не переносится |
| Адаптер | `.doc/web/ADAPTERS.local.md`, создаётся установщиком |
| Состояние | `.doc/web/state`, не переносится |
| Рантайм | образ `copytrust-tools:local`, собирается на Target |

Шаги:

1. `rebase_project.ps1` копирует код, исключая `state`, `ADAPTERS.local.md`, `actions.local.json`.
2. `-RunSetup` вызывает `.doc/web/install.ps1 -Check`, затем `-Project`.
3. `install.sh --check` проверяет `python3`, `bash`, `pwsh`, `docker`, `service.json`, `actions.json`.
4. `docker compose -p copytrust-tools -f .doc/web/compose.tools.yml up -d --build` поднимает сервис на `127.0.0.1:8077`.
5. `verify.sh` проверяет health, реестр действий и граф харнеса.

Компонент не считается установленным, если `install.sh --check` или `verify.sh` вернули ошибку.

## 4. Установка MCP

### 4.1 Файлы

| Что | Где |
|---|---|
| Конфигурация | `.cursor/mcp.json` |
| Исходники локального сервера | `.tools/mcp-servers/{name}/`, каталог вне git |
| Секреты | `.cursor/mcp.env`, только имена в документах |
| Правило вызова | `.cursor/rules/mcp/{server}.mdc` |
| Главная карта | `.cursor/rules/mcp.mdc` |
| Документ | `.doc/harnes/mcp/{server}.md` |
| Состояние | `.doc/harnes/state/04-mcp.md` |
| DSH-карта | `.dsh/adapters/mcp-names.md` |

### 4.2 Шаги

1. Добавить сервер в `.cursor/mcp.json`, секреты в `.cursor/mcp.env`.
   Исходники локального сервера положить в `.tools/mcp-servers/{name}/`. Копии в
   `.cursor/`, `.codex/` и `.agents/` не создавать: синхронизация удаляет
   legacy `.agents/mcp-servers/` и `.codex/mcp-servers/`, а конфиги сред
   ссылаются на путь `.tools/mcp-servers/{name}/`.
2. Создать правило `.cursor/rules/mcp/{server}.mdc`: когда вызывать, все
   инструменты, аргументы, ошибки, проверка. Если сервер добавляет обязательный
   предварительный шаг, добавить короткий указатель в always-правило
   `.cursor/rules/gates.mdc`; детальный MCP-файл оставить по требованию. Для
   path-trigger правила добавить `attach: glob` в frontmatter.
3. Создать документ `.doc/harnes/mcp/{server}.md`: установка, перенос, несколько
   проектов, все параметры и текущие значения.
4. Добавить строку в `.cursor/rules/mcp.mdc` с пометкой о назначении.
5. Обновить `state/04-mcp.md` и `mcp/README.md`.
6. Обновить `.dsh/adapters/mcp-names.md`: имя, префикс `mcp__{server}__`, статус,
   fallback.
7. Если сервер не должен попадать в DSH, записать причину в `mcp-names.md`.
8. Выполнить генерацию клиентских конфигов и проверки из раздела 6.

### 4.3 DSH

`generate-dsh-config.py` включает включенный сервер в `.dsh/project.patch.yml`
автоматически. Вручную нужно обновить `mcp-names.md` и проверить:

```bash
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-dsh-config.py --root . --check
bash .dsh/scripts/smoke.sh
```

Новый сервер не считается установленным, пока не описаны его инструменты,
fallback и статус в `mcp-names.md`.

---

## 5. Новый компонент в DSH

DSH не читает `.cursor` напрямую. Он получает:

| Что | Как |
|---|---|
| Правила | `DSH-RULES.md` из `.cursor/rules` |
| Скилы | `{SKILLS_ROOT}` через `skill(name)` |
| MCP | `.dsh/project.patch.yml` из `.cursor/mcp.json` |
| Скрипты | вызов по repo-relative пути через `run-ps1.sh` |
| Адаптеры | `.dsh/adapters/` |

Поэтому при добавлении компонента DSH обновляется вручную:

1. `dsh-router`: счетчик скилов, маршрут, путь к правилу или скрипту.
2. `mcp-names.md`: новый сервер, префикс, статус, fallback.
3. `shell.md`: пример запуска нового скрипта.
4. `prepare-plan-digest.md`: если изменился путь канона, который он цитирует.
5. `kit.manifest.json`: новый файл обвязки.
6. `smoke.sh`: проверка нового критичного файла.

Если компонент не входит в DSH-цикл, записать это в `mcp-names.md` или в
`dsh-router`, чтобы отсутствие не считалось ошибкой.

---

## 6. Проверки

```bash
# структура скилов и документы
python3 {SKILLS_ROOT}/harness-improvement/scripts/validate_skills.py
python3 {SKILLS_ROOT}/harness-improvement/scripts/validate_docs.py

# реестр и правила
python3 {SKILLS_ROOT}/harness-improvement/scripts/validate_registry.py
python3 {SKILLS_ROOT}/harness-improvement/scripts/validate_rules.py \
  --rules-dir .cursor/rules --skills-dir {SKILLS_ROOT}

# синхронизация и parity
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . visibility --summary
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py \
  --canonical {SKILLS_ROOT} --manifest .doc/skil_data/harness-core/parity-report.json --check

# MCP
python3 .agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py \
  --canonical .cursor/mcp.json --kilo .kilo/kilo.jsonc \
  --expanded .agents/mcp.json --codex-toml .codex/config.toml
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs

# DSH
python3 .agents/skills/harness-router/children/environment-sync/tests/test_dsh_config.py
python3 .agents/skills/harness-router/children/environment-sync/tests/test_dsh_kit.py
bash .dsh/scripts/smoke.sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-dsh-config.py --root . --check
```

Дополнительно вручную:

- Cursor: Customize -> Skills и Rules, новый компонент виден один раз.
- Kilo: `/reload`, новый скил виден, правило в `instructions`.
- Antigravity: Settings -> Customizations, скил виден, правило с `trigger`.
- DSH: `/skills` или `skill(name)`, новый скил виден; MCP-инструмент доступен.

---

## 7. Миграция между проектами

1. Экспорт копирует `.cursor`, `.agents`, `.codex`, `.kilo` и DSH kit.
2. Новый скил в `{SKILLS_ROOT}` попадает автоматически.
3. Новый скрипт в `.dsh/scripts` копируется через `copy-dsh-kit.ps1`, а его
   наличие проверяется по `kit.manifest.json`.
4. Новый MCP попадает в `.cursor/mcp.json` и генерируется на Target.
5. На Target выполняется `sync-agent-views.sh`.
6. Проверяется `copy-dsh-kit.ps1 -Check`.
7. Запускаются Full и Core сборки, проверяется `$must`.
8. Запускается `smoke.sh` и проверка видимости компонента.

Новый компонент обязан быть либо в `$must`, либо в `kit.manifest.json`, иначе
отсутствие на Target не будет замечено.

---

## 8. Чеклист нового компонента

- [ ] компонент лежит в правильном корне;
- [ ] есть `SKILL.md`, `README.md`, `skill.json` для скила;
- [ ] есть документ в `.doc/harnes/skills`, `scripts` или `mcp`;
- [ ] обновлен индекс раздела;
- [ ] обновлен реестр или `dependencies`;
- [ ] обновлен `dsh-router` или `mcp-names.md`, если компонент виден в DSH;
- [ ] файл DSH добавлен в `kit.manifest.json`;
- [ ] синхронизация прошла;
- [ ] visibility гейтов и path-trigger правил прошла в `harness_mirror.py`;
- [ ] parity, MCP views и DSH smoke зеленые;
- [ ] Full и Core export прошли;
- [ ] Target видит компонент во всех средах.

---

## Связи

- [Карта харнеса](./index.md) - точка входа
- [Формат скила](./skill-format.md) - структура и манифест
- [Документирование компонентов](./component-docs.md) - шаблоны документов
- [Размещение MCP](./archive/mcp/rules-placement.md) - папка `mcp/` и среды
- [Миграция между агентами](./state/13-agent-migration.md) - синк и parity
- [Миграция между проектами](./state/14-project-migration.md) - export kit
- [add-skill](../../.agents/skills/harness-router/children/add-skill/SKILL.md) - установка локального скила с документацией
- [remove-skill](../../.agents/skills/harness-router/children/remove-skill/SKILL.md) - удаление скила и очистка ссылок
- [skill-authoring](../../.agents/skills/harness-router/children/skill-authoring/SKILL.md) - создание и аудит скила
- [migration-review](../../.agents/skills/harness-router/children/migration-review/SKILL.md) - разбор локальных скилов, правил и MCP после переноса
- План миграции - фазы M0-M11

---

## Известные проблемы и ограничения

### П-1: DSH router не является каталогом скилов

- Симптом: новый скил не появляется в таблице маршрутов.
- Причина: router маршрутизирует цикл, а не перечисляет все скилы.
- Ограничение: скил доступен через `skill(name)`, но маршрут и счетчик надо
  обновить вручную.

### П-2: `mcp-names.md` не генерируется

- Симптом: новый MCP есть в патче, но его нет в карте DSH.
- Причина: файл ведется вручную.
- Ограничение: добавление MCP без строки в `mcp-names.md` считается неполным.

### П-3: `copy-dsh-kit.ps1 -Check` проверяет только фиксированный список

- Симптом: новый адаптер или скрипт не скопирован, проверка зеленая.
- Причина: `required` в скрипте не пополняется автоматически.
- Ограничение: до появления `kit.manifest.json` новый файл добавляется в
  `required` вручную.

---

## История изменений

- 2026-11-11: локальные MCP-серверы размещаются в `.tools/mcp-servers/{name}/`; добавлены строка таблицы и шаг установки без копий в представления сред.
- 2026-11-09: уточнено, что `.agents/skills` является каноном, а не зеркалом.
- 2026-11-02: создан документ установки скила, скрипта и MCP с проверками сред,
  DSH и переноса между проектами
- 2026-11-09: добавлена проверка visibility-контракта правил для гейтов и path-trigger;
  установка MCP обновляет always-указатель, если новый сервер добавляет обязательный шаг
