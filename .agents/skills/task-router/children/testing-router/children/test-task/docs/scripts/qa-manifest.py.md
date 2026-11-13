# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-manifest.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, qa-manifest]
-->

## Суть
Строит и верифицирует неизменные входы QA-прогона (fingerprints). Вердикт имеет смысл только для точного кода, тестового кода и требований задачи, которые использовались в прогоне. Генерационные выходы и test-runs намеренно исключены из трёх отпечатков.

Три основных fingerprint (SHA256):
- `code_sha256` — исходный код проекта (git ls-files, расширения php/js/vue/ts/css/tpl/sql, исключая vendor/node_modules/.doc/.cursor/test-runs)
- `tests_sha256` — тестовый код (Codeception tests, .doc/tasks/{N}/tests, .doc/qa, исключая test-runs/_output)
- `requirements_sha256` — требования задачи (task.md, test.md, plan.md, doc.md, ac-matrix.json, requirements.json, diff.files.md)
- `skills_sha256` — скилы: prepare-task-test, test-task, browser-verify, prepare-plan (SKILL.md)
- `environment_sha256` — рантайм: выбранные env vars + codeception.env SHA256 + docker image ID php-контейнера

## Когда запускать
- Автоматически в `task-test.sh` в начале прогона (создаёт manifest.json)
- В `make-verdict.py` (--check) для проверки совпадения fingerprint текущего состояния с манифестом прогона
- В `gates.py` (G12) для проверки staleness прогона

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --task |  | string | да |  | Номер задачи |
| --group |  | string | да |  | Группа Codeception |
| --output |  | string | да |  | Путь для записи manifest.json |
| --check |  | string | нет |  | Путь к существующему manifest.json для сравнения |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Манифест создан / совпадает (--check) | продолжать |
| 1 | --check: fingerprint не совпадает | перезапустить инвалидированный слой |

## Что читает и что пишет
**Читает:**
- Git tracked/untracked файлы (`git ls-files`)
- Файлы проекта по расширениям
- `.doc/tasks/{N}/` требования
- `.cursor/skills/{name}/SKILL.md` скилов
- `.tools/codeception/.env` (SHA256)
- Docker: `docker inspect` php-контейнера (image ID)
- Env vars: QA_PHPUNIT_CONTAINER, QA_PHPSTAN_LEVEL, CHROMEDRIVER_*, MYSQL_*

**Пишет:**
- `{output}` — manifest.json (schema 2):
  - task, group, commit, code_sha256, tests_sha256, requirements_sha256, skills_sha256, environment_sha256
  - environment: выбранные env + codeception_env_sha256 + php_container_image
  - code_files[], test_files[], requirement_files[], skill_files[] — с путями и SHA256 каждого файла

**Вывод (--check):**
- JSON: `{"ok": true/false, "mismatched": ["field1", "field2"]}`

## Побочные эффекты
- File write: manifest.json
- Docker inspect (read-only)
- Git ls-files

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| QA_PHPUNIT_CONTAINER | Имя php контейнера для image ID | `copytrust-dev-php-apache-1` |
| Git | В PATH |
| Docker | В PATH (опционально) |

## Примеры
```bash
# Создать манифест в начале прогона
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-manifest.py \
  --task 2605 --group task-2605 \
  --output .doc/tasks/2605/test-runs/2026-11-07_143022/manifest.json

# Проверить совпадение (в make-verdict.py / gates.py)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/qa-manifest.py \
  --task 2605 --group task-2605 \
  --check .doc/tasks/2605/test-runs/2026-11-07_143022/manifest.json
```

## Ограничения
- Не включает в fingerprint: vendor, node_modules, .doc, .cursor, test-runs, _output
- environment_sha256 не включает секреты (только имена+значения выбранных vars + env файл SHA256)
- Требует git репозиторий
- schema 2 (добавлен environment_sha256)

## Связи
- Вызывается: `task-test.sh` (создание), `make-verdict.py` (проверка), `gates.py` (G12)
- Канон: `.doc/harnes/tests.md` § manifest

## История изменений
- 2026-11-07: полная документация (status: draft → actual)