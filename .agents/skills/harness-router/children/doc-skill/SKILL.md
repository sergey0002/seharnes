---
name: doc-skill
description: >
  Документирование скилов харнеса: документация скила это его README.md.
  Проверяет назначение, длину, отсутствие ссылок и раздела Связи.
  Use when: задокументируй скил, аудит скилов, проверь README скила.
---

# Doc Skill

У скила нет отдельной карточки. Документация скила это `README.md` в его папке.
README отвечает на вопрос "зачем скил и что он делает", шаги и флаги остаются в
`SKILL.md`.

## Правило

| Файл | Роль |
|---|---|
| `SKILL.md` | канон: шаги, триггеры, ограничения |
| `README.md` | документация: назначение, без ссылок |
| `skill.json` | манифест: файлы, зависимости, entrypoints |

Карточки в `.doc/harnes/skills/` не создаются и не поддерживаются.

## Шаги

1. `--list` показывает все скилы и наличие README.
2. Агент читает `SKILL.md` и пишет `README.md`: 2-4 предложения о назначении,
    без пошаговых инструкций, без ссылок.
3. `--audit` проверяет README.

## Аудит README

1. Файл существует.
2. Содержит назначение и границы, без ссылок и пошаговых команд.
3. Нет markdown-ссылок и голых URL.
4. Нет раздела `## Связи`.
5. Не пустой.
6. Не пересказывает шаги `SKILL.md`.
7. Нет заглушек `Заполнить:`, `Описание уточняется`, `Скил установлен`.

## Команды

```bash
python3 .agents/skills/harness-router/children/doc-skill/scripts/doc_skill.py --list
python3 .agents/skills/harness-router/children/doc-skill/scripts/doc_skill.py --audit
python3 .agents/skills/harness-router/children/doc-skill/scripts/doc_skill.py --skill .agents/skills/harness-router/children/mirror
```

## Связи

- Структура скила: `.doc/harnes/skill-format.md`.
- Вызывается из `improvement` при проблеме в README скила.
- Зеркало: узлы `type=skill`, поле `analysis` строится из `SKILL.md` и README.
