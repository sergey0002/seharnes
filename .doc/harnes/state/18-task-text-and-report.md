# Тексты задачи, бизнес-правила и отчёты

<!-- meta
type: architecture
status: actual
version: 1.0
updated: 2026-11-11
related: [../index.md, ./17-business-analyst.md, ./02-skills.md, ./03-rules.md, ./05-scripts.md, ./06-jsondoc.md, ./07-workflows.md, ../../buisnes_analis/plan.md]
tags: [harness, business-logic, texts, reports, ui, jira, activity, release]
-->

---

## Суть

Документ фиксирует изменения в текстах задачи, бизнес-правилах, change-report и
локальной панели. Главная цель: любой текст в артефакте должен быть понятен без
чтения задачи, без расшифровки кода и без восстановления контекста из чата.

Контур бизнес-анализа описан в [17-business-analyst.md](./17-business-analyst.md).
Скил `business-analyst`, его скрипты и раздел 8 этого документа сняты с харнеса
2026-11-10. Актуальны текстовый контракт, change-report и раздел про диалоги без
задачи.

---

## 1. Текстовый контракт

Общий контракт текста один: `.cursor/rules/text-style.mdc`. Он задаёт
самодостаточный тезис, простой язык, запреты и чек-лист для чата,
документации, отчётов и Jira.

Этот документ не повторяет общий контракт. Он фиксирует только решения по
текстам задачи и результаты их внедрения. Специфика артефактов живёт в
скилах-владельцах:

| Артефакт | Владелец правил |
|---|---|
| `task.md`, `brief-extract.json` | `gototask` |
| `plan.md`, AC в `task.json` | `prepare-plan` |
| `test.md`, Cest | `test-task` |
| `doc.md` | `task-doc` |
| `report-model.json` | `task-change-report` |
| комментарий Jira | `jira-report` |

Запрещено дублировать в этом документе текст `.cursor/rules/text-style.mdc`.

---

## 2. Бизнес-правила

### 2.1 Формат

Правило содержит:

- `title` до 100 символов;
- `statement` 2-4 предложения, 80-600 символов;
- `fact_type`: `business_rule`, `business_fact`, `technical_fact`, `ui_rule`;
- условия с русским текстом;
- `code_anchors` с `symbol_sha256`;
- `test_refs` или `test_status`;
- `evidence_ref` на рабочую зону аналитика.

Пример:

```text
Если клиент отменяет оплаченный заказ, вся списанная за него сумма возвращается
на лицевой счёт клиента. Возврат зачисляется на баланс клиента, а не уходит
в платёжный канал.
```

### 2.2 Где хранится

| Место | Что лежит |
|---|---|
| `task.json business_logic.facts` | только verified факты |
| `registry.json` | общий канон |
| `architecture/business-rules` | бизнес-правила |
| `architecture/technical-facts` | env, API, миграции |
| `architecture/ui-rules` | отображение и маркеры |
| `work/{N}/candidates.json` | цитаты и кандидаты |
| `quarantine.json` | не прошло проверку |

В `task.json` запрещены `quote`, `candidate`, `confidence`, `raw_text`,
`comment_body`.

### 2.3 Текущий результат

| Показатель | Значение |
|---|---:|
| Задач с фактами | 16 |
| Фактов | 54 |
| Business rules | 38 |
| Technical facts | 11 |
| UI rules | 5 |
| Anchors exact | 40 |
| Anchors partial | 14 |
| Тесты planned | 54 |
| Конфликты | 0 |
| Quarantine | 1 |

Задача 2624 не дала бизнес-правил: это техническая задача по PHP 7.4.

---

## 3. Change-report

### 3.1 Два слоя

В `report-model.json` теперь два слоя изменений:

```json
{
  "business_changes": [
    {
      "title": "Фильтр активных заказов",
      "statement": "...",
      "type": "business_rule",
      "code": ["..."],
      "tests": ["планируется"]
    }
  ],
  "changes": [
    {
      "title": "Активный список статусов",
      "before": "PENDING_STATUS_IDS = [3, 4, 5]",
      "after": "PENDING_STATUS_IDS = [3, 4, 5, 9]",
      "rationale": "Требование задачи",
      "source": "admin/lib/Objects/Order/AdminOrderController.php"
    }
  ]
}
```

- `business_changes` показывает, что меняется для бизнеса.
- `changes` остается техническим слоем.
- В панели и HTML бизнес-слой выводится первым.
- Технические изменения сворачиваются отдельно.

### 3.2 Скил

`task-change-report` обязан заполнять `business_changes[]`, если в `task.json`
есть verified `business_logic.facts`.

Схема: `.agents/skills/task-router/children/reporting-router/children/task-change-report/templates/report-model.schema.json`.
Renderer: `.agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/generate_report.py`.

### 3.3 Ограничение

Если `report-model.json` нет, полный change-report не собирается автоматически.
Бизнес-правила задачи при этом доступны в разделе “Бизнес-логика”.

---

## 4. Локальная панель

Файлы:

- `.doc/web/app/lib.php`
- `.doc/web/public/index.php`
- `.doc/web/public/assets/style.css`

### 4.1 Что добавлено

- раздел “Бизнес-логика” из `task.json business_logic.facts`;
- “Что меняется для бизнеса” из `report-model.json business_changes[]`;
- ссылка “Открыть CT-{N} в Jira” под H1;
- кликабельные связанные задачи из `relations`;
- карточки истории и принятых решений;
- метки “готово” и “не сделано” вместо `[x]` и `[ ]`.

### 4.2 Что исправлено

- `Array` в ответственных. Причина: assignee хранился объектом, PHP приводил его
  к строке. Теперь берется `name` или `displayName`.
- дубли `Комментарии Jira` и `Изменения Jira` удалены, остается лента активности;
- HTML-комментарии `<!-- ... -->` удалены из секций; служебные `meta`, `generated`, `updated`, `task-dir` и `project-root` остаются по контракту;
- пустые секции не выводятся;
- `no-release` показывается как “без релиза”;
- дублирующая секция “Связанные задачи” скрыта, вместо нее один блок ссылок.

### 4.3 Лента активности

Источник: `task.json tracker.snapshot.comments` и `tracker.snapshot.changelog`.
Для старых экспортов данные переносятся из `_jsondoc/work/tracker.json`.
Если changelog в tracker пустой, разбираются `*Changed:*` из `task.md`.

Скрипт `backfill_activity.py` удален вместе с `business-analyst` 2026-11-10.
Старые экспорты без `snapshot.comments` и `changelog` требуют повторного `gototask`.

### 4.4 Диалоги без задачи

Чекбокс в фильтре правого меню, по умолчанию выключен. При включении в списке
появляются сессии из `.doc/task-analytics/out/unassigned/` с заголовком из
первого сообщения, а клик открывает страницу их детерминированных метрик без
ИИ. Графики и таблицы метрик общие с блоком диалогов задачи. У задачи те же
таблицы показывают сводку по всем ее сессиям.

Подробности: [README панели](../../web/README.md#диалоги-без-задачи).

---

## 5. Релизы

Причина “без релиза”: `metadata.release` отсутствовал в старых `task.json`,
хотя в `task.md` был `Version`.

Сделано:

- 119 задач получили `metadata.release` из `task.md`;
- 39 задач остались без релиза, потому что Version нет в источнике;
- панель показывает “без релиза” вместо `no-release`.

---

## 6. Покрытие условий

Таблица покрытия формируется в `doc.md` из `task.json sections`, скил `task-doc`.

Формат:

| Условие | Где проверено | Статус |
|---|---|---|
| Если заказ оплачен и обработка началась, заказ переходит из статуса Оплачен в статус В работе. | cron, продление, удаление, архивация, ONCERT | закрыто проверкой |

Правила:

- условие пишется как самостоятельное утверждение;
- код и методы только в колонке “Где проверено”;
- без стрелок `→`;
- без контекста задачи;
- статус явный: закрыто тестом, закрыто проверкой, закрыто после #N, вне задачи.

Для 2077 и 2354 таблицы переписаны. Методы `cancelWithFullRefund`,
`partialComplete`, `isClientCancelForbidden` перенесены в “Где проверено”.

---

## 7. JSONdoc

Изменения:

- `document.schema.json`: добавлено `business_logic`;
- `contract.py`: `business_logic` разрешён в `set` whitelist;
- `update.schema.json` и `document.schema.json`: actor `business-analyst`;
- `promote_rules.py` пишет `business_logic` через `Store.apply`;
- `ingest-tracker` не затирает `business_logic`.

---

## 8. Скрипты

| Скрипт | Роль |
|---|---|
| `jira_sync.py` | tracker/task JSON -> `jira.json` |
| `extract_rules.py` | `prepare` и `commit`, без эвристики |
| `resolve_anchors.py` | проверка agent anchors и fallback |
| `verify_rules.py` | score, checks, quarantine |
| `promote_rules.py` | verified facts -> task.json |
| `aggregate_rules.py` | facts -> registry |
| `render_rules.py` | registry -> business/technical/ui docs |
| `impact_rules.py` | diff -> test-matrix |
| `test_impact.py` | matrix -> test-plan |
| `auto_run.py` | prepare и оркестрация |
| `validate_state.py` | схемы, хеши, запрещённые поля |
| `check-doc-text.py` | текст `doc.md`: baseline по секциям, номера строк; служебные комментарии и inline-код не считаются ошибкой |
| `rollback_rules.py` | откат registry |

---

## 9. Проверка

- 9 тестов: зелёные.
- `validate_state --root .`: `ok: true`, 0 ошибок.
- `check-links.py --root .doc/harnes`: 0 битых ссылок.
- `check-links.py --root .doc/architecture`: 0 битых ссылок.
- На странице задач `Array`: 0.
- Дубли `Комментарии Jira` и `Изменения Jira`: 0.
- Неслужебные HTML-комментарии в секциях: 0; служебные `meta`, `generated`, `updated`, `task-dir`, `project-root` разрешены.

---

## 10. Что осталось

- 14 anchors остаются partial: доменный класс или общий метод.
- 54 теста имеют статус `planned`.
- Не все старые `doc.md` переписаны под новый текстовый контракт.
- `test-task --impact` пока не запускает тесты по test-plan.
- Для задач без `report-model.json` нет полного HTML-отчёта, только бизнес-правила.

---

## Связи

- [Автономный бизнес-анализ](./17-business-analyst.md)
- [Скилы](./02-skills.md)
- [Рулесы](./03-rules.md)
- [Скрипты](./05-scripts.md)
- [JSONdoc](./06-jsondoc.md)
- [Workflows](./07-workflows.md)
- План business analyst в архиве проекта Target
- [Скил task-change-report](../../../.agents/skills/task-router/children/reporting-router/children/task-change-report/SKILL.md)

---

## История изменений

- 2026-10-30: создан документ по текстам задачи, бизнес-правилам, change-report, панели, активности и релизам.
- 2026-11-02: в панель добавлен фильтр “Диалоги без задач” и страница метрик сессии.
- 2026-11-03: текстовый контракт сведён к ссылке на `.cursor/rules/text-style.mdc`; дубли из документа и скилов удалены.
- 2026-11-06: `check-doc-text.py` исключает inline-код, цитаты и служебные комментарии, проверяет только изменившиеся секции по baseline и печатает номера строк; добавлена команда `jsondoc.py validate --task|--arch|--all --links`.
- 2026-11-11: путь диалогов без задачи исправлен на `.doc/task-analytics/out/unassigned/`; `backfill_activity.py` и скрипты бизнес-анализа помечены удаленными вместе с `business-analyst`.
