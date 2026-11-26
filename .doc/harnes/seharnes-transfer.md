# Перенос правок харнеса в seharnes

<!-- meta
type: rules
status: actual
version: 1.0
updated: 2026-11-25
related: [./index.md, ./state/14-project-migration.md, ./component-install.md, ../rebase_project.md, ./plan/06-harness-transfer-docs.md]
tags: [harness, transfer, seharnes, export, sync, migration]
-->

---

## Суть

`/home/newuser/projects/seharnes` это эталонный репозиторий харнеса без
продуктового кода CopyTrust. Правки харнеса рождаются в рабочем проекте
`/home/newuser/projects/copytrust/testdeploydocker` и переносятся в эталон тем же
движком `export_kit.py`, что и в любой другой проект.

Приоритет в этой операции один: источник `testdeploydocker` главнее. Целевая
папка сохраняет только то, что перечислено в `--keep` и в защищённых путях
движка. Документ описывает точную процедуру, исключения и проверки, чтобы
перенос повторялся без разбора каждый раз.

## 1. Стороны и что считается правкой

| Имя | Путь | Роль |
|---|---|---|
| Source | `/home/newuser/projects/copytrust/testdeploydocker` | рабочий проект, здесь правят харнес |
| Target | `/home/newuser/projects/seharnes` | эталон харнеса, git-репозиторий |
| Baseline | `.doc/.rebase-kit.json` в Target | хеши источника и цели после прошлого переноса |

Правкой харнеса считается изменение в `.agents/`, `.cursor/`, `.codex/`,
`.kilo/`, `.opencode/`, `.omp/`, `.serena/`, `.tools/`, `.doc/harnes/`,
`.doc/qa/`, `.doc/web/`, а также в корневых `AGENTS.md`, `kilo.json`,
`mcp.index.md`, `.codeprism.toml`, `.cbmignore`.

Продуктовый код CopyTrust, задачи `.doc/tasks`, архитектура `.doc/architecture`
и данные скилов `.doc/skil_data` в эталон не переносятся.

## 2. Что переносится, а что исключено

| Область | Решение | Причина |
|---|---|---|
| `.agents`, `.cursor`, `.codex`, `.kilo`, `.opencode`, `.omp`, `.serena` | переносить | это сам харнес |
| `.doc/harnes` | переносить | документация харнеса |
| `.doc/qa` | переносить | QA-контур входит в kit профиля `developer` |
| `.tools/codeception`, `.tools/mcp-servers`, `.tools/scripts` | переносить | инструменты харнеса |
| `.doc/harnes/astra_plan` | исключить флагом `--exclude` | 2352 файла, 32 МБ, 2325 из них evidence, ссылок из документов нет |
| `.doc/harnes/state/.validate-rules-last.json` | исключить флагом | рантайм-состояние, меняется каждым прогоном |
| `.doc/tasks`, `.doc/architecture`, `.doc/skil_data`, `.doc/temp` | не переносить | это данные проекта, а не харнеса |
| `.doc/web/state`, `.doc/web2` | не трогать | рантайм панели и локальная панель эталона |
| `.tools/docker-dev`, `.tools/php85-scan` | не трогать | продуктовые стенды, в kit не входят |
| `.agents/skills/login-as-user` | удалить в Target | скил исключён из kit, must-check считает его запрещённым |
| старый PS1-движок | удалить в Target один раз | движок удалён из источника |

## 3. Режимы и выбор режима

| Режим | Приоритет | Когда применять |
|---|---|---|
| `install` | Target | первый перенос в пустой проект; существующие файлы не перезаписываются |
| `update` | Source | обычный перенос правок в seharnes |
| `mirror` | Source плюс удаление | точная копия эталона; удаляет файлы kit, которых нет в источнике |

Для seharnes штатный режим `update`. `mirror` применять только после ревью
списка удалений, потому что он затрагивает локальные файлы эталона.

## 4. Быстрый цикл на одну правку

```bash
cd /home/newuser/projects/copytrust/testdeploydocker

# 1. предпросмотр: ничего не пишет
python3 .agents/skills/harness-router/children/new-project/scripts/harness_transfer.py export \
  --source . \
  --target /home/newuser/projects/seharnes \
  --profile developer --mode update \
  --skip-runtime-deps \
  --exclude .doc/harnes/astra_plan \
  --exclude .doc/harnes/state/.validate-rules-last.json \
  --keep .kilo/.gitignore \
  --dry-run

# 2. перенос
python3 .agents/skills/harness-router/children/new-project/scripts/harness_transfer.py export \
  --source . \
  --target /home/newuser/projects/seharnes \
  --profile developer --mode update \
  --skip-runtime-deps \
  --exclude .doc/harnes/astra_plan \
  --exclude .doc/harnes/state/.validate-rules-last.json \
  --keep .kilo/.gitignore \
  --yes
```

Код возврата `0` означает `status: passed`, код `2` означает, что must-check
нашёл пропуски или запрещённые файлы.

## 5. Пошаговая процедура

1. Проверить, что Source чист по продуктовым правкам, которые не относятся к
   харнесу. Перенос заберёт все файлы kit, а не только ожидаемые.
2. Поставить тег отката в Target:

```bash
git -C /home/newuser/projects/seharnes tag before-sync-$(date +%Y%m%d-%H%M)
```

3. Запустить предпросмотр из раздела 4 и прочитать счётчики: `added`,
   `overwritten`, `preserved`, `same`.
4. Если в `overwritten` есть документы, где Target новее источника, решить
   вручную. Список таких файлов и правило выбора даны в
   [плане переноса документации](./plan/06-harness-transfer-docs.md), раздел 6a.7.
   Сохранить их через `--keep` можно только целиком, частичное слияние делается
   после переноса.
5. Запустить перенос без `--dry-run`.
6. Удалить в Target то, что `update` не удаляет:
   `login-as-user` и файлы старого PS1-движка.
7. Пересобрать индекс зеркала в Target, иначе гейт `mirror-check` упадёт:

```bash
cd /home/newuser/projects/seharnes
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . rebuild
```

8. Прогнать проверки из раздела 6.
9. Показать пользователю `git status`, `git diff --stat` и список удалений.
   Коммит и push только по явной просьбе.

## 6. Проверки после переноса

| Проверка | Где | Команда | Ожидание |
|---|---|---|---|
| Доктор эталона | Target | `python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py --root . doctor` | `status: passed`, `failed_gates: []` |
| Доктор источника | Source | та же команда в Source | `passed` |
| Тесты движка | Source | `python3 -m unittest discover -s .agents/skills/harness-router/children/new-project/tests -p 'test_*.py'` | 117 тестов OK |
| Идемпотентность | Source | повторить перенос | `added 0`, `overwritten 0` |
| Зеркало | Target | `harness_mirror.py --root . rebuild` | `drift 0` |
| Receipt | Target | `python3 -c "import json;print(len(json.load(open('.doc/.rebase-kit.json'))['files']))"` | число равно размеру kit |

Проверка идемпотентности обязательна. Если второй прогон снова пишет файлы,
значит адаптации идут после сравнения и Baseline не сходится.

## 7. Особенности и подводные камни

| Симптом | Причина | Решение |
|---|---|---|
| `status: failed`, `forbidden: .agents/skills/login-as-user` | скил исключён из kit, но остался в Target | удалить каталог в Target и повторить прогон |
| `update` не удалил старый движок | `update` не удаляет файлы, которых нет в источнике | удалить 4 скрипта и 4 документа вручную |
| `mirror-check` падает после переноса | индекс зеркала не пересобран | `harness_mirror.py --root . rebuild` |
| `docs-scripts` требует строку аргумента | новый флаг не описан в документе скрипта | обновить `docs/scripts/*.md` в Source, затем повторить перенос |
| `.kilo/.gitignore` изменился, хотя передан `--keep` | файл пересобирает `sync-agent-views.sh` после копирования | `--keep` защищает только этап копирования; принять версию синка |
| `tests.md` отличается на одну строку | нормализатор пометил ссылку на удалённый `login-as-user` | это ожидаемо, не считать расхождением |
| документы вернулись заглушкой `# Stub` | Target содержит заглушку, источник реальный | приоритет Source заменяет заглушку автоматически |
| `astra_plan` снова появился | забыт `--exclude` | всегда передавать оба `--exclude` из раздела 4 |
| часть документов осталась версией Target | они перечислены в `--keep` или совпали по хешу | сверить `preserved` в отчёте |
| панель `web2` изменилась | `web2` вне kit, но `web` входит | проверить, что менялся только `web` |
| `.serena/project.yml` получил чужое имя | не передан `--project-name` | передать `--project-name seharnes` |
| секреты попали в Target | `.env`, `mcp.env`, `config.env` не должны копироваться | проверить `git status` в Target до коммита |

## 8. Откат и коммит

Откат делается средствами git Target, потому что движок пишет backup только
перезаписанных файлов.

```bash
git -C /home/newuser/projects/seharnes status
git -C /home/newuser/projects/seharnes checkout -- .
git -C /home/newuser/projects/seharnes clean -fd
```

Backup перезаписанных файлов лежит в `.doc/.rebase-backup/{stamp}/` внутри Target.
Отчёт и план переноса: `.doc/.rebase-report.md`, `.doc/.rebase-report.json`,
`.doc/.rebase-conflicts.json`, `.doc/.rebase-preserved.txt`.

Коммит и push не выполняются без явной просьбы. Subject коммита в эталоне не
привязан к номеру задачи CopyTrust, потому что эталон не входит в трекер.

## 9. Опорный прогон 2026-11-25

Первый полный перенос в seharnes режимом `update` с приоритетом Source.

| Показатель | Значение |
|---|---|
| Source | `testdeploydocker`, `5e8e7b7a3` |
| Target до переноса | `81adfaf` |
| Добавлено | 62 |
| Перезаписано | 132 |
| Без изменений | 1373 |
| Сохранено локально | 31 |
| Удалено вручную | 11 файлов: `login-as-user` (3) и старый движок (8) |
| Исключено | `astra_plan` 2352 файла, `.validate-rules-last.json` |
| Повторный прогон | `added 0`, `overwritten 0`, `same 1566` |
| `doctor` в Target | `passed`, 0 падений вместо 9 до переноса |
| `doctor` в Source | `passed` |
| Тесты `new-project` | 117 OK |
| Receipt | 1568 файлов, 348 КБ |

Заменены 10 документов-заглушек, среди них `plan/субагенты.md`,
`plan/deepseek.md`, `plan/01`-`05`, `idea/01-roadmap-hpta.md`,
`archive/mcp/sourcegraph-local.md`, `dsh/deepseek-harness-02-ustanovka.md`.
Всего 5471 строка реального текста.

## 10. Границы

Документ описывает перенос харнеса между двумя конкретными папками. Перенос
продуктового кода CopyTrust, базы данных и задач в эталон не входит. Общая
модель профилей и режимов описана в
[state/14-project-migration.md](./state/14-project-migration.md), классы
документов и правила приоритета в
[плане 06](./plan/06-harness-transfer-docs.md).

## Связи

- [state/14-project-migration.md](./state/14-project-migration.md) - карта переноса, профили и режимы
- [component-install.md](./component-install.md) - установка компонента в проект
- [../rebase_project.md](../rebase_project.md) - канон процедуры переноса
- [./plan/06-harness-transfer-docs.md](./plan/06-harness-transfer-docs.md) - классы документов и разбор различий
- [index.md](./index.md) - карта документации харнеса

## История изменений

- 2026-11-25: документ создан по опорному переносу в seharnes; зафиксированы
  приоритет Source, исключения `astra_plan` и рантайма, флаги `--exclude` и
  `--keep`, проверки, подводные камни и откат.

#harness #transfer #seharnes #export
