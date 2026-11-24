# Валидация, гейты и коды

Валидация отвечает на вопрос «данные и работа достаточно определены?», а
процедурная проверка — «внешняя проверка действительно выполнилась?». Эти вещи
не смешиваются.

## Три уровня

### Уровень 1: схема и факты записи

`Validator.record` проверяет контракт `TASK` (внутренний идентификатор версии — `TASK-6`):

- известны только разрешённые ключи;
- `id`, `title`, `kind`, `status` непусты;
- id имеет форму `T-NNN`, тип — строчные буквы/цифры/дефисы;
- статус входит в восемь значений;
- `due` — `ГГГГ-ММ-ДД`, `priority` — целое, `estimate_h` — число;
- массивы состоят из объектов с адресом и непустым текстом;
- refs, artifacts, comments и source соответствуют своим строгим схемам;
- пути артефактов не уходят из папки записи;
- для зеркала существует `source.raw`.

Проверка не устанавливает лимитов длины свободного текста.

### Уровень 2: объявление типа

`FieldValidator` берёт `extra` только из `type.json`. Проверяются:

- неизвестное дополнительное поле;
- обязательное поле;
- тип `string`, `int`, `number`, `bool`, `array`, `object`;
- `enum` и `pattern`, если они объявлены.

Гейты типа проверяются по фактам записи: evidence для тестов, handoff,
refs, reproduce, docs и verdict. Например, `feature` требует тестовое
свидетельство и документированный файл, а `research` требует handoff и refs.

### Уровень 3: процедурный CheckPlugin

Тип может объявить `checks` в `type.json`. Модуль загружается из папки типа и
возвращает только JSON с ключами `ok`, `findings`, `summary`. Проверка запускается
явным вызовом/фазой, а не при каждом чтении. Код результата обязан быть `0`, `1`
или `3`; неизвестные ключи и коды дают `CHECK_CONTRACT`.

### Documentation workspace

Для документационного домена есть отдельный контур:

```bash
tcheck docs check --root <root>
tcheck docs check --root <root> --strict
tcheck docs stale --root <root>
tcheck docs render --root <root> --key entity/order
```

`docs check` валидирует manifest, module/sidecar envelopes, claims, наличие
Markdown и source fingerprints; `--strict` трактует предупреждения как ошибки.
`stale` отдельно показывает расхождение source fingerprints, а `render` делает
детерминированную Markdown fence/syntax check. Эти команды проверяют один
workspace и не запускают recursive aggregate.

## `strict`

```bash
tcheck validate T-001 --strict --queue site
tcheck doctor --root . --all --strict
```

Без `--strict` часть недостатков остаётся предупреждением. В строгом режиме
`doctor` превращает предупреждения в ошибки. Это нужно перед сдачей, но не
заменяет смыслового решения человека.

## Гейты закрытия

`ttask close` и `ttask status --status closed` вызывают проверку типа. Тип может
требовать:

| Гейт | Что считается выполнением |
|---|---|
| `tests: required` | artifact вида `log`, `report` или `tests`, либо evidence/verification в отчёте |
| `handoff: required` | хотя бы одна реплика `kind: handoff` |
| `refs: true` | хотя бы один указатель |
| `reproduce: true` | `extra.reproduce` или фактический текст воспроизведения |
| `docs: true` | в `report.files_changed` есть `.md` или путь с `docs/` |
| `acceptance: verdict_required` | заполнено `extra.verdict` |
| `acceptance_min: N` | в строгой проверке достаточно критериев после выхода из draft |
| отчёт | для каждого `AC-N` есть `acceptance_status` со статусом `met`, `not_met` или `blocked` |

Если ошибка есть, запись не переводится в `closed`. Команда печатает отчёт и
готовое действие; исправлять нужно входные данные, а не вручную ставить статус.

## Частые коды и действие

| Код | Причина | Следующий вызов |
|---|---|---|
| `QUEUE_NOT_RESOLVED` | нельзя выбрать очередь | `tqueue list --queue <алиас>` или `tqueue init <алиас>` |
| `INDEX_ORPHAN` | индекс указывает на отсутствующую запись | `tqueue index-rebuild` |
| `RECORD_UNLISTED` | папка записи не попала в индекс | `tqueue index-rebuild` |
| `INDEX_MISMATCH` | строка индекса расходится с task.json | `tqueue index-rebuild` |
| `JSON_MALFORMED` | JSON не разбирается | `tcheck doctor --all --strict` |
| `TYPE_FIELD_UNKNOWN` | extra не объявлено типом | `tcheck types fields <тип>` |
| `TYPE_FIELD_MISSING` | обязательное поле не задано | `ttask set <id> --extra имя=значение --by <имя>` |
| `REF_NOTE_MISSING` | указатель без смысла | `ttask ref add <id> … --note … --by …` |
| `ARTIFACT_MISSING` | файл артефакта отсутствует | положить файл в папку, затем `ttask artifact add <id> --kind other --path <путь> --note <что> --by <имя>` |
| `LINK_BROKEN` | указатель на запись битый | `ttask ref remove <id> --path <адрес> --note <почему> --by <имя>` |
| `MIRROR_READONLY` | ручная правка зеркала | `ttask new «Формализация стадии» --type intake --parent <зеркало> --by <имя>` |
| `COMMENT_SOURCE_LOCKED` | комментарий внешнему зеркалу | `ttask new «Служебное уточнение» --type intake --parent <зеркало> --by <имя>`
| `DIGEST_STALE` | digest старее task.json | `ttask digest <id>` |
| `SOURCE_RAW_MISSING` | нет дословного внешнего входа | повторить импорт |
| `TYPE_IMMUTABLE` | попытка сменить тип | новая запись с `--parent` |
| `ID_IMMUTABLE` | попытка сменить id | новая дочерняя запись |
| `READ_MODE_UNKNOWN` | режим чтения неизвестен | `ttask show <id> --mode full` |
| `PACK_INCOMPLETE` | пакет субагенту неполон | `tcheck types show <тип>` |
| `CAPABILITY_UNBOUND` | capability не привязана проектом | `tcheck tools bind <cap> --command … --by …` |
| `FLOW_STATE_MISMATCH` | индекс не согласован с flow.json | `tcheck flows show <поток>` |
| `FLOW_OUTPUT_MISSING` | предыдущий шаг не оставил заявленный выход | `ttask flow next <id>` |
| `FLOW_CONDITION_UNMET` | условие перехода, например audit verdict, не выполнено | исправить prerequisite и повторить `ttask flow next <id>` |
| `FLOW_PREREQUISITE_OPEN` | prerequisite ещё не закрыт | `ttask flow state <id>` |
| `FLOW_JOIN_PENDING` | fan-in ждёт закрытия всех элементов шага | `ttask flow state <id>` |
| `FLOW_FANOUT_INVALID` | список fan-out не соответствует объявленному контракту | `ttask flow state <id>` |
| `ROLE_UNKNOWN` | роль не найдена | `tcheck roles list` |
| `BATCH_FAILED` | пакет не применился целиком | `ttask batch <файл> --dry-run` |
| `PROSE_HIDDEN_TEXT` | опасная невидимая вставка в Markdown | `tcheck doctor --all --strict` |
| `DOC_WORKSPACE_MISSING` | manifest документации не создан | `tcheck docs init --root <root>` |
| `DOC_MANIFEST_INVALID` | manifest не проходит WORKSPACE-1 | `tcheck docs check --root <root> --strict` |
| `DOC_KEY_UNKNOWN` | модуль с таким `doc_key` не найден | `tcheck docs catalog --root <root>` |
| `DOC_MODULE_INVALID` | module envelope не проходит DOC-1 | `tcheck docs check --root <root> --strict` |
| `DOC_CLAIM_NO_EVIDENCE` | claim требует evidence refs | добавить provenance/evidence и повторить check |
| `DOC_STALE` | source fingerprint изменился | `tcheck docs stale --root <root>` |
| `DOC_POLICY_DISABLED` | documentation path отключён policy | проверить `tcheck docs policy show` |
| `DOC_RENDER_FAILED` | Markdown не проходит render check | `tcheck docs render --key <family/name> --root <root>` |

Верхняя таблица оставлена как быстрый маршрут по наиболее частым отказам;
полный runtime-справочник ниже. Команда действия всегда является подсказкой:
она не выполняется автоматически, пока человек не проверит контекст.

## Полный runtime-справочник кодов

Ниже перечислены все коды из `tdcore.errors.HINTS` на момент v0.7. Это
нормативная таблица действий: если код добавляется в код, ему нужно добавить
готовые `hint` и `command`, иначе `tcheck selftest`/coverage должны отказать.

| Код | Что означает | Следующий вызов |
|---|---|---|
| `AC_TOO_FEW` | критериев приёмки меньше, чем требует тип: задача непроверяема | `ttask set <id> --acceptance <текст критерия>` |
| `ARTIFACT_MISSING` | артефакт объявлен, но файла в папке записи нет | `ttask artifact add <id> --kind <род> --path <путь> --note <что внутри>` |
| `ASK_USER` | нужно решение человека: команда ничего не создала и ничего не правила | `прочитай вывод и повтори вызов с явным решением` |
| `BATCH_FAILED` | пакет операций не выполнен целиком: транзакция откатилась | `ttask batch <файл> --dry-run` |
| `CAPABILITY_UNBOUND` | возможность среды объявлена типом, а привязки в проекте нет | `tcheck tools bind <возможность> --command <команда>` |
| `CHECK_CONTRACT` | проверка типа нарушает контракт: вход, выход или коды возврата | `tcheck types show <тип>` |
| `CHECK_LOAD_FAILED` | объявленную типом проверку не загрузить | `tcheck types show <тип>` |
| `COMMENT_SOURCE_LOCKED` | в ленту записи из внешней системы пишет только импорт | `ttask comment add <id> --kind proposal --by <кто> --body <текст>` |
| `DIGEST_STALE` | выгрузка устарела: запись правили после неё | `ttask digest <id>` |
| `EMPTY` | значение обязательно и не может быть пустым | `ttask set <id> --title <значение> --by <имя>` |
| `FLOW_CONDITION_UNMET` | условие перехода, например `plan-audit.extra.verdict == approved`, не выполнено | исправить prerequisite или пройти revision явно |
| `FLOW_OUTPUT_MISSING` | шаг закрыт и оставил не всё, что объявил следующему | `ttask flow next <id>` |
| `FLOW_FANOUT_INVALID` | закрытый источник не оставил корректный список fan-out | `ttask flow state <id>` |
| `FLOW_JOIN_PENDING` | fan-in ждёт закрытия всех элементов dynamic шага | `ttask flow state <id>` |
| `FLOW_PREREQUISITE_OPEN` | prerequisite шага ещё не закрыт | `ttask flow state <id>` |
| `FLOW_STATE_MISMATCH` | состояние потока в индексе расходится с определением | `ttask flow state <id>` |
| `FLOW_STEP_MISSING` | шаг потока ссылается на шаг, которого в определении нет | `tcheck flows show <поток>` |
| `ID_IMMUTABLE` | идентификатор записи не меняется после создания | `ttask new «Новая дочерняя работа» --type <тип> --parent <id> --by <имя>` |
| `INDEX_MISMATCH` | поле строки индекса расходится с файлом записи | `tqueue index-rebuild` |
| `INDEX_ORPHAN` | строка индекса указывает на запись, которой нет в папке data | `tqueue index-rebuild` |
| `JSON_MALFORMED` | файл не разбирается как JSON: данные и конфиги правит только CLI | `tcheck doctor --all --strict` |
| `KEY_UNKNOWN` | ключ не из схемы: опечатка или лишнее поле | `tcheck schema TASK` |
| `LINK_BROKEN` | указатель на запись ведёт в никуда | `ttask ref remove <id> --path <адрес> --by <кто>` |
| `MIRROR_READONLY` | зеркало внешней системы правит только импорт | `ttask new «Формализация стадии» --type intake --parent <зеркало> --by <имя>` |
| `NOT_IMPLEMENTED` | команда объявлена планом, но в этой фазе ещё не реализована | `tcheck selftest` |
| `NO_HANDOFF` | тип требует реплику пересменки перед закрытием | `ttask comment add <id> --kind handoff --by <кто> --body <что передать>` |
| `NO_REFS` | тип требует указатели на файлы, символы или документацию | `ttask ref add <id> --kind file --path <путь> --note <зачем>` |
| `NO_TESTS` | гейт типа требует свидетельство прогона теста | `ttask evidence <id> --kind tests --path <путь> --note <что> --by <имя>` |
| `PACK_INCOMPLETE` | пакет субагенту не собран: не хватает объявленного предмета | `ttask pack <id> --mode handoff` |
| `PATH_OUTSIDE` | путь ведёт за пределы папки записи | `ttask artifact add <id> --kind other --path <путь внутри папки>` |
| `PROFILE_LOAD_FAILED` | профиль типа, объявленный в конфиге, не загрузился | `tcheck types show <тип>` |
| `PROSE_HIDDEN_TEXT` | в прозе найдена невидимая вставка: скрытый комментарий или символ нулевой ширины | `tcheck doctor --all --strict` |
| `QUEUE_NOT_RESOLVED` | очередей несколько, а какая нужна, не названо | `tqueue list --queue <алиас> --root <root>` |
| `QUEUE_UNKNOWN` | очередь не найдена в реестре | `tqueue find --root <root>` |
| `READ_MODE_UNKNOWN` | неизвестный режим чтения | `ttask show <id> --mode full` |
| `RECORD_NOT_FOUND` | записи с таким идентификатором в очереди нет | `tqueue list --queue <алиас>` |
| `RECORD_UNLISTED` | запись лежит в папке data, но её нет в индексе | `tqueue index-rebuild` |
| `REF_NOTE_MISSING` | указатель без пояснения: непонятно, что в нём смотреть | `ttask ref add <id> --kind file --path <путь> --note <зачем>` |
| `RELEASE_FORMAT` | имя релиза — null либо непустая строка | `ttask set <id> --release <имя>` |
| `ROLE_UNKNOWN` | роль не объявлена в файле ролей | `tcheck roles list` |
| `SOURCE_KEYS_EXTRA` | в источнике лишний ключ: схема `SOURCE` строга | `tcheck schema SOURCE` |
| `SOURCE_RAW_MISSING` | у записи с источником нет содержимого дословно | `tcheck import jira --file <путь> --by <имя>` |
| `STATUS_UNKNOWN` | статус не из восьми объявленных | `tcheck schema STATUSES` |
| `TYPE_FIELD_INVALID` | значение поля не проходит правило типа: тип значения, перечень или формат | `tcheck types fields <тип>` |
| `TYPE_FIELD_MISSING` | обязательное поле типа не заполнено | `ttask set <id> --extra <имя>=<значение>` |
| `TYPE_FIELD_UNKNOWN` | тип не объявляет такого поля в extra | `tcheck types fields <тип>` |
| `TYPE_IMMUTABLE` | тип записи не меняется после создания | `ttask new --type <нужный тип> --parent <id>` |
| `TYPE_UNKNOWN` | тип не объявлен: ни в поставке, ни в папке типов проекта | `tcheck types list` |

## Проверка поставки

```bash
python3 -m unittest discover todone/tests
python3 -m py_compile todone/scripts/tdcore/*.py \
  todone/scripts/tqueue.py todone/scripts/ttask.py todone/scripts/tcheck.py
python3 todone/scripts/tcheck.py selftest
python3 todone/scripts/tcheck.py doctor \
  --root todone/examples/v6-project --all --strict
```

Тесты проверяют object core, CLI, матрицу типов/потоков/схем/кодов и сценарии
зеркала, digest, links, reports и batch.
