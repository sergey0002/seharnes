# Скрипт: `.agents/skills/skill-auditor/scripts/static_audit.py`

<!-- meta
type: script
status: actual
updated: 2026-11-11
related: [../../SKILL.md, ./score_aggregator.py.md]
tags: [harness, script, skill-auditor, static-audit, portability]
-->

## Суть
Детерминированный статический предаудит навыков и связанных конфигов: структура пакета, `SKILL.md`, дочерние скилы, скрипты, ссылки, evals, архивы `.skill` и `.zip`, `AGENTS.md`, правила `.mdc`, профили агентов и наборы скилов. Проверяет совместимость с 17 агентскими средами и защиту от Zip-Slip и Zip-Bomb. Смысловые оценки текста не делает, они остаются за моделью.

## Когда запускать
Перед смысловым аудитом, перед упаковкой навыка и в CI. Скрипт дает машинный отчет, на который опирается `score_aggregator.py`. Без него итоговая оценка неполная.

## Аргументы
| Аргумент | Алиас | Тип | Обязателен | По умолчанию | Что делает |
|---|---|---|---|---|---|
| `target` | | string | да | | каталог скила, `.skill` или `.zip`, `SKILL.md`, `AGENTS.md`, правило `.mdc`, профиль агента или каталог набора скилов |
| `--target-type TYPE` | | `auto`, `skill`, `agents-md`, `cursor-mdc`, `agent-profile`, `fleet` | нет | `auto` | принудительно задает тип цели |
| `--output PATH` | `-o` | string | нет | `-` (stdout) | путь для JSON-отчета |
| `--fail-on-critical` | | flag | нет | | вернуть код 2 при критической уязвимости или провале ядра совместимости |
| `--self-audit-safe` | | flag | нет | | игнорировать таблицы сигнатур в `references/` и `evals/` при аудите самого аудитора |

## Коды выхода
| Код | Значение | Действие вызывающего |
|---|---|---|
| 0 | аудит завершен | передать JSON в `score_aggregator.py` |
| 1 | неверная цель или аргументы | исправить путь или тип цели |
| 2 | критический блокер при `--fail-on-critical` | остановить упаковку и разобрать `security_findings` |

## Что читает и что пишет
Читает файлы цели: `SKILL.md`, `skill.json`, скрипты, ссылки, evals, архивы, правила и профили. Пишет JSON-отчет в stdout или по `--output`. Сеть и база не используются.

## Побочные эффекты
- Пишет JSON-отчет по указанному пути.
- Распаковывает архивы только во временный каталог с проверкой Zip-Slip и Zip-Bomb.
- Проверяемый скил не меняет.

## Окружение и зависимости
Python 3.9 или новее. Обязательна стандартная библиотека, `PyYAML` и `tomllib` подключаются при наличии. Без `PyYAML` работает встроенный разбор YAML с ограничениями.

## Примеры
```bash
python3 .agents/skills/skill-auditor/scripts/static_audit.py \
  path/to/skill \
  --output /tmp/audit/static_audit.json

python3 .agents/skills/skill-auditor/scripts/static_audit.py \
  path/to/skills \
  --target-type fleet \
  --fail-on-critical
```

## Ограничения
Не оценивает смысл, тон и качество текста. Проверки совместимости описывают формальные признаки, а не поведение в конкретной среде. Архивы проверяются на безопасность распаковки, но не на смысл содержимого.

## Связи
- Скил: `.agents/skills/skill-auditor/SKILL.md`.
- Итоговая агрегация: `score_aggregator.py`, документ `./score_aggregator.py.md`.
- Упаковка навыка: `.agents/skills/skill-creator/scripts/package_and_verify.py`.

## История изменений
- 2026-11-11: документ создан, аргументы и поведение сверены с кодом.
