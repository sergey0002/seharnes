# Добавление среды нового редактора

> Актуализация 2026-11-13: перенос и обновление выполняет `harness_transfer.py`; `kit.json` и PowerShell-списки являются переходными. Инструкции про `.git/info/exclude` ниже исторические: новый overlay по умолчанию не меняет Git-состояние приложения.

<!-- meta
type: rules
status: actual
version: 1.0
updated: 2026-11-11
related: [./index.md, ./component-install.md, ./state/01-canon-envs.md, ./state/13-agent-migration.md, ./state/14-project-migration.md, ./state/19-harness-mirror.md, ../plan/harnesmigrations.md]
tags: [harness, environment, sync, parity, export, editor, opencode]
-->

---

## Суть

Новая среда редактора это не только каталог с конфигом. Среда считается
добавленной, когда она получает правила, скилы, MCP и инструкции из канона,
проходит parity, попадает в перенос проекта и отражается в документации.
Документ фиксирует полный список точек изменения и порядок проверки.
Пример новой среды - opencode, потому что opencode читает `.agents/skills` и
`AGENTS.md` нативно и требует только проектный `opencode.json` и генерируемый
каталог `.opencode/rules`.

---

## 1. Три режима интеграции

| Режим | Что делает среда | Пример | Объем работы |
|---|---|---|---|
| Нативные скилы | читает `.agents/skills` и `AGENTS.md` сама | opencode, Kilo, Qwen Code, omp | низкий |
| Зеркало скилов | требует свою копию `.editor/skills` | Codex, Qoder | средний |
| Свое правило | требует свой формат правил | Codex `flat_md`, Qoder `trigger`, Qwen `paths` | средний или высокий |

Сначала определить режим по официальной документации редактора. Источник
документации брать через MCP `context7`, а не по памяти. Проверять нужно четыре
вопроса:

1. Где редактор ищет проектные правила и скилы.
2. Где лежит проектный конфиг и какое у него имя.
3. Какой формат MCP-серверов: `command` массивом, `url`, `headers`, `environment`.
4. Поддерживает ли редактор глобальный конфиг, который нельзя перезаписывать.

---

## 2. Точки изменения

| Слой | Файл | Что менять |
|---|---|---|
| Реестр сред | `.agents/skills/harness-router/children/harness-core/assets/environments.json` | объект среды: id, adapter, rules, skills, mcp |
| Адаптер для doctor | `.agents/skills/harness-router/children/harness-core/scripts/adapters/{name}.py` | пустой класс `Adapter` с `name` |
| Генератор среды | `.agents/skills/harness-router/children/environment-sync/scripts/generate-{name}-config.py` | запись конфига и `--check` |
| Оркестратор синка | `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` | вызов генератора и `--check` |
| Parity правил и скилов | `.agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py` в вызове синка | добавить `--view` и `--rules-view` |
| Проверка MCP | `.agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py` | добавить конфиг среды |
| Kit экспорта | `.agents/skills/harness-router/children/harness-core/assets/kit.json` | каталог среды в `copy` |
| CLI переноса | `.agents/skills/harness-router/children/harness-core/scripts/harness_cli.py` | каталог среды в `HARNESS_DIRS` |
| Скрипт переноса | `.agents/skills/harness-router/children/new-project/scripts/export_kit.py` | состав из `kit.json`, профили, режимы install/update/mirror |
| Инструкции агента | `AGENTS.md` | строка адаптера и правило чтения |
| Состояние | `.doc/harnes/state/01-canon-envs.md`, `.doc/harnes/state/13-agent-migration.md` | таблица сред и артефактов |
| Индекс | `.doc/harnes/index.md` | строка нового документа |

Один генератор пишет только свои файлы. Чужие каталоги и локальные файлы
разработчика генератор не удаляет.

---

## 3. Порядок добавления

1. Прочитать официальную документацию редактора через `context7`.
2. Определить пути правил, скилов, конфига и формат MCP.
3. Добавить объект в `environments.json`. Для нативных скилов указать
   `"skills": {"mode": "native", "target": ".agents/skills"}`.
4. Создать `adapters/{name}.py`. Он нужен для `doctor`, даже если реальную
   работу делает отдельный генератор.
5. Написать `generate-{name}-config.py` с двумя режимами: запись и `--check`.
   Генератор должен быть идемпотентным: повторный запуск не меняет файл.
6. Подключить генератор в `sync-agent-views.sh` до записи parity-манифеста.
7. Добавить каталог среды в `kit.json` и `HARNESS_DIRS`. Экспорт читает состав
   из `kit.json`, отдельный список в скрипте переноса не нужен.
8. Выполнить синк, затем чистый экспорт в `/tmp` и синк уже в экспортированном
   проекте. Без второго шага проверяется только текущий репозиторий.
9. Обновить `AGENTS.md`, `state/01-canon-envs.md`, `state/13-agent-migration.md`
   и строку в `.doc/harnes/index.md`.

---

## 4. Пример opencode

opencode читает проектные правила из `AGENTS.md`, скилы из
`.agents/skills/{name}/SKILL.md`, а проектный конфиг из `opencode.json` в корне.
Глобальный конфиг лежит в `~/.config/opencode/opencode.json` и принадлежит
пользователю, его нельзя перезаписывать синком.

Минимальный проектный конфиг:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "instructions": [".opencode/rules/gates.md", ".opencode/rules-index.md"],
  "mcp": {
    "servers": {
      "mysql": {
        "type": "local",
        "command": ["bash", "/abs/project/.tools/scripts/run-with-mcp-env.sh", "node", "/abs/project/.tools/scripts/mysql-mcp-proxy.mjs"]
      },
      "codebase-memory-mcp": {
        "type": "remote",
        "url": "http://127.0.0.1:9131/mcp"
      }
    }
  }
}
```

Правила для генератора:

- `instructions` указывает на always-правила в `.opencode/rules` и компактный
  `.opencode/rules-index.md`. Каталог `.agents/rules` содержит frontmatter
  Antigravity и все 38 правил; подключать его целиком нельзя, иначе каждый запрос
  получает около 217 KB правил.
- Правила копируются в `.opencode/rules/*.md` без Cursor-frontmatter.
- MCP `stdio` переводится в `type: local` с массивом `command`.
- MCP `http` и `sse` переводятся в `type: remote` с `url` и `headers`.
- Выключенный сервер получает `disabled: true`; в `mcp.servers` поля `enabled` нет.
- `${workspaceFolder}` раскрывается в абсолютный путь: OpenCode не раскрывает
  переменные в JSON.
- Значение заголовка `${env:VAR}` переводится в `{env:NAME}`. Секреты остаются в
  `.cursor/mcp.env` и подставляются через `run-with-mcp-env.sh`; поля `envFile` у
  OpenCode нет.
- `timeout` канона не переносится: в `mcp.servers` это объект, а не число.
- `alwaysAllow` и `disabledTools` пишутся в `.opencode/permissions.fragment.json`
  для ручного слияния.
- `opencode.json` и `.opencode/` добавить в `.git/info/exclude` и в `kit.json`,
  потому что харнес в этом проекте не коммитится.

Ограничение: opencode загружает все файлы из `instructions` в каждый запрос.
Поэтому в стартовый набор входят только always-правила, остальные лежат в
компактном индексе `.opencode/rules-index.md` и читаются по триггеру.

Оценка для одной среды opencode: 0.5-1 день. Три среды при текущей архитектуре
по отдельности: 2-3 дня. После выноса общих правил в декларативный адаптер
следующая среда стоит 2-4 часа.

---

## 5. Что происходит с локальными скилами и правилами

Синк работает по принципу merge, а не mirror. Канон обновляет свои файлы и не
удаляет локальные добавления.

| Место | Локальный скил или правило | Результат синка |
|---|---|---|
| `.agents/skills/{name}` | скил, созданный в Antigravity | сохраняется, считается каноном, попадает в зеркала |
| `.codex/skills/{name}` | локальный скил Codex | сохраняется, в канон не попадает |
| `.qoder/skills/{name}` | локальный скил Qoder | сохраняется, в канон не попадает |
| `.agents/rules/{name}.md` | локальное правило Antigravity | сохраняется, каноном не становится |
| `.codex/rules/{name}.md` | локальное правило Codex | сохраняется, каноном не становится |
| `.qoder/rules`, `.qwen/rules` | локальное правило | сохраняется, каноном не становится |

Если локальный файл совпадает по пути с файлом канона, канон его перезаписывает.
Чтобы правило или скил заработал во всех средах, его нужно добавить в канон:
скил в `.agents/skills`, правило в `.cursor/rules`.

Что синк действительно удаляет:

- `__pycache__` в сгенерированных представлениях;
- каталоги `.data` внутри копируемых представлений;
- legacy `.kilo/mcp.json`;
- при экспорте с профилем Core: перечисленные task-скилы, правила
  `bitbucket-tasks` и `task-doc`, каталоги `.doc/qa`, `.tools/codeception`,
  `.doc/skil_data/jira`.

Профиль Core применяется только при экспорте. Обычный синк в существующем
проекте эти файлы не удаляет.

Отдельно про Antigravity:

- `.agents/skills` это канон скилов, а `.cursor/skills` это симлинк на него.
  Скил, созданный в Antigravity в этом каталоге, сразу становится каноном.
- `.agents/rules` генерируется из `.cursor/rules`. Локальные правила в
  `.agents/rules` генератор `generate-antigravity-rules.py` сохраняет и печатает
  `kept N local rule(s)`.
- локальное правило в `.agents/rules` не появится у Cursor, Codex, Kilo, Qoder и
  Qwen. Для этого его нужно перенести в `.cursor/rules/{name}.mdc`.

---

## 6. Учет локальных файлов в дереве харнеса

`harness_mirror.py scan` по умолчанию читает канон: `.cursor/rules`,
`.cursor/skills`, `.agents/skills`, `.tools/scripts`, `.cursor/mcp-stack`,
`.tools/mcp-servers`. Новый скил в `.agents/skills` попадает в дерево всегда.

Зеркала `.codex`, `.kilo`, `.agents`, `.antigravity`, `.gemini` добавляются
флагом `--include-mirrors`. Кнопка панели `Пересобрать граф харнеса` вызывает
`rebuild` и включает зеркала, если они уже есть в кеше зеркала.

Практические следствия:

- новый скил в `.agents/skills` виден в дереве как канонический узел;
- новый локальный скил в `.codex/skills` виден только при скане зеркал и остается
  узлом среды, а не канона;
- локальное правило в `.agents/rules` видно при скане зеркал, потому что `.agents`
  входит в `MIRROR_ROOTS`;
- глобальные скилы в `~/.agents/skills` в дерево не попадают: скан работает
  только внутри проекта;
- локальные узлы увеличивают `nodes_without_projection`, но проверка `check`
  проходит, потому что хеш узла совпадает с его собственным файлом.

---

## 7. Синхронизация при переносе проекта

Экспорт и синхронизация это два разных шага.

`harness_cli.py export` запускает `export_kit.py`. Скрипт копирует kit, пишет
`EXPORT_NEXT_STEPS.md` и сам вызывает `sync-agent-views.sh --local-only` в Target.

`onboard-project.py` пытается запустить `.doc/synh_harnes/sync-agent-views.sh`.
Этого файла в текущем каноне нет, поэтому шаг синка пропускается с состоянием
`missing`.

Правильный порядок после экспорта:

```bash
# в корне нового проекта
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py \
  --canonical .agents/skills \
  --manifest .doc/skil_data/harness-core/parity-report.json --check
```

Автоматического переноса вместе с синком сейчас нет. Это осознанное разделение:
сначала копируется kit, затем в новом проекте создаются пути, порты и секреты,
и только после этого генерируются зеркала.

---

## 8. Проверки

```bash
python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py doctor
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py \
  --canonical .agents/skills \
  --manifest .doc/skil_data/harness-core/parity-report.json --check
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py \
  --rules-dir .cursor/rules --skills-dir .cursor/skills
python3 .agents/skills/harness-router/children/improvement/scripts/validate_skills.py
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py rebuild
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py check
```

Обязательная проверка переноса:

```bash
python3 .agents/skills/harness-router/children/new-project/scripts/export_kit.py \
  --source . --target /tmp/new-project --profile developer --mode install --skip-runtime-deps
# затем в /tmp/new-project
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
```

Синк в чистом экспорте должен завершиться строкой
`All Agent Views (including MCP config) Successfully Synced`.

---

## Связи

- [Индекс харнеса](./index.md) - точка входа в документацию харнеса
- [Установка скила, скрипта и MCP](./component-install.md) - общий чеклист компонента
- [Канон и среды](./state/01-canon-envs.md) - канон, зеркала, parity и freshness
- [Миграция между агентами](./state/13-agent-migration.md) - артефакты каждой среды
- [Миграция между проектами](./state/14-project-migration.md) - профили Full и Core, экспорт
- [Зеркало харнеса](./state/19-harness-mirror.md) - узлы, зеркала и drift
- [add-skill](../../.agents/skills/harness-router/children/add-skill/SKILL.md) - установка локальных скилов после миграции
- [remove-skill](../../.agents/skills/harness-router/children/remove-skill/SKILL.md) - удаление скила и очистка ссылок
- [skill-authoring](../../.agents/skills/harness-router/children/skill-authoring/SKILL.md) - создание и аудит скилов
- [migration-review](../../.agents/skills/harness-router/children/migration-review/SKILL.md) - разбор локальных компонентов после переноса
- План миграции харнеса - этапы приведения компонентов к формату

---

## Известные проблемы и ограничения

### П-1: Устаревший MCP-артефакт в `harness-core`

- Симптом: старый `antigravity_mcp_config.json` в `.doc/skil_data/harness-core/`
  содержал пути `.agents/skills/task-management/...`, которых уже нет.
- Причина: генератор по умолчанию пишет `.doc/skil_data/harness-router/antigravity_mcp_config.json`,
  а старый файл в `harness-core` остался от прежней раскладки.
- Решение: исправлено 2026-11-11. `sync-agent-views.sh:15` читает
  `harness-router`, `generate-mcp-config.py:253` пишет туда же; лишний файл в
  `harness-core` удалён. Тест `test_sync_views.py:767` закрепляет путь.
- Файлы: `.agents/skills/harness-router/children/environment-sync/scripts/generate-mcp-config.py:253`,
  `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh:15`

### П-2: Команда verify в CLI не работает

- Симптом: `harness_cli.py verify` завершалась ошибкой argparse.
- Причина: `harness_cli.py` не передавал обязательный `--canonical`.
- Решение: исправлено 2026-11-05, команда передает `--canonical .agents/skills`.
- Файлы: `.agents/skills/harness-router/children/harness-core/scripts/harness_cli.py`

### П-3: Sync dry-run не является безопасным

- Симптом: `sync --dry-run` меняет глобальный симлинк Gemini.
- Причина: dry-run запускает настоящий `sync-agent-views.sh` во временном каталоге,
  а скрипт на строке 149 перевешивает `~/.gemini/config/mcp_config.json` на этот
  временный каталог.
- Ограничение: после удаления временного каталога глобальный конфиг остается битым.
- Решение: в dry-run запретить глобальные записи или запускать с отдельным `HOME`.
- Файлы: `.agents/skills/harness-router/children/harness-core/scripts/harness_cli.py:98`,
  `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh:149`

### П-4: Must-аудит экспорта не учитывает профиль

- Симптом: успешный экспорт Core печатает MISSING для файлов, которые Core удаляет.
- Причина: старый список обязательных файлов был статическим.
- Решение: список строится по профилю и по `environments.json` в `export_kit.py`.
- Файлы: `.agents/skills/harness-router/children/new-project/scripts/export_kit.py`

### П-5: Внешний freshness-гейт не покрывает Qwen и DSH

- Симптом: ручная правка `.qwen/rules`, `.qwen/skills` или `.dsh` не ловится
  внешней проверкой parity.
- Причина: `verify_parity.py --check` проверяет только `canon_hash` и записанные view.
  Qwen и DSH проверяются только внутри синка.
- Ограничение: после синка их можно править незаметно для внешнего гейта.
- Решение: добавить qwen и dsh в parity или отдельный freshness-гейт.

### П-6: Описания environment-sync и new-project не соответствуют коду

- Симптом: `SKILL.md` этих скилов ссылается на подкоманды `harness_cli.py`, которых нет.
- Причина: реальные точки входа это `sync-agent-views.sh` и `export_kit.py`.
- Решение: шаги скилов приведены к этим скриптам.

### П-7: Экспорт без IncludeKilo оставляет проект без .kilo до синка

- Симптом: после экспорта нет `.kilo`.
- Причина: каталог копируется только с флагом `-IncludeKilo`; синк создает его заново.
- Ограничение: до синка проект неполный. Это допустимо, если синк выполняется сразу.

---

## История изменений

- 2026-11-24: добавлена среда omp: нативный режим правил и скилов, генератор `generate-omp-config.py` пишет только `.omp/mcp.json`, адаптер `omp` для doctor, `.omp` в `kit.json`, `HARNESS_DIRS` и исключениях Git. Вложенные правила и скилы в зеркало не попадают: omp сканирует корень на один уровень, а корневые файлы это роутеры со ссылками на детей. Отдельный файл нужен для MCP, потому что провайдер Cursor игнорирует `disabled`, `envFile`, `${workspaceFolder}` и `${env:VAR}`. Детали: [state/13-agent-migration.md](./state/13-agent-migration.md).
- 2026-11-20: введена декларативная политика сред через `environments.json` с переключателем `enabled`; добавлен `environment_policy.py` (чтение переключателей, список управляемых путей, безопасная очистка); синхронизация и перенос используют `render_agent_views.py` с фильтрацией по `enabled`; `compact_agent_views.py` читает список управляемых копий из реестра; `verify_rule_triggers.py`, `harness_mirror.py` и doctor фильтруют проверки по `enabled`; отключены Qoder, Qwen, DSH, Agents (Antigravity) и Cursor (канон); включены Codex, Kilo, OpenCode; Cursor остался каноном с `enabled: false`; OpenCode v2: `generate-opencode-config.py` пишет `opencode.json` (`mcp.servers`, `disabled`), `.opencode/rules` и компактный индекс; `compact_agent_views.py` читает список управляемых копий из реестра и не удаляет изменённые MCP-записи.
- 2026-11-11: П-1 переписан как исправленная проблема: генератор и синк используют один путь в `harness-router`, старый артефакт в `harness-core` удалён.
- 2026-11-11: в области сканирования харнеса путь `.cursor/mcp-servers` заменён на `.tools/mcp-servers`.
- 2026-11-05: создан документ. Зафиксированы точки добавления среды, режимы
  интеграции, пример opencode, поведение merge при синке, учет локальных скилов
  в дереве харнеса и известные проблемы переноса.
