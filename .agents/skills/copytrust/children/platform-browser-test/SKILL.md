---
name: platform-browser-test
description: >-
  Браузерная проверка задачи CopyTrust на выбранной площадке: локальный стенд
  или удалённый d-стенд. Скил спрашивает площадку, если она не названа, проводит
  авторизацию, вход под нужной ролью или клиентом и выполняет сценарий задачи.
  Заказ это частный случай. Use when the user says проверь задачу в браузере,
  браузерная проверка задачи, на какой площадке тестировать, локальный стенд,
  d8, зайди в админку, войди под клиентом, открой страницу задачи.
---

# platform-browser-test

Механизм браузерной проверки любой задачи CopyTrust. Скил не задаёт один
фиксированный сценарий: он выбирает площадку, получает доступ, входит под
нужной ролью и выполняет шаги из задачи. Проверка заказа это один из случаев.

## Когда применять

- нужно проверить задачу Jira в браузере на локальном стенде или на d-стенде;
- нужно воспроизвести поведение под конкретным клиентом или администратором;
- нужно проверить ветку, для которой нет Cest или PHPUnit метода;
- нужно снять доказательства для отчёта: страницы, DOM, скриншоты.

## Вход

| Параметр | Обязателен | Значение |
|---|---|---|
| Номер задачи | да | Jira `2077` или номер заказа, если задача про заказ |
| Площадка | да | `local` (локальный стенд) или `d1`, `d2`, `d4`, `d5`, `d8`, `d9`, `d10` |
| Роль | нет | администратор, клиент, гость; определяется сценарием задачи |
| clientId | нет | если сценарий идёт под клиентом |
| Сценарий | да | шаги и ожидаемый результат из `task.md` и `plan.md` |

Если площадка не названа, спросить её до первого действия:

```
Где тестировать: локально (http://localhost:8030/) или на d-стенде (каком)?
```

Не подставлять d8 молча и не начинать проверку без ответа. Если пользователь
уже назвал площадку или она следует из задачи, вопрос не задавать.

## Выбор площадки

| Площадка | URL | Особенности |
|---|---|---|
| local dev | `http://localhost:8030/` | сайт в `.tools/docker-dev`, PHP 7.1, есть dev-login и Codeception |
| local test | `http://127.0.0.1:8230/` | стенд `.tools/docker-test`, если он поднят |
| d1, d2, d4, d5, d8, d9, d10 | `https://www.d<номер>.copytrust.ru` | Basic, антибот 1Gb, форма админки, общие данные |

Прод не использовать. Локальный стенд без спроса не поднимать и не перезапускать:
сначала проверить доступность, затем спросить.

## Доступ и вход

### Локальный стенд

Проверить, что стенд отвечает. Проверку делать вне sandbox, иначе `000` на
`localhost:8030` ничего не доказывает.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8030/
```

Вход без пароля только для dev/test:

| Роль | Запрос |
|---|---|
| Администратор | `GET http://localhost:8030/.tools/codeception/scripts/dev-login.php?as=admin` |
| Клиент | `GET http://localhost:8030/.tools/codeception/scripts/dev-login.php?as=client&id=<clientId>` |

После dev-login открыть нужную страницу: `/admin/`, `/account/edit`,
`/order/view/<id>` или страницу из сценария задачи. Dev-login ставит cookie
`login` и `pass`, поэтому POST-форма и SmartCaptcha не нужны.

### Удалённый d-стенд

1. HTTP Basic. В Playwright задать заголовок контекста, в консоли или curl
   передать `-u <basicUser>:<basicPass>`. Значения доступов брать в
   `.doc/qa/d-stands-testing.md`, раздел "Доступ", в скил их не копировать.
2. Антибот 1Gb. Если открылась страница "Доступ в панель управления сайтом",
   дождаться автоматического перехода или нажать "ВОЙТИ". Скрипт страницы
   отправляет `ip` и `ipflag` на `/ipsec_set_cookies` и перезагружает страницу.
3. Форма администратора. `POST /admin/index.php` с полями `login` и `pass`.
   Если включена SmartCaptcha, поставить галку в iframe
   `smartcaptcha.cloud.yandex.ru`. После входа открывается `|Admin Mode|`.
4. Вход под клиентом. `POST /admin/m_router.php?q=client/login-by-client` с телом
   `id=<clientId>&clientId=<clientId>`. Ожидается `200` и `{"success":true}`.
   Затем открыть `/account/edit` и сверить e-mail и ФИО клиента.
5. Проверить версию стенда. В подвале клиентских страниц указано
   `COPYTRUST, <версия>`. Тестировать сценарий другой версии нельзя. Наблюдение
   2026-11-05: d8 отдавал `5.6.0.5`.

### Админские и клиентские URL

| Что | Локально и на d-стенде |
|---|---|
| Главная админки | `/admin/editor.php` |
| Список заказов | `/admin/m_order.php?pending=0` |
| Неоплаченные заказы | `/admin/m_order.php?pending=1` |
| Клиент | `/admin/m_router.php?q=client/edit/{clientId}` |
| Список клиентов | `/admin/m_router.php?q=client/list` |
| Кабинет клиента | `/account/edit` |
| Карточка заказа | `/order/view/{orderId}` |

`/admin/m_router.php?q=order/view/{id}` не существует и отдаёт 404. Карточка
заказа открывается через клиентский маршрут после входа под клиентом.

## Сценарий задачи

Сценарий берётся из задачи, а не придумывается. Перед проверкой прочитать:

| Файл | Что даёт |
|---|---|
| `.doc/tasks/{N}/task.md` | требования, комментарии, заказы, клиенты, UIN |
| `.doc/tasks/{N}/doc.md` | принятые решения и текущий статус |
| `.doc/tasks/{N}/plan.md` | этапы, ожидаемое поведение, проверки |
| `.doc/tasks/{N}/diff.md` | что именно изменено |
| `.doc/tasks/{N}/test.md` и `ac-matrix.json` | ветки логики и готовые сценарии |

Из задачи собрать чеклист: роль, точка входа, шаги, ожидаемый результат, данные
для проверки. Если для локального стенда есть Cest, сначала запустить
`test-task` или `browser-verify`, а этот скил использовать для ручных веток и
удалённых стендов.

## Шаги

1. Определить номер задачи и площадку. Если площадки нет, задать вопрос из
   раздела "Вход".
2. Прочитать пакет задачи и собрать чеклист проверки.
3. Проверить доступность площадки и версию.
4. Получить доступ: dev-login на локальном стенде или цепочку Basic, антибот и
   форма на d-стенде.
5. Войти под ролью из сценария: администратор, клиент или гость.
6. Выполнить шаги сценария. На каждом шаге фиксировать URL, видимый текст и
   изменение состояния.
7. Сверить результат с ожидаемым. При ошибке собрать текст ошибки, консоль
   браузера и сетевые ответы.
8. Сохранить доказательства в
   `.doc/tasks/{N}/test-runs/{date}_{platform}-browser/`.
9. Вернуть отчёт: что проверено, что совпало, что расходится.

## Пример Playwright

Локальный стенд, вход администратором:

```js
async (page) => {
  await page.goto('http://localhost:8030/.tools/codeception/scripts/dev-login.php?as=admin');
  await page.goto('http://localhost:8030/admin/editor.php', { waitUntil: 'domcontentloaded' });
  return await page.evaluate(() => document.body.innerText.slice(0, 2000));
}
```

Локальный стенд, вход клиентом:

```js
async (page, clientId) => {
  await page.goto('http://localhost:8030/.tools/codeception/scripts/dev-login.php?as=client&id=' + clientId);
  await page.goto('http://localhost:8030/account/edit', { waitUntil: 'domcontentloaded' });
  return await page.evaluate(() => document.body.innerText.slice(0, 2000));
}
```

Удалённый d-стенд:

```js
async (page, taskUrl, clientId) => {
  const basic = 'Basic ' + Buffer.from('<basicUser>:<basicPass>').toString('base64');
  await page.context().setExtraHTTPHeaders({ Authorization: basic });
  await page.goto('https://www.d8.copytrust.ru/admin/', { waitUntil: 'domcontentloaded' });

  if (await page.locator('input[name="login"]').count()) {
    await page.fill('input[name="login"]', '<adminLogin>');
    await page.fill('input[name="pass"]', '<adminPass>');
    await page.click('input[type="submit"], button[type="submit"]');
    await page.waitForLoadState('domcontentloaded');
  }
  if (!/editor\.php/.test(page.url())) {
    await page.goto('https://www.d8.copytrust.ru/admin/editor.php', { waitUntil: 'domcontentloaded' });
  }
  if (clientId) {
    await page.evaluate(async (id) => {
      await fetch('/admin/m_router.php?q=client/login-by-client', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body: 'id=' + encodeURIComponent(id) + '&clientId=' + encodeURIComponent(id),
      });
    }, clientId);
  }
  await page.goto(taskUrl, { waitUntil: 'domcontentloaded' });
  return await page.evaluate(() => document.body.innerText.replace(/\s+/g, ' ').slice(0, 6000));
}
```

В браузере без Node `Buffer` заголовок Basic собирается через `btoa`.

## Проверки

| Что | Как проверить | Признак ошибки |
|---|---|---|
| Условия задачи | каждый пункт Acceptance criteria из `task.md` и `plan.md` | пункт не выполняется |
| UI | нужный блок, текст, кнопка, поле, статус на странице | блок отсутствует или показывает другое |
| Роль | доступность действия под администратором, клиентом и гостем | действие доступно не той роли |
| Данные | карточка, список, счётчик, сумма, статус | значения расходятся с ожидаемыми |
| Ошибки | текст ошибки, консоль браузера, сетевые ответы | ошибка или пустой ответ |
| Регрессия | соседний флоу из `.doc/qa/index.md` | соседний сценарий сломан |

## Частный случай: заказ

Если задача про заказ, к общим проверкам добавить поля карточки:

| Поле | Ожидание |
|---|---|
| Статус | совпадает со сценарием задачи |
| Сумма | совпадает с платежами заказа |
| Ресурсы | все ОИС заказа на месте |
| Комментарий | есть отправка, ответ, успех или текст ошибки |
| Скачивание | доступно только в разрешённых статусах |

## Выход

- отчёт: площадка, версия, задача, роль, clientId, URL, шаги;
- список проверок со статусом "совпало" или "расходится";
- пути скриншотов, текста страниц и заметок.

## Ограничения

- По умолчанию только чтение. Оплата, создание заказа, сохранение тарифов и
  изменение клиента выполняются только после явного разрешения пользователя.
- Прод не использовать: только локальный стенд и тестовые d-стенды.
- Локальный стенд без спроса не поднимать. Шаблоны и код ради теста не править.
- Пароли, cookie и персональные данные не копировать в отчёт, чат и git.
- Антибот, SmartCaptcha и доступы меняются: при расхождении свериться с
  `.doc/qa/d-stands-testing.md` и `.doc/qa/browser-setup.md`.
- Скриншот макета или вручную подставленного DOM не доказывает исправление.
- Принудительный logout не вызывать, если маршрут не подтверждён: сессию
  завершать закрытием контекста.

## Связи

- `.agents/skills/task-router/children/testing-router/children/browser-verify/SKILL.md` - браузерная проверка на локальном стенде.
- `.agents/skills/task-router/children/testing-router/children/test-task/SKILL.md` - оркестратор тестов задачи.
- `.agents/skills/login-as-user/SKILL.md` - вход под клиентом через админку.
- `.doc/qa/d-stands-testing.md` - стенды, доступы, админские URL.
- `.doc/qa/browser-setup.md` - локальный стенд, dev-login, Playwright, chromedriver.
