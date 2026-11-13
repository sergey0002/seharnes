# Раскладка каталогов харнеса

<!-- meta
type: architecture
status: actual
updated: 2026-11-11
related: [index.md, ./state/01-canon-envs.md, ./skill-format.md, ./component-docs.md, ./state/05-scripts.md, ./state/canon-paths.yaml]
tags: [harness, layout, canon, scripts, tools]
-->

---

## Суть

Документ фиксирует, где лежит каждая часть агентского харнеса и чего в каталоге быть не должно. Канон: правила в `.cursor/rules`, скилы в `.agents/skills`, MCP-конфиг в `.cursor/mcp.json`, исполняемые программы и утилиты в `.tools/{name}`. Остальные документы харнеса ссылаются сюда и не повторяют дерево. Область документа только харнес: раскладку продуктового кода проекта он не задаёт.

---

## 1. Границы: харнес и проект

Харнес это агентская конфигурация. К харнесу относятся `AGENTS.md`, `.cursor/`, `.agents/`, `.codex/`, `.kilo/`, `.qoder/`, `.qwen/`, `.dsh/`, `.tools/` и данные скилов в `.doc/skil_data/{skill}/`.

Проект это приложение: `admin/`, `lib/`, `templates/`, `styles/`, `frontend/`, `scripts/`, тесты и проектная документация в `.doc/`. Раскладку этих каталогов задаёт архитектура проекта, а не этот документ.

Правило `.tools/` задаёт место для исполняемых программ и утилит, которые нужны харнесу и dev-контуру. Продуктовый код в `.tools/` не переносится.

Каталог `.doc/` это документация проекта. Исключение только одно: `.doc/skil_data/{skill}/` хранит данные и состояние скила, потому что папка скила для них запрещена ([skill-format.md](./skill-format.md), правило S11).

---

## 2. Корневые каталоги

| Путь | Роль | Кто правит |
|---|---|---|
| `AGENTS.md` | Корневой указатель для всех агентов: канон, адаптеры, порядок MCP | человек, вручную |
| `.cursor/` | Канон правил, общих скриптов и MCP-конфига | человек и harness-improvement |
| `.agents/` | Канон скилов и сгенерированное представление для Antigravity | скилы правятся вручную, остальное генератором |
| `.codex/` | Сгенерированное представление для Codex CLI | только синхронизация |
| `.kilo/` | Сгенерированное представление для Kilo | только синхронизация |
| `.qoder/` | Сгенерированное представление для Qoder | только синхронизация |
| `.qwen/` | Сгенерированное представление для Qwen Code | только синхронизация |
| `.dsh/` | Сгенерированное представление для DeepSeek Harness | только синхронизация |
| `.tools/{name}/` | Исполняемые программы, стеки и утилиты, одна папка на инструмент | человек, локально; каталог вне git |
| `.doc/` | Документация проекта и данные скилов | человек и скилы документации |

Границы харнеса, индексация и отбрасывание ссылок на `.doc/`: [state/01-canon-envs.md](./state/01-canon-envs.md), раздел "Границы харнеса".

---

## 3. `.agents/`

`.agents/skills/` это единственный канон скилов. Остальное в `.agents/` генерируется из `.cursor/`.

| Путь | Что лежит | Статус |
|---|---|---|
| `skills/{name}/` | `SKILL.md`, `README.md`, `skill.json`, `scripts/`, `docs/`, `references/`, `assets/`, `tests/`, `children/` | канон, правится вручную |
| `rules/*.md` | Плоские правила для Antigravity | генерируется из `.cursor/rules` |
| `mcp.json`, `mcp_config.json` | MCP-конфиг с раскрытыми путями | генерируется из `.cursor/mcp.json` |
| `mcp.env` | Переменные MCP | копия `.cursor/mcp.env`, не канон |
| `scripts/` | Не создаётся: скрипты лежат в `.tools/scripts` и `scripts/` скилов | - |
| `README.md` | Указатель на этот документ; текущий текст устарел (П-1) | правится вручную |

Чего в `.agents/` быть не должно:

- ручных правил и ручных копий `.cursor/rules`, их перезапишет синхронизация;
- второго канона скилов, дублей `SKILL.md` и симлинков внутри папки скила;
- скриптов вне `{skill}/scripts/` и данных скила вне `.doc/skil_data/{skill}/`;
- копий MCP-серверов: серверы живут в `.tools/mcp-servers/{name}/`, синхронизация удаляет legacy `.agents/mcp-servers/` и `.codex/mcp-servers/`;
- секретов как источника: секреты живут в `.cursor/mcp.env`, копии в представлениях не редактируются;
- сгенерированных кешей, `vendor/`, `node_modules/` и временных файлов.

---

## 4. `.cursor/`

| Путь | Что лежит | Статус |
|---|---|---|
| `rules/**/*.mdc` | Правила с триггерами, включая `rules/mcp/{server}.mdc` | канон |
| `scripts/` | Общие лаунчеры MCP, обвязки PHP и пакетные обертки `multi-search` / `multi-exec` | канон |
| `mcp.json` | Единый MCP-конфиг для всех адаптеров | канон |
| `mcp.env` | Секреты MCP | канон, вне git |
| `skills` | Симлинк на `../.agents/skills` для Cursor | представление, не второй канон |
| `tools/` | Собранные PHP CLI для MCP: `phpstan`, `phpda` | legacy-исключение, цель `.tools/php-cli/` |
| `README.md`, `README-MCP-SETUP.md`, `recommendations.md` | Документация канона | правится вручную |

Чего в `.cursor/` быть не должно:

- собственных `SKILL.md` вместо симлинка на канон;
- сгенерированных конфигов Codex, Kilo, Qoder и Qwen;
- данных скилов, кешей, `vendor/` и `node_modules/` инструментов;
- скриптов, которые принадлежат конкретному скилу: они лежат в `{skill}/scripts/`;
- бинарников и программ вне `.tools/{name}/`, кроме действующего исключения `tools/`.

---

## 5. `.tools/`

Правило: одна исполняемая программа или утилита равна одной папке `.tools/{name}/`. Имя папки строчными буквами через дефис. Внутри лежат только файлы инструмента: `compose.yaml`, `Dockerfile`, `scripts/`, `state/`, `workspace/`, конфиги.

| Папка | Инструмент |
|---|---|
| `.tools/codeception/` | Автотесты Codeception и их окружения |
| `.tools/docker-dev/` | Dev-стенд: PHP 7.4 + Apache, MySQL, compose |
| `.tools/docker-test/` | Test-стенд |
| `.tools/disk-scan/` | Сканирование диска |
| `.tools/hermes/` | Стек Hermes |
| `.tools/mcp-servers/` | Локальные MCP-серверы, включая `php-toolchain` |
| `.tools/openhands/` | Стек OpenHands |
| `.tools/php85-scan/` | Сканер PHP 8.5 |

Правила размещения:

- скрипт скила лежит в `.agents/skills/{skill}/scripts/`;
- общий лаунчер или обвязка MCP лежит в `scripts/` своего скила, системная утилита в `.tools/scripts/`;
- внешняя программа, бинарник, стек или сканер лежит в `.tools/{name}/`;
- документация скрипта лежит в `{skill}/docs/scripts/`, документация MCP в `{skill}/docs/mcp/` ([component-docs.md](./component-docs.md)).

Чего в `.tools/` быть не должно:

- отдельных исполняемых файлов в корне `.tools/`, каждый инструмент живёт в своей папке;
- продуктового кода проекта;
- скриптов скилов, они принадлежат скилу;
- конфигов, которые обязаны быть в каноне харнеса;
- секретов и дампов в git, каталог `.tools/` целиком локальный.

---

## 6. Скрипты харнеса

| Тип скрипта | Где лежит | Документ |
|---|---|---|
| Шаг скила | `.agents/skills/{skill}/scripts/` | `{skill}/docs/scripts/{файл}.md` |
| Скрипт дочернего скила | `.agents/skills/{parent}/children/{child}/scripts/` | `{child}/docs/scripts/{файл}.md` |
| Общий лаунчер MCP | `.agents/skills/{mcp}/scripts/` | `{mcp-skill}/docs/scripts/{файл}.md` |
| Системная утилита | `.tools/scripts/` | `harness-core/docs/scripts/tools/{файл}.md` |
| Генератор представлений сред | `.agents/skills/harness-router/children/environment-sync/scripts/` | `environment-sync/README.md` |
| Внешняя утилита | `.tools/{name}/` | README инструмента |

Запрещено класть скрипты в корень репозитория, в `.doc/` и в папку скила вне `scripts/`. Копия скрипта в `.codex/`, `.kilo/`, `.qoder/`, `.qwen/`, `.dsh/` и `.agents/scripts/` генерируется и вручную не правится.

---

## 7. Архитектура скила

```
.agents/skills/{name}/
├── SKILL.md          инструкция агенту: вход, шаги, выход, ограничения
├── README.md         зачем скил и как работает, без ссылок
├── skill.json        машинный манифест состава и зависимостей
├── scripts/          исполняемые файлы скила
├── docs/scripts/     документы скриптов, имя повторяет файл
├── docs/mcp/         документы MCP-серверов скила
├── references/       подробности, которые грузятся по требованию
├── assets/           шаблоны и схемы
├── tests/            тесты скила
└── children/         дочерние скилы, маршрутизирует родитель
```

Нормативные требования к папке, frontmatter, `skill.json`, детям и проверкам: [skill-format.md](./skill-format.md). Требования к документам компонентов: [component-docs.md](./component-docs.md). Пошаговая установка: [component-install.md](./component-install.md).

---

## 8. Куда смотреть по каталогам

| Каталог | Документ |
|---|---|
| `.cursor/rules` | [state/03-rules.md](./state/03-rules.md) |
| `.agents/skills` | [skill-format.md](./skill-format.md), [state/02-skills.md](./state/02-skills.md) |
| `.cursor/mcp.json` | [state/04-mcp.md](./state/04-mcp.md), [state/20-mcp-rules.md](./state/20-mcp-rules.md) |
| `.tools/scripts` и `scripts/` скилов | [state/05-scripts.md](./state/05-scripts.md), [state/26-tools.md](./state/26-tools.md) |
| `.tools` | этот документ, раздел 5; стенды в [tests.md](./tests.md) |
| `.doc/harnes` | [index.md](./index.md) |
| Синхронизация сред | [state/13-agent-migration.md](./state/13-agent-migration.md) |
| Машинная карта канона | [state/canon-paths.yaml](./state/canon-paths.yaml) |

---

## Связи

- [index.md](./index.md) - точка входа в документацию харнеса
- [state/01-canon-envs.md](./state/01-canon-envs.md) - синхронизация, parity и границы харнеса
- [skill-format.md](./skill-format.md) - нормативная структура скила
- [component-docs.md](./component-docs.md) - документы скилов, скриптов и MCP
- [component-install.md](./component-install.md) - установка нового компонента
- [state/05-scripts.md](./state/05-scripts.md) - карта скриптов и их аргументы
- [state/13-agent-migration.md](./state/13-agent-migration.md) - как строятся представления сред
- [doc_rules.md](./doc_rules.md) - правила записи в `.doc/`

---

## Известные проблемы и ограничения

### П-1: `.agents/README.md` противоречит канону

- Симптом: README называет `.agents/` устаревшим и отправляет в `.codex/`.
- Причина: текст остался от прежней схемы синхронизации.
- Ограничение: авторитет у `AGENTS.md` и этого документа; `.agents/skills/` остаётся каноном скилов. README следует заменить указателем на этот документ.
- Файлы: `.agents/README.md`

### П-2: PHP CLI лежат в `.cursor/tools`

- Симптом: `phpstan` и `phpda` собраны в `.cursor/tools/vendor/`.
- Причина: историческое размещение до правила `.tools/{name}/`.
- Ограничение: каталог считается legacy-исключением, целевое место `.tools/php-cli/`. Сам MCP-сервер уже лежит в `.tools/mcp-servers/php-toolchain/`; перенос CLI требует правки `phpstan-docker.sh` и `setup.ps1`.
- Файлы: `.cursor/tools/`, `.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh`, `.cursor/setup.ps1`

### П-3: `.cursor/skills` это симлинк

- Симптом: каталог выглядит как второй набор скилов.
- Причина: Cursor ищет скилы в `.cursor/`, канон лежит в `.agents/skills/`.
- Ограничение: править нужно `.agents/skills/`, симлинк не является копией и не редактируется отдельно.
- Файлы: `.cursor/skills`

---

## История изменений

- 2026-11-11: уточнено, что синхронизация удаляет legacy `.codex/mcp-servers/` вместе с `.agents/mcp-servers/`; цель переноса PHP CLI приведена к `.tools/php-cli/`.
- 2026-11-11: документ создан. Раскладка каталогов перенесена из `readmy.md` раздел 2 и `state/01-canon-envs.md` раздел 1, вместо копий поставлены ссылки. Добавлены правила `.tools/{name}/`, размещения скриптов и архитектуры скила. Устаревший инвентарь `readmy.md` удален, файл стал указателем.
