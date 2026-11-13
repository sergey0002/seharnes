# Скрипт: `.agents/skills/skill-creator/scripts/scaffold_skill.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md, ./package_and_verify.py.md]
tags: [harness, script, skill-creator, scaffold]
-->

## Суть
Создает каркас переносимого навыка для 17 агентских сред: `SKILL.md`, `README.md`, `skill.json`, необязательные `scripts/`, `references/`, `assets/`, `agents/openai.yaml` и `evals`. Поддерживает архетипы `atomic`, `script`, `multi-agent`, `user-invoked` и режимы вызова `model` и `user`. Проверяет kebab-case имени и не перезаписывает существующий каталог без `--force`.

## Когда запускать
При создании нового навыка до написания содержания. Скрипт задает структуру и обязательные поля, дальше автор заполняет `SKILL.md` и ресурсы. Без него структура пакета собирается вручную и расходится между средами.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `name` | | string | да | | имя навыка в kebab-case |
| `--output-dir DIR` | | string | нет | `.` | родительский каталог для `<name>/` |
| `--description TEXT` | | string | нет | шаблон по имени | описание триггеров для `description` |
| `--archetype TYPE` | | `atomic`, `script`, `multi-agent`, `user-invoked` | нет | `atomic` | стартовая структура и набор ресурсов |
| `--invocation MODE` | | `model`, `user` | нет | из архетипа | режим вызова навыка |
| `--license ID` | | string | нет | `MIT` | SPDX-идентификатор лицензии |
| `--author NAME` | | string | нет | `skill-author` | значение `metadata.author` |
| `--version VER` | | string | нет | `1.0.0` | значение `metadata.version` |
| `--compatibility TEXT` | | string | нет | | необязательная заметка о совместимости |
| `--resources LIST` | | string | нет | пусто | каталоги через запятую: `scripts`, `references`, `assets`, `agents`, `evals` |
| `--no-openai-yaml` | | flag | нет | | не создавать `agents/openai.yaml` |
| `--display-name NAME` | | string | нет | из имени | `display_name` для Codex UI |
| `--short-description TEXT` | | string | нет | из описания | `short_description` для Codex UI, 25-64 символа |
| `--mirror-project DIR` | | string | нет | | корень проекта для относительных симлинков-зеркал |
| `--mirror-targets LIST` | | string | нет | `.claude/skills,.qoder/skills,.kiro/skills` | каталоги зеркал через запятую |
| `--force` | | flag | нет | | перезаписать существующий каталог навыка |
| `--json` | | flag | нет | | вывести результат в JSON |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | каркас создан | заполнить `SKILL.md` и ресурсы |
| 1 | неверное имя, архетип, ресурс или существующий каталог без `--force` | исправить аргументы и повторить |

## Что читает и что пишет
Читает аргументы командной строки и при наличии `config.json` шаблоны скила. Пишет каталог `<name>/` с `SKILL.md`, `README.md`, `skill.json`, выбранными ресурсами, `agents/openai.yaml` и `evals`. При `--mirror-project` создает относительные симлинки в указанных каталогах. Сеть не использует.

## Побочные эффекты
- Создает каталоги и файлы навыка.
- При `--force` перезаписывает существующий каталог.
- Создает симлинки-зеркала при `--mirror-project`.

## Окружение и зависимости
Python 3.9 или новее, стандартная библиотека. `PyYAML` необязателен и используется только для проверки.

## Примеры
```bash
python3 .agents/skills/skill-creator/scripts/scaffold_skill.py my-skill --output-dir .agents/skills
python3 .agents/skills/skill-creator/scripts/scaffold_skill.py my-skill --archetype script --resources scripts,references
python3 .agents/skills/skill-creator/scripts/scaffold_skill.py my-skill --json
```

## Ограничения
Создает структуру и шаблонный текст, но не пишет содержательный `SKILL.md`. Не проверяет качество описания и триггеров. Симлинки-зеркала работают только в средах, где они поддерживаются файловой системой.

## Связи
- Скил: `.agents/skills/skill-creator/SKILL.md`.
- Проверка и упаковка: `package_and_verify.py`, документ `./package_and_verify.py.md`.
- Формат навыка: `.doc/harnes/skill-format.md`.

## История изменений
- 2026-11-11: документ создан, аргументы и поведение сверены с кодом.
