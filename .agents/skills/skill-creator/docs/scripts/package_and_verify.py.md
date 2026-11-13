# Скрипт: `.agents/skills/skill-creator/scripts/package_and_verify.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md, ./scaffold_skill.py.md]
tags: [harness, script, skill-creator, package, preflight]
-->

## Суть
Собирает навык в архив `.skill` и выполняет детерминированную предполетную проверку для 17 агентских сред. Проверяет структуру пакета, `SKILL.md`, ссылки, запрещенные каталоги, секреты и имена файлов, затем при необходимости вызывает соседний `skill-auditor/scripts/static_audit.py`. Архив создается только при успешной предполетной проверке.

## Когда запускать
Перед публикацией или передачей навыка, когда нужно получить `.skill` и подтвердить переносимость. В режиме `--verify-only` скрипт используется как проверка без записи архива.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `skill_dir` | | string | да | | каталог навыка с `SKILL.md` |
| `--output-dir DIR` | | string | нет | родительский каталог навыка | куда положить `<name>.skill` |
| `--verify-only` | | flag | нет | | проверить без создания архива |
| `--auditor-script PATH` | | string | нет | поиск соседнего `static_audit.py` | явный путь к аудитору |
| `--no-external-auditor` | | flag | нет | | не вызывать `skill-auditor` |
| `--json` | | flag | нет | | вывести результат в JSON |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | предполетная проверка прошла, архив создан или режим `--verify-only` завершен | использовать архив или считать проверку пройденной |
| 1 | проверка не прошла, ошибка внешнего аудитора или запись архива | разобрать `errors` и повторить |

## Что читает и что пишет
Читает каталог навыка, `SKILL.md`, `agents/openai.yaml`, скрипты, ссылки и метаданные. Пишет `<name>.skill` в `--output-dir`, если проверка прошла и не задан `--verify-only`. При вызове внешнего аудитора получает JSON-отчет. Сеть не использует.

## Побочные эффекты
- Создает или перезаписывает архив `.skill`.
- Запускает соседний `static_audit.py` как дочерний процесс.
- Исходный каталог навыка не меняет.

## Окружение и зависимости
Python 3.9 или новее. `PyYAML` необязателен: без него используется встроенный разбор. Для внешней проверки нужен установленный `skill-auditor`.

## Примеры
```bash
python3 .agents/skills/skill-creator/scripts/package_and_verify.py path/to/skill
python3 .agents/skills/skill-creator/scripts/package_and_verify.py path/to/skill --verify-only --json
python3 .agents/skills/skill-creator/scripts/package_and_verify.py path/to/skill --no-external-auditor
```

## Ограничения
Не исправляет найденные ошибки и не меняет навык. Внешняя проверка зависит от наличия `skill-auditor` и его версии. Архив не подписывается.

## Связи
- Скил: `.agents/skills/skill-creator/SKILL.md`.
- Каркас навыка: `scaffold_skill.py`, документ `./scaffold_skill.py.md`.
- Внешний аудит: `.agents/skills/skill-auditor/scripts/static_audit.py`.

## История изменений
- 2026-11-11: документ создан, аргументы и поведение сверены с кодом.
