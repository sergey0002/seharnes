# Скрипт: `.agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.sh`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, build-testanalyze]
-->

## Суть
Обёртка для запуска `build-testanalyze.py` из корня репозитория. Вычисляет корень проекта и передаёт все аргументы в Python-скрипт. Упрощает вызов из любой директории.

## Когда запускать
Те же сценарии, что и для `build-testanalyze.py`. Используется как удобная точка входа.

## Аргументы
Пробрасывает все аргументы в `build-testanalyze.py`:
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| --all |  | flag | нет |  | все папки задач |
| --staged-only |  | flag | нет |  | только задачи с stage* |
| --multi-stage |  | flag | нет |  | только >=2 планов |
| --task |  | int | нет |  | номер задачи (повторяемый) |
| --with-diffs |  | flag | нет |  | записать дифы |
| --full-diff |  | flag | нет |  | также .patch файлы |
| --refresh-jira |  | flag | нет |  | экспорт task.md из Jira |
| --limit |  | int | нет | 0 | лимит задач |
| --skip-readme |  | flag | нет |  | не перезаписывать README |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех (передаёт код Python) | продолжать |
| 1 | Ошибка Python-скрипта | проверить stderr |
| 127 | Python не найден | установить python3 |

## Что читает и что пишет
Не читает/пишет сам — делегирует `build-testanalyze.py`.

## Побочные эффекты
- Запуск дочернего процесса Python

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| python3 | Должен быть в PATH |

## Примеры
```bash
# Из любой директории
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.sh --multi-stage --with-diffs

# Конкретная задача
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.sh --task 2410 --with-diffs
```

## Ограничения
- Требует запуска из репозитория (вычисляет ROOT по BASH_SOURCE)
- Не работает вне git-рабочей копии

## Связи
- Вызывает: `build-testanalyze.py`
- Альтернатива: прямой вызов Python

## История изменений
- 2026-11-07: полная документация (status: draft → actual)