# Скрипт: `.agents/skills/task-router/children/jira/scripts/export_task.py`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, export_task, jira]
-->

## Суть
Python-скрипт для экспорта задачи Jira в Markdown-файл `.doc/tasks/{N}/task.md`. Работает без PHP и Docker — минимальный фолбэк, когда основной экспортер (`server.php`) недоступен. Загружает задачу через REST API v3 с раскрытием changelog, пагинирует комментарии, конвертирует ADF (Atlassian Document Format) в Markdown, сохраняет метаданные, описание, историю изменений и все комментарии в хронологическом порядке.

## Когда запускать
- Когда `server.php` (MCP-сервер) не запускается (нет PHP, нет Docker, нет зависимостей)
- Для разового экспорта задачи без поднятия MCP-стек
- В CI/CD пайплайнах, где проще вызвать Python-скрипт
- **Не** использовать как основной способ — MCP-сервер даёт больше функций (релизы, кэш, валидация)

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| $1 | issue_number | string | да | — | Нumeric ID задачи (например, `2538`), ключ (`CT-2538`) или полный URL browse |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: файл записан, в stdout — путь, ключ, заголовок, счётчики | Использовать путь к `.doc/tasks/{N}/task.md` |
| 1 | Ошибка: нет аргумента, неверный ID, ошибка сети/API, нет конфига | Проверить stderr: usage, HTTP код, детали ошибки |

## Что читает и что пишет
**Читает:**
- `config.env` (рядом со скриптом или по `JIRA_CONFIG_FILE`) — `JIRA_BASE_URL`, `JIRA_PROJECT_KEY`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- Jira REST API: `/rest/api/3/issue/{KEY}?expand=changelog`, `/rest/api/3/issue/{KEY}/comment` (пагинация по 100)

**Пишет:**
- `.doc/tasks/{N}/task.md` — полный Markdown с метаданными, описанием, комментариями, историей изменений
- Создаёт директорию `.doc/tasks/{N}/` если нет

**Сеть:**
- Несколько HTTPS-запросов к Jira Cloud API (Basic Auth)

## Побочные эффекты
- network requests (Jira API)
- file writes (создаёт task.md и директории)
- Не меняет данные в Jira (только чтение)

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| JIRA_CONFIG_FILE | Путь к config.env (по умолчанию рядом со скриптом) |
| JIRA_BASE_URL | Базовый URL Jira Cloud |
| JIRA_PROJECT_KEY | Ключ проекта (например, `CT`) |
| JIRA_EMAIL | Email учётной записи |
| JIRA_API_TOKEN | API токен |

**Зависимости:** Python 3.8+, стандартная библиотека (`urllib`, `json`, `base64`, `datetime`, `pathlib`). Никаких внешних пакетов.

## Примеры
```bash
# Экспорт задачи 2538
python3 export_task.py 2538

# Экспорт по ключу
python3 export_task.py CT-2538

# С кастомным конфигом
JIRA_CONFIG_FILE=/opt/jira/config.env python3 export_task.py 2538
```

**Вывод при успехе:**
```
Saved: /home/user/project/.doc/tasks/2538/task.md
Key: CT-2538
Title: Исправить расчёт скидки при оплате бонусами
Comments: 12
Changes: 8
```

## Ограничения
- Только Jira Cloud REST API v3 (не Server/DC)
- Не экспортирует вложения (attachments) — только текст комментариев и changelog
- ADF-конвертер покрывает базовые узлы (text, link, code, strong, heading, list, codeBlock, mention, emoji, rule, inlineCard, hardBreak, doc, paragraph, listItem, blockquote, tableCell, tableHeader, bulletList, orderedList). Сложные таблицы и медиа могут потеряться
- Не кэширует запросы — каждый запуск бьёт в API заново
- Не проверяет права на просмотр — 403 вернётся как ошибка
- Не создаёт `task.json` (JSONdoc) — только `task.md`

## Связи
- Фолбэк для `server.php` (MCP-сервер) — тот же формат `task.md`
- Используется `gototask` скриптом при нерабочем MCP
- Документирован в `../../SKILL.md` (раздел «Экспорт задачи»)
- Конфиг совместим с `diag-auth.php` и `server.php`

## История изменений
- 2026-11-07: заполнена полная документация по коду (был draft)