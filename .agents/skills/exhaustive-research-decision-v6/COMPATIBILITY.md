# Совместимость с современными агентами

Проверено 2026-11-10 по официальной [спецификации Agent Skills](https://agentskills.io/specification) и документам вендоров. Пакет следует **открытому стандарту**, а не расширениям одного клиента.

## Короткий ответ

**Корневой `SKILL.md` совместим со всеми клиентами, реализующими Agent Skills.** Обязательные поля `name` + `description`, `name` == имени папки, `description` ≤ 1024, frontmatter первым делом, относительные ссылки одним уровнем, тело < 500 строк, любые дополнительные файлы разрешены — всё это соблюдено.

Официальный [Client Showcase](https://agentskills.io/clients) насчитывает 40+ клиентов: Claude Code, ChatGPT/Codex, Cursor, VS Code, GitHub Copilot, Gemini CLI, Kilo Code, Amp, Goose, OpenHands, Letta, TRAE, Firebender, Tabnine, OpenClaw, Windsurf-совместимые, Cline/Roo-производные и др.

**Универсальная точка установки:** `.agents/skills/exhaustive-research-decision-v6/` — её читают Cursor, Codex, Kilo Code, Gemini CLI, GitHub Copilot и VS Code. Для Claude Code используй `.claude/skills/`. Никуда переименовывать папку нельзя.

**Одна папка = всё.** `SKILL.md` + 10 дочерних скиллов в `children/` + `scripts/` + `references/agents/` + `assets/templates/` + `assets/schemas/` + `assets/examples/` + docs — физически находятся внутри `exhaustive-research-decision-v6/`. Ничего не выносится наружу. Опциональный дубль `references/agents/*.md` в `.cursor/agents/` — единственное, что может оказаться за пределами папки, и он не обязателен.

## Матрица

| Клиент | Project | User/global | Вызов | Вложенные `children/*/SKILL.md` | Статус корня |
|---|---|---|---|---|---|
| **Cursor** | `.cursor/skills/`, `.agents/skills/`, `.claude/skills/`, `.codex/skills/` | `~/.cursor/skills/`, `~/.agents/skills/` | `/name` | ✅ рекурсивно, отдельные скиллы | ✅ как есть |
| **Claude Code** | `.claude/skills/` | `~/.claude/skills/` | `/name` | ⚠️ читаются корнем как процедуры | ✅ как есть |
| **OpenAI Codex / ChatGPT** | `.agents/skills/` (сканируется вверх до root) | `~/.agents/skills/`, `/etc/codex/skills/` | `$name`, `/skills` | ⚠️ глубина discovery = 1 | ✅ как есть |
| **Kilo Code** | `.kilo/skills/`, `.agents/skills/`, `.claude/skills/`* | `~/.kilo/skills/`, `~/.agents/skills/` | `/name`, `/reload` | ⚠️ глубина discovery = 1 | ✅ как есть |
| **Gemini CLI** | `.gemini/skills/`, `.agents/skills/` alias | `~/.gemini/skills/`, `~/.agents/skills/` | `/skills list`, `gemini skills install` | ⚠️ глубже 1 уровня не обнаруживаются | ✅ как есть + `/trust` для workspace |
| **GitHub Copilot / VS Code** | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | `~/.copilot/skills/`, `~/.agents/skills/` | агент mode, `gh skill` | ⚠️ читаются корнем | ✅ как есть |
| **Windsurf** | `.windsurf/skills/`, `.devin/skills/`** | — | `/name` | ⚠️ читаются корнем | ✅ формат тот же |
| **OpenCode** | `.agent/skills/`** | `~/.agent/skills/`** | `opencode run @skill-name` | ⚠️ читаются корнем | ✅ формат тот же |
| **Cline / Roo Code** | Kilo-совместимые пути** | — | `/name` | ⚠️ читаются корнем | ✅ формат тот же |
| **Amp, Goose, OpenHands, Letta, TRAE, Firebender, Tabnine, OpenClaw, VT Code, Command Code, Autohand, Hermes, Emdash, Deep Code, Pulumi Neo, nanobot, AdaL, Antigravity, Kiro** | см. [Client Showcase](https://agentskills.io/clients) | — | по докам клиента | ⚠️ читаются корнем | ✅ минимальный формат одинаков |

\* `.claude/skills/` в Kilo — только при включённой «Claude Code Compatibility».
\*\* Пути из документации сообщества/производных проектов; официально перепроверены только верхние строки таблицы.

## Что именно было непереносимым — и исправлено

| Элемент | Проблема | Решение |
|---|---|---|
| `paths:` в 10 дочерних скиллах | Расширение Cursor/Claude Code, **не входит** в спецификацию | **Убрано.** Остались `name`, `description` |
| `.cursor/research/**` в glob | Жёсткая привязка к Cursor | Убрано вместе с `paths` |
| `disable-model-invocation: true` | Расширение Cursor/Claude Code; в формате харнеса поле запрещено | **Убрано.** Дочерние скиллы вызываются по маршрутизации родителя |
| `model` / `readonly` / `is_background` в `references/agents/*.md` | Поля нативных Cursor subagents | Не копировать напрямую в `.claude/agents/` / `.cursor/agents/` других клиентов без адаптации. Работает inline-fallback из `research-assignment` |
| `description` на 869 символов | Codex урезает список скиллов до 2% контекста / 8000 символов | Сокращён до ~600 с сохранением триггеров |
| Глубина вложенности > 1 | Kilo, Gemini, Codex, Copilot ищут `SKILL.md` только на 1 уровень | Корневой `SKILL.md` ссылается на все 10 напрямую; они читаются как обычные файлы. В Cursor дополнительно становятся отдельными скиллами |
| Python 3 для `check_gates.py` | Не у всех агентов есть shell/Python | Добавлено стандартное поле `compatibility`; без валидатора процедурная часть работает, но `gates.json PASS` недостижим (G9) |

## Стандартные поля, которые мы теперь используем

```yaml
name: exhaustive-research-decision-v6          # обязательно, == папке
description: ...                               # обязательно, <= 1024
compatibility: Requires Python 3.9+ ...        # опционально, <= 500
metadata:                                      # опционально, string -> string
  version: "6.1"
  scope: "universal-deep-research"
```

`license` не выставлен сознательно: лицензия пакета не объявлялась. `allowed-tools` не используется — поле экспериментальное и по-разному трактуется клиентами.

## Нативные субагенты по клиентам

| Клиент | Где регистрируются | Наши `references/agents/*.md` |
|---|---|---|
| Cursor | `.cursor/agents/`, `~/.cursor/agents/` | опц. `cp`, поля совпадают |
| Claude Code | `.claude/agents/`, `~/.claude/agents/` | нужна адаптация: `tools` / `model` / `permissionMode` вместо `readonly` / `is_background` |
| Codex | `AGENTS.md` + `agents/openai.yaml` | как спецификации ролей |
| Kilo / Gemini / Copilot | свои механизмы | как спецификации ролей |

**Без единого дополнительного шага** `research-assignment` читает `references/agents/<name>.md` от корня пакета и передаёт роль в промпт обычного subagent/`Task`. Это и есть переносимый путь.

## Fallback для агентов без Agent Skills

Готовый сниппет лежит **внутри** папки скилла: [assets/AGENTS.md.snippet](assets/AGENTS.md.snippet). Его можно скопировать в корень репозитория как `AGENTS.md`, если агент вообще не поддерживает Agent Skills. **Для минимальной установки этот шаг не нужен** и ни на что не влияет у skills-совместимых клиентов.

## Чек-лист под конкретный клиент

1. Скопировать папку **без переименования** в путь из таблицы.
2. Убедиться, что frontmatter идёт первым (до H1/пустых строк) — требование Gemini CLI и спецификации.
3. `python3 scripts/check_gates.py assets/examples/minimal-passing-run` → `PASS errors=0 warnings=0`.
4. Вызвать `/exhaustive-research-decision-v6` (`$name` в Codex, `/skills` + имя в Gemini, `/name` в Kilo).
5. Если клиент не показывает 10 вложенных скиллов в своём списке — **это ожидаемо**: корень прочитает их по ссылкам сам.
6. Для Gemini CLI workspace: `/trust` + `/skills reload`; для Kilo: `/reload`; для Cursor/Claude: перезапуск сессии.

## Источники

- [Agent Skills — Specification](https://agentskills.io/specification) · [Client Showcase](https://agentskills.io/clients) · [Overview](https://agentskills.io/home)
- [Cursor — Agent Skills](https://cursor.com/docs/skills) · [Cursor — Subagents](https://cursor.com/docs/subagents)
- [Claude Code — Extend Claude with skills](https://code.claude.com/docs/en/skills)
- [ChatGPT / Codex — Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Kilo Code — Skills](https://kilo.ai/docs/customize/skills)
- [Gemini CLI — Agent Skills](https://geminicli.com/docs/cli/skills/)
- [GitHub Copilot — Agent skills](https://docs.github.com/en/copilot/concepts/customizations/agent-skills) · [VS Code — Agent Skills](https://code.visualstudio.com/docs/agent-customization/agent-skills)
