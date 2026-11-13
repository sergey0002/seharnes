# Формат узла харнеса v2.1

<!-- meta
type: config
status: draft
updated: 2026-10-31
related: [plan.md, ../harnes/index.md]
tags: [harness, json, schema, mirror, portability]
-->

---

## Суть

Формат описывает один JSON на один файл харнеса. Склейка блоков по `order` обязана давать исходный файл байт в байт. Два вида узла: декларативный для правил, скилов и конфигов, исполняемый для скриптов. Зеркало это отдельный узел со ссылкой на канон, а не копия внутри узла канона.

Версия 2.1 исправляет противоречия версии 2: обязательный якорь у автоматических связей, дубль пути, время разбора внутри узла и неоднозначность `node_id` у зеркал. Машинная схема лежит в `assets/harness-node.schema.json`, здесь нормативный текст и примеры.

План внедрения: [plan.md](./mirror-plan.md).

---

Переносимая копия этого формата лежит рядом со скилом:
[`references/node-format.md`](../references/node-format.md).
При расхождении нормативной считается копия в скиле, потому что она едет вместе с реализацией.

---

## 1. Область

Описываются только файлы харнеса:

- правила, скилы, их `references`, `scripts`, `assets`;
- конфиги MCP и клиентов;
- скрипты и генераторы харнеса;
- текстовые стандарты харнеса;
- patch-манифесты и роутеры DSH.

Не описываются: продуктовый код, миграции, шаблоны, бизнес-документация, задачи, зеркала внутри `node_modules`, `vendor` и `__pycache__`.

Граф `graph.json` собирается из узлов отдельным шагом и узлом не является.

---

## 2. Два вида узла

| Вид | Расширения | Поле блоков |
|---|---|---|
| `harness_declarative_node` | `.md`, `.mdc`, `.markdown`, `.txt`, `.yml`, `.yaml`, `.json`, `.jsonc` | `content_blocks` |
| `harness_executable_node` | `.sh`, `.bash`, `.zsh`, `.py`, `.js`, `.mjs`, `.ts` | `code_blocks` |

Для `.json` и `.jsonc` блок один, `block_type: "section"`, если файл не разбирается по заголовкам. Для `.md` и `.mdc` действует разбиение по заголовкам.

---

## 3. Идентичность и зеркала

`node_id` строится как `{type}:{slug}`.

- Канон: `rule:doc-rules`, `skill:task-doc`.
- Зеркало: `rule:doc-rules@antigravity`, `skill:task-doc@kilo`. Суффикс среды ставится всегда, даже если среда одна.
- `slug` берется из `name`. Перенос файла в другой каталог не меняет `node_id`.
- `node_id` уникален в пределах проекта. Два файла с одним идентификатором это ошибка проекта, ее нельзя чинить молча.

Поля проекции:

- `canonical: true` только у файла в каноническом каталоге.
- У канона `projection_of` равно `null`.
- У зеркала `canonical: false`, `projection_of` содержит `node_id` канона.
- `environment` определяется по префиксу пути, не по содержимому файла.

Один и тот же текст в `.cursor` и `.kilo` дает два разных узла. Это нужно, чтобы видеть расхождение и знать, какой файл реально прочитал агент.

Автоматические связи зеркала:

- `mirrors` с `origin: auto` на канон;
- `synced_by` с `origin: auto` на скрипт синхронизации.

Они не заменяют смысловые связи и не описывают бизнес-логику.

---

## 4. Среды

| Префикс | environment | Роль | Особенности разбора |
|---|---|---|---|
| `.cursor/` | `cursor` | канон, единственный источник правды | правила `.mdc` с frontmatter, полный набор скилов |
| `.codex/` | `codex` | зеркало | у правил снят frontmatter, расширение `.md`; конфиг `config.toml` |
| `.kilo/` | `kilo` | зеркало | правила `.md`; регистрация в `.kilo/kilo.jsonc` -> `instructions` |
| `.antigravity/` | `antigravity` | зеркало | правила `.mdc`; `mcp.json`, `mcp_config.json` с раскрытыми путями |
| `.gemini/` | `gemini` | зеркало | как antigravity |
| `.agents/` | `agents` | зеркало | правила `.mdc`, полный набор скилов |
| `.dsh/` | `dsh` | отдельная среда | patch-манифест, роутер скилов, adapters, sandbox_policy |
| каталог adapter-файла проекта | `project` | локальные значения | `transferable: false`, в графе помечается отдельно |

`dsh` не является копией `.cursor`. У него свои узлы и связь `patches_target`. Ребро `mirrors` для него не ставится.

Среда `project` ставится файлам вроде `ADAPTERS.local.md`, которые содержат значения конкретного проекта. Такие узлы не переносятся и не считаются частью переносимого ядра.

---

## 5. Байтовые инварианты

1. Файл читается как байты, хеш считается по байтам.
2. Склейка блоков по возрастанию `order` дает исходные байты, включая BOM, CRLF, mixed endings, хвостовые переводы и комментарии.
3. Нормализация пробелов, обрезка `\n`, переформатирование и удаление комментариев запрещены.
4. Если файл не декодируется как UTF-8, узел не создается, возвращается ошибка с кодом 2.
5. В JSON пути только относительные от корня проекта, разделитель `/`.
6. Вывод скрипта детерминирован: одинаковый вход дает одинаковые байты JSON.

---

## 6. Схема A: декларативный узел

```json
{
  "meta": {
    "node_id": "skill:task-doc",
    "name": "task-doc",
    "type": "skill",
    "environment": "cursor",
    "source_file_path": ".agents/skills/documentation-router/children/task-doc/SKILL.md",
    "canonical": true,
    "projection_of": null,
    "transferable": true,
    "content_sha256": "c2b1...",
    "parser_version": "2.1",
    "schema_version": "2.1",
    "description": "Документирует задачу и сверяет архитектуру с кодом."
  },
  "lifecycle": {
    "trigger_condition": "задокументируй задачу",
    "phase": "post-execution",
    "priority": 50
  },
  "sources_of_truth": [
    { "name": "doc_rules", "path": ".cursor/rules/doc-rules.mdc", "scope": "формат документации" }
  ],
  "reconstruction_meta": {
    "total_blocks": 7,
    "has_frontmatter": true,
    "line_ending": "\n",
    "bom": false,
    "final_newline": true
  },
  "content_blocks": [
    {
      "block_id": "b000",
      "order": 0,
      "block_type": "frontmatter",
      "header_text": null,
      "header_level": null,
      "raw_content": "---\nname: task-doc\n---\n",
      "relations": []
    }
  ],
  "global_relations": [],
  "analysis": { "status": "filled", "model": "agent" }
}
```

Для декларативного узла `type` в `meta` один из `skill`, `rule`, `config`, `doc`.

---

## 7. Схема B: исполняемый узел

```json
{
  "meta": {
    "node_id": "script:harness-mirror-scan@kilo",
    "name": "harness-mirror-scan",
    "type": "script",
    "environment": "kilo",
    "source_file_path": ".codex/skills/harness-router/children/mirror/scripts/harness_mirror.py",
    "canonical": false,
    "projection_of": "script:harness-mirror-scan",
    "transferable": true,
    "content_sha256": "9f1c...",
    "parser_version": "2.1",
    "schema_version": "2.1",
    "description": "Сканирует харнес и пишет узлы без потери текста."
  },
  "execution_profile": {
    "runtime": "python",
    "interpreter_shebang": "#!/usr/bin/env python3",
    "command_template": "python3 harness_mirror.py --root . scan",
    "env_vars_required": [],
    "arguments": [
      { "name": "--root", "type": "string", "required": false, "default": ".", "description": "корень проекта" }
    ]
  },
  "lifecycle": {
    "trigger_condition": "шаг H1, ручной запуск",
    "phase": "pre-execution",
    "security_level": "idempotent_write"
  },
  "sandbox_policy": {
    "requires_approval": false,
    "filesystem_access": "workspace_only",
    "network_access": false
  },
  "reconstruction_meta": {
    "total_blocks": 4,
    "line_ending": "\n",
    "bom": false,
    "final_newline": true
  },
  "code_blocks": [
    {
      "block_id": "b000",
      "order": 0,
      "line_range": "1-12",
      "name_or_purpose": "shebang и импорты",
      "raw_code": "#!/usr/bin/env python3\nimport json\n",
      "relations": []
    }
  ],
  "global_relations": [],
  "analysis": { "status": "pending", "model": null }
}
```

`interpreter_shebang` берется из первого блока дословно. Если шебанга нет, значение `null`.

---

## 8. Разбиение на блоки

Декларативный файл:

- frontmatter `--- ... ---` идет блоком `order: 0`, `block_type: "frontmatter"`, заголовок `null`;
- текст до первого заголовка это `preamble`;
- каждая секция начинается с заголовка `#`, `##`, `###` и включает весь текст до следующего заголовка, включая пустые строки;
- `header_text` без символов `#`, `header_level` это число решеток;
- если заголовков нет, весь файл это один блок `preamble`.

Исполняемый файл:

- шебанг и инициализация;
- импорты и константы;
- каждая функция верхнего уровня;
- разбор аргументов;
- точка входа;
- `line_range` в формате `start-end`, нумерация с 1;
- вложенные функции и классы остаются в блоке родителя.

`block_id` стабилен: `b000`, `b001` и далее по порядку. При повторном разборе того же файла идентификаторы блоков сохраняются, если не изменилась структура.

---

## 9. Связи

Таксономия:

| Тип | Смысл |
|---|---|
| `invokes_tool` | запускает консольную команду или скрипт |
| `delegates_to` | передает управление скилу, плагину, субагенту |
| `constrained_by` | подчиняется статическому ограничению |
| `governed_by` | ссылается на стандарт качества или источник правды |
| `enforces_gate` | выполняет роль барьера качества |
| `reads_context` | читает конфиг, лог, память или документацию |
| `next_stage_pipeline` | задает обязательный следующий этап |
| `patches_target` | расширяет или меняет другой узел, DSH Cordis |
| `mirrors` | сгенерированная копия канона |
| `synced_by` | пересобирается конкретным скриптом |

Поля связи:

```json
{
  "target_name": "doc-rules.mdc",
  "target_type": "rule",
  "target_path": ".cursor/rules/doc-rules.mdc",
  "target_node_id": "rule:doc-rules",
  "relation_type": "governed_by",
  "origin": "agent",
  "resolution": "resolved",
  "candidates": [],
  "anchor_text": "перед любой работой с документацией",
  "execution_moment": "шаг B0, до правки файлов",
  "description": ""
}
```

Правила:

1. `origin: agent` ставит агент. `anchor_text` обязателен и обязан быть точной подстрокой того блока, где связь объявлена.
2. `origin: auto` ставит скрипт: `mirrors`, `synced_by`, структурные ребра. Якорь не обязателен.
3. `resolution` обязателен всегда:
   - `resolved` - ровно один кандидат в индексе проекта;
   - `ambiguous` - несколько кандидатов, список в `candidates`;
   - `unresolved` - кандидатов нет, путь и `target_node_id` равны `null`;
   - `missing` - цель была в индексе, но её файл исчез, путь и `target_node_id` сохраняются;
   - `external` - цель вне проекта, например `git`, `npm`, `curl`, `python3`.
4. Запрещено подставлять похожий путь, дописывать расширение на угад и ссылаться на файл, которого нет в индексе.
5. Отсутствие связи не означает отсутствие зависимости. Связь описывает только явное упоминание.

---

## 10. sources_of_truth

Массив объектов `{name, path, scope}`. Сюда попадают стандарты и контракты, которым файл подчиняется: правила документации, стандарты качества, схемы API, регламенты DSH.

- `path` равен `null`, если стандарт упомянут без ссылки.
- `scope` объясняет, что именно берется из источника.
- Смысловые связи с этими источниками ставятся отдельно, в `relations` или `global_relations`.

---

## 11. analysis

```json
{ "status": "pending", "model": null }
```

- `status`: `pending` или `filled`.
- `model`: имя модели или `agent`, либо `null`.
- Время разбора в узле не хранится. Оно лежит в `cache.map`, иначе повторный разбор того же файла дает другой JSON и ломает сравнение версий.

`pending` означает, что скрипт разобрал структуру, а смысловые поля пустые. `filled` ставится только после успешного `apply`.

---

## 12. Кеш

`cache.map` это отдельный файл, не узел:

```json
{
  ".agents/skills/documentation-router/children/task-doc/SKILL.md": {
    "sha256": "c2b1...",
    "node_id": "skill:task-doc",
    "parsed_at": "2026-10-31T08:00:00Z",
    "parser_version": "2.1",
    "schema_version": "2.1"
  }
}
```

Правила:

- хеш совпал и `parser_version` совпал: разбор пропускается;
- хеш совпал, но `parser_version` вырос: узел переразбирается;
- хеш не совпал: узел переразбирается, сравнивается с прошлой версией по `block_id`;
- `schema_version` вырос: переразбор всех узлов обязателен.

---

## 13. Область сканирования и исключения

По умолчанию канон:

- `.cursor/rules/**/*.mdc`, `.md`;
- `.agents/skills/**` (SKILL.md, references, scripts, assets);
- `.cursor/scripts/**`;
- `.cursor/mcp.json`, `.cursor/mcp.env`, `.cursor/mcp-stack/**`.

Зеркала по флагу `--include-mirrors`: те же относительные пути в `.codex`, `.kilo`, `.antigravity`, `.gemini`, `.agents`.

DSH: `.dsh/**/*.md`, `.dsh/**/*.yml`, `.dsh/**/*.json`, `.dsh/**/*.py`, `.dsh/**/*.sh`.

Исключения всегда:

- `node_modules`, `vendor`, `__pycache__`, `.git`;
- `.cursor/tools`, `.kilo/worktrees`, `.kilo/node_modules`;
- `**/.history/**`, каталог данных карты, каталог `prompts`;
- файлы секретов: `mcp.env`, `*.env`, `*.key`, `*.pem`, `secrets*`, `*credentials*`;
- бинарные файлы и изображения;
- продуктовый код, задачи и документация вне `.cursor`, `.codex`, `.kilo`, `.antigravity`, `.gemini`, `.agents`, `.dsh`.

Значения переменных окружения в узлы не попадают. Разрешено хранить только имена переменных в `execution_profile.env_vars_required`. Если файл похож на секрет, узел не создается, в лог пишется путь и причина.

Симлинки не раскрываются. Узел описывает реальный файл, у симлинка записывается `symlink_target`.

---

## 14. Валидация

Перед записью узла проверить по порядку:

1. Файл существует, путь относительный от корня.
2. `environment` совпадает с префиксом пути.
3. `node_id` уникален, у зеркала есть суффикс среды и `projection_of`.
4. `content_sha256` посчитан по байтам.
5. У канона `canonical: true` и `projection_of: null`.
6. У зеркала `canonical: false`, `projection_of` ведет на существующий канон.
7. Все смысловые связи имеют `origin: agent` и непустой `anchor_text`, который есть в блоке.
8. Автоматические связи имеют `origin: auto`.
9. Склейка блоков совпала с файлом байт в байт.
10. `line_ending`, `bom`, `final_newline` совпадают с фактическими.
11. Нет полей вне схемы, нет `null` вместо обязательного значения.
12. JSON разбирается стандартным парсером, без trailing commas.

Ошибка любого пункта означает, что узел не сохраняется. Догадки не подставляются.

---

## 15. Переносимость

Формат не содержит значений проекта. Переносимость обеспечивается тремя правилами:

1. Пути, канон и каталог данных приходят аргументами или из adapter-файла.
2. Локальные значения хранятся в `ADAPTERS.local.md` с `transferable: false`.
3. Смысловой анализ не привязан к IDE. Один и тот же узел валиден в Cursor, Kilo, Codex, Antigravity, Gemini, Agents и DSH.

Узел считается переносимым, если в его `SKILL.md` и `references` нет названий продукта, номеров задач, локальных URL, портов и имен классов. Проектные упоминания допустимы только в adapter-файле.

---

## 16. Примеры

Правило канона:

```json
{
  "meta": {
    "node_id": "rule:doc-rules",
    "name": "doc-rules",
    "type": "rule",
    "environment": "cursor",
    "source_file_path": ".cursor/rules/doc-rules.mdc",
    "canonical": true,
    "projection_of": null,
    "transferable": true,
    "content_sha256": "a41b...",
    "parser_version": "2.1",
    "schema_version": "2.1",
    "description": ""
  },
  "lifecycle": {
    "trigger_condition": "alwaysApply: true",
    "phase": "pre-execution",
    "priority": 0
  }
}
```

Зеркало того же правила:

```json
{
  "meta": {
    "node_id": "rule:doc-rules@antigravity",
    "name": "doc-rules",
    "type": "rule",
    "environment": "antigravity",
    "source_file_path": ".antigravity/rules/doc-rules.mdc",
    "canonical": false,
    "projection_of": "rule:doc-rules",
    "transferable": true,
    "content_sha256": "a41b...",
    "parser_version": "2.1",
    "schema_version": "2.1",
    "description": ""
  },
  "global_relations": [
    {
      "target_name": "doc-rules",
      "target_type": "rule",
      "target_path": ".cursor/rules/doc-rules.mdc",
      "target_node_id": "rule:doc-rules",
      "relation_type": "mirrors",
      "origin": "auto",
      "resolution": "resolved",
      "description": "сгенерированная копия канона"
    },
    {
      "target_name": "verify_parity.py",
      "target_type": "script",
      "target_path": ".cursor/scripts/harness/verify_parity.py",
      "target_node_id": "script:harness-verify_parity",
      "relation_type": "synced_by",
      "origin": "auto",
      "resolution": "resolved"
    }
  ]
}
```

Связь агента:

```json
{
  "target_name": "git-task-blame",
  "target_type": "skill",
  "target_path": ".agents/skills/task-router/children/git-task-blame/SKILL.md",
  "target_node_id": "skill:git-task-blame",
  "relation_type": "delegates_to",
  "origin": "agent",
  "resolution": "resolved",
  "anchor_text": "git-task-blame обязателен в prepare-plan",
  "execution_moment": "шаг P0.5b, перед построением Patches"
}
```

`target_path` в примере взят из индекса проекта. Если файла нет, связь получает `unresolved` или `external`, а не выдуманный путь.

---

## 17. Ревизии

| Версия | Изменения |
|---|---|
| 1.0 | Две схемы, побайтовая обратимость, таксономия связей, DSH, запрет на выдуманные пути |
| 2.0 | `node_id`, `environment`, `canonical`, `projection_of`, `content_sha256`, `parser_version`, кеш, `resolution`, `mirrors`, `synced_by` |
| 2.1 | `origin` у связи и якорь только для `agent`; убран дубль `repo_relative_path`; убран `analysis.at`; добавлены `transferable`, `final_newline`; суффикс среды у зеркал обязателен; анализ зеркал наследуется от канона; описаны исключения, переносимость и граф |

Изменения 2.1 закрывают четыре реальные проблемы:

1. Автоматическая связь `mirrors` не имеет текста в блоке, поэтому обязательный якорь делал ее невалидной.
2. `analysis.at` менялся при каждом разборе и ломал сравнение версий.
3. `repo_relative_path` дублировал `source_file_path` и расходился с ним после переименования.
4. `node_id` зеркала без суффикса нарушал требование уникальности.

---

## Связи

- [План скилла](./mirror-plan.md) - этапы, переносимость, тест в Kilo Code, приемка

---

## История изменений

- 2026-10-31: версия 2.1. Исправлены противоречия 2.0, добавлены `origin`, `transferable`, `final_newline`, описаны исключения и переносимость.
