# Типы записи

В поставке 14 JSON-плагинов:

`mirror`, `default`, `intake`, `planning`, `plan-audit`, `research`, `libs-research`,
`feature`, `fix`, `small-fix`, `test-prep`, `testing`, `code-review`, `doc`.

Каждый тип имеет `type.json` и `instruction.md`; у части типов есть `agents/*.json`.
Тип может также объявить `fields`, `capabilities`, `checks`, `editor`, `profile`.

```bash
tcheck types list
tcheck types show research
tcheck types fields planning
```

Выбирай тип по способу работы и гейтам, а не по красивому имени:

- `mirror` — только импортируемый внешний источник;
- `intake` — формализация сырого входа;
- `research`/`planning` — знание и план; `planning` также оставляет
  `implementation_plan` и `slice_list`, если preset использует fan-out;
- `plan-audit` — read-only независимая проверка плана с `approved`, `changes_required` или `blocked`;
- `feature`/`fix`/`small-fix` — изменения продукта;
- `test-prep`/`testing` — подготовка и фактический прогон;
- `code-review` — ревью;
- `doc` — документация;
- `default` — работа без особой формы;
- `libs-research` — выбор библиотеки.

После создания тип не меняется. Смена типа — child record с `--parent` и
указателем. Поля `extra` проверяются только объявлением типа; не добавляй
произвольные числовые квоты текста.
