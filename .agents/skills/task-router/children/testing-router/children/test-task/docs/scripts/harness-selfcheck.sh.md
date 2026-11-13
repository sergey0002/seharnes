# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selfcheck.sh`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, harness-selfcheck]
-->

## Суть
Запускает все self-тесты харнеса (юнит-тесты скилов, структурные валидаторы). Существует, потому что в харнесе есть регрессионные тесты для своих скриптов, но их никто не вызывал. Сломанный скрипт (missing import) оставался сломанным, потому что не было гейта, smoke-шага или CI файла, вызывающего тесты, которые уже это ловили.

## Когда запускать
- Перед коммитом изменений в харнес (скилы, правила, скрипты)
- В CI для валидации харнеса
- При подозрении на сломанные внутренние тесты

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --quiet |  | flag | нет |  | Только провалы + итоговая сводка |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Все наборы пройдены, нет отсутствующих | продолжать |
| 1 | Есть провалы или отсутствующие наборы | прочитать вывод, исправить/восстановить тесты |

## Что читает и что пишет
**Читает (запускает):**
- Юнит-тесты скилов (python3 -m pytest style, stdlib only):
  - `.agents/skills/harness-router/children/improvement/tests/test_harness_improvement.py`
  - `.agents/skills/task-router/children/task-intake/tests/test_intake_state.py`
  - `.agents/skills/task-router/children/task-intake/tests/test_intake_analysis.py`
  - `.agents/skills/task-router/children/task-intake/tests/test_intake_orchestrator.py`
  - `.agents/skills/task-router/children/task-intake/tests/test_doc_sections.py`
  - `.agents/skills/task-router/children/reporting-router/children/task-change-report/tests/test_generate_report.py`
  - `.agents/skills/task-router/children/reporting-router/children/task-change-report/tests/test_workflow_contract.py`
  - `.agents/skills/task-router/children/reporting-router/children/task-change-report/tests/test_skill_integration.py`
  - `.agents/skills/harness-router/children/environment-sync/tests/test_sync_views.py`
  - `.agents/skills/harness-router/children/environment-sync/tests/test_dsh_config.py`
  - `.agents/skills/harness-router/children/environment-sync/tests/test_dsh_kit.py`
- Структурные валидаторы:
  - `.agents/skills/harness-router/children/improvement/scripts/validate_skills.py`
  - `.agents/skills/harness-router/children/improvement/scripts/validate_docs.py`
  - `.doc/web/bin/selfcheck.py`

**Пишет:** ничего (только stdout/stderr)

## Побочные эффекты
- Запускает дочерние Python-процессы (timeout 300с каждый)
- Пишет логи валидаторов в `/tmp/selfcheck-validator.log`

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| python3 | В PATH |
| REPO_ROOT | Корень репозитория (вычисляется автоматически) |

## Примеры
```bash
# Полный прогон с выводом
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selfcheck.sh

# Только сводка
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/harness-selfcheck.sh --quiet
```

## Ограничения
- Тесты должны быть в stdlib (без pytest зависимостей)
- Таймаут 300с на набор
- Отсутствующие тестовые файлы считаются провалом (exit 1)
- Не проверяет MCP-серверы — только внутренние скрипты/скилы

## Связи
- Валидирует: все скилы в `.agents/skills/`
- Вызывается: вручную, в CI (опционально)

## История изменений
- 2026-11-07: полная документация (status: draft → actual)