---
name: platform-logs
description: >-
  Чтение логов площадки CopyTrust через админский DbLog: параметры запроса,
  пагинация, фильтры, поиск по номеру заказа, UIN, e-mail клиента и taskId,
  разбор таймлайна и поиск заказов. Use when the user says логи площадки, логи
  заказа, что в логах по заказу, ct_log, DbLog, ошибки по заказу, найди заказ в
  логах, таймлайн заказа, copytrust logs, platform logs.
---

# platform-logs

Чтение `ct_log` через админскую страницу DbLog. Скил описывает endpoint как API:
все параметры поиска, формат ответа, разбор строк и оптимальный поиск по времени
и идентификатору. Работает в браузере на стенде; консольный вызов дан как
резервный путь.

## Когда применять

- нужно найти события по номеру заказа (`1359` или `1359/1126`), UIN, e-mail
  клиента, taskId или тексту ошибки;
- нужно восстановить таймлайн автоматического заказа: отправка, ответ реестра,
  задача, `TaskFinished` или `TaskFailed`, смена статуса;
- нужно понять, почему заказ завис или не сменил статус;
- нужно найти заказ или клиента по идентификатору перед браузерной проверкой.

## Вход

| Параметр | Обязателен | Значение |
|---|---|---|
| Стенд | нет | `d8` по умолчанию; `d1`, `d2`, `d4`, `d5`, `d8`, `d9`, `d10` |
| Идентификатор | да | номер заказа, UIN, e-mail, taskId или номер задачи Jira |
| Период | нет | дата и время события; без периода ищется последняя страница |
| Категория | нет | `INFO`, `ERR`, `NB`, `TIME`; по умолчанию все |

## API DbLog

Админская страница читает таблицу `ct_log` и отдаёт готовый HTML. Отдельного
JSON API нет, фильтра по тексту и дате на сервере нет.

`GET https://www.<stand>.copytrust.ru/admin/m_dblog.php`

| Параметр | Тип | По умолчанию | Что делает |
|---|---|---|---|
| `page` | число | `1` | номер страницы, 100 строк на страницу, сортировка по `id` по убыванию |
| `notimes` | флаг | выключен | скрывает строки категории `TIME` |
| `errorsonly` | флаг | выключен | оставляет только `category = 'ERR'` |
| `errnb` | флаг | выключен | оставляет `category IN ('ERR','NB')` |

Флаг передаётся любым непустым значением, например `notimes=on`.

Ответ: HTML-таблица. Колонки строки:

| Колонка | Что содержит |
|---|---|
| Time | дата и время вида `YYYY-MM-DD H:MM:SS`, часовой пояс стенда |
| Cat | `INFO`, `ERR`, `NB` или `TIME` |
| Description | текст события; на экране обрезан до 130 символов, полный текст лежит в скрытом `div#div{id}` |
| User | e-mail клиента, если он привязан к записи |
| Params | URL и стек вызова; на экране обрезан, полный текст лежит в скрытом `div#url{id}` |

Особенности, без которых поиск даёт неверный результат:

1. Строки одной секунды идут в порядке `id` по убыванию. Внутри одной страницы
   это обратный хронологический порядок, между страницами порядок сбивается ещё
   сильнее. Сортировать найденные строки по `id` по возрастанию.
2. Номер `id` берётся из скрытого блока: `#div{id}` или `#url{id}` в HTML строки.
3. Полный текст описания и стека читается через `textContent`, а не через
   видимый `innerText`: скрытый блок в `innerText` не попадает.
4. Дата без ведущего нуля в часах: `2026-11-05 2:40:03`. Перед сравнением
   строк час нормализуется до двух цифр, иначе `9:00` окажется позже `12:00`.
5. Время на странице относится к часовому поясу стенда, не к поясу рабочей
   машины.

## Шаги

1. Определить стенд и идентификатор. Если дан номер задачи Jira, сначала открыть
   `.doc/tasks/{N}/task.md` и взять оттуда номера заказов, clientId и UIN.
2. Войти в админку стенда: HTTP Basic, антибот 1Gb и форма администратора.
   Доступы и порядок входа описаны в `.doc/qa/d-stands-testing.md`, раздел
   "Доступ".
3. Открыть `https://www.<stand>.copytrust.ru/admin/m_dblog.php?notimes=on`.
4. Определить страницу с нужным периодом. Быстрый путь: бинарный поиск по дате
   первой строки страницы. Медленный путь: листать `page` по одной, 100 строк за
   шаг.
5. Скачать целевую страницу и две соседние в обе стороны, чтобы не потерять
   события на границе страниц.
6. Отфильтровать строки по идентификатору регулярным выражением по колонкам
   Description, User и Params. Номер заказа и UIN искать в Description и Params,
   e-mail в User, taskId в Description.
7. Отсортировать найденные строки по `id` по возрастанию и собрать таймлайн.
8. Проверить цепочку: отправка, ответ реестра, создание задачи, обратный вызов,
   смена статуса. Отметить отсутствующие звенья.
9. Сохранить таймлайн и сырые строки в
   `.doc/skil_data/platform-logs/logs/{stand}-{query}-{stamp}.md`.

## Поиск в браузере

Открыть DevTools на странице стенда, где уже выполнен вход в админку, и выполнить
код. Он работает с той же сессией, пароль в коде не нужен. В примере стоит
`notimes=on`; уберите флаг, если нужны строки категории `TIME`.

```js
function ctLogTs(value) {
  const m = value.match(/^(\d{4}-\d{2}-\d{2}) (\d+):(\d{2}):(\d{2})$/);
  return m ? m[1] + ' ' + m[2].padStart(2, '0') + ':' + m[3] + ':' + m[4] : value;
}

async function ctLogPage(page) {
  const r = await fetch('/admin/m_dblog.php?notimes=on&page=' + page, {
    credentials: 'same-origin',
  });
  const doc = new DOMParser().parseFromString(await r.text(), 'text/html');
  return [...doc.querySelectorAll('table tr')].map((tr) => {
    const td = [...tr.querySelectorAll('td')];
    if (td.length < 4) return null;
    const c = td.map((x) => x.textContent.replace(/\s+/g, ' ').trim());
    if (!/^\d{4}-\d{2}-\d{2} \d+:\d{2}:\d{2}/.test(c[0])) return null;
    const id = (tr.innerHTML.match(/#(?:div|url)(\d+)/) || [])[1];
    return { id: id ? +id : 0, ts: ctLogTs(c[0]), cat: c[1], text: c[2], user: c[3], url: c[4] };
  }).filter(Boolean);
}

async function ctLogFind(from, to, pattern) {
  const re = new RegExp(pattern, 'i');
  from = ctLogTs(from);
  to = ctLogTs(to);
  let lo = 1;
  let hi = 1;
  let rows = await ctLogPage(1);
  while (rows.length && rows[rows.length - 1].ts > from && hi < 4096) {
    lo = hi;
    hi *= 2;
    rows = await ctLogPage(hi);
  }
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    const midRows = await ctLogPage(mid);
    if (!midRows.length) { hi = mid; continue; }
    if (midRows[0].ts >= from) lo = mid; else hi = mid;
  }
  const hits = [];
  for (let p = Math.max(1, lo - 1); p <= lo + 2; p++) {
    for (const row of await ctLogPage(p)) {
      if (row.ts >= from && row.ts <= to && re.test([row.text, row.user, row.url].join(' '))) {
        hits.push(row);
      }
    }
  }
  return hits.sort((a, b) => a.id - b.id);
}

// Пример: заказ 1360 за 03.11.2026, окно 17:30-17:40
await ctLogFind('2026-11-03 17:30:00', '2026-11-03 17:40:00', '1360|07N-5T');
```

Для поиска по всему периоду без известного времени пройти страницы от 1 вверх,
пока первая строка страницы не станет старше нужной даты. Не качать все страницы
сразу: это десятки запросов и мегабайты HTML.

## Поиск в консоли, если браузер недоступен

Basic-авторизация и антибот обязательны. Значения `ip` и `ipflag` берутся из
HTML страницы-антибота.

```bash
mkdir -p .doc/temp/platform-logs
curl -s -u '<basicUser>:<basicPass>' -c .doc/temp/platform-logs/d8.cookies \
  -b .doc/temp/platform-logs/d8.cookies \
  https://www.d8.copytrust.ru/admin/ -o .doc/temp/platform-logs/antibot.html
curl -s -u '<basicUser>:<basicPass>' -c .doc/temp/platform-logs/d8.cookies \
  -b .doc/temp/platform-logs/d8.cookies -X POST \
  -d 'ip=<ip>&ipflag=<ipflag>' https://www.d8.copytrust.ru/ipsec_set_cookies
curl -s -u '<basicUser>:<basicPass>' -c .doc/temp/platform-logs/d8.cookies \
  -b .doc/temp/platform-logs/d8.cookies -L \
  --data-urlencode 'login=<adminLogin>' --data-urlencode 'pass=<adminPass>' \
  https://www.d8.copytrust.ru/admin/index.php
curl -s -u '<basicUser>:<basicPass>' -b .doc/temp/platform-logs/d8.cookies \
  'https://www.d8.copytrust.ru/admin/m_dblog.php?notimes=on&page=2'
```

Консольный путь хуже браузерного: антибот и SmartCaptcha меняются, cookie
привязаны к IP, HTML нужно разбирать вручную. Браузер оставлять основным путём.

## Поиск заказов

| Что | Где |
|---|---|
| Все заказы | `/admin/m_order.php?pending=0` |
| Неоплаченные заказы | `/admin/m_order.php?pending=1` |
| Клиент | `/admin/m_router.php?q=client/edit/{clientId}` |
| Список клиентов | `/admin/m_router.php?q=client/list` |
| Карточка заказа | `/order/view/{orderId}` после входа под клиентом |

Карточка заказа через `/admin/m_router.php?q=order/view/{id}` отдаёт 404. Номер
заказа и clientId из списка заказов или из `task.md`; при доступе к БД заказ
ищется в таблице `ct_order`, схема проверяется через `describe_table`, колонки не
придумываются.

## Выход

- таймлайн: время, `id`, категория, событие, taskId, UIN, ссылка на стек;
- отдельный список отсутствующих звеньев, например "нет `TaskFinished` для
  taskId X";
- найденные заказы и clientId, если запрос был про поиск заказа;
- путь файла с полным сырым набором строк.

## Ограничения

- Только чтение. Никаких `UPDATE`, `DELETE`, смены статусов и повторной оплаты.
- Нет серверного поиска по тексту, дате и заказу: фильтрация только на клиенте
  после загрузки страниц.
- `errorsonly` и `errnb` не заменяют поиск по идентификатору: часть событий
  пишется в `INFO`.
- Логи могут быть очищены или ротированы: отсутствие строки не доказывает, что
  события не было, если период старше срока хранения.
- Персональные данные и cookie не копировать в отчёт и не коммитить.

## Связи

- `.doc/qa/d-stands-testing.md` - стенды, доступы, админские URL.
- `.doc/harnes/skill-format.md` - формат скила и правила маршрутизации.
