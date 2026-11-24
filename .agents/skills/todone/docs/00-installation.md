# Установка и требования

## Что именно устанавливается

`todone` в текущем виде — локальная поставка, а не пакет Python с отдельным
installer-ом. Достаточно получить каталог `todone/` вместе с его `scripts/`,
`types/`, `flows/`, `schemas/` и тестами.

Runtime использует Python 3 и пакет `jsonschema` (ветка 4.x подходит для
текущих JSON Schema 2020-12 checks). Отдельного `pyproject.toml`/installer-а
у поставки нет, поэтому зависимость проверяется и устанавливается вручную.

Проверить окружение:

```bash
python3 --version
python3 -c 'import jsonschema; print(jsonschema.__version__)'
```

Если пакет не установлен:

```bash
python3 -m pip install "jsonschema>=4"
```

## Запуск из checkout

Из корня репозитория:

```bash
python3 todone/scripts/tqueue.py --help
python3 todone/scripts/ttask.py --help
python3 todone/scripts/tcheck.py --help
```

Если нужны короткие команды, можно сделать локальные wrapper-ы или добавить
`todone/scripts` в `PATH`. Это не меняет данные и не является обязательным.

## Что считается корнем проекта

`--root` указывает **рабочий проект**, а не каталог установки навыка. По
умолчанию documentation workspace создаётся в `<root>/docs`; точку записи можно
явно задать относительным к root `--docs-path` при `tcheck docs init`. Выбор
сохраняется в `<root>/.todone/docs-path.json` по контракту `DOC-PATH-1`, поэтому
последующие `tcheck docs` и `ttask document` находят custom path после restart.
Пути за пределами project root запрещены.

```text
/home/user/todone/              # установленная поставка и встроенные presets
/home/user/my-project/          # рабочий root проекта
/home/user/my-project/.todone/  # project registry/configuration
/home/user/my-project/docs/     # documentation workspace по умолчанию
/home/user/my-project/tasks/    # очереди проекта
```

Пример с отдельным проектом:

```bash
mkdir -p /tmp/my-project
python3 todone/scripts/tqueue.py init site \
  --root /tmp/my-project \
  --path /tmp/my-project/tasks/site
```

Поставка автоматически находит встроенные `types/` и `flows/` рядом со своими
скриптами. Проектные overrides читаются из
`<root>/.todone/types/` и `<root>/.todone/flows/`.

## Первый health check

После получения checkout запусти:

```bash
python3 -m py_compile todone/scripts/tdcore/*.py
python3 -m unittest discover todone/tests
python3 todone/scripts/tcheck.py selftest
python3 todone/scripts/tcheck.py doctor \
  --root todone/examples/v6-project --all --strict
```

Эти команды проверяют поставку. Для пользовательского проекта `doctor` запускай
с его `--root`; он проверяет очереди, roles, tools, flows и прозу. Для
documentation workspace используй отдельный `tcheck docs check` — это не часть
общего `doctor`-прохода.

## Что не выполняется при установке

Установка не создаёт очередь, не импортирует внешний источник и не запускает
агрегацию автоматически. Эти действия выполняются явно командами из
[быстрого старта](00-quick-start.md) и [агрегации](18-aggregation.md).
Сетевого Jira/OpenSpec/Spec Kit клиента и отдельного `todoc_scan` runtime в этой
поставке нет.
