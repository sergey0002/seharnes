# skill-creator

Проектирует, собирает и упаковывает переносимые AI-скиллы для 17 агентов:
Claude, Codex, Cursor, OpenCode, Kilo, Antigravity, Pi, Qoder и других.
Создаёт `SKILL.md`, сценарии, `openai.yaml`, оценки и проверяет пакет перед
выдачей. Используется для нового скилла или упаковки рабочего процесса в
архив `.skill`.

## Когда применять

- Создать новый скилл с нуля.
- Собрать скрипты, `openai.yaml`, наборы оценок и упаковать архив.
- Проверить совместимость скилла с несколькими агентами.

Для аудита уже существующего скилла используется `skill-auditor`.

## Состав пакета

- `SKILL.md` - конвейер создания и правила портабельности.
- `scripts/scaffold_skill.py` - детерминированный генератор каркаса.
- `scripts/package_and_verify.py` - сборка и проверка архива.
- `scripts/self_test.py` - самотест пакета.
- `references/agents/` - профиль независимого рецензента и конфиг Codex.
- `references/` - методология авторства, оценки, портабельность.
- `tests/evals/` - форматы оценок и триггерных запросов.
- `assets/skill-md-blueprints.md` - заготовки `SKILL.md`.
- `references/README-upstream.md` - полное описание upstream-пакета.

## Запуск

`python3 scripts/scaffold_skill.py --name <skill-name>` создаёт каркас.
Проверка и упаковка выполняется `scripts/package_and_verify.py`.
