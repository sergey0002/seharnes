# Установка локального скила

## Классификация источников

| Категория | Что значит | Действие |
|---|---|---|
| `canon_local` | скил уже в `.agents/skills`, но его нет в манифесте пакета | проверить, добавить документацию и реестр |
| `view_local` | скил есть только в зеркале среды | скопировать в канон, затем документировать |
| `conflict` | один скил есть в нескольких средах с разными файлами | выбрать источник через `--from` |
| `package_modified` | скил пакета изменен | не устанавливать автоматически, выяснить причину |
| `mirror_drift` | зеркало отличается от канона | запустить синхронизацию, не устанавливать |
| `name_collision` | имя занято другим скилом канона | переименовать локальный скил |
| `missing` | скил есть в манифесте, но отсутствует на диске | разобраться с удалением или восстановлением |

## Манифест пакета

Файл `.doc/skil_data/harness-core/kit-manifest.json` содержит относительные пути
скилов и хеши файлов. Его пишет экспорт проекта или команда:

```bash
python3 .agents/skills/harness-router/children/add-skill/scripts/scan_local_skills.py \
  --root . --write-baseline
```

Без манифеста сканер видит только скилы, которых нет в каноне. Скилы, добавленные
в канон после миграции, в этом режиме не отличаются от пакета.

## Проверки перед установкой

1. Имя папки соответствует шаблону `^[a-z0-9]+(?:-[a-z0-9]+)*$`.
2. В корне есть один `SKILL.md`.
3. `name` во frontmatter совпадает с именем папки.
4. Нет симлинков.
5. Каталоги верхнего уровня только `scripts`, `references`, `assets`, `tests`, `children`.
6. Нет секретов и приватных ключей.
7. Нет абсолютных путей. Флаг `--allow-absolute-paths` оставляет предупреждение.
8. `skill.json` валиден, если уже существует.

## Что создает скрипт

- `README.md`, если его нет;
- `skill.json`, если его нет, с фактическим составом каталогов;
- строку в `.doc/harnes/state/02-skills.md`;
- строку в `.doc/harnes/index.md`;
- запись в `component_registry.json`;
- запись `children/{name}` в родительском `skill.json`, если скил дочерний;
- пересобранный роутер через `rebuild-routers.py`.

## Конфликты

Если один и тот же скил есть в нескольких средах с разными хешами, сканер
показывает `conflict`. Установка требует явный источник:

```bash
python3 .agents/skills/harness-router/children/add-skill/scripts/add_skill.py \
  --root . --name my-skill --from codex --yes
```

Файлы из разных сред не объединяются. Объединение делает человек после сравнения.

## Документация после установки

Агент обязан:

1. Прочитать `SKILL.md` и `README.md` установленного скила.
2. Заменить описание, состав и ограничения на проверенные.
3. Проверить связи и родительский роутер.
4. Создать документы скриптов в `{skill}/docs/scripts/`.
5. Повторить валидаторы.

## Проверки после установки

```bash
python3 .agents/skills/harness-router/children/improvement/scripts/validate_skills.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_docs.py
python3 .agents/skills/harness-router/children/harness-core/scripts/rebuild-routers.py --root . --check
bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
```

## Откат

Перед перезаписью существующего канона скрипт кладет копию в
`.doc/skil_data/harness-core/install-backup/{timestamp}/{name}`. Для отката
вернуть каталог на место и отменить записи документации из отчета `actions`.
