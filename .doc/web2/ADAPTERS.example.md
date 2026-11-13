# Adapters: copytrust-tools

<!-- transferable: false -->

Локальные значения машины. Файл `ADAPTERS.local.md` не переносится и создаётся установщиком.

| Adapter | Значение |
|---|---|
| `SERVICE_ROOT` | `.doc/web` |
| `WORKSPACE_ROOT` | корень проекта, где лежат `.doc`, `.cursor`, `.agents` |
| `STATE_DIR` | `.doc/web/state` |
| `DATA_DIR` | `.doc/skil_data/mirror` |
| `KILO_DATA_DIR` | `~/.local/share/kilo`, каталог с `kilo.db` для аналитики |
| `PORT` | `8077`, переопределяется `WEB_PANEL_PORT` |
| `PROFILE` | `core` или `full` |
| `PYTHON` | `python3` |
| `PHP` | `php` |
| `PWSH` | `pwsh` |
| `ACTIONS_LOCAL` | `.doc/web/config/actions.local.json` |
| `PRICES_LOCAL` | `.doc/web/config/prices.local.json` |
| `KILO_DB` | `/host-kilo/kilo.db` в контейнере, `~/.local/share/kilo/kilo.db` на хосте |

Правила:

- пути в `service.json` относительные, от корня проекта;
- `STATE_DIR` не переносится и не коммитится;
- `ADAPTERS.local.md` и `actions.local.json` остаются на машине.
