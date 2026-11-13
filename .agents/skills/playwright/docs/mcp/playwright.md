# MCP: playwright

<!-- meta
type: config
status: actual
updated: 2026-11-01
related: [../../../../../.doc/harnes/archive/mcp/README.md, ../../../../../.doc/harnes/state/04-mcp.md]
tags: [harness, mcp, browser, ui]
-->

---

## Суть

Браузерная проверка UI: навигация, снимок DOM, клики, ввод, оценка JS и скриншоты. Основное покрытие дает Codeception, Playwright закрывает ветки без метода.

---


## Когда вызывать

Когда брать сервер и в каком порядке: правило `.cursor/rules/mcp/playwright.mdc`, раздел `Когда`. Здесь фиксируется только эксплуатационное условие: сервер берут, когда локальный файл или тест не дают ответ дешевле.

## Конфигурация

| Параметр | Значение |
|---|---|
| Тип | stdio |
| Запуск | `npx -y @playwright/mcp@0.0.38` |
| Браузер | headed Chrome через `chrome-wrap.sh` |
| Переменные | `PLAYWRIGHT_MCP_EXECUTABLE_PATH`, `CHROME_PATH`, `LD_LIBRARY_PATH` |

---


## Текущие значения

| Параметр | Значение |
|---|---|
| Статус | включен |
| Транспорт | `command: npx -y @playwright/mcp@0.0.38` |
| Переменные окружения | CHROME_PATH`, `LD_LIBRARY_PATH`, `PLAYWRIGHT_MCP_EXECUTABLE_PATH |

Секреты не печатаются, только имена переменных. Полная конфигурация в разделе `Конфигурация`.

## Инструменты

| Инструмент | Параметры | Зачем |
|---|---|---|
| `browser_navigate` | `url` | открыть страницу |
| `browser_snapshot` | - | DOM-снимок и `ref` |
| `browser_click` | `element`, `ref`, `button`, `doubleClick`, `modifiers` | клик |
| `browser_type` | `element`, `ref`, `text`, `submit`, `slowly` | ввод |
| `browser_fill_form` | `fields[]`: `name`, `type`, `ref`, `value` | форма |
| `browser_evaluate` | `function`, `element`, `ref` | JS |
| `browser_take_screenshot` | `type`, `filename`, `element`, `ref`, `fullPage` | скриншот |

Отключены: `browser_press_key`, `browser_navigate_back`, `browser_drag`,
`browser_hover`, `browser_select_option`, `browser_tabs`.

В пакете есть `browser_verify_*`, `browser_mouse_*`, `browser_network_requests`,
`browser_wait_for`, `browser_close`, `browser_resize`, `browser_handle_dialog`,
`browser_pdf_save`, `browser_file_upload`, `browser_generate_locator`,
`browser_console_messages`, `browser_start_tracing`, `browser_stop_tracing`,
`browser_install`. В маршрут задачи они не входят.

---

## Правила использования

1. Основное покрытие Codeception Acceptance, Playwright только для веток без Cest или PHPUnit метода.
2. Через скилы `browser-verify` и `test-task`.
3. Браузер всегда видимый (headed), скрытые облачные инструменты не используются.
4. Не править шаблоны ради теста.

---

## Установка и перенос

- Установка: Node и `npx -y @playwright/mcp@0.0.38`; нужен Chrome и `chrome-wrap.sh`.
- Перенос: скопировать запись `playwright` и переменные `PLAYWRIGHT_MCP_EXECUTABLE_PATH`, `CHROME_PATH`, `LD_LIBRARY_PATH`.
- Проверка: `node .agents/skills/harness-router/children/mcp-audit/scripts/test-mcp-servers.mjs --only=playwright`.

## Несколько проектов

- stdio-сервер запускается на каждый проект отдельно; браузер и профиль не общие.
- URL стенда передается в `browser_navigate`, он у каждого проекта свой.
- Не держать два headed-браузера без необходимости: это память и лишние окна.

## Связи

- [Карта MCP](../../../../../.doc/harnes/archive/mcp/README.md) - общий список
- [MCP-серверы](../../../../../.doc/harnes/state/04-mcp.md) - правила UI-проверок
- [Правило test-task](../../../../../.cursor/rules/test-task.mdc) - порядок прогона
- [Браузерная настройка](../../../../../.cursor/rules/test-task.mdc) - стенд, chromedriver, sandbox

---

## Известные проблемы и ограничения

- Симптом: браузер не стартует.
  Причина: нет дисплея или не найден Chrome по указанному пути.
  Решение: проверить `chrome-wrap.sh` и `LD_LIBRARY_PATH`.
  Файлы: `.cursor/mcp.json`
- Симптом: нужен `browser_tabs` или drag.
  Причина: инструменты отключены осознанно.
  Решение: сценарий через Codeception или явное включение в каноне.

---

## История изменений

- 2026-11-01: создан по данным `.cursor/mcp.json` и state/04-mcp.md
- 2026-11-01: добавлены разделы установки, переноса и нескольких проектов; уточнены инструменты и аргументы
