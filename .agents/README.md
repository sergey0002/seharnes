# Deprecated — use `.codex/`

Каталог `.agents/` больше не является источником skills и rules для Codex.

| Было | Стало |
|------|-------|
| `.agents/skills/` | [`.codex/skills/`](../.codex/skills/) |
| `.agents/rules/` | [`.codex/rules/`](../.codex/rules/) |
| инструкции агента | [`.codex/AGENTS.md`](../.codex/AGENTS.md) |

Codex подхватывает `model_instructions_file = ".codex/AGENTS.md"` из [`.codex/config.toml`](../.codex/config.toml).

**Не создавайте здесь новые SKILL.md** — дубли с одинаковым `name:` в frontmatter вызывают зацикливание агента.
