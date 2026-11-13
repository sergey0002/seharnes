# Скрипт: `.agents/skills/task-router/children/jira/scripts/diag-auth.php`

<!-- meta
type: script
status: actual
argv: manual
updated: 2026-11-07
related: [../../SKILL.md]
tags: [harness, script, diag-auth, jira]
-->

## Суть
PHP-скрипт для диагностики подключения к Jira Cloud через REST API v3. Проверяет корректность учётных данных (JIRA_EMAIL, JIRA_API_TOKEN), выводит детали токена (длина, кавычки, пробелы) без раскрытия секрета, и выполняет тестовый запрос к `/rest/api/3/myself` или к конкретной задаче. Используется для быстрой проверки доступа перед запуском экспортеров задач.

## Когда запускать
- При настройке нового окружения или смене токена Jira
- При ошибках 401/403 от экспортеров (`export_task.py`, `server.php`)
- Для проверки, что переменные окружения из `config.env` подхвачены правильно
- Никогда не запускать в продакшене — только локально на dev-стенде

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| $argv[1] | mode | string | нет | issue | Режим теста: `myself` (проверка пользователя) или `issue` (проверка задачи) |
| $argv[2] | issue_number | string | нет | 2538 | Номер задачи Jira (для mode=issue) |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Запрос выполнен (HTTP код выводится в stdout) | Проверить вывод: `HTTP 200` = успех, `HTTP 401` = неверные креды, `HTTP 403` = нет прав |
| 1 | PHP fatal / curl ошибка | Проверить наличие curl и network |

## Что читает и что пишет
**Читает:**
- `config.env` (в той же папле скрипта) — переменные `JIRA_BASE_URL`, `JIRA_PROJECT_KEY`, `JIRA_EMAIL`, `JIRA_API_TOKEN`
- Файлы классов из `src/` (`EnvConfig.php`, `IssueIdParser.php`)

**Пишет:**
- Только в stdout: диагностика конфига, URL запроса, HTTP код, ответ API (user displayName / issue key / summary)

**Сеть:**
- Один HTTP-запрос к `JIRA_BASE_URL/rest/api/3/myself` или `/rest/api/3/issue/{KEY}`

## Побочные эффекты
- network requests (один GET к Jira API)
- Никаких файлов не создаёт, никаких секретов не логирует

## Окружение и зависимости
| Переменная | Описание |
|---|---|
| JIRA_BASE_URL | Базовый URL Jira Cloud (например, `https://company.atlassian.net`) |
| JIRA_PROJECT_KEY | Ключ проекта (по умолчанию `CT`) |
| JIRA_EMAIL | Email учётной записи Atlassian |
| JIRA_API_TOKEN | API токен (создаётся в Atlassian Account → Security → API tokens) |
| JIRA_CONFIG_FILE | Путь к альтернативному config.env (опционально) |

**Зависимости:** PHP 7.1+, расширение `curl`, классы `EnvConfig`, `IssueIdParser` из `src/`.

## Примеры
```bash
# Базовая проверка пользователя (myself)
php diag-auth.php myself

# Проверка доступа к задаче CT-2538
php diag-auth.php issue 2538

# С кастомным конфигом
JIRA_CONFIG_FILE=/path/to/config.env php diag-auth.php myself
```

## Ограничения
- Не проверяет права на запись (только чтение задачи/пользователя)
- Не работает с Jira Server/Data Center (только Cloud REST API v3)
- При токене с обёрточными кавычками (`"token"` или `'token'`) выведет предупреждение `token_has_wrapping_quotes=yes` — токен в config.env должен быть без кавычек
- Пробелы в токене (`token_has_whitespace=yes`) тоже ломают авторизацию
- Не использует MCP — чистый CLI-скрипт

## Связи
- Вызывается вручную разработчиком при настройке
- Использует те же `EnvConfig` и `IssueIdParser`, что и `server.php`
- Результат помогает диагностировать ошибки `export_task.py` и MCP-сервера
- Документирован в `../../SKILL.md` (раздел «Диагностика авторизации»)

## История изменений
- 2026-11-07: заполнена полная документация по коду (был draft)