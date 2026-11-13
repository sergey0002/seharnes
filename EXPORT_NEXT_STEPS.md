# После export-rebase-project

Целевой проект: `/home/newuser/projects/seharnes`
Serena project_name: `seharnes`
Профиль: `Full`

Экспорт переносит среду агента, а не приложение. Ниже полный порядок запуска
на новом проекте: секреты, пути, индексы, панель, тесты и проверка.

## 0. Что уже сделано

- Скопированы `.cursor/`, `.codex/`, `.qoder/`, `.qwen/`, `.serena/project.yml`, `.agents/`, DSH kit, стандарты `.doc/` и QA-контур.
- Из `.doc/skil_data` перенесены только `*.example.*`; рабочие данные создаются на Target.
- Документация харнеса из `.doc/architecture` перенесена вместе с JSON-каноном, где он есть. Ссылки на исключённые задачи и контент приложения помечены; список: `.doc/.rebase-doc-links.json`.
- Абсолютные пути образца заменены на `/home/newuser/projects/seharnes` в конфигах и лаунчерах.
- `.serena/project.yml` получил `project_name: "seharnes"`.
- Записан `.git/info/exclude`, `mcp.env` созданы из примеров без секретов.
- Из реестра компонентов убраны скилы, которых нет в этом проекте, и runtime-пути.
- Файлы Target, которых нет в образце, не удаляются. Отчёт: `.doc/.rebase-report.md` и `.doc/.rebase-report.json`, список: `.doc/.rebase-preserved.txt`.
- Отчёт показывает, сколько в проекте документации, задач и кастомных скилов, какие файлы kit перезаписаны.
- Точное зеркало kit с удалением лишнего включается отдельным флагом `-MirrorKit`.
- Повторный перенос обновлённого kit выполняется той же командой из репозитория-образца; файлы проекта сохраняются, отчёт перезаписывается.
- Не копировались: задачи, контент архитектуры Copytrust, `.codegraph/`, venv (`.cursor/tools/codeprism-ai/venv`), `.doc/qa/tmp-runs`, `sourcegraph-local`.
- `.tools/` переносится безопасным набором: `.tools/scripts`, `docker-dev/compose.yaml`, `docker-dev/php-apache`, `php85-scan`, `codeception/codeception.yml`, `codeception/composer.json`, `codeception/composer.lock`, `codeception/scripts`, `codeception/tests/_envs`; без `.env`, `dump.sql`, `vendor`, `_output`, `__pycache__`.

## 0.1. MCP: что проверить до работы

| Сервер | Что должно быть | Если не так |
|---|---|---|
| `codebase-memory-mcp` | проект Target в `list_projects`, граф готов | `index_repository(repo_path="/home/newuser/projects/seharnes", mode="fast")` |
| `codegraph` | `.codegraph/` построен, `pendingChanges` пуст | `codegraph init --yes /home/newuser/projects/seharnes` |
| `codeprism` | отдельный сервер проекта, ответ `get_graph_stats` подтверждает корень и готовый индекс | раздел 4.3 |
| `serena` | порт `9123`, project `seharnes` | раздел 4.5 |
| `jdocmunch` | repo `local/seharnes`, индекс собран | раздел 4.4 |
| `mysql` | выключен, если проект не на MySQL | раздел 2 |

Вопросы, которые агент обязан задать до правок и запусков:

1. Имя PHP-контейнера и путь к PHP-обвязкам.
2. Какая БД и порт, если включать mysql.
3. Есть ли доступ к Jira и какую учётную запись брать.
4. Нужен ли Sourcegraph и какой репозиторий.
5. Какой стенд и URL для тестов, есть ли браузер и chromedriver.
6. Какой провайдер Qwen задан в `~/.qwen/settings.json`.
7. Какой порт Serena закреплён за проектом: `9123`.

## 1. Первые 10 минут

1. Открыть этот каталог как корень workspace: `/home/newuser/projects/seharnes`. Не открывать родительскую папку.
2. Reload Window и проверить, что Settings -> MCP видит серверы.
3. Выполнить синхронизацию представлений:

   ```bash
   bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
   ```

   Синк пересобирает `.codex`, `.kilo`, `.agents`, `.qoder` и `.qwen` из канона.
   Скопированные `.qoder` и `.qwen` до синка могут содержать пути и настройки образца.

4. Qoder: `.qoder/settings.json` запускает stdio MCP через `.cursor/mcp.env`;
   для Qoder IDE пользовательские коннекторы хранятся в `~/.qoder/settings.json`.
5. Qwen Code: `.qwen/rules` и `.qwen/settings.json` генерируются из канона,
   `.agents/skills` читается нативно, `AGENTS.md` тоже. Путь и провайдер задаются
   в `~/.qwen/settings.json` внутри `qwen`; секреты в проект не копируются.
6. Заполнить секреты из раздела 2.
7. Прогнать smoke MCP:

   ```bash
   node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs
   ```

   Ожидаемо: все включённые серверы OK. Допустимые отклонения до настройки:
   `sourcegraph`, `xdebug`, `bitbucket-task` и `deepwiki` SKIP (выключены в каноне),
   `jira-task` FAIL до подъёма Docker-стенда, `mysql` SKIP если relay уже занят,
   `codeprism` SKIP до настройки отдельной службы,
   `codebase-memory-mcp` DEGRADED до `index_repository` (раздел 4.1).

## 1a. Мастер настройки проекта

Скрипт запускается **в корне Target**, не в репозитории-образце. Экспорт уже скопировал его в `.agents/skills/harness-router/children/project-setup/scripts/onboard-project.py`.

Сначала проверка без изменений:

```bash
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --check
```

Первичная настройка, с индексами:

```bash
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --yes \
  --php-container <container> \
  --mysql disable --mysql-database <db> --mysql-port <port> \
  --serena-port 9123 --web-port <free-port>
```

Повторный запуск после очередного экспорта, когда индексы уже построены:

```bash
python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --yes --skip-indexes \
  --php-container <container> \
  --mysql disable --mysql-database <db> --mysql-port <port> \
  --serena-port 9123
```

После повторного экспорта вернуть проектный `AGENTS.md`, если он был заменён версией образца.

Флаги: `--mysql keep|disable|set`, `--mysql-database`, `--mysql-port`,
`--reindex-project-docs` (медленный индекс `.dsh`, 15-20 мин),
`--add-harness-to-git` (по умолчанию харнес в git не добавляется),
`--include-harness`, `--include-docs`, `--exclude-docs`, `--add-docs-to-git`,
`--skip-indexes`. Отчёт: `.doc/onboard-report.md` и `.doc/onboard-report.json`.
Скрипт не коммитит и не удаляет файлы проекта.

## 2. Секреты

| Файл | Ключи | Откуда взять |
|---|---|---|
| `.cursor/mcp.env` | `MYSQL_*`, `DOCKER_PHP_CONTAINER`, `NODE_BIN`, `PHP_BIN` | `.env` своего `.tools/docker-dev` |
| `.codex/mcp.env` | те же | тот же файл |
| `.kilo/mcp.env` | те же | тот же файл; создан из примера, не из образца |
| `.doc/skil_data/jira/config.env` | `JIRA_*` | доступ к Jira под своей учётной записью |


Проверка, что секретов образца нет:

```bash
grep -RIn "sgp_\|JIRA_API_TOKEN=." .cursor/mcp.env .codex/mcp.env .kilo/mcp.env .doc/skil_data/jira/config.env
```

Ожидаемо: только пустые значения и комментарии.

## 3. Имена продукта

Экспорт заменяет абсолютные пути образца и имя его каталога во всех файлах kit
(`.cursor`, `.codex`, `.kilo`, `.agents`, `.qoder`, `.qwen`, `AGENTS.md`, `mcp.index.md`). Остальные
продуктовые строки нужно заменить вручную:

```bash
grep -rIn "testdeploydocker\|copytrust-dev-php-apache-1\|repo:\^\|CT-" \
  .cursor .codex .kilo .agents .qoder .qwen .dsh AGENTS.md mcp.index.md
```

Заменить:

- имя Docker-контейнера PHP;
- фильтр `repo:` под свой `repos.conf`;
- префикс задач `CT-`;
- имя БД и порт стенда в `.cursor/mcp.env` и `.codex/mcp.env`;
- URL стенда и S3 в `.doc/architecture/index.md` после заполнения архитектуры.

После замены повторить `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh`.

## 4. Индексы и графы

Порядок важен: сначала индексы, потом smoke MCP.

### 4.1. Codebase Memory (CBM)

```
index_repository(repo_path="/home/newuser/projects/seharnes", mode="fast")
index_status(project="...")
```

Имя проекта взять из `list_projects`. Индекс строится на Target, из образца он не переносится.

### 4.2. CodeGraph

```bash
codegraph init --yes /home/newuser/projects/seharnes
codegraph status --json
```

`.codegraph/` не копируется. Ожидаемо: `fileCount`, `nodeCount` и `edgeCount` больше нуля, `pendingChanges` пуст.

### 4.3. CodePrism

CodePrism после переноса отключен. Вместо адреса образца записана заглушка
`http://127.0.0.1:0/mcp`: включайте сервер только после проверки, что он
обслуживает Target. Адрес образца нельзя включать в Target: он
может обслуживать чужой проект. Один процесс обслуживает один проект; несколько
редакторов подключаются к нему. Ниже порядок для Linux или WSL с работающим
`systemctl --user`. Нативная служба Windows этим скриптом не создаётся.

1. Войдите в корень Target и выберите отдельный свободный порт. Например, 9202
   подходит только если порт свободен и не закреплён за другой службой. Проверьте
   свои настройки DSH, глобальные клиентские конфигурации и запущенные процессы.
   Старые stdio-процессы именно Target могут обращаться к той же базе; согласуйте
   и остановите их до запуска новой службы. Другие проекты не останавливайте.

```bash
PROJECT="$(pwd -P)"
PORT=9202
systemctl --user list-units --all 'mcp-codeprism*'
ss -ltnp
ps -eo pid,ppid,args | grep '[c]odeprism_serve.py'
```

2. Проверьте `.codeprism.toml`: файл скопирован из образца, если в Target его
   не было. Языки и исключения должны подходить Target. Не копируйте чужую базу
   или виртуальное окружение. Если venv уже существует, проверьте его и не
   пересоздавайте без решения владельца. Для отсутствующего venv:

```bash
mkdir -p "$PROJECT/.cursor/tools/codeprism-ai"
uv venv "$PROJECT/.cursor/tools/codeprism-ai/venv"
uv pip install --python "$PROJECT/.cursor/tools/codeprism-ai/venv/bin/python" 'codeprism-ai==0.1.11'
```

3. Создайте unit в каталоге пользовательского systemd. Скрипт проверяет свободный
   порт и имеющиеся unit в указанном каталоге, не перезаписывает другой unit и
   печатает точное имя службы. Проверьте выведенный путь и содержимое unit до
   запуска: `WorkingDirectory`, Python, сервер, корень и порт должны относиться
   к Target. При занятом порте выберите другой и повторите регистрацию.

```bash
mkdir -p "$HOME/.config/systemd/user"
python3 "$PROJECT/.cursor/mcp-stack/add-codeprism.py" "$PROJECT" "$PORT" \
  --output-dir "$HOME/.config/systemd/user"
```

4. После проверки выполните выведенные скриптом команды `systemctl --user
   daemon-reload` и `systemctl --user enable --now <имя-unit>`. Проверьте
   состояние и журнал этого unit. Сервер начинает фоновую индексацию при запуске;
   `CODEPRISM_NO_AUTO_INDEX=1` отключает также наблюдатель файлов.

```bash
systemctl --user status '<имя-unit>' --no-pager
journalctl --user -u '<имя-unit>' -n 100 --no-pager
```

5. До включения клиентов подключитесь отдельным MCP-клиентом к
   `http://127.0.0.1:<PORT>/mcp` и вызовите `get_graph_stats(path=".")`.
   Дождитесь `index_status = ready`; `project_path` после `realpath` должен
   точно совпасть с `PROJECT`. Открытый порт и список инструментов не доказывают
   принадлежность графа. При ошибке или чужом пути не включайте CodePrism.

```bash
"$PROJECT/.cursor/tools/codeprism-ai/venv/bin/python" - "$PROJECT" "$PORT" <<'PY'
import asyncio
from pathlib import Path
import sys
from fastmcp import Client

async def main():
    async with Client(f'http://127.0.0.1:{int(sys.argv[2])}/mcp') as client:
        result = await client.call_tool('get_graph_stats', {'path': '.'})
        data = result.structured_content or result.data
        if result.is_error or not isinstance(data, dict):
            raise RuntimeError('CodePrism вернул ошибку')
        if Path(data['project_path']).resolve() != Path(sys.argv[1]).resolve():
            raise RuntimeError('CodePrism обслуживает другой проект')
        if data.get('index_status') != 'ready':
            raise RuntimeError('индекс не готов; повторите проверку позже')
        print('CodePrism: проект и готовность индекса подтверждены')

asyncio.run(asyncio.wait_for(main(), timeout=30))
PY
```

6. Только после проверки измените запись `codeprism` в каноне `.cursor/mcp.json`:
   укажите `type: "http"`, URL `http://127.0.0.1:<PORT>/mcp` и снимите
   `disabled`. Сохраните остальные параметры. Затем синхронизируйте используемые
   клиентские представления из канона и проверьте через каждый клиент тот же
   `project_path`. Stdio-мост Codex проверяет корень и читает URL из канона;
   `CODEPRISM_TARGET` сам по себе не выбирает граф сервера.

   Перед общим `sync-agent-views.sh` проверьте его побочные эффекты: скрипт
   обновляет представления Codex и может изменить глобальную конфигурацию Gemini.
   Нестандартные DSH и глобальные конфигурации проверьте отдельно. Полная
   синхронизация и доступ Windows-клиента к WSL не подтверждаются одним наличием
   URL. После включения комплексная проверка: `bash .cursor/mcp-stack/verify.sh "$PROJECT"`.

Сервер доступен на loopback без аутентификации и предназначен для доверенных
локальных процессов. При отключении сначала отключите клиентов, затем выполните
`systemctl --user disable --now <имя-unit>` для службы Target. База при остановке
не удаляется. Инструкция не исправляет ограничения самого переноса kit: некоторые
существующие настройки Codex или DSH останавливают перенос до записи.

### 4.4. jDocMunch

```bash
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index
bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --repo
```

Первый запуск загружает модель 25-60 с. Индекс лежит в `~/.doc-index/local/<name>.json`.

### 4.5. Serena

Serena обслуживает один проект на юнит:

```bash
bash .cursor/mcp-stack/add-serena.sh "/home/newuser/projects/seharnes" 9123
bash .cursor/mcp-stack/verify.sh "/home/newuser/projects/seharnes"
```

Порт `9123` уже записан в клиентские конфиги. После регистрации проверить,
что ни один клиент не смотрит на порт образца, и сделать Reload Window.

## 5. Codex

1. Проверить, что `.codex/config.toml` содержит пути `/home/newuser/projects/seharnes`, а не каталог образца.
2. Добавить trust на новый путь и обновить `.codex/global-trust.snippet.toml`.
3. Перезапустить Codex и проверить MCP.

## 6. Панель документации

```bash
cd .doc/web
./install.sh --check
./install.sh --project
./verify.sh
./start.sh
```

Панель слушает порт 8077, другой порт задаётся `WEB_PANEL_PORT`. `install.sh --project` создаёт `state/`, `ADAPTERS.local.md` и `.env` с путями Target. Windows: `install.ps1 -Check`, затем `install.ps1 -Project`.

## 7. QA, браузер и тесты

- `.tools/codeception/vendor` скопирован, если экспорт шёл без `-SkipRuntimeDeps`.
- Свой `dump.sql` и БД стенда нужны обязательно: дамп Copytrust не переносится.
- Chrome и chromedriver: `.doc/qa/browser-setup.md`.
- Приложение берётся из git целевого проекта. В `.tools/` переносятся только конфиги и скрипты; `.env`, дамп MySQL, `vendor` и `_output` создаются на месте.
- Первый прогон: `bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh`, затем `codecept run`.

## 8. Git

- `.git/info/exclude` уже записан. `.gitignore` проекта не копируется и не перезаписывается.
- Харнес (`.cursor`, `.codex`, `.kilo`, `.agents`, `.qoder`, `.qwen`, `.dsh`, `.serena`) исключён по умолчанию и в git не добавляется.
- Документация `.doc`: по умолчанию экспорт исключает её; для нового проекта с отслеживаемой документацией используйте экспорт `-IncludeDocs` или `onboard-project.py --include-docs`.
- Только документация без харнеса: `--include-docs` и не передавать `--include-harness`.
- Добавить харнес: `onboard-project.py --add-harness-to-git` (стейджинг без коммита).
- Добавить документацию: `onboard-project.py --include-docs --add-docs-to-git` (архитектура, задачи, manifest, archviz).
- Скрыть документацию: `--exclude-docs`.
- Коммит не создавать до `git status` и проверки, что в индекс не попали секреты и лишние runtime-файлы.

## 9. Хост-инструменты

| Инструмент | Зачем | Проверка |
|---|---|---|
| Node 20+, npm, npx | MCP на Node | `node -v`, `npx -v` |
| uv, uvx | serena, semgrep, git, codeprism | `uv --version` |
| Docker Desktop | стенд, MySQL, Jira | `docker ps` |
| codebase-memory-mcp | CBM | `codebase-memory-mcp --version` |
| codegraph | граф кода | `codegraph status` |
| Chrome и chromedriver | Codeception, Playwright | `.doc/qa/browser-setup.md` |
| Python 3.12 | скрипты `.doc`, content-extractor | `python3 --version` |

## 10. Финальный чеклист

```bash
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py \
  --rules-dir .cursor/rules --skills-dir .agents/skills
node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs
```

Ожидаемо:

- sync заканчивается строкой `All Agent Views ... Successfully Synced`;
- `test_sync_views.py` печатает `21/21 tests passed`;
- `validate_registry.py` возвращает `status: passed`;
- `validate_rules.py` не содержит `severity: error`, warnings допустимы;
- MCP smoke: 14 OK, разрешённые SKIP, `jira-task` зелёный только после стенда.

## 11. Частые ошибки

| Симптом | Причина | Решение |
|---|---|---|
| `jira-task` FAIL или Loading | нет Docker-контейнера или неверное имя | поднять стенд, поправить имя контейнера в `.cursor/mcp.json` |
| `serena` Loading | первый запуск `uvx` | подождать, затем Reload Window |
| `mysql` не подключается | занят `127.0.0.1:3306` или неверный `MYSQL_PORT` | освободить порт, сверить `.env` docker-dev |
| `phpstan` или `php-deps` Error на Windows | `bash` из WSL ломает путь `C:\...` | открыть через WSL Remote или перейти на `node-mcp.cmd` |
| `codeprism` не стартует | venv не создан, он не копируется | команды из раздела 4.3 |
| `codegraph` пустой | индекс не построен | `codegraph init --yes /home/newuser/projects/seharnes` |
| `jdocmunch` не находит документы | индекс не собран | `bash .agents/skills/jdocmunch/scripts/jdocmunch-mcp.sh --index` |
| `validate_rules.py` ругается на `login-as-user` | скил Copytrust-only удалён | warning допустим, error лечится обновлением ссылки в скиле |
| панель не открывается | нет `state/`, `.env` или порт занят | `install.sh --project`, затем `verify.sh` |
| пути указывают на старый проект | правка сделана после экспорта | повторить `sync-agent-views.sh` и проверить `grep -R` по старым путям |

## 12. Что не скопировано намеренно

| Путь | Причина |
|---|---|
| `.doc/tasks/{N}/`, `.doc/tasks/index.md` | задачи другого продукта |
| `.doc/architecture/*` кроме `index.md` | архитектура другого продукта |
| `.codegraph/` | локальный индекс, строится на Target |
| `.cursor/tools/codeprism-ai/venv` | Python venv с абсолютными путями |
| `.doc/qa/tmp-runs` | артефакты прогонов образца |
| `.doc/skil_data/task-doc/runs`, `work`, `state` | прогоны и состояние образца |
| живые `mcp.env`, `config.env`, SG-токен, `mcp.token` | секреты |
| `.doc/web/state`, `ADAPTERS.local.md`, `actions.local.json` | состояние панели |
| корневой `node_modules/` приложения | не нужен MCP |

## 13. Канон

- `.doc/rebase_project.md` - полная процедура, Day0, День 1, ошибки П-1 - П-20.
- `.doc/harnes/state/14-project-migration.md` - краткая карта переноса.
- `.doc/harnes/mcp/{server}.md` - настройка каждого MCP.
- `.doc/harnes/doc_rules.md` - правила записи документации.
- `.agents/skills/harness-router/children/new-project/SKILL.md` - экспорт kit, этап 0 и подтверждение.
- `.agents/skills/harness-router/children/project-setup/SKILL.md` - настройка MCP, портов, индексов и git.