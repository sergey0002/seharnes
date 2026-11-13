# Скрипт: `.agents/skills/task-router/children/testing-router/children/prepare-task-test/scripts/new-task-test.py`

<!-- meta
type: script
status: actual
updated: 2026-11-07
related: [../../SKILL.md, ../../../testing-router/children/test-task/scripts/check-tests.sh, ../../../testing-router/children/test-task/scripts/task-test.sh, ../../../testing-router/children/test-task/scripts/gates.py]
tags: [harness, script, prepare-task-test, cest, test-md, codeception]
-->

## Суть
Создаёт заготовку приёмочного теста задачи (Cest + test.md) по новой раскладке. Генерирует:
1. `.doc/tasks/{N}/tests/{Name}Cest.php` — класс с `_before` (клиент, консоль), `happyPath` и `negativeCase` методами, уже помеченными `@group task-{N}`, с `checkpoint`, `seeNoConsoleErrors`, `dontSeeErrorModal` и TODO местами под Page/Step вызовы, DB проверки, UI литералы.
2. `.doc/tasks/{N}/test.md` — шаблон документации теста с таблицей сценариев, ветками логики (по testaudit §9), 13-пунктным чек-листом (tests.md §7), гейт-маркерами.
3. Симлинк `.tools/codeception/tests/Acceptance/Task/{N}` → `../../../../../.doc/tasks/{N}/tests` для автообнаружения Codeception.

Заготовка намеренно не пустая — содержит каркас, который проверяют гейты (G5, G6, G10, G13). Агент заполняет только бизнес-логику.

## Когда запускать
В начале подготовки тестов задачи (`prepare-task-test` SKILL.md), после того как есть `plan.md` с Decomposition. Вызывается агентом вручную. Если не запустить — агент пишет Cest с нуля, пропускает обязательные гейт-проверки.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `task` | | string (позиционный) | **да** | | Номер задачи (только цифры) |
| `name` | | string (позиционный) | **да** | | Имя Cest класса без суффикса `Cest`, CamelCase (напр. `QualityWarning`) |
| `--title` | | string | нет | `TODO краткое описание` | Описание задачи для шапки Cest и test.md |
| `--force` | | flag | нет | | Перезаписать Cest если уже существует |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | Успех: файлы созданы/пропущены, симлинк готов | Переходить к заполнению сценариев |
| 1 | Ошибка: task не цифры, name не CamelCase, Cest существует без `--force` | Исправить аргументы или добавить `--force` |

## Что читает и что пишет
**Читает:** ничего (только аргументы)

**Пишет:**
- `.doc/tasks/{N}/tests/{Name}Cest.php` — PHP класс теста
- `.doc/tasks/{N}/test.md` — документация теста (если не существует)
- Симлинк `.tools/codeception/tests/Acceptance/Task/{N}` → `../../../../../.doc/tasks/{N}/tests`
- `.doc/tasks/{N}/test-runs/` — создаёт каталог если нет

**Stdout:** пути созданных файлов и инструкции следующие шаги.

## Сгенерированный Cest каркас
```php
final class {Name}Cest {
    public function _before(AcceptanceTester $I): void {
        $I->haveInDbDefaultClient();
        $I->devLoginAsClient(1);
        $I->initConsoleCapture();
    }

    /** @group task-{N} */
    public function happyPath(AcceptanceTester $I): void {
        // TODO Page/Step шаги
        $I->checkpoint('{N}-happy-path');
        // TODO UI литерал из task.md
        // TODO DB проверка (гейт G6)
        $I->seeNoConsoleErrors();
        $I->dontSeeErrorModal();
    }

    /** @group task-{N} */
    public function negativeCase(AcceptanceTester $I): void {
        // TODO
        $I->checkpoint('{N}-negative');
    }
}
```

## test.md структура
- Мета: type=task-test, status=draft
- Таблица сценариев (Happy path, Negative)
- Таблица веток логики (ID, Ветка, Источник R/S, Слой, Тест, Ожидание, Статус)
- 13-пунктный чек-лист (tests.md §7)
- Гейт-маркеры: литералы, red-first

## Побочные эффекты
- Создаёт файлы в `.doc/tasks/{N}/tests/` (вне git)
- Создаёт симлинк в `.tools/codeception/tests/Acceptance/Task/` (вне git)
- Не меняет код проекта, не коммитит

## Окружение и зависимости
- Python 3.8+
- Стандартная библиотека: `argparse`, `pathlib`, `re`, `sys`, `datetime`
- Нет внешних зависимостей
- Codeception suite должна быть настроена на `.tools/codeception/`

## Примеры
```bash
# Создать заготовку для задачи 2236
python .agents/skills/task-router/children/testing-router/children/prepare-task-test/scripts/new-task-test.py 2236 QualityWarning

# С кастомным title
python .../new-task-test.py 2236 QualityWarning --title "Предупреждение о качестве заказа"

# Перезаписать существующий Cest
python .../new-task-test.py 2236 QualityWarning --force
```

## Ограничения
- Не пишет сами тестовые шаги — только каркас с TODO
- Не проверяет селекторы (это `check-selectors.py` позже)
- Не создаёт Page/Step объекты — они должны существовать в `Tests/Support/Page/`, `Tests/Support/Step/`
- `test.md` не перезаписывается если существует (только Cest с `--force`)
- Симлинк создаётся только если целевая папка не существует или не симлинк
- Работает только в структуре проекта с `.doc/tasks/` и `.tools/codeception/`

## Связи
- Вызывается: `prepare-task-test` SKILL.md, вручную агентом
- Зависит от: структуры `.doc/tasks/`, `.tools/codeception/`
- Результат потребляет: `check-tests.sh` (синтаксис), `task-test.sh` (прогон), `gates.py` (гейты), `check-selectors.py` (G10)
- Связанные: `prepare-task-test` SKILL.md, `test-task` SKILL.md, `testaudit.md` §9, `tests.md` §7

## История изменений
- 2026-11-07: полная документация заполнена агентом на основе кода