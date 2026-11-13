# Установка: одна папка

Пакет самодостаточен и следует [открытому стандарту Agent Skills](https://agentskills.io/specification). Внутри `exhaustive-research-decision-v6/` лежит всё: корневой `SKILL.md`, 10 вложенных скиллов, спецификации агентов, шаблоны, схемы, валидатор, пример и документация.

**Имя папки менять нельзя**: `name` обязан совпадать с родительской папкой.

> ## Минимальная установка = ровно ОДНА команда
>
> ```bash
> mkdir -p .agents/skills && cp -r exhaustive-research-decision-v6 .agents/skills/
> ```
>
> **Всё.** Внутри этой одной папки уже лежат: `SKILL.md`, 10 дочерних `children/*/SKILL.md`, `scripts/`, `references/`, `assets/templates/`, `assets/schemas/`, `assets/examples/`, 8 спецификаций `references/agents/`, документация. Никаких файлов вне папки, никаких симлинков, никаких вторых копий создавать не нужно. Скилл работает сразу после перезапуска сессии.
>
> Единственное, что **можно, но не обязательно** сделать отдельно — продублировать `references/agents/*.md` в `.cursor/agents/` (или аналог клиента) ради нативных `/candidate-scout`, `readonly`, `is_background`. Без этого дубля роли читаются из `references/agents/` внутри скилла и инлайнятся в обычный `Task`.

Полная матрица по 40+ клиентам, ограничения и fallback: **[COMPATIBILITY.md](COMPATIBILITY.md)**.

## Рекомендуемый универсальный путь

```bash
mkdir -p .agents/skills
cp -r exhaustive-research-decision-v6 .agents/skills/
```

`.agents/skills/` читают Cursor, OpenAI Codex, Kilo Code, Gemini CLI, GitHub Copilot и VS Code. Для **Claude Code** используй `.claude/skills/`.

## Куда ещё можно положить

| Клиент | Project | User/global |
|---|---|---|
| Cursor | `.cursor/skills/`, `.agents/skills/` | `~/.cursor/skills/`, `~/.agents/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |
| OpenAI Codex / ChatGPT | `.agents/skills/` | `~/.agents/skills/` |
| Kilo Code | `.kilo/skills/`, `.agents/skills/` | `~/.kilo/skills/`, `~/.agents/skills/` |
| Gemini CLI | `.gemini/skills/`, `.agents/skills/` | `~/.gemini/skills/`, `~/.agents/skills/` |
| GitHub Copilot / VS Code | `.github/skills/`, `.claude/skills/`, `.agents/skills/` | `~/.copilot/skills/`, `~/.agents/skills/` |
| Windsurf / OpenCode / Cline-Roo | `.windsurf/skills/`, `.devin/skills/`, `.agent/skills/` | по докам клиента |

После установки: перезапуск сессии (`/reload` в Kilo, `/skills reload` в Gemini, `/trust` для Gemini workspace). Вызов: `/exhaustive-research-decision-v6`, `$name` в Codex, `/skills` + имя в Gemini.

## Что подхватывается сразу

- корневой `SKILL.md` (193 строки, < 500) — **во всех** skills-совместимых клиентах;
- **10 дочерних `children/*/SKILL.md`** — лежат рядом, читаются корнем по прямым ссылкам;
- **`scripts/check_gates.py`** — валидатор прямо в папке скилла, запускается как `python scripts/check_gates.py ...`;
- **`assets/templates/` (28)**, **`assets/schemas/` (5)**, **`references/` (6)**, **`assets/examples/`**, **`references/agents/` (8)** — всё внутри;
- `README.md`, `INSTALL.md`, `COMPATIBILITY.md`, `DESIGN-NOTES-v6.md` — документация тоже внутри;
- `scripts/`, `references/`, `assets/` — каноничные папки стандарта; остальные — разрешённые дополнительные ресурсы;
- все ссылки из корня — **одного уровня**, без цепочек «ссылка на ссылку».

### Важный нюанс про вложенные скиллы

Только **Cursor** обходит skills root рекурсивно и регистрирует `children/*/SKILL.md` как отдельные скиллы. Остальные клиенты (Kilo, Codex, Gemini, Copilot, Claude Code) обнаруживают `SKILL.md` лишь на один уровень вглубь — поэтому внутри одного пакета наши 10 файлов работают как **процедурные reference-файлы, которые корень читает по ссылкам**. На работоспособность это не влияет: именно так и задумывалось («просто ссылаться из основного»). Поле `disable-model-invocation` убрано: формат харнеса его запрещает.

Нестандартное поле `paths:` мы **убрали** из дочерних скиллов ради чистоты спецификации.

## Дочерние скиллы: папка `children/`

Формат харнеса закрепляет за дочерними скиллами папку `children/`, стандарт Agent Skills отдельного типа «child skill» не имеет. Важно:

- у каждой вложенной папки свой `SKILL.md`;
- `name` совпадает с **её** папкой, а не с родительской;
- корневой `SKILL.md` ссылается на них напрямую;
- frontmatter идёт первым делом, без H1/пустой строки до `---` (требование Gemini CLI и спецификации).

## Агенты: один необязательный шаг

Нативные Cursor subagents берутся **только** из `.cursor/agents/` / `~/.cursor/agents/`; изнутри папки скилла они не регистрируются.

- **Каноническая копия `references/agents/` уже внутри скилла.** Без дополнительного шага скилл работает: `research-assignment` читает `references/agents/<name>.md` от корня пакета и передаёт спецификацию роли в промпт обычного `Task`/subagent. Это переносимый путь для всех клиентов.
- Опциональный `cp` ниже — это **дубль** тех же 8 файлов в нативный каталог клиента, а не перенос их из скилла. Удалять `references/agents/` из папки скилла не нужно.
- **Опционально для Cursor**:
  ```bash
  mkdir -p .cursor/agents
  cp exhaustive-research-decision-v6/references/agents/*.md .cursor/agents/
  ```
- Для Claude Code не копируйте напрямую: там другие поля (`tools`, `model`, `permissionMode`). Детали — в `COMPATIBILITY.md`.

Не клади агентов в `.cursor/rules/*.md` — обычные `.md` там игнорируются, правилам нужен `.mdc`.

## Агент без поддержки Agent Skills — НЕ часть минимальной установки

[assets/AGENTS.md.snippet](assets/AGENTS.md.snippet) лежит **внутри** папки скилла и нужен только в редком случае, когда агент вообще не умеет Agent Skills. Тогда его можно скопировать в корень репозитория как `AGENTS.md`. Для Cursor / Claude Code / Codex / Kilo / Gemini / Copilot этот шаг **не выполняется** — они читают `SKILL.md` сами.

## Проверка после установки

```bash
cd .agents/skills/exhaustive-research-decision-v6
python3 scripts/check_gates.py assets/examples/minimal-passing-run
# PASS errors=0 warnings=0

python3 scripts/check_gates.py --init-v6 /tmp/research-smoke --force
python3 scripts/check_gates.py /tmp/research-smoke
# FAIL — ожидаемо: свежие шаблоны с placeholders не являются готовым прогоном
```

`scripts/check_gates.py` — Python 3.9+, только stdlib. Это единственная runtime-зависимость; она объявлена в стандартном поле `compatibility` фронтматтера.

## Каноничные и дополнительные папки

| Папка | Статус |
|---|---|
| `scripts/` | стандарт: исполняемый код |
| `references/` | стандарт: документация по требованию |
| `assets/` | стандарт: шаблоны и статические ресурсы |
| `children/` | дочерние скиллы |
| `references/agents/` | спецификации ролей, не нативные subagents |
| `assets/schemas/`, `assets/examples/` | схемы и пример прогона |
| `README.md`, `INSTALL.md`, `COMPATIBILITY.md`, `DESIGN-NOTES-v6.md` | документация пакета |

## Проверено по

- [Agent Skills — Specification](https://agentskills.io/specification) · [Client Showcase](https://agentskills.io/clients)
- [Cursor — Agent Skills](https://cursor.com/docs/skills) · [Subagents](https://cursor.com/docs/subagents)
- [Claude Code — Skills](https://code.claude.com/docs/en/skills) · [Claude best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)
- [ChatGPT / Codex — Build skills](https://learn.chatgpt.com/docs/build-skills)
- [Kilo Code — Skills](https://kilo.ai/docs/customize/skills)
- [Gemini CLI — Agent Skills](https://geminicli.com/docs/cli/skills/)
- [GitHub Copilot — Agent skills](https://docs.github.com/en/copilot/concepts/customizations/agent-skills) · [VS Code](https://code.visualstudio.com/docs/agent-customization/agent-skills)
