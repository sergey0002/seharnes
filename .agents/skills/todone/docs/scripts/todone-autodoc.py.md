# Скрипт: `tcheck autodoc`

<!-- meta
type: script
status: actual
updated: 2026-11-18
related: [../../SKILL.md]
tags: [harness, script, autodoc]
argv: passthrough
-->

## Суть
Генерирует автодокументацию: JSON-схемы типов, отчет диархии FLOW-1, HTML (с вставками Mermaid), Markdown каталог. Используется `tcheck autodoc generate --root <root> [--audit]`.

## Когда запускать
После обновления типов, потоков, проверок: `tcheck autodoc generate --root . [--audit]`. После изменений в процессе генерации или исправления (`--audit`).

## Аргументы
Общие флаги: `--root`, `--html` (создать HTML), `--json` (создать JSON), `--audit` (проверить, произвести исправления), `--dry-run`, `--strict` (ошибки паритета вызывают неудачу).

## Коды выхода
- 0: успех
- 1: ошибки генерации/валидации
- 3: требуется участие человека

## Что читает и что пишет
Читает: `<root>/assets/types/`, `<root>/assets/flows/`, `<root>/.todone/flows/` и `<root>/.todone/types/` (проектные переопределения). Пишет: `<root>/.todone/autodoc/bundle.json`, `<root>/docs_html/*.html`, `<root>/docs/autodoc-*.md`.

## Побочные эффекты
Генерирует HTML и Markdown, записывает `autodoc/audit.json`. Может сохранять временные файлы в `<root>/.todone/autodoc/`.

## Окружение и зависимости
`TODONE_ROOT`. Требует Python 3.8+, Node.js для Mermaid (диаграммы).

## Примеры
```bash
# только JSON-бандл
tcheck autodoc generate --root .
# HTML + JSON
tcheck autodoc generate --root . --html --json --audit
```

## Ограничения
Не обновляет неавтодокируемую документацию (такие как `docs/*.md`). Диаграммы Mermaid требуют Node.js (опционально).

## Связи
Вызывается из `tcheck autodoc` (список команд). Процедура: `docs/20-autodoc.md`.

## История изменений
- 2026-11-18: документация заполнена агентом
