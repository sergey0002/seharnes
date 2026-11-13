---
transferable: false
description: Проектные значения скила harness-index для CopyTrust: пути, порты, команды проверки. Читает canon-paths.yaml.
updated: 2026-11-08
---

# Adapters: CopyTrust

Локальные привязки скила. При переносе в другой проект этот файл не копируется.

| Ключ | Значение | Источник |
|---|---|---|
| `TOOL` | `.agents/skills/harness-router/children/mirror/scripts/harness_mirror.py` | локально |
| `DATA_DIR` | `.doc/skil_data/mirror` | локально |
| `CANON_ROOT_RULES` | `.cursor/rules` | canon-paths.yaml |
| `CANON_ROOT_SKILLS` | `.agents/skills` | canon-paths.yaml |
| `CANON_ROOT_MCP` | `.cursor/mcp.json` | canon-paths.yaml |
| `CANON_ROOT_SCRIPTS` | `.tools/scripts` | canon-paths.yaml |
| `CANON_ROOT_MCP_SERVERS` | `.tools/mcp-servers` | canon-paths.yaml |
| `SYNC_COMMAND` | `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh` | canon-paths.yaml |
| `PARITY_CHECK` | `python3 .agents/skills/harness-router/children/environment-sync/scripts/verify_parity.py` | canon-paths.yaml |
| `VIEWER_URL` | `http://127.0.0.1:8090/` | локально |
| `VIEWER_AUTOSTART` | systemd user unit `mirror.service` | локально |
| `PANEL_URL` | `http://127.0.0.1:8077/` | локально |

Команды проекта:

```bash
# картина по скилу
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py review --skill gototask
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py bundle --skill gototask

# аудит всего канона
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py lint
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py review --all

# после правок файлов
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py scan
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py build
python3 .agents/skills/harness-router/children/mirror/scripts/harness_mirror.py check
```

Документация проекта в индекс не входит: `.doc/` не сканируется, связи на него отбрасываются.
