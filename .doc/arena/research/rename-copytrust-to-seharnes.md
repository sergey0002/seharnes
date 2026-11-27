# План: де-брендинг харнеса copytrust → seharnes

<!-- meta
type: plan
status: draft
updated: 2026-11-26
related: [../README.md, ../../harnes/doc_rules.md]
tags: [plan, rename, harness, seharnes]
-->

---

## Суть

Харнес должен быть **универсальным**, а «copytrust» — это конкретный продукт/проект.
Необходимо убрать все упоминания `copytrust`/`CopyTrust` из харнеса и документации и
назвать универсальную среду **seharnes**. План зафиксирует объём и порядок замены;
код меняется **только после утверждённого согласования** этого плана.

> **AI:** пока план `draft`, код не трогать. Перед реализацией убедись, что статус
> согласован (`agreed`).

---

## Цель и критерий готовности

**Цель:** в repo не осталось упоминаний `copytrust`/`CopyTrust`, все runtime-имена
переведены на `seharnes`, синхронизация зеркал и проверки харнеса зелёные.

**Критерий готовности:**

```bash
git grep -in -E 'copytrust|copitrust|копитраст'   # 0 результатов
./.agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh
python3 .agents/skills/harness-router/children/improvement/scripts/validate_registry.py
python3 .agents/skills/harness-router/children/improvement/scripts/validate_rules.py \
  --rules-dir .cursor/rules --skills-dir .agents/skills
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py check
```

---

## Объем (файлы/категории)

Найдено **512 строк в 155 файлах**. По категориям (уточнённые с пользователем):

| Категория | Ключ | Строки | Примеры |
|---|---|---:|---|
| A. URL-стенды | `copytrust.ru` | 26 | `d8.copytrust.ru`, `<stand>.copytrust.ru` |
| B. Контейнеры/образы | `copytrust-dev-*`, `copytrust-codecept`, `copytrust-tools` | 224 | `copytrust-dev-php-apache-1`, `copytrust-tools:local` |
| C. Скилл | `.agents/skills/copytrust/**` | 34 | скил + дети `platform-logs`, `platform-browser-test` |
| D. Локальные пути | `C:\projects\copytrust`, `/home/newuser/projects/copytrust` | ~29 | профили, примеры, ADAPTERS.local |
| E. Graphiti-группы | `copytrust-testdeploydocker`, `copytrust-cms` | (в B) | group_id |
| F. Schema-URL | `copytrust.local` | 1 | `$id` в skill.schema.json |
| G. Артефакты | `out_copytrust.json` | 4 | выходные файлы |
| H. Остальное | `CopyTrust` в тексте | ~198 | описания, комментарии, заголовки |

**Важно:** категории B и E — это **runtime-имена**, не текст. Их переименование
меняет окружение: нужно вместе заменить имена контейнеров/образов и дефолты в
скриптах/конфигах, иначе всё перестаёт работать.

---

## Шаги

1. **Скилл `copytrust` (кат. C).** Решение: сохранить как платформенный скил, но
   переименовать в `seharnes` (саллеты `platform-logs`, `platform-browser-test` уже
   универсальны по названию). Исправить ссылки из других скилов (`bug-cause`, registry).
2. **Текст и документация (H, A, G, D).** Прямая замена с корректировкой смысла
   (не слепой regex): описания, заголовки, примеры, `file:///`-ссылки, локальные пути.
3. **Runtime-имена (B, E, F).** Параллельно: скрипты + конфиги + реальное окружение.
   Имена контейнеров/образов на машине и дефолты в скриптах заменяются в один проход.
4. **Синхронизация зеркал.** После правки канона (`.agents`, `.cursor`) прогнать
   `sync-agent-views.sh`, чтобы сгенерированные `.codex`/`.kilo`/`.qoder` не отстали.
5. **Проверки** по критерию готовности выше.

---

## Проверки после внедрения

- `git grep -in -E 'copytrust|copitrust|копитраст'` → 0.
- sync-agent-views (LF, parity, freshness-гейт).
- `validate_registry.py`, `validate_rules.py`.
- `harness_mirror.py check` (граф харнеса).
- Ссылки `.doc` (`check-links.py`) — 0 ошибок.

---

## Ограничения и риски

- **Runtime-имена:** если только поменять текст в скриптах, а не пересоздать
  контейнеры/образы на машине, запуски сломаются. Выполнять B/E/F вместе с
  пересозданием окружения.
- **`.doc/web` сервис:** имя `copytrust-tools` используется в `compose.tools.yml`,
  `service.json`, `start.sh`/`stop.sh`/`install.sh` — часть runtime, менять параллельно.
- **Зеркала сред:** ручная правка сгенерированных `.codex`/`.kilo` перезапишет sync;
  править канон и синхронизировать.
- **Упоминания вне repo:** контейнеры/образы на машине, `.cursor/mcp.env`,
  `.doc/web/state` — локальные, в git не отслеживаются.
- **Скилл `copytrust`** — после переноса в другой проект может нуждаться в
  подстановке собственных стендов; оставить механизм подстановки, не хардкод.

---

## История изменений

- 2026-11-26: создан черновик плана. Обзор нашёл 512 упоминаний в 155 файлах.
  Названо универсальное имя — **seharnes**. Статус `draft`, к коду не применялся.
