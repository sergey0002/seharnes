# Kaiten API (kaiten.ru)

<!-- meta
type: api
status: actual
updated: 2026-07-21
related: []
tags: [kaiten, api, rest, webhooks, scim, integrations]
sources:
  - https://developers.kaiten.ru/
  - https://kshvakov.github.io/kaiten-api/ (extract from developers.kaiten.ru, 2026-02-12)
-->

---

## Суть

Kaiten (kaiten.ru) - облачный таск-трекер (Kanban/Scrum). Публичный API: REST JSON на домене компании, Bearer-токен из профиля пользователя.

Официальный портал: [developers.kaiten.ru](https://developers.kaiten.ru/). Покрытие: REST, outbound/inbound webhooks, SCIM 2.0, bulk Import, User Metadata, Addons (OAuth, beta).

Это **не** продукт docs.kaiten.sh (другой API, токены `ksh_*`). Здесь только kaiten.ru / developers.kaiten.ru.

---

## Базовый URL и версии

| Параметр | Значение |
|----------|----------|
| Base URL | `https://<your_domain>.kaiten.ru/api/v1` |
| Latest alias | `https://<your_domain>.kaiten.ru/api/latest` |
| Content-Type | `application/json` |
| Формат | JSON REST |

`<your_domain>` - slug компании (например `acme` -> `https://acme.kaiten.ru`). On-prem: свой хост вместо `*.kaiten.ru`.

В примерах официальных docs часто `https://example.kaiten.ru/api/latest/...`.

---

## Аутентификация

### Как получить токен

1. Открыть инстанс: `https://<your_domain>.kaiten.ru`
2. Профиль -> API Key / API-ключ (`/profile/api-key`)
3. Создать токен, скопировать сразу

Публичный REST для скриптов/интеграций: Bearer API-токен. OAuth у публичного REST для обычных интеграций не используется (OAuth есть у Addons, beta).

### Заголовок

```http
Authorization: Bearer <API_TOKEN>
Accept: application/json
Content-Type: application/json
```

### Пример

```bash
curl --request GET \
  --url 'https://<your_domain>.kaiten.ru/api/latest/spaces' \
  --header 'Accept: application/json' \
  --header 'Authorization: Bearer <API_TOKEN>'
```

Ошибка `401` = невалидный/отозванный токен.

---

## Лимиты и совместимость

| Параметр | Значение |
|----------|----------|
| Rate limit | 5 запросов в секунду |
| При превышении | HTTP `429` |

Заголовки ответа:

| Header | Смысл |
|--------|-------|
| `X-RateLimit-Remaining` | сколько запросов осталось в окне |
| `X-RateLimit-Reset` | UTC epoch сброса лимита |

Параметр совместимости `broken_api` (custom properties / user id):

- по умолчанию `true` до 2026-04-01: user UID в custom properties как строки
- `false`: user id как integers
- для новых интеграций: `broken_api=false`

Типичные коды:

| Code | Смысл |
|------|-------|
| 200 / 201 / 202 | успех (202 - фоновый job, batch update) |
| 400 | validation |
| 401 | invalid token |
| 402 | фича не в тарифе |
| 403 | forbidden |
| 404 | not found |
| 409 | duplicate (SCIM) |
| 429 | rate limit |

---

## Модель сущностей (кратко)

```
Company
  └── Space (пространство)
        ├── Board (доска на space)
        │     ├── Column / Subcolumn (колонки)
        │     ├── Lane (дорожки)
        │     └── Card (карточка)
        │           ├── members, tags, comments
        │           ├── checklists, time-logs, files
        │           ├── blockers, children/parents
        │           └── custom properties
        ├── Automations
        └── Users (доступ к space)
```

Ключевые id карточки: `board_id`, `column_id`, `lane_id`. Состояние колонки: `1` queue, `2` in progress, `3` done. Состояние карточки `state`: `1` queued, `2` inProgress, `3` done. `condition`: `1` live, `2` archived (`3` deleted в части ответов).

Custom properties на карточке: объект `properties` вида `id_{propertyId}: value`.

---

## Карта API по разделам

Официальный каталог: [developers.kaiten.ru](https://developers.kaiten.ru/). Ниже - сжатый индекс (метод + путь). Детали полей - на страницах `/<group>/<operation>`.

### Spaces и boards

| Метод | Путь | Операция |
|-------|------|----------|
| POST | `/spaces` | создать space |
| GET | `/spaces` | список spaces |
| GET | `/spaces/{space_id}` | space |
| PATCH | `/spaces/{space_id}` | обновить |
| DELETE | `/spaces/{space_id}` | удалить |
| POST | `/spaces/{space_id}/boards` | создать board |
| GET | `/spaces/{space_id}/boards` | список boards |
| GET | `/spaces/{space_id}/boards/{id}` | board |
| PATCH | `/spaces/{space_id}/boards/{id}` | обновить board |
| DELETE | `/spaces/{space_id}/boards/{id}` | удалить board |
| GET | `/boards/{id}` | board без space в path |

Docs: [spaces](https://developers.kaiten.ru/spaces/retrieve-list-of-spaces), [space-boards](https://developers.kaiten.ru/space-boards/create-new-board).

### Columns, subcolumns, lanes

| Метод | Путь |
|-------|------|
| POST/GET/PATCH/DELETE | `/boards/{board_id}/columns` (+ `/{id}`) |
| POST/GET/PATCH/DELETE | `/columns/{column_id}/subcolumns` (+ `/{id}`) |
| POST/GET/PATCH/DELETE | `/boards/{board_id}/lanes` (+ `/{id}`) |

### Cards (ядро)

| Метод | Путь | Операция |
|-------|------|----------|
| POST | `/cards` | создать |
| GET | `/cards` | список (фильтры, пагинация) |
| GET | `/cards/{card_id}` | одна карточка |
| PATCH | `/cards/{card_id}` | обновить / переместить |
| PATCH | `/cards` | batch update (фон, `202` + job id) |
| DELETE | `/cards/{card_id}` | удалить |
| GET | `/cards/{card_id}/location-history` | история локаций |
| GET | `/cards/{card_id}/baselines` | baselines |

Docs: [create](https://developers.kaiten.ru/cards/create-new-card), [list](https://developers.kaiten.ru/cards/retrieve-card-list), [update](https://developers.kaiten.ru/cards/update-card).

#### Create card - тело запроса

Обязательные поля (практика интеграций + docs):

```json
{
  "title": "Название",
  "board_id": 123,
  "column_id": 456,
  "lane_id": 789
}
```

Частые опциональные: `description`, `owner_id`, `type_id`, `size` / `size_text`, `asap`, `due_date`, `planned_start`, `planned_end`, `sort_order`, `position` (`1` - в начало ячейки, `2` - в конец), `external_id`, `properties`, `service_id`.

Перемещение: `PATCH /cards/{id}` с новым `board_id` / `column_id` / `lane_id` / `sort_order`.

Список: `GET /cards` с query-фильтрами (`space_id`, `board_id`, и др.), постранично. Описание в list-ответе часто только если запрошено через `additional_card_fields`.

### Card components

| Группа | Базовый путь |
|--------|--------------|
| Blockers | `/cards/{card_id}/blockers` |
| Blocker categories | `/blockers/{blocker_id}/categories`, `/categories` |
| Blocker users | `/blockers/{blocker_id}/users`, `/users/current/blockers` |
| Tags on card | `/cards/{card_id}/tags` |
| Comments | `/cards/{card_id}/comments` |
| External links | `/cards/{card_id}/external-links` |
| Children | `/cards/{card_id}/children` |
| Members | `/cards/{card_id}/members` |
| Time logs | `/cards/{card_id}/time-logs` |
| Checklists | `/cards/{card_id}/checklists` (+ `/items`) |
| Files | `PUT/PATCH/DELETE /cards/{card_id}/files` |
| SLA | `/cards/{card_id}/sla-rules-measurements` |
| SD recipients | `/cards/{card_id}/sd-external-recipients` |
| Allowed users | `/cards/{card_id}/allowed-users` |

Глобальные теги: `POST/GET /tags`. Типы карточек: `/card-types`.

Файлы (private): `/cards/.../files`, comment files, custom-property files - отдельные private endpoints в каталоге docs.

### Users и доступ

| Метод | Путь | Примечание |
|-------|------|------------|
| GET | `/users` | список |
| GET | `/users/current` | текущий |
| PATCH | `/users/{id}` | обновить |
| CRUD | `/user-roles` | роли |
| CRUD | `/spaces/{space_id}/users` | доступ к space |
| GET/PATCH/DELETE | `/company/users` | пользователи компании |
| CRUD | `/company/groups` | группы (часть BETA) |
| | `/company/groups/{uid}/users|admins|entities` | состав групп |
| GET | `/tree-entity-roles`, `/tree-entities` | дерево сущностей |

### Custom properties и directories

| Группа | Путь |
|--------|------|
| Properties | `/company/custom-properties` |
| Select values | `.../select-values` |
| Catalog values | `.../catalog-values` |
| Collective score/vote | `/cards/{card_id}/custom-properties/{property_id}/...` |
| Directories | `/custom-directories` (+ fields, records) |

### Time, sprints, service desk

| Метод | Путь |
|-------|------|
| GET | `/time-logs` | timesheet |
| GET | `/sprints`, `/sprints/{id}` |
| GET | `/service-desk/services` |

### Automations

`/spaces/{space_id}/automations` - CRUD.

Триггеры (примеры): `card_moved_in_path`, `card_created`, `comment_posted`, `card_user_added`, `due_date_changed`, `tag_added`, `blocked`, `all_conditions_met`, ...

Действия (примеры): `add_assignee`, `add_tag`, `move_to_path`, `archive`, `add_comment`, `add_due_date`, ...

### Documents, iterations, audit

В каталоге developers.kaiten.ru также:

- Documents / document-groups / document-schemas
- Iterations (+ cards in iteration)
- Audit logs: `/audit-logs`
- Space template checklists

### Tags, checklists (глобальные)

| Метод | Путь |
|-------|------|
| POST/GET | `/tags` |
| GET | `/checklists/{id}` | карточки с чеклистом |
| POST/PATCH/DELETE | `/checklists/{id}/items` |

---

## Webhooks

### Outbound (Kaiten -> ваш URL)

Подписка на события, HTTP POST на ваш endpoint.

Регистрация (по extract docs): `POST https://<your_domain>.kaiten.ru/api/latest/webhooks`

Обзор: [Webhooks](https://developers.kaiten.ru/webhooks). Есть интеграция Sentry.

События:

| Event | Смысл |
|-------|-------|
| `card:add` / `card:update` | карточка |
| `block:add` / `block:update` | блокер |
| `comment:add` / `update` / `remove` | комментарий |
| `timelog:add` / `update` / `remove` | таймлог |
| `tag:add` / `update` / `remove` | тег |
| `board:add` / `board:update` | доска |
| `file:add` / `update` / `remove` | файл |
| `space:update` | space |
| `card_member:add` / `update` / `remove` | участник (`update` - когда назначают ответственного) |

### External / inbound (внешняя система -> Kaiten)

Входящие webhooks: события снаружи создают/меняют сущности в Kaiten.

Обзор: [External Webhooks](https://developers.kaiten.ru/external-webhooks).

Операции в каталоге: `card:add|update`, `block:*`, `comment:*`, `timelog:*`, `tag:*`, `board:add|update`, `file:*`, `space:update`, `card_member:*`.

---

## SCIM 2.0

Base: `https://<your_domain>.kaiten.ru/api/latest/scim`

| Метод | Путь | Примечание |
|-------|------|------------|
| GET/POST | `/Users` | список / создать (`201`, `409` duplicate email) |
| GET/PATCH | `/Users/{user_id}` | PATCH: `active`, `name` |
| GET/POST | `/Groups` | |
| GET/PATCH | `/Groups/{group_id}` | PATCH: `displayName`, `members` |

Обзор: [SCIM](https://developers.kaiten.ru/scim) (раздел на портале).

Не путать с обычным `/users` (lowercase) REST API.

---

## Import API

Bulk-импорт через набор JSON-файлов. Точка входа: `meta-data.json` с `entities` и `entities_paths_map`.

Сущности схем: boards, cards, card-timers, columns, columns-mapping, comments, custom-fields, documents, document-files, files, folders, properties-mapping, spaces, users.

`properties_mapping`: сопоставление внешних id кастомных полей с внутренними id Kaiten, чтобы не плодить дубликаты.

Цвета типов/карточек (appendix): id `1..16` (`red`, `pink`, ..., `blueGrey`).

Docs: [Imports](https://developers.kaiten.ru/) (раздел Imports на портале).

---

## Addons и User Metadata

- **Addons**: кастомные расширения UI/логики; secrets, styling, error handling; API access через OAuth (beta). Каталог: раздел Addons на [developers.kaiten.ru](https://developers.kaiten.ru/).
- **User Metadata**: кастомные метаданные пользователей.

---

## Примеры рабочих сценариев

### 1. Список spaces

```bash
curl -sS \
  -H "Authorization: Bearer $KAITEN_TOKEN" \
  -H "Accept: application/json" \
  "https://$KAITEN_DOMAIN/api/latest/spaces"
```

### 2. Создать карточку

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $KAITEN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Test","board_id":1,"column_id":2,"lane_id":3}' \
  "https://$KAITEN_DOMAIN/api/latest/cards"
```

### 3. Переместить карточку

```bash
curl -sS -X PATCH \
  -H "Authorization: Bearer $KAITEN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"column_id":10,"lane_id":3,"position":1}' \
  "https://$KAITEN_DOMAIN/api/latest/cards/42"
```

### 4. Комментарий

```bash
curl -sS -X POST \
  -H "Authorization: Bearer $KAITEN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"text":"hello from API"}' \
  "https://$KAITEN_DOMAIN/api/latest/cards/42/comments"
```

### 5. Текущий пользователь (smoke-check токена)

```bash
curl -sS \
  -H "Authorization: Bearer $KAITEN_TOKEN" \
  "https://$KAITEN_DOMAIN/api/latest/users/current"
```

Переменные:

| Env | Пример |
|-----|--------|
| `KAITEN_DOMAIN` | `acme.kaiten.ru` |
| `KAITEN_TOKEN` | токен из профиля |

---

## Источники (что читать дальше)

| Источник | Зачем |
|----------|-------|
| [developers.kaiten.ru](https://developers.kaiten.ru/) | канон: полный каталог операций |
| [cards/create-new-card](https://developers.kaiten.ru/cards/create-new-card) | создание карточки |
| [cards/retrieve-card-list](https://developers.kaiten.ru/cards/retrieve-card-list) | фильтры списка |
| [webhooks](https://developers.kaiten.ru/webhooks) | outbound events |
| [external-webhooks](https://developers.kaiten.ru/external-webhooks) | inbound events |
| [kshvakov.github.io/kaiten-api](https://kshvakov.github.io/kaiten-api/) | полный текстовый extract OpenAPI/docs (2026-02-12), удобно для офлайн-поиска |
| support@kaiten.ru | вопросы по интеграции |

Портал docs рендерится как SPA: сырой HTML малоинформативен, детали смотреть в интерактивной странице операции или в extract выше.

---

## Связи

- [Правила документации проекта](../harnes/doc_rules.md) - формат `.doc/`
- Внешний канон: [developers.kaiten.ru](https://developers.kaiten.ru/)

---

## Известные проблемы и ограничения

### П-1: Путать с kaiten.sh

- Симптом: в примерах токены `ksh_*`, base `api.kaiten.sh`
- Причина: другой продукт с похожим именем
- Решение: для kaiten.ru использовать `https://<domain>.kaiten.ru/api/latest` и Bearer из `/profile/api-key`

### П-2: Rate limit 5 rps

- Симптом: `429`, массовый sync падает
- Решение: очередь, backoff по `X-RateLimit-Reset`, батчи где есть (`PATCH /cards`)

### П-3: SPA docs плохо парсятся автоматически

- Симптом: fetch страницы операции отдаёт только оглавление
- Решение: открывать конкретный URL в браузере или использовать extract [kshvakov.github.io/kaiten-api](https://kshvakov.github.io/kaiten-api/)

### П-4: `broken_api` до 2026-04-01

- Симптом: типы user id в custom properties отличаются
- Решение: явно `broken_api=false` в новых интеграциях

### П-5: Тарифные фичи

- Симптом: `402` на SCIM / automations / части endpoints
- Решение: сверить тариф, писать в support@kaiten.ru

### П-6: Пагинация и объём list cards

- Симптом: огромные ответы, таймауты
- Решение: фильтры `board_id`/`space_id`, limit/offset, не тянуть `description` без нужды

---

## История изменений

- 2026-07-21: первичный ресерч API kaiten.ru, сохранён сжатый справочник в `.doc/kaiten/doc.md` (каталог endpoints, auth, webhooks, SCIM, import, примеры)
