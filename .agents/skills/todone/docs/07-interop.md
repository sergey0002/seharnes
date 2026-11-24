# Внешний вход и локальный импорт

Внешняя система не становится вторым источником правды. `todone` принимает
локальный snapshot-файл, сохраняет его содержимое целиком и создаёт зеркало. В
текущей поставке есть три именованных профиля импортера: `jira`, `openspec`,
`speckit`. Для Jira дополнительно создаются валидированные
`JIRA-MIRROR-1` projection и completeness artifacts. Сетевого Jira клиента,
полноценного OpenSpec/Spec Kit bundle adapter-а и legacy migration нет.

## Контракт зеркала

Запись импорта имеет:

```json
{
  "kind": "mirror",
  "status": "mirror",
  "source": {
    "system": "jira",
    "id": "PROJ-7",
    "url": null,
    "imported_at": "…",
    "by": "importer",
    "raw": "весь исходный текст без нормализации",
    "revision": 1
  }
}
```

`source.raw` не извлекается из метаданных, не форматируется и не обрезается.
Метаданные (`title`, id, URL, комментарии) лишь помогают найти запись и сделать
повторный импорт идемпотентным.

## Создать зеркало напрямую

```bash
ttask new «PROJ-7» --from-text «сырой текст» \
  --source-system jira --source-id PROJ-7 --by importer --queue site

ttask new «PROJ-7» --from-file /tmp/jira.json \
  --source-system jira --source-id PROJ-7 --by importer --queue site
```

`--source-system` принимает `jira`, `openspec`, `speckit`, `chat`, `file`.
При `--from-file` без явной системы используется `file`; при `--from-text` —
`chat`. Для пустого текста будет `SOURCE_RAW_MISSING`. После создания команда
печатает предложение создать дочернюю запись `intake`, но сама её не создаёт.

## Импорт из локального JSON/текста

```bash
tcheck import jira --file jira.json --id PROJ-7 --title «Опциональный title» \
  --queue site --by importer
tcheck import openspec --file change.json --queue site --by importer
tcheck import speckit --file spec.json --queue site --by importer
```

Импортер читает файл UTF-8 с сохранением переводов строк. Для JSON он пытается
найти id в `id`, `key`, `issue_id`, заголовок в `title`, `summary`, `name` или
вложенных `fields`; URL — в `url`, `self`, `html_url`; комментарии — в `comments`
или в Jira-подобном `fields.comment.comments`. Не JSON также допустим: raw
сохраняется, а id по умолчанию становится именем файла.

### Повторный импорт

По паре `source.system + source.id` находится существующее зеркало. При повторе:

1. raw заменяется новым дословным входом;
2. `revision` увеличивается;
3. мета источника обновляется;
4. уже импортированные комментарии не дублируются по fingerprint
   (`external_id`, время, автор, текст);
5. для новых комментариев печатаются дочерние `intake`-команды;
6. если новых комментариев нет, команда сообщает, что дочерний черновик не нужен.

Это единственная операция, которая редактирует зеркало. Если надо ответить на
внешний текст, создаётся дочерняя запись; `ttask set`, ручной `comment`, `ref` и
`artifact` получают readonly-отказ.

## Формализация внешнего входа

```bash
ttask new «Формализовать PROJ-7» --type intake --parent T-001 \
  --queue site --by analyst
ttask ref add T-002 --kind queue --path T-001 \
  --note «сырой вход, из которого сделана формализация» --by analyst
```

Формализация хранит собственный вывод и ссылки. Содержимое зеркала не копируется
в `problem`, `context` или `notes`; так источник остаётся один, а адрес связи
виден явно.

## Границы совместимости

- Импорт OpenSpec и Spec Kit — это локальный вход по одному контракту, а не
  полные внешние workflow и не экспорт обратно.
- Импорт не запускает внешний workflow и не создаёт дочерние записи молча:
  он печатает следующий локальный вызов, а решение остаётся у человека.
- Ошибки импорта не создают частично заполненное зеркало: сначала читается и
  проверяется вход, затем создаётся/обновляется запись через атомарное хранилище.

## Jira: фактическая граница текущего runtime

Этот раздел описывает реализованный локальный profile `JIRA-MIRROR-1`, а не
сетевой Jira API client.

### Что сохраняется без потери

При `tcheck import jira --file jira-snapshot.json ...`:

- весь переданный UTF-8 текст сохраняется дословно в `source.raw`;
- Jira `id`, `key`, URL, project, issue type, status, summary, description,
  environment, labels, components, `fixVersions`, `versions`, parent, users,
  links, attachments, worklogs, changelog, properties и custom fields остаются
  в разобранном `fields`/`external` projection artifact;
- ADF description/environment и ADF comments получают deterministic text
  projection, при этом исходный JSON остаётся в raw/projection;
- комментарии сохраняются в task ленте как строковый `text` с external id,
  author и timestamp;
- создаются `artifacts/jira-projection.json` и
  `artifacts/jira-completeness.json`;
- повторный импорт увеличивает `source.revision`, не дублирует уже импортированные
  комментарии и обновляет projection/completeness artifacts;
- профиль принимает как rich Jira REST-shaped snapshot, так и legacy/minimal
  `id`/`key`/`fields` payload без потери исходного raw;
- сбой записи snapshot, projection или queue/index откатывает mirror, index и
  artifact tree к состоянию до импорта; пустая новая mirror-запись не остаётся.

`task.json` не превращает provider-specific поля в новые canonical поля. Для
проверяемой structured формы используй артефакт `JIRA-MIRROR-1`, а источником
правды остаётся локальный mirror и его `source.raw`.

### Completeness

`jira-completeness.json` фиксирует наличие `fields`, comments, changelog,
attachments, worklogs, properties и links, количество custom fields и отметку
`raw_preserved`. Отсутствие поля в локальном snapshot не объявляется
`permission_denied`: runtime не знает, запрашивался ли соответствующий Jira
endpoint. Для API-level completeness нужен внешний request manifest.

### Что всё ещё не сделано

- сетевой Jira REST client и credentials/permission handling;
- автоматическое получение Project Versions и release registry;
- pagination отдельных comments/worklogs/changelog endpoints;
- загрузка binary attachments и полный archival bundle;
- экспорт обратно в Jira или lossless provider workflow.

Поэтому корректная формулировка сейчас: **все данные, присутствующие в переданном
Jira snapshot-файле, сохраняются raw и в projection; автоматического получения
всех данных из Jira API пока нет**.
