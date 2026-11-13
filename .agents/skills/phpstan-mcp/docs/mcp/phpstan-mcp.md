# MCP: phpstan-mcp

<!-- meta
type: config
status: actual
updated: 2026-11-11
related: [../../../../../.doc/harnes/archive/mcp/README.md, ../../../../../.doc/harnes/state/04-mcp.md, ../../../../../.doc/harnes/state/05-scripts.md]
tags: [harness, mcp, php, static-analysis]
-->

---

## Суть

Статический анализ PHP через локальный php-toolchain. Нужен после правок PHP и перед коммитом при риске ошибок типов.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/phpstan-mcp.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | stdio |
| Запуск | `node-mcp.sh` плюс `.tools/mcp-servers/php-toolchain/server.js` |
| Режим | `MCP_PHP_TOOLCHAIN_MODE=phpstan` |
| Окружение | `MCP_WORKSPACE` в `mcp.json`; `PHP_BIN`, `PHPSTAN_DOCKER_IMAGE`, `PHPSTAN_MEMORY_LIMIT` из `mcp.env` |
| Runtime PHP | образ dev-стенда `copytrust-dev-php-apache:latest`, PHP 7.4 |
| Конфиг анализа | `.cursor/tools/phpstan.neon`, `phpVersion: 70100` |
| Обертка Docker | `.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh` |
| Обертка задачи | `.agents/skills/phpstan-mcp/scripts/phpstan-task.sh` |

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `command: bash ${workspaceFolder}/.tools/scripts/node-mcp.sh ${workspaceFolder}/.tools/mcp-servers/php-toolchain/server.js` |
| Переменные окружения | `MCP_PHP_TOOLCHAIN_MODE`, `MCP_WORKSPACE`, `PHP_BIN`, `PHPSTAN_DOCKER_IMAGE`, `PHPSTAN_MEMORY_LIMIT` |
| PHPStan phar | `.cursor/tools/vendor/phpstan/phpstan/phpstan.phar`, версия 2.1.55 |
| Уровень по умолчанию | 0 |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

- `phpstan_analyze` с параметрами `task`, `paths` и `level` от 0 до 9.
- `task` берет PHP-файлы задачи из `.doc/tasks/{N}/diff.files.md` и незакоммиченных правок. Это основной режим.
- `paths` задает явные файлы или каталоги. Без `task` и `paths` инструмент возвращает ошибку, а не запускает весь проект.

---

## Правила использования

1. После правок PHP запускать `phpstan_analyze` с `task=<N>`.
2. Уровень по умолчанию 0. Для рисковых правок поднимать до 2-5, шум растет.
3. Не анализировать `vendor/`, `node_modules/`, `templates_c/` и сгенерированные каталоги.
4. Не запускать анализ без `task` и `paths`: полный проект долгий и шумный.

---

## Установка и перенос

- Установка: `.tools/mcp-servers/php-toolchain` (каталог `.tools` вне git), `node-mcp.sh`, зависимости Node в каталог toolchain.
- Причина отдельного запуска: на хосте PHP не установлен, а phar PHPStan 2.1.55 требует `^7.4|^8.0`. Основной стенд `.tools/docker-dev` работает на PHP 7.4, поэтому phar запускается в образе стенда `copytrust-dev-php-apache:latest`.
- Отдельный образ не нужен: подходит любой контейнер с PHP 7.4 и новее. `PHPSTAN_DOCKER_IMAGE` в `.cursor/mcp.env` указывает на `copytrust-dev-php-apache:latest`. Ограничение `phpVersion: 70100` задает целевой язык анализа, а не версию runtime.
- Решение: `.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh` монтирует корень проекта в `/app` и запускает phar в образе из `PHPSTAN_DOCKER_IMAGE`, память задает `PHPSTAN_MEMORY_LIMIT`. Отсутствующий образ по умолчанию собирается только из `.tools/docker-dev/php-apache`. Пользовательский тег скрипт автоматически не пересобирает.
- Конфиг `.cursor/tools/phpstan.neon` задает `phpVersion: 70100`, `level: 0`, bootstrap `.cursor/tools/phpstan-bootstrap.php` с константами `PATH` и `HOME_DIR`, символику legacy-кода через `scanDirectories: lib` и `scanFiles` для `langManager.php`, `lang.php`, `maket.php`.
- `.agents/skills/phpstan-mcp/scripts/phpstan-task.sh <N> [level]` собирает PHP-файлы задачи из `.doc/tasks/{N}/diff.files.md`, `git diff`, staged и untracked, убирает `vendor`, `node_modules`, `templates_c`, `.tools`, `.kilo`, `.cursor` и передает список в PHPStan.
- Перенос: скопировать `.tools/mcp-servers/php-toolchain`, оба скрипта `phpstan-*.sh`, `.cursor/tools/phpstan.neon` и `.cursor/tools/phpstan-bootstrap.php`, задать `MCP_WORKSPACE`, `PHPSTAN_DOCKER_IMAGE`, `PHPSTAN_MEMORY_LIMIT`.
- Проект с PHP 7.4 или новее может работать без Docker: не задавать `PHPSTAN_DOCKER_IMAGE`, тогда используется `PHP_BIN`.

## Несколько проектов

- stdio-сервер запускается на каждый проект отдельно; `MCP_WORKSPACE` задает корень анализа.
- Один процесс не обслуживает два проекта: конфиг PHPStan и пути берутся из `MCP_WORKSPACE`.
- Конфиг и скрипты переносятся в `.cursor` проекта, сервер в `.tools/mcp-servers`. Образ Docker можно не переносить, если проект работает на PHP 7.4 или новее.
- Задача задается номером ветки или аргументом. Без номера `phpstan-task.sh` берет номер из имени ветки вида `bugfixes/#2077`.

## Проверка

- `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=phpstan-mcp` отвечает `OK phpstan-mcp` и показывает 1 инструмент.
- `.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh analyze -c /app/.cursor/tools/phpstan.neon --no-progress --level=0 lib/src/Order/ProlongationReconciliationService.php` запускает phar в PHP 7.4.
- `.agents/skills/phpstan-mcp/scripts/phpstan-task.sh 2077 0` на 2026-11-05 проверил 22 файла задачи 2077 и вернул 5 замечаний уровня 0. Время около 30 секунд.
- `docker image inspect copytrust-dev-php-apache:latest` подтверждает наличие образа стенда. Если образ отсутствует, первый запуск `phpstan-task.sh` собирает его и продолжает анализ без ручных шагов.
- `PHPSTAN_DOCKER_IMAGE=php:8.4-cli .agents/skills/phpstan-mcp/scripts/phpstan-task.sh 2070 0` на 2026-11-06 дал тот же результат на PHP 8.4, что и PHP 7.4: 12 файлов, 3 замечания.
- `.agents/skills/phpstan-mcp/scripts/phpstan-task.sh 2070 0` на 2026-11-06 без переменных окружения взял образ `copytrust-dev-php-apache:latest`, проверил 12 PHP-файлов задачи 2070 и вернул 3 замечания уровня 0.
- MCP вызов `phpstan_analyze` с `{ "task": 2077, "level": 0 }` возвращает тот же список файлов и замечаний.

## Связи

- [Карта MCP](../../../../../.doc/harnes/archive/mcp/README.md) - общий список
- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - правила анализа
- [Скрипты](../../../../../.doc/harnes/state/05-scripts.md) - node-mcp и php-toolchain

---

## Известные проблемы и ограничения

### П-1: PHPStan на старом стенде PHP 7.1 (закрыто)

- Симптом: `phar` падал с `Parse error ... Analyser.php` на PHP 7.1.
- Причина: phar PHPStan 2.1.55 требует PHP 7.4 или новее.
- Решение: основной стенд переведен на PHP 7.4 (`copytrust-dev-php-apache:latest`), phar запускается в образе стенда через `.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh`; анализ PHP 7.1 задает `phpVersion: 70100` в `.cursor/tools/phpstan.neon`.
- Файлы: `.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh`, `.cursor/tools/phpstan.neon`, `.cursor/mcp.env`

### П-2: Анализ идет долго или падает по памяти

- Симптом: долгий прогон или ошибка памяти.
- Причина: широкий `paths` и высокий `level`.
- Решение: запускать `task=<N>`, понизить уровень, поднять `PHPSTAN_MEMORY_LIMIT`.
- Файлы: `.agents/skills/phpstan-mcp/scripts/phpstan-task.sh`

### П-3: Ложные ошибки про legacy-методы

- Симптом: на уровне 2 и выше появляются ошибки вида `Call to an undefined method Mailer::SendToClient()`.
- Причина: в `lib/Mailer.php` и `lib/SwiftMailer.php` объявлены два разных класса `Mailer`, PHPStan видит один из них.
- Ограничение: уровень 0 таких ошибок не показывает. Для проверки legacy-классов использовать `get_diagnostics_for_file` и тесты.
- Файлы: `lib/Mailer.php`, `lib/SwiftMailer.php`

### П-4: Нет образа Docker для PHPStan

- Симптом: `phpstan-docker.sh: image <тег> not found`, команда `phpstan-task.sh <N>` завершается с кодом 2 и не анализирует файлы.
- Причина: образ `PHPSTAN_DOCKER_IMAGE` не собран на машине или удален очисткой Docker. Образ стенда `copytrust-dev-php-apache:latest` собирается из локального `.tools/docker-dev/php-apache`; каталог не входит в git.
- Решение: `phpstan-docker.sh` собирает отсутствующий образ по умолчанию только из `.tools/docker-dev/php-apache`. Ручная сборка: `docker build -t copytrust-dev-php-apache:latest .tools/docker-dev/php-apache`. Автосборка отключается переменной `PHPSTAN_AUTO_BUILD=0`, другой тег задается переменной `PHPSTAN_DOCKER_IMAGE` в `.cursor/mcp.env` и подготавливается отдельно. Резервные Dockerfile из `docs/` не используются.
- Файлы: `.agents/skills/phpstan-mcp/scripts/phpstan-docker.sh`, `.tools/docker-dev/php-apache/Dockerfile`, `.cursor/mcp.env`

---

## История изменений

- 2026-11-01: создан по данным `.cursor/mcp.json` и state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
- 2026-11-05: PHPStan переведен на PHP 7.4 Docker из-за стенда на PHP 7.1; добавлен режим `task=<N>` для файлов задачи, конфиг `phpVersion: 70100`, скрипты `phpstan-docker.sh` и `phpstan-task.sh`
- 2026-11-06: `phpstan-docker.sh` собирает отсутствующий образ автоматически из локального `.tools/php74/docker`; в П-4 описано восстановление образа; отслеживаемые файлы `docs/` не менялись
- 2026-11-06: уточнено, что отдельный образ не обязателен: подходит любой PHP 7.4 или новее, `php:8.4-cli` дал тот же результат на задаче 2070
- 2026-11-06: основной стенд переведен на PHP 7.4; `PHPSTAN_DOCKER_IMAGE` указывает на `copytrust-dev-php-apache:latest`, отдельный `copytrust-php74:local` больше не нужен
- 2026-11-07: автосборка ограничена Dockerfile основного локального стенда; исключены резервные источники и подмена пользовательского тега локальным образом.
- 2026-11-11: php-toolchain перенесён из `.cursor/mcp-servers` в `.tools/mcp-servers`; конфиги сред и перенос kit обновлены, копии в зеркалах `.codex` и `.agents` удалены.
