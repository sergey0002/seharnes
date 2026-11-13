# Синхронизация харнеса между средами разработки

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [../index.md, ../doc_rules.md, ./14-project-migration.md, ./01-canon-envs.md]
tags: [harness, migration, agents, sync, parity]
-->

---

## Суть

Документ описывает синхронизацию агентского харнеса между средами разработки одного проекта. Канон распределён между `.cursor/`, `.agents/skills/` и корневым `AGENTS.md`. Скрипт `.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` создаёт представления Codex, Kilo, Qoder, Qwen, Antigravity и DSH и запускает проверки. Управляемые зеркала вручную не правятся. Перенос пакета в другой проект описан отдельно в [документе переноса](./14-project-migration.md).

---

## 1. Что считается каноном

| Источник | Содержимое |
|---|---|
| `.agents/skills/` | Канонические скилы, их инструкции, скрипты и ресурсы. `.agents/skills` не является зеркалом. |
| `.cursor/rules/` | Канонические правила `.mdc` с метаданными подключения. |
| `.tools/scripts/` и `scripts/` скилов | Системные утилиты и скрипты-владельцы. Скрипты скилов синхронизируются вместе с деревом `.agents/skills`. |
| `.tools/mcp-servers/` | Локальные MCP-серверы и инструменты. В представления сред не копируются. |
| `.cursor/mcp.json` | Канонический состав и состояния MCP-серверов. |
| `.cursor/mcp.env` | Переменные окружения MCP, если файл существует. |
| `AGENTS.md` | Общие инструкции проекта. |

Канонический DSH kit расположен в `.dsh/skills/`, `.dsh/adapters/`, `.dsh/scripts/`, `.dsh/tests/`, `.dsh/models.overlay.json` и `.dsh/kit.manifest.json`. DSH kit переносится между проектами отдельно; обычный sync генерирует DSH patch и правила.

Канон лежит в локальном git-exclude вместе с `.doc/`, поэтому правки харнеса не
попадают в продуктовые коммиты. Переносится канон копированием дерева, а не `git clone`.

---

## 2. Куда раскладывается

| Среда | Артефакт | Как получается |
|---|---|---|
| Codex CLI | `AGENTS.md` (bootstrap), `.codex/rules/*.md`, `.codex/rules-index.md`, `.agents/skills/`, `.codex/mcp.json` | `generate-agent-configs.py`: frontmatter `.mdc` снимается, MCP копируется как есть; `rules-index.md` делит правила на обязательные и по требованию. Скрипты MCP и инструментов лежат в `scripts/` скилов и копируются вместе с деревом скилов |
| Codex CLI (TOML) | `.codex/config.toml` | `generate-codex-mcp.py` заменяет MCP-секции по канону, сохраняет другие настройки и проверяет результат; `alwaysAllow` не переносится автоматически |
| Kilo | `.kilo/kilo.jsonc`, `.kilo/rules/*.md`, `.kilo/rules-index.md`, `.agents/skills/` | `generate-agent-configs.py`: в `instructions` только `alwaysApply: true`, остальные правила в `.kilo/rules-index.md` по требованию, `type local` с argv, http в `type remote`, `${workspaceFolder}` раскрывается, `${env:VAR}` не инлайнится |
| Qoder | `.qoder/rules/*.md`, `.qoder/skills/`, `.qoder/settings.json` | `generate-qoder-config.py`: `alwaysApply`/`globs` в `trigger`/`glob`, MCP через `run-with-mcp-env.sh`, включенные серверы в `mcp.enabledProjectMcpServers` |
| Qwen Code | `.qwen/rules/*.md`, `.qwen/skills/rule-*/`, `.qwen/settings.json` | `generate-qwen-config.py`: baseline правила без `paths`, glob в `paths`, model decision в skill `rule-*`, HTTP в `httpUrl`, SSE в `url`, выключенные в `mcp.excluded`, `.agents/skills` и `AGENTS.md` нативно |
| Antigravity | `.agents/` (`rules`, `skills`, `mcp_config.json`) | `generate-mcp-config.py`: пути и `envFile` раскрыты; legacy `.antigravity/` и `.gemini/` удалены |
| Antigravity на Windows | `%USERPROFILE%\.gemini\config\mcp_config.json`, артефакт `antigravity_mcp_config.windows-wsl.json` | `generate-mcp-config.py --host windows-wsl`: HTTP как URL, stdio через `wsl.exe ... bash -lc` |
| Agents (legacy) | `.agents/` | те же копии, что Antigravity |
| DeepSeek Harness (generated) | `.dsh/project.patch.yml`, `DSH-RULES.md` | `generate-dsh-config.py`, профиль `full`, отключённые серверы не попадают |
| DeepSeek Harness (kit) | `.dsh/skills/`, `.dsh/adapters/`, `.dsh/scripts/`, `.dsh/tests/`, `.dsh/models.overlay.json` | `copy-dsh-kit.ps1` при переносе удаляет лишние файлы в управляемых каталогах и проверяет содержимое по SHA-256 |

Классификация правил общая для всех адаптеров: `environment-sync/scripts/rule_model.py`
выдаёт `always`, `conditional`, `agent_requested` или `manual`, причём
`alwaysApply: true` важнее `globs`. `gate: true` требует inline-инжект, `attach: glob`
сохраняет path-trigger. Qoder и Antigravity получают `trigger`, Qwen делит на baseline,
paths и `rule-*` skill. Kilo, Codex и DSH не умеют glob-trigger и получают
сгенерированную glob-таблицу в индексе. `verify_rule_triggers.py` проверяет адаптеры,
`harness_mirror.py visibility` проверяет фактическую матрицу; синк падает при нарушении.

Порядок в синке: генераторы Codex/Kilo, очистка `__pycache__`, MCP для
Antigravity/Gemini, Qoder view, Qwen view, копии сред, DSH-патч, затем гейты. Манифест
`parity-report.json` записывается до части проверок, поэтому `passed` означает
успех parity и не подтверждает прохождение остальных гейтов. В конце синка гейт
`parity-fresh` повторно сверяет манифест с текущим каноном.

Общего бэкапа и транзакции на все среды нет. Ошибка в середине синхронизации может оставить часть представлений обновлённой. После проверок sync сканирует локальные скилы; в интерактивном терминале скрипт может предложить их установку. `HARNESS_SYNC_NO_PROMPT=1` отключает вопрос.

## 2a. Когда и как заменяются файлы

| Управляемая область | Поведение обычного sync |
|---|---|
| `.codex/rules/`, `.agents/skills/` | Генератор пересоздаёт правила; Codex читает скилы из канона напрямую. Bootstrap в корневом `AGENTS.md` содержит gate-правила и ссылку на обязательный индекс. Старые отличающиеся копии сохраняются в `.doc/skil_data/environment-sync/backups/`. |
| `.kilo/rules/` | Генератор пересоздаёт правила с удалением лишнего. Kilo читает скилы из `.agents/skills/`; существующий `.kilo/skills/` генератор сохраняет. |
| `.qoder/rules/`, `.qoder/skills/` | Генератор удаляет лишние файлы управляемых правил и скилов. В `.qoder/settings.json` заменяются управляемые MCP-серверы и список включённых серверов; другие настройки сохраняются. |
| `.qwen/rules/`, `.qwen/skills/rule-*/` | Генератор удаляет лишние управляемые правила и сгенерированные `rule-*` скилы. Остальные `.qwen/skills/` сохраняются. В `.qwen/settings.json` заменяются управляемые MCP-разделы; остальные настройки сохраняются. |
| `.agents/rules/` | Правила генерируются из канона. Отдельного пула скриптов в `.agents` нет: системные утилиты лежат в `.tools/scripts`, скрипты MCP в `scripts/` скилов. `.agents/skills/` остаётся каноном. |
| `.agents/mcp.json`, `.agents/mcp_config.json` | Файлы заменяются сгенерированным нативным MCP-конфигом. |
| `.cursor/skills/` | В исходном репозитории это симлинк на `.agents/skills`, синк его не трогает. В перенесённом проекте экспорт раскрывает симлинк в реальный каталог, и sync обновляет копию из канона, чтобы она не замирала после правок скилов. |
| Windows Antigravity `mcp_config.json` | Если каталог профиля найден, файл заменяется независимо от его происхождения и сравнивается с Windows-артефактом. |
| `.codex/config.toml` | Заменяются MCP-секции. Остальные настройки TOML и существующие поля подтверждения Codex для одноимённых серверов сохраняются. |
| `.dsh/project.patch.yml` | Сгенерированный файл обновляется. Patch без маркера генератора считается ручным и без `--force` не перезаписывается; проверка такого patch завершается ошибкой, поэтому обычный sync не проходит. |
| `DSH-RULES.md` | Генерируется из правил канона. |

Если `.cursor/mcp.env` существует, sync копирует его в соответствующие представления. Если файл отсутствует, генератор Codex/Kilo сохраняет имеющиеся целевые `mcp.env`; отсутствие канона не означает удаление секретов. Проверка наличия обязательного исходного каталога предотвращает очистку зеркала при отсутствующем источнике.

MCP-серверы лежат в `.tools/mcp-servers` и в представления сред не копируются. Legacy-каталоги `.agents/mcp-servers/`, `.codex/mcp-servers/` при синке удаляются. При повреждённом JSON `settings.json` генераторы Qoder и Qwen создают новый объект настроек: локальные настройки повреждённого файла не сохраняются. Скрытые пути исключаются из генерируемых копий скилов.

`copy-dsh-kit.ps1` при переносе в другой проект пересоздаёт четыре управляемых каталога kit и копирует файлы kit. Сравнение SHA-256 после копирования и `-Check` проверяют результат; хеш не используется как разрешение перезаписи. Этот скрипт не запускается при обычном sync сред одного проекта.

Сравнение байтов Windows-конфига выполняется после замены. Сравнение содержимого при сборке Codex избегает лишней записи, а проверка одновременного изменения целевого TOML останавливает запись при конфликте. Условия контроля не означают, что любой файл среды заменяется целиком: исключения перечислены в таблице.

DSH не является отдельным каноном: он читает `.cursor/rules` и `.agents/skills`
и генерирует `DSH-RULES.md` и `.dsh/project.patch.yml`. Поэтому перенос правил в
`.cursor/rules/mcp/`, правка скилов и смена набора MCP обязаны проходить через
`generate-dsh-config.py` и тесты DSH. Целевые фазы и разрывы:
план (удалён) M9-M11 и
аудит (удалён).

---

## 3. Команды

```bash
# полная синхронизация из корня репо
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh

# внешний гейт свежести (pre-commit, CI): ничего не пишет
python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py \
  --canonical .agents/skills \
  --manifest .doc/skil_data/harness-core/parity-report.json --check

# сверка набора MCP по всем средам
python3 .agents/skills/harness-router/children/mcp-audit/scripts/verify_mcp_views.py \
  --canonical .cursor/mcp.json --kilo .kilo/kilo.jsonc \
  --expanded .agents/mcp.json --expanded .qoder/settings.json \
  --qwen .qwen/settings.json --codex-toml .codex/config.toml

# тесты самого синка
python3 .agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py
python3 .agents/skills/harness-router/children/environment-sync/tests/test_codex_mcp.py
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . visibility --summary
python3 .agents/skills/harness-router/children/environment-sync/tests/test_dsh_config.py
python3 .agents/skills/harness-router/children/environment-sync/tests/test_dsh_kit.py
bash .dsh/scripts/smoke.sh
```

`--allow-drift` позволяет продолжить после ошибок проверок, выполняемых через `verify_step`. По умолчанию провал такой проверки даёт exit 1. Ошибка генерации или копирования останавливает скрипт до проверок независимо от `--allow-drift`.

Проверка Codex без записи:

```bash
python3 .agents/skills/harness-router/children/environment-sync/scripts/generate-codex-mcp.py \
  --root . --config .codex/config.toml --check
```

---

## 4. Что проверяется

| Слой | Проверка |
|---|---|
| Skills | побайтовый паритет всех зеркал после LF-нормализации, динамический подсчёт |
| Rules | совпадение по stem и телу без Cursor-frontmatter; видимость gates и path-trigger проверяется отдельно |
| MCP | `verify_mcp_views.py` проверяет имена, состояния и раскрытие переменных по правилам каждого формата. Для Codex TOML отдельный `generate-codex-mcp.py --check` сравнивает сгенерированные секции. |
| Manifest | `status: passed` и `canon_hash` совпадает с текущим каноном |
| DSH | `generate-dsh-config.py --check` в синке, smoke проверяет kit |
| Синк | `test_sync_views.py`, `test_dsh_config.py`, `test_dsh_kit.py`; каждый набор проверяет свои сценарии независимо |

`verify_mcp_views.py` не сравнивает семантику команд и аргументов разных адаптеров: форматы и обёртки различаются. `generate-codex-mcp.py --check` проверяет соответствие TOML результату собственного преобразования. Проверки файлов не запускают MCP-серверы и не подтверждают регистрацию инструментов в живой сессии.

---

## 4a. Один проект на инструмент

| Инструмент | Как выбирается проект | Изоляция |
|---|---|---|
| `codebase-memory-mcp` | параметр `project` в каждом вызове, имя из `list_projects` | Один сервер, много проиндексированных репозиториев |
| `serena` | свой systemd-юнит и порт на проект (9121, 9122), клиенты по HTTP | Один активный проект на процесс; общий процесс на все проекты Serena не поддерживает |
| `codegraph` stdio | `projectPath=<root>` в вызове, по умолчанию корень из обертки | Один индекс `.codegraph/` на проект, демон-писатель один |

Правило: `project` и `projectPath` не угадывать, брать из `list_projects` и
параметров обертки. В `.doc/` и чужие репозитории не ходить.

## 4b. Antigravity на Windows

Antigravity IDE 2.5.5 запускает language server как
`language_server_windows_x64.exe` даже для workspace `vscode-remote://wsl+ubuntu/...`.
Глобальный MCP он читает из `%USERPROFILE%\.gemini\config\mcp_config.json` на
Windows-стороне. WSL-путь `~/.gemini/config/mcp_config.json`, куда синк кладет
симлинк, этому процессу не виден, поэтому без отдельного Windows-конфига список
MCP остается пустым.

Синк делает два артефакта:

| Артефакт | Для кого | Команды stdio |
|---|---|---|
| `antigravity_mcp_config.json` | клиенты внутри WSL/Linux (`.agents/`) | нативные Linux-команды |
| `antigravity_mcp_config.windows-wsl.json` | Windows-процесс Antigravity | `wsl.exe -d <distro> -- bash -lc '<cd + env + exec>'` |

Для stdio Windows-конфиг использует `wsl.exe`, а `bash -lc` читает `envFile` внутри WSL. HTTP-серверы используют заданные в конфигурации адреса. Переменные в аргументах, inline-окружении и HTTP-заголовках генератор может раскрыть в Windows JSON. Нативный JSON Antigravity и DSH patch также могут содержать значения из env-файлов. Эти файлы нужно считать потенциально секретными и не выводить их содержимое в отчёт.

При наличии каталога Windows-профиля синк всегда заменяет `mcp_config.json`
версией текущего проекта и проверяет побайтовое совпадение. Настройки других
проектов и ручные изменения в этом файле не сохраняются.

После установки нужен Reload Window в Antigravity: language server читает
`mcp_config.json` при старте.

---

## 5. Правила правки

1. Менять канон `.cursor/`, `.agents/skills/` или корневой `AGENTS.md`, затем `sync-agent-views.sh`.
2. Не редактировать генерируемые представления `.codex/`, `.kilo/`, `.agents/rules/`,
   `.qoder/`, `.qwen/` и `.dsh/` как источники.
3. После изменения `mcp.json` запустить sync: MCP-секции `.codex/config.toml` генерируются из канона.
   Детали по серверу вести в `.doc/harnes/mcp/{server}.md`, один файл на сервер.
4. Перед правкой харнеса идти через `harness-improvement` и полную историю компонента.
5. Проверка parity доказывает совпадение файлов, но не runtime-регистрацию в IDE.
   Для runtime есть `runtime_registration.py`.
6. Структура скилов и документы компонентов ведутся по
   [skill-format.md](../skill-format.md) и [component-docs.md](../component-docs.md).
   Приведение действующих скилов к формату: harnesmigrations.md (план удалён).

---

## 6. Границы

- Kilo не поддерживает `envFile`: значения приходят из `mcp.env` через
  `run-with-mcp-env.sh` в рантайме, секреты в `kilo.jsonc` не попадают.
- В Codex `disabledTools` преобразуется в `disabled_tools`; `alwaysAllow` автоматически не переносится. Генератор предупреждает и сохраняет существующую политику подтверждений Codex. Фактические разрешения зависят от конфигурации клиента.
- Отключённый Sourcegraph с буквальным секретным заголовком представлен в Codex неработающей заглушкой с `enabled = false`. При включении требуется заголовок из переменной окружения. Секрет не печатается в отчёт.
- Antigravity и Gemini не раскрывают `${workspaceFolder}` и `${env:VAR}`: генератор
  подставляет абсолютные пути, поэтому конфиг привязан к каталогу проекта.
- Windows-конфиг Antigravity привязан к WSL-корню и дистрибутиву (`WSL_DISTRO_NAME`).
  Переключение на другой проект требует синка этого проекта, иначе stdio-серверы
  будут смотреть в старый каталог.
- `alwaysAllow` и `disabledTools` Cursor не имеют аналога в Kilo: они фиксируются
  в шапке `kilo.jsonc` и в `kilo-permissions.fragment.jsonc`, применяются вручную.
- Qoder не поддерживает `envFile`: stdio-серверы идут через `run-with-mcp-env.sh`,
  а `disabledTools` превращается в `excludeTools`. Qoder ограничивает активные
  правила 100 000 символов; генератор переводит правила без `alwaysApply` в
  `model_decision` или `glob`, поэтому на старте загружается около 24 тысяч символов.
- Qwen Code не имеет model-decision правил и `envFile`. Правила без globs
  превращаются в baseline или в скилы `rule-*`, stdio MCP идет через
  `run-with-mcp-env.sh`, а выключенные серверы не попадают в `mcpServers` и
  перечисляются в `mcp.excluded`. Паритет `.qwen/rules` проверяет
  `generate-qwen-config.py --check`, а не `verify_parity.py`, потому что часть
  правил живет в `.qwen/skills`.
- При наличии `alwaysAllow` у MCP-сервера Qwen-адаптер устанавливает серверу `trust: true`. Это преобразование не доказывает эквивалентность разрешения отдельного списка инструментов; фактическую политику Qwen нужно проверять отдельно.
- Синк удаляет лишние файлы в управляемых каталогах правил и скилов Qoder.
  Дополнения правил и скилов нужно держать в `.cursor/rules` и `.agents/skills`.
  Плагины Qoder ставятся в пользовательский каталог, проект их не содержит.
- Sourcegraph в каноне отключен (legacy). graphify выведен из канона, его место занял codegraph.
- DSH-патч содержит 14 MCP-клиентов из 14 включённых серверов канона.

---

## Связи

- [Точка входа](../index.md) - карта документации харнеса
- [Итог миграции](./21-harness-migration-2026-11-02.md) - текущий канон и проверки
- [Установка компонента](../component-install.md) - новый скил, скрипт, MCP во всех средах
- [Перенос между проектами](./14-project-migration.md) - вторая миграция, export kit
- [Правила документации](../doc_rules.md) - стандарт `.doc/`
- [Скрипт синхронизации](../../../.agents/skills/harness-router/children/environment-sync/docs/scripts/sync-agent-views.sh.md) - аргументы и побочные эффекты
- [Генератор Codex MCP](../../../.agents/skills/harness-router/children/environment-sync/docs/scripts/generate-codex-mcp.py.md) - формат, проверки и ограничения TOML

---

## Известные проблемы и ограничения

- Ручной DSH patch без маркера не заменяется обычным sync; проверка прерывает строгий прогон. Для осознанной замены генератор DSH поддерживает `--force`.
- Проверка свежести parity без явных `--view` сверяет отчёт и хеш канона, но не читает текущие зеркала. Для проверки зеркал нужно передать их через `--view` или запустить полный sync.
- Зеркала - реальные копии, а не симлинки. До следующего синка они отстают от канона.
- Паритет сравнивает файлы, не регистрацию скила в конкретной IDE.
- codegraph требует локального индекса `.codegraph/`; на новом каталоге его нет,
  инструмент подскажет `codegraph init`.
- Общий HTTP-стек (юниты, порты, лимиты) описан в [15-mcp-stack.md](./15-mcp-stack.md).
- Legacy graphify (9130, `graph.json`, `graphify-mcp-serve.cmd`) сохранен для
  истории и в активном маршруте не используется.
- Antigravity IDE на Windows не читает WSL-симлинк `~/.gemini/config/mcp_config.json`.
  До появления `--host windows-wsl` синк писал только WSL-сторону, и MCP-серверы
  в Windows-клиенте не регистрировались.
- Antigravity читает правила как `.agents/rules/*.md` с `trigger`; генератор преобразует в этот формат канонические `.mdc`.
- Antigravity сканирует скилы и правила на один уровень. `children/` и вложенные
  правила находятся только через `skills.json` или `rules.json`.
- Cursor читает `.agents/skills`, `.codex/skills` и `.claude/skills`. Копии Codex
  и Claude дают дубли, даже если канон один.
- `.antigravity/skills` и `.gemini/skills` удалены как legacy; рабочая точка
  Antigravity это `.agents/skills`.

---

## Исправление discovery 2026-11-12

Канон не меняет расположение. Codex и Cursor больше не получают копии скилов; Antigravity получает `.agents/skills.json` с вложенными каталогами. DSH получает плоские скилы-указатели на вложенный канон. Родительские скилы остаются в общем каталоге. Qoder сохраняет зеркало до runtime-проверки глубины обнаружения.

Gate-правила включаются в управляемый блок корневого `AGENTS.md`; остальные обязательные правила Codex читает по индексу. Наличие пути в индексе больше не считается inline. Стандартное подключение через `model_instructions_file = "AGENTS.md"` удаляется без изменения других настроек. Ссылки правил после преобразования ведут на канонические ресурсы; Antigravity получает globs строкой.

Генератор проверяет receipt перед заменой discovery-файлов и не затирает ручные изменения. Runtime-загрузка в IDE требует отдельного прогона.

## История изменений

- 2026-11-12: исправлены discovery скилов Codex/Cursor/Antigravity/DSH, bootstrap Codex, ссылки перемещённых правил и формат globs.

- 2026-11-11: MCP-серверы вынесены в `.tools/mcp-servers`; синк больше не копирует их в представления сред, legacy-каталоги удаляются.
- 2026-11-09: процесс синхронизации сверен с текущими генераторами; добавлены границы перезаписи, проверки и исключения Codex и DSH.
- 2026-11-09: Windows-конфиг Antigravity всегда заменяется при синхронизации и сверяется с артефактом проекта.
- 2026-11-09: сборка MCP-секций Codex подключена к синхронизации и переносу; существующая политика подтверждений Codex сохраняется.
- 2026-11-09: перенос DSH kit проверяет содержимое и удаляет лишние файлы в управляемых каталогах.
- 2026-11-09: управляемые зеркала переводятся на удаление лишних файлов; уточнены границы канона и отчёта parity.
- 2026-10-29: создан как отдельный документ по миграции между агентами
- 2026-10-29: зафиксированы 16 правил, 18 MCP-серверов (15 включённых), 18 скриптов, DSH 15 клиентов, ручной `.codex/config.toml`
- 2026-10-30: добавлен Windows-артефакт Antigravity (`antigravity_mcp_config.windows-wsl.json`) и установка в `%USERPROFILE%\.gemini\config\mcp_config.json`; stdio через `wsl.exe`
- 2026-11-01: лаунчер `jdocmunch` перенесён из `.dsh/scripts/` (kit) в канон `.cursor/scripts/`; канонический `mcp.json` ссылается на `${workspaceFolder}/.cursor/scripts/...`, а не на абсолютный путь kit
- 2026-11-02: дерево канона обновлено по факту: 36 правил и 26 скилов
- 2026-11-05: Kilo получил Cursor-семантику `alwaysApply`: всегда-правила идут в `instructions`, agent-requested правила в генерируемый `.kilo/rules-index.md`; исправлен разрыв миграции, из-за которого в стартовый промпт попадали все 38 правил
- 2026-11-05: единый классификатор `rule_model.py` и проверка `verify_rule_triggers.py`; Antigravity научился читать блочный `globs`, Qoder, Qwen, DSH и Kilo используют один порядок классификации
- 2026-11-05: Codex получил `.codex/rules-index.md` с обязательными и on-demand правилами, ссылка добавлена в `.codex/AGENTS.md`; проверка `rule-triggers` сверяет и его
- 2026-11-09: синк получил visibility-контракт `gate`/`attach`; Kilo, Codex и DSH генерируют glob-таблицы, а harness mirror показывает и проверяет режим инжекта каждого правила
- 2026-11-02: добавлена связь с планом M9-M11 и аудитом; DSH обязан проходить
  через `generate-dsh-config.py` после переноса правил и скилов
- 2026-11-02: проверено по официальной документации: Antigravity правила `.md` с
  `trigger`, сканирование на один уровень, `.agents/skills` общий корень
- 2026-11-02: удалены `.antigravity`, `.gemini`, `.kilocode`; синк, parity, smoke
  и export переведены на `.codex`, `.kilo`, `.agents`
- 2026-11-03: добавлена среда Qoder по официальной документации: `.qoder/rules`
  с `trigger`/`glob`, `.qoder/skills`, `.qoder/settings.json` с `mcpServers` и
  `mcp.enabledProjectMcpServers`; MCP через `run-with-mcp-env.sh`, проверки в синке и parity
- 2026-11-03: добавлена среда Qwen Code: `.qwen/rules`, `.qwen/settings.json`,
  model-decision правила как скилы `rule-*`, `httpUrl`/`url`/`mcp.excluded`,
  отдельная проверка `generate-qwen-config.py --check`
- 2026-11-11: sync обновляет `.cursor/skills` в перенесённом проекте, если экспорт раскрыл симлинк в реальный каталог; в документации уточнён порядок записи `parity-report.json` и гейт `parity-fresh`.
