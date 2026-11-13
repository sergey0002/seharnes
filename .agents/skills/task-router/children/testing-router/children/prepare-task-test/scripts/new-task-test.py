#!/usr/bin/env python3
"""Заготовка теста задачи: Cest + test.md по правилам новой раскладки.

    python3 .agents/skills/task-router/children/testing-router/children/prepare-task-test/scripts/new-task-test.py 2236 QualityWarning

Создаёт:
    .doc/tasks/2236/tests/QualityWarningCest.php
    .doc/tasks/2236/test.md                       (если ещё нет)
    симлинк .tools/codeception/tests/Acceptance/Task/2236

Заготовка намеренно не пустая: в ней уже стоят @group task-N,
devLoginAsClient, initConsoleCapture, checkpoint и места под проверки
БД и литералов — то есть ровно те пункты, которые проверяют гейты.
Агенту остаётся подставить логику задачи, а не вспоминать каркас.
"""

import argparse
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
TASKS = REPO / ".doc/tasks"
TASK_SUITE = REPO / ".tools/codeception/tests/Acceptance/Task"

CEST = '''<?php

declare(strict_types=1);

namespace Tests\\Acceptance\\Task\\T{task};

use Tests\\Support\\AcceptanceTester;

/**
 * CT-{task}: {title}
 *
 * Задача:  .doc/tasks/{task}/task.md
 * План:    .doc/tasks/{task}/plan.md
 * Сценарии: .doc/tasks/{task}/test.md
 *
 * Селекторы сюда не пишем — они в Tests\\Support\\Page\\*.
 * Проверяет check-selectors.py (гейт G10).
 */
final class {cls}Cest
{{
    public function _before(AcceptanceTester $I): void
    {{
        $I->haveInDbDefaultClient();
        $I->devLoginAsClient(1);
        $I->initConsoleCapture();
    }}

    /**
     * @group task-{task}
     */
    public function happyPath(AcceptanceTester $I): void
    {{
        // TODO шаги через Page/Step, например:
        // $I->wizardPage()->open();

        $I->checkpoint('{task}-happy-path');

        // TODO проверка UI по литералу из task.md:
        // $I->see('точная формулировка из задачи');

        // TODO проверка эффекта в БД (гейт G6):
        // $I->seeInDatabase('ct_item', ['id' => 1, 'name' => '...']);

        $I->seeNoConsoleErrors();
        $I->dontSeeErrorModal();
    }}

    /**
     * Негативный сценарий: чего быть НЕ должно.
     * Без него тест зелёный на любой реализации.
     *
     * @group task-{task}
     */
    public function negativeCase(AcceptanceTester $I): void
    {{
        // TODO
        $I->checkpoint('{task}-negative');
    }}
}}
'''

TEST_MD = """# Тесты задачи CT-{task}

<!-- meta
type: task-test
status: draft
updated: {today}
related: [task.md, plan.md, ../../tests.md, ../../qa/index.md]
tags: [qa, task-{task}]
-->

## Что проверяем

{title}

Источник требований: [task.md](task.md).

## Как гонять

```bash
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh            # быстрая проверка без браузера
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {task}          # прогон + артефакты + verdict.json
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py {task}           # гейты готовности
```

Тесты: [tests/](tests/). Результаты прогонов: [test-runs/](test-runs/).

## Сценарии

| Сценарий | Тест | Ожидание |
|---|---|---|
| Happy path | `{cls}Cest::happyPath` | TODO |
| Негативный | `{cls}Cest::negativeCase` | TODO |

## Ветки логики

Канон: [testaudit.md §9](../../testaudit.md#9-когда-проверять-и-что-считать-веткой).
Одна строка = один наблюдаемый исход из Decomposition (R/S) или из диффа.
`open` и `partial` не дают готовность, это проверяет гейт G13.

| ID | Ветка | Источник | Слой | Тест | Ожидание | Статус |
|---|---|---|---|---|---|---|
| B1 | TODO | R1 / S1 | cest | `{cls}Cest::happyPath` | TODO | open |

## Чек-лист

13 категорий из [tests.md §7](../../tests.md). Отмечай:
`[x]` покрыто, `[-]` неприменимо + причина, `[~]` частично + чем добираем.
Пустых `[ ]` быть не должно — гейт G5 их не пропустит.

- [ ] 1. Happy path
- [ ] 2. Негативные сценарии
- [ ] 3. Серверные и глобальные ошибки
- [ ] 4. Уведомления и сообщения
- [ ] 5. Побочные эффекты в БД
- [ ] 6. Консоль браузера
- [ ] 7. Network
- [ ] 8. Скриншот шага
- [ ] 9. DOM-дельта
- [ ] 10. Идемпотентность
- [ ] 11. Права доступа
- [ ] 12. Состояние после reload
- [ ] 13. Соседние флоу, регрессия

Категории 6, 8, 9 закрываются автоматически, если в тесте есть
`checkpoint()`: он снимает скриншот, консоль и дельту DOM.

## Отдельные отметки для гейтов

- [ ] Литералы из task.md закреплены в тестах: «TODO точная формулировка»
- [ ] Red-first: тест падал до фикса (только для задач-ошибок, иначе `[-]`)

## Известные ограничения

TODO или «нет».
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", help="номер задачи, только цифры")
    ap.add_argument("name", help="имя Cest без суффикса, например QualityWarning")
    ap.add_argument("--title", default="TODO краткое описание", help="описание для шапки")
    ap.add_argument("--force", action="store_true", help="перезаписать Cest")
    args = ap.parse_args()

    if not args.task.isdigit():
        sys.exit("номер задачи — только цифры")
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", args.name):
        sys.exit("имя Cest — CamelCase без суффикса Cest, например QualityWarning")

    from datetime import date

    task_dir = TASKS / args.task
    tests_dir = task_dir / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "test-runs").mkdir(exist_ok=True)

    cest = tests_dir / f"{args.name}Cest.php"
    if cest.exists() and not args.force:
        sys.exit(f"{cest.relative_to(REPO)} уже есть, нужен --force")

    fields = {"task": args.task, "cls": args.name, "title": args.title,
              "today": date.today().isoformat()}

    cest.write_text(CEST.format(**fields), encoding="utf-8")
    print(f"создан {cest.relative_to(REPO)}")

    test_md = task_dir / "test.md"
    if test_md.exists():
        print(f"пропущен {test_md.relative_to(REPO)} (уже есть)")
    else:
        test_md.write_text(TEST_MD.format(**fields), encoding="utf-8")
        print(f"создан {test_md.relative_to(REPO)}")

    TASK_SUITE.mkdir(parents=True, exist_ok=True)
    link = TASK_SUITE / args.task
    if link.is_symlink():
        link.unlink()
    if not link.exists():
        link.symlink_to(f"../../../../../.doc/tasks/{args.task}/tests")
        print(f"симлинк Task/{args.task} -> ../../../../../.doc/tasks/{args.task}/tests")

    print("\nДальше:")
    print(f"  1. заполни сценарии в .doc/tasks/{args.task}/test.md")
    print(f"  2. допиши шаги в {cest.relative_to(REPO)} через Page/Step")
    print("  3. bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/check-tests.sh")
    print(f"  4. bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {args.task}")
    print(f"  5. python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py {args.task}")


if __name__ == "__main__":
    main()
