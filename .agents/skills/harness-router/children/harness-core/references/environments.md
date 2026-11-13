# Среды

`assets/environments.json` описывает все среды. Поля: `id`, `enabled`, `adapter`, `rules`, `skills`, `mcp`, `instructions`.

Добавление среды: запись в JSON и модуль в `scripts/adapters/`. Другие скрипты не меняются.

Форматы правил: `mdc`, `flat_md`, `trigger`, `paths`. Режимы скилов: `native` или `mirror`.
