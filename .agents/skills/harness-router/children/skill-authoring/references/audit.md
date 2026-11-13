# Аудит скила

## Что проверяет

| Категория | Проверка |
|---|---|
| Структура | `SKILL.md`, `README.md`, `skill.json`, допустимые каталоги, симлинки |
| Frontmatter | `name`, `description`, запрещенные поля, валидность |
| README | наличие, нет ссылок и URL |
| Манифест | schema 1, имя, ресурсы, объявленные скрипты, тесты, дети |
| Скрипты | каждый файл в `scripts` объявлен в `skill.json` |
| Тесты | файлы существуют, тесты лежат в `tests/` |
| Безопасность | секреты и абсолютные пути |
| Ссылки | относительные ссылки в `SKILL.md` существуют |
| Документация | карточка, `skills/README.md`, `harnes/index.md` |
| Реестр | запись и обязательные файлы |
| Роутер | запись в родительском `skill.json` и таблице роутера |
| Зависимости | имена скилов и проектные пути существуют |

## Уровни

- `ERROR`: нарушение обязательного правила, скил не готов.
- `WARN`: отклонение, которое нужно проверить человеку.
- `score`: 100 минус 15 за ошибку и минус 5 за предупреждение, не ниже 0.

## Режимы

```bash
# один скил
python3 .agents/skills/harness-router/children/skill-authoring/scripts/audit_skill.py \
  --root . --name my-skill

# все скилы
python3 .agents/skills/harness-router/children/skill-authoring/scripts/audit_skill.py \
  --root . --all

# строгий режим: предупреждения тоже считаются ошибкой
python3 .agents/skills/harness-router/children/skill-authoring/scripts/audit_skill.py \
  --root . --all --strict
```

## Что делать с результатом

1. Ошибки исправить в источнике: `SKILL.md`, `README.md`, `skill.json`, карточка.
2. Предупреждения разобрать по одному. Если отклонение осознанное, записать его
   в раздел ограничений скила.
3. После правок повторить аудит.
4. Затем выполнить `validate_skills.py`, `validate_docs.py` и синхронизацию.

## Границы

Аудит не проверяет runtime-регистрацию скила в Cursor, Codex, Kilo, Qoder,
Qwen или Antigravity. Для этого нужен отдельный smoke-тест среды.
