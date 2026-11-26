# QA: интерфейс и браузерная проверка — Индекс

<!-- meta
type: index
status: actual
updated: 2026-09-15
related: [../architecture/index.md, ../harnes/doc_rules.md]
tags: [index, qa, e2e, navigation]
-->

---

## Суть

Раздел описывает **контракт поведения UI-флоу** (что должно происходить в браузере,
какими селекторами это проверяется, каким тестом покрыто) — отдельно от
`.doc/architecture/`, где описано «как устроено по коду».

Используется скилом [`browser-verify`](../../.agents/skills/task-router/children/testing-router/children/browser-verify/SKILL.md)
для точечной проверки реализованной задачи и регрессии соседних флоу.

> **AI:** читай этот индекс перед browser-verify, не сканируй `flows/*.md` подряд —
> только флоу, пересекающиеся с `diff.files.md` задачи или прямо названные пользователем.
> **Сначала:** таблица «Флоу» ниже → нужный `flows/{name}.md`.
> **См. также:** [architecture/index.md](../architecture/index.md) — бизнес-контракт,
> на который ссылается каждый flow-документ (без копирования текста).

Как устроена тестовая система целиком (раскладка, слои Page/Step, гейты,
скрипты): [README.md](README.md). Здесь — только реестр флоу и селекторы.

---

## Конвенция селекторов `data-test`

Фронтенд (Smarty-шаблоны + legacy Vue, см. frontend.md (`../architecture/frontend.md`; missing in kit))
уже использует устойчивый атрибут-контракт в BEM-стиле:

```
data-test="блок"                  # контейнер компонента
data-test="блок__элемент"         # конкретный элемент внутри блока
```

Примеры из кода: `templates/Item/form/step2.tpl`, `templates/account/signin_new.tpl`.
Этот же атрибут уже используется в Codeception Acceptance-тестах
(`.doc/codeception/tests/Acceptance/*.php`, `AcceptanceTester::loginAsClient()`).

**Правило:** в flow-документах и проверках **предпочитай уже существующий** `data-test`
в разметке. Если атрибута нет - используй стабильные альтернативы (id, текст, BEM,
scoped XPath, `executeJS` для Vue) в тесте/фрагменте. **Не** править `templates/`
из скилов verify/prepare ради нового `data-test` - только отдельная продуктовая
задача с явным решением пользователя (см. hard rules `browser-verify` / `.doc/harnes/tests.md` §1).

**Где живут селекторы:** в Page-объектах `.doc/codeception/tests/Support/Page/`,
не в Cest задачи. Каждый `data-test` из Page сверяется с реестром
[`_map/data-test.tsv`](_map/data-test.tsv), который собирает
`collect-data-test.py` прямо из шаблонов. Переименовали атрибут - проверка
краснеет сразу, а не превращает `dontSeeElement()` в вечно зелёный.

```bash
python3 .doc/qa/scripts/collect-data-test.py   # пересобрать реестр
python3 .doc/qa/scripts/check-selectors.py     # сверить
```

---

## Как устроена браузерная проверка (два слоя)

| Слой | Инструмент | Когда | Стоимость |
|---|---|---|---|
| 1. Регрессия | **Codeception Acceptance** (`.doc/codeception/`) | Флоу уже покрыт Cest-тестом | 0 токенов LLM, детерминированно, проверяет UI **и** БД (`seeInDatabase`) |
| 2. Новая логика | **Playwright MCP** | Флоу/ветка логики без покрытия | Без LLM-затрат на клик (snapshot + click по `data-test`), только интерпретация — токены агента |

Оба слоя работают **только с видимым браузером** (headed) — требование проекта,
чтобы во время проверки можно было наблюдать за происходящим. Никаких облачных
или headless браузерных MCP.

**Как смотреть прогон на экране (WSL):**
1. `bash .agents/skills/task-router/children/testing-router/children/browser-verify/scripts/start-chromedriver-wsl.sh` — порт 9515, Chrome в WSLg
2. `bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/task-test.sh {N}` — раннер сам берёт 9515, если он жив
3. Пауза между шагами: `QA_VISIBLE_DELAY` в `.tools/codeception/.env` (по умолчанию `0`, пауза выключена; `0.3` включает показ действий)

Selenium в Docker (`:4444`) браузер на экране не показывает — только через
noVNC `http://127.0.0.1:7900`. Раннер предпочитает локальный chromedriver.

**Инфра браузера (Chrome / chromedriver / Playwright на WSL):**
[browser-setup.md](browser-setup.md) - что установлено, старт драйвера, `.env`, MCP env.

Запуск Codeception локально: [`.tools/codeception/README.md`](../../.tools/codeception/README.md)
(ссылается на browser-setup).
Playwright MCP (инструменты): [`.cursor/README.md`](../../.cursor/README.md) §playwright;
пути Chrome: [browser-setup.md](browser-setup.md).

План развития (библиотека фрагментов, тесты в папках задач, вход под пользователем
через админку, скриншоты/консоль/DOM-дельта на каждом шаге): [`.doc/harnes/tests.md`](../harnes/tests.md).

Каталог уже реализованных переиспользуемых фрагментов `AcceptanceTester`
(вход клиентом/админом, вход под произвольным `clientId`, `checkpoint()` с
консолью/скриншотом/DOM-дельтой): [`fragments.md`](fragments.md).

---

## Скилы

| Скил | Cursor/Codex | Назначение |
|---|---|---|
| `test-task` | `.cursor/skills/`, `.codex/skills/` | Оркестратор: «тестируй задачу N» → prepare-task-test (если нет Cest) → browser-verify → отчёт |
| `browser-verify` | `.cursor/skills/`, `.codex/skills/` | Проверка: слой 1 (Codeception) → слой 2 (Playwright MCP) + отчёт §8 |
| `login-as-user` | `.cursor/skills/`, `.codex/skills/` | Вход под конкретным `clientId` через админ-имперсонацию |
| `prepare-task-test` | `.cursor/skills/`, `.codex/skills/` | Конструктор Cest задачи `fragments.md` + `flows/*.md` + `test.md` |

Канон чек-листа и отчёта: [`.doc/harnes/tests.md`](../harnes/tests.md).

---

## Флоу

| Флоу | Документ | Покрыт тестом | Архитектурный контракт |
|---|---|---|---|
| Вход клиента (login) | [account-signin.md](flows/account-signin.md) | `ClientCest::iCanLoginAsClient`, `AcceptanceTester::loginAsClient()`, задача 2591 (`@group task-2591`) | authorization.md (`../architecture/authorization.md`; missing in kit) |
| Регистрация клиента (signup) | [account-signup.md](flows/account-signup.md) | задача 2591 (`@group task-2591`) | register-oauth-legacy-root-js.md (`../architecture/register-oauth-legacy-root-js.md`; missing in kit), authorization.md (`../architecture/authorization.md`; missing in kit) |
| Восстановление пароля (remind / restore) | [account-restore-password.md](flows/account-restore-password.md) | задача 2601 (`@group task-2601`) + `Page\AccountRemindRestorePage` | authorization.md (`../architecture/authorization.md`; missing in kit) §2.6, П-15, CT-2601 |
| Черновик объекта ОИС (шаги wizard) | [item-draft.md](flows/item-draft.md) | `ItemDraftCest` + `Page\WizardPage`, `Step\DepositionSteps` | deposition.md (`../architecture/deposition.md`; missing in kit), item.md (`../architecture/item.md`; missing in kit) |
| Заказ проверки качества ОИС | [order-quality-check.md](flows/order-quality-check.md) | задача 2236 (`@group task-2236`) + `Page\OrderCheckPage` | CT-2236 |
| Доступность тарифа по типу профиля | [tariff-profile-availability.md](flows/tariff-profile-availability.md) | задача 2466 (`@group task-2466`) | tariffs.md (`../architecture/tariffs.md`; missing in kit), person-profile.md (`../architecture/person-profile.md`; missing in kit), CT-2466 |
| Маркеры витрины тарифа (ограничение профиля, базовый, isOnShowcase) | [tariff-showcase-markers.md](flows/tariff-showcase-markers.md) | задача 2467 (`@group task-2467`) | tariffs.md П-14 (`../architecture/tariffs.md#п-14-маркеры-витрины-ограничение-профиля-и-базовый-2467`; missing in kit), CT-2467 |
| Скрытый тариф (Архивный) на view | [tariff-hidden-archive.md](flows/tariff-hidden-archive.md) | задача 2511 (`@group task-2511`) | tariffs.md П-15 (`../architecture/tariffs.md#п-15-скрытый-тариф-архивный-на-view-и-блок-смены-2511`; missing in kit), CT-2511 |
| Пересчёт unpaid при смене тарифа | [tariff-unpaid-recalc.md](flows/tariff-unpaid-recalc.md) | задача 2379 (`@group task-2379`) + `Page\TariffChangePage` | tariffs.md П-7 (`../architecture/tariffs.md#п-7-пересчёт-неоплаченных-заказов-при-смене-тарифа-2379`; missing in kit), orders.md (`../architecture/orders.md`; missing in kit), CT-2379 |
| D-стенды d1..d10 | d-stands-testing.md (`../archive/qa/d-stands-testing.md`; missing in kit) | доступ, админка, клиент 35, ТАБ, заказы, troubleshooting | d-stands-testing.md (`../architecture/d-stands-testing.md`; missing in kit) |
| Удаление тарифа в админке | [tariff-delete.md](flows/tariff-delete.md) | `TariffDeleteCest` (5 сценариев, id 9001-9006) | tariffs.md (`../architecture/tariffs.md`; missing in kit), promo-system.md (`../architecture/promo-system.md`; missing in kit), CT-2428 |
| Альтернативный тариф (admin select + delete-block) | [tariff-alternative.md](flows/tariff-alternative.md) | задача 2427 (`@group task-2427`) + `Page\AdminTariffEditPage` | tariffs.md П-11 (`../architecture/tariffs.md#п-11-альтернативный-тариф-при-пролонгации-2427`; missing in kit), CT-2427 |
| Полный список тарифов | [tariff-full-list.md](flows/tariff-full-list.md) | задача 2520 (`@group task-2520`) | tariffs.md (`../architecture/tariffs.md`; missing in kit) TariffFullList /tariffs/showall, CT-2520 |
| Скидка абонплаты на витрине | [tariff-showcase-discount.md](flows/tariff-showcase-discount.md) | задача 2429 (`@group task-2429`) | tariffs.md (`../architecture/tariffs.md`; missing in kit) П-9, frontend.md (`../architecture/frontend.md`; missing in kit) П-4, CT-2429 |
| Пополнение: настройки канала (kurs / isActive2 / statusDescription2) | [payments-replenishment.md](flows/payments-replenishment.md) | задача 2602 (`@group task-2602`) | payments.md (`../architecture/payments.md`; missing in kit), CT-2602 |
| Страна (адрес) в заказах ПКСР / выписка / комплект | [order-print-country.md](flows/order-print-country.md) | задача 2606 (`@group task-2606`) | orders.md (`../architecture/orders.md`; missing in kit), CT-2606 |
| Бронирование часов специалиста (4000 / 2035) | [order-booking.md](flows/order-booking.md) | задача 2548 (`@group task-2548`) | orders.md П-21 (`../architecture/orders.md#п-21-бронирование-слота-специалиста-2548`; missing in kit), CT-2548 |
| Список заказов, групповая оплата | [order-main.md](flows/order-main.md) | задача 2061 (`@group task-2061`) + `Page\OrderMainPage` | orders.md (`../architecture/orders.md`; missing in kit) П-12, payments.md (`../architecture/payments.md`; missing in kit) П-11, CT-2061 |
| Настройка сообщений в учётке (Best Value + одно окно НПУЗ) | [account-messages.md](flows/account-messages.md) | задача 2605 (`@group task-2605`), задача 2603 (`@group task-2603`) | tariffs.md (`../architecture/tariffs.md`; missing in kit) Best Value / П-16, CT-2605, CT-2603 |
| Смена логина клиента в админке | [admin-client-login.md](flows/admin-client-login.md) | задача 2597 (`@group task-2597`) + `Page\AdminClientProfilePage` | admin.md §5-6 (`../architecture/admin.md#5-клиенты`; missing in kit), CT-2597 |
| JSON SOAP на карточке ОИС (админ) | [admin-item-soap-json.md](flows/admin-item-soap-json.md) | задача 2596 (`@group task-2596`, `@group admin-item-soap-json`) | authorization.md П-13 (`../architecture/authorization.md#п-13-блок-для-администратора-на-itemview--только-admin_ids`; missing in kit), server-soap.md П-7 (`../architecture/server-soap.md#п-7-debug-json-soap-на-itemview-без-submit-2596`; missing in kit), CT-2596 |
| Заказ удаления ОИС (2030) + unpaid cancel Hidden | [order-remove.md](flows/order-remove.md) | задача 2070 (`@group task-2070`, `@group order-remove`) | orders.md П-19 (`../architecture/orders.md#п-19-заказ-удаления-оис-2030-2070`; missing in kit), П-20 (`../architecture/orders.md#п-20-отмена-неоплаченного-откатывает-hidden-2070`; missing in kit), CT-2070 |

Тесты задач лежат в `.doc/tasks/{N}/tests/`, не в общем каталоге suite.
Раскладка и причины: [README.md](README.md).

Статус раздела: `actual`; новые флоу добавляются по мере задач через `browser-verify`
(Index Gate: сначала проверь эту таблицу, не создавай дубль).

**WSL без PHP на хосте, Selenium, капча админки, dev-БД:** см.
[browser-setup.md](browser-setup.md) и cicd.md §3.5-3.6 (`../architecture/cicd.md#35-как-проводить-проверку-порядок-работ`; missing in kit).

## Как проводить проверку (кратко)

```bash
# 1. стенд и chromedriver должны быть подняты человеком, не агентом
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8030/
docker start selenium-chrome-test        # либо bash .doc/codeception/scripts/start-chromedriver-wsl.sh

# 2. быстрая проверка без браузера
bash .doc/qa/scripts/check-tests.sh

# 3. прогон: раннер сам выберет PHP, порт WebDriver и сеть
bash .doc/qa/scripts/task-test.sh 2236
bash .doc/qa/scripts/task-test.sh 2236 --group item-draft

# 4. готова ли задача (включает post-check главной)
python3 .doc/qa/scripts/gates.py 2236
```

Раньше эту цепочку приходилось собирать руками из `docker run ... php:8.3-cli`
с `host-resolver-rules`; теперь это внутри [`scripts/lib.sh`](../../.agents/skills/task-router/children/testing-router/children/test-task/scripts/lib.sh).
Ручной вариант и разбор ошибок остались в [browser-setup.md](browser-setup.md).

Полный порядок с PHPUnit и Playwright: cicd.md §3.5 (`../architecture/cicd.md#35-как-проводить-проверку-порядок-работ`; missing in kit).
Правила данных в dev-БД: cicd.md §3.6 (`../architecture/cicd.md#36-данные-acceptance-на-dev-стенде-гигиена`; missing in kit).

---

## Связи

- [`.doc/architecture/index.md`](../architecture/index.md) — бизнес-контракт и код, на которые ссылаются flow-документы
- [`.doc/harnes/doc_rules.md`](../harnes/doc_rules.md) — общие правила документации, применяются и здесь
- [`.doc/harnes/tests.md`](../harnes/tests.md) - план развития системы тестирования (фрагменты, тесты задач, вход через админку)
- [`fragments.md`](fragments.md) - каталог уже реализованных фрагментов `AcceptanceTester`
- [`browser-setup.md`](browser-setup.md) - Chrome for Testing, chromedriver, Playwright MCP на WSL
- cicd.md §3 (`../architecture/cicd.md#3-локальные-тесты-и-qa-инструменты`; missing in kit) - архитектура: слои QA, WSL/Docker, что не в CI
- [`browser-verify` (Cursor)](../../.agents/skills/task-router/children/testing-router/children/browser-verify/SKILL.md) / [`browser-verify` (Codex)](../../.codex/skills/task-router/children/testing-router/children/browser-verify/SKILL.md) - скил, использующий этот раздел
- [`.tools/codeception/README.md`](../../.tools/codeception/README.md) - запуск Acceptance-тестов

---

## История изменений

- 2026-07-09: раздел создан, добавлены флоу `account-signin` и `item-draft`
- 2026-07-09: добавлена ссылка на [`fragments.md`](fragments.md) - реализация
  первой партии фрагментов из `.doc/harnes/tests.md` (вход клиентом/админом/под
  произвольным `clientId`, `checkpoint()`)
- 2026-07-09: добавлен раздел «Скилы» (`login-as-user`, `prepare-task-test`);
  обновлена строка `item-draft` в «Флоу» - добавлены негативный тест и тест
  прав доступа
- 2026-09-15: флоу `tariff-showcase-markers` (CT-2467)
- 2026-07-16: добавлен флоу `tariff-profile-availability` (CT-2466)
- 2026-07-17: ссылка на [`browser-setup.md`](browser-setup.md) (Chrome/chromedriver/Playwright WSL)
- 2026-08-12: флоу `tariff-delete` (CT-2428); статус `actual`; cicd §3.5-3.6, browser-setup
- 2026-09-15: флоу `order-booking` (CT-2548)
- 2026-09-14: флоу `order-print-country` (CT-2606)
- 2026-09-15: флоу `account-restore-password` (CT-2601)
- 2026-09-15: флоу `tariff-full-list` (CT-2520, `/tariffs/showall`)
- 2026-09-15: флоу `order-main` (CT-2061 групповая оплата)
- 2026-09-15: флоу `account-signup` (CT-2591, Index Gate)
- 2026-09-15: флоу `order-booking` (CT-2548)
- 2026-09-15: тесты задач переехали в `.doc/tasks/{N}/tests/`, селекторы в
  Page-объекты, добавлен реестр `data-test` и раннер; общее описание
  системы вынесено в [README.md](README.md)
- 2026-09-15: флоу `order-remove` (CT-2070)
- 2026-09-15: флоу `tariff-showcase-discount` (CT-2429)
- 2026-09-15: флоу `account-messages` покрыт также CT-2603 (одно окно оплаты bool НПУЗ)
- 2026-09-15: флоу `tariff-hidden-archive` (CT-2511)
- 2026-09-15: флоу `tariff-alternative` (CT-2427)
- 2026-11-05: ссылки на `browser-verify` переведены на `.agents/skills/task-router/children/testing-router/children/` и `.codex/skills/task-router/children/testing-router/children/`.
- 2026-09-15: флоу `tariff-unpaid-recalc` (CT-2379)
- 2026-09-15: флоу `admin-item-soap-json` (CT-2596)
- 2026-09-15: флоу `admin-client-login` (CT-2597)
