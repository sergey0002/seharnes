# Скрипт: `.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py`

<!-- meta
type: script
status: actual
updated: 2026-11-09
related: [../../SKILL.md]
tags: [harness, script, harness_mirror]
-->

## Суть
Скрипт строит и обслуживает графовое зеркало файлов харнеса (один JSON-узел на файл с детерминированным разделением на блоки, хешированием и обратимой конкатенацией байт в байт). Команда `visibility` строит матрицу инжекта правил по средам и проверяет обязательные `gate` и `attach: glob` контракты; `check` запускает ту же проверку, `build` записывает поле `injection` для канонических правил.

## Когда запускать
Скрипт вызывается при индексации файлов харнеса (`scan`, `build`, `rebuild`), проверке целостности зеркала (`check` в гейте `mirror-check` скрипта `harness_cli.py doctor`), инспекции связей навыка (`bundle`) и локальном просмотре графа через веб-интерфейс (`serve`).

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `--root` | | string | нет | . | корень проекта (по умолчанию ближайший .git или .cursor) |
| `--data` | | string | нет | .doc/skil_data/mirror | каталог данных графа относительно корня |
| `scan: --paths` | | string | нет | [] | список относительных путей для выборочного сканирования |
| `scan: --include-mirrors` | | flag | нет | выключен | включать зеркала сред (.codex, .kilo, .agents) |
| `scan: --include-dsh` | | flag | нет | выключен | включать каталог .dsh |
| `scan: --force` | | flag | нет | выключен | игнорировать кеш хешей при сканировании |
| `prompt: --node` | | string | да | | идентификатор целевого узла графа |
| `apply: --node` | | string | да | | идентификатор целевого узла графа |
| `apply: --json` | | string | нет | | путь к файлу семантического анализа (или stdin) |
| `apply: --model` | | string | нет | | название модели для фиксации авторства анализа |
| `get: --node` | | string | да | | идентификатор целевого узла графа |
| `get: --slim` | | flag | нет | выключен | выводить только метки и связи узла без текстовых блоков |
| `visibility: --summary` | | flag | нет | выключен | выводить статус и нарушения без полной матрицы rule × environment |
| `bundle: --skill` | | string | да | | имя навыка для построения бандла или ревью |
| `review: --node` | | string | нет | | идентификатор узла для ревью |
| `review: --skill` | | string | нет | | имя навыка для ревью |
| `review: --all` | | flag | нет | выключен | компактный сводный аудит всех навыков и правил |
| `audit: --node` | | string | нет | | идентификатор узла для аудита |
| `audit: --skill` | | string | нет | | имя навыка для аудита |
| `set: --node` | | string | да | | идентификатор целевого узла графа |
| `set: --block` | | string | нет | | идентификатор блока для точечной замены (omit с --file) |
| `set: --file` | | flag | нет | выключен | заменять весь файл целиком (только skills и rules) |
| `set: --content` | | string | нет | | путь к файлу с новым содержимым (или stdin) |
| `serve: --host` | | string | нет | 127.0.0.1 | адрес хоста для запуска веб-просмотрщика |
| `serve: --port` | | int | нет | 8090 | сетевой порт локального сервера |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | операция успешно выполнена или проверка инвариантов пройдена | продолжить работу |
| 1 | проверка инвариантов check/lint обнаружила несоответствия | исправить поврежденные узлы или пересканировать зеркало |
| 2 | неверные параметры командной строки или ошибка валидации аргументов | проверить синтаксис команды |

## Что читает и что пишет
Читает файлы канона правил `.cursor/rules`, навыки `.agents/skills`, зеркала сред. Пишет JSON-узлы и метаданные в `.doc/skil_data/mirror/nodes/`, итоговый `graph.json` и ассеты просмотрщика.

## Побочные эффекты
Создает и обновляет файлы графа в каталоге данных `.doc/skil_data/mirror/`. В режиме `set` изменяет исходные файлы правил или навыков. В режиме `serve` открывает локальный HTTP-сервер на указанном порту.

## Окружение и зависимости
Требуется Python 3.8+ со стандартной библиотекой (`argparse`, `hashlib`, `json`, `os`, `re`, `shutil`, `tempfile`, `pathlib`).

## Примеры
```bash
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py check
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . visibility
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py --root . visibility --summary
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py scan --include-mirrors
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py bundle --skill doc-script
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py build
```

## Ограничения
Детерминированная часть анализирует синтаксическую структуру, блоки и литеральные ссылки. Семантические описания и выводы заполняются агентом через команду `apply`.

## Связи
Используется гейтом `mirror-check` в `harness_cli.py doctor`. Связан с навыками `mirror`, `harness-core`, `improvement`.

## История изменений
- 2026-11-07: создан проверенный документ скрипта.
- 2026-11-07: добавлены подкомандные префиксы для аргументов (--paths, --include-mirrors, --include-dsh)
- 2026-11-09: добавлены visibility-матрица, проверки `gate`/`attach: glob`, поле `injection` в графе и компактный режим `--summary`