<!-- generated from architecture:deepseek-harness-index by doc_render.py; do not edit -->

# DeepSeek Harness - точка входа

task unknown - status unknown - branch unknown - release unknown

# DeepSeek Harness - точка входа
<a id="deepseek-harness---точка-входа"></a>
<!-- meta
type: index
status: actual
updated: 2026-10-20
related: [../harnes/index.md, ../harnes/doc_rules.md, ../harnes/plan/07-dsh-final.md]
tags: [deepseek, harness, dsh, index]
-->

---

## Суть
<a id="суть"></a>
Документация харнеса DeepSeek Harness для проекта CopyTrust. Харнес - тонкий
слой поверх канонических скилов и правил `.cursor/`, который даёт DSH тот же
цикл работы с задачей, что Cursor, Codex и Kilo: переход к задаче, план, аудит
плана, реализация, тест, отправка в git.

Харнес касается только DeepSeek Harness. Канон `.cursor/` и зеркала других
сред (`.codex/`, `.kilo/`, `.agents/`, `.antigravity/`, `.gemini/`) не меняются.
Файлы харнеса живут в `.dsh/`, `DSH-RULES.md` и этой папке документации.

> **AI:** читай этот doc если работаешь с DeepSeek Harness в этом проекте или
> переносишь харнес на другой сервер.
> **Сначала:** [02-установка.md](./deepseek-harness-02-ustanovka.md) если разворачиваешь заново,
> [03-workflow.md](./deepseek-harness-03-workflow.md) если выполняешь задачу.
> **Не читай целиком:** этот index - только навигация.
> **См. также:** [../harnes/index.md../index.md) - устройство всего
> харнеса, [../harnes/doc_rules.md../doc_rules.md) - правила документации.

---

## Быстрый старт
<a id="быстрый-старт"></a>
```bash

# 1. проверить, что харнес живой
<a id="1.-проверить,-что-харнес-живой"></a>
bash .dsh/scripts/smoke.sh --task 2622

# 2. перейти к задаче
<a id="2.-перейти-к-задаче"></a>
bash .dsh/scripts/run-ps1.sh .agents/skills/task-router/children/gototask/scripts/gototask.ps1 \
  -TaskNumber 2622 -Action inspect
```

Если `smoke.sh` упал, читай [02-установка.md](./deepseek-harness-02-ustanovka.md), раздел
"Если что-то не поднялось".

---

## Навигация
<a id="навигация"></a>

### [01-устройство.md](./deepseek-harness-01-ustroystvo.md)
<a id="[01-устройство.md](./deepseek-harness-01-ustroystvo.md)"></a>
Что включает харнес: файлы `.dsh/`, слои, границы, связь с каноном, отличие от Cursor.
Теги: `deepseek` `harness` `structure`

### [02-установка.md](./deepseek-harness-02-ustanovka.md)
<a id="[02-установка.md](./deepseek-harness-02-ustanovka.md)"></a>
Как развернуть: pwsh, генерация патча с флагами, запуск с `--patch`, проверка.
Теги: `deepseek` `deploy` `setup`

### [03-workflow.md](./deepseek-harness-03-workflow.md)
<a id="[03-workflow.md](./deepseek-harness-03-workflow.md)"></a>
Цикл задачи: переход, классификация размера, план, аудит, реализация, тест, git.
Теги: `deepseek` `workflow` `task`

### [04-модели.md](./deepseek-harness-04-modeli.md)
<a id="[04-модели.md](./deepseek-harness-04-modeli.md)"></a>
Что доступно сейчас (одна модель) и как включить xai, anthropic, google.
Теги: `deepseek` `models` `routing`

### [05-скрипты.md](./deepseek-harness-05-skripty.md)
<a id="[05-скрипты.md](./deepseek-harness-05-skripty.md)"></a>
Оболочка, шим `run-ps1.sh`, `smoke.sh`, скрипты канона, 14 MCP-серверов.
Теги: `deepseek` `scripts` `mcp`

### [07-сценарии.md](./deepseek-harness-07-scenarios.md)
<a id="[07-сценарии.md](./deepseek-harness-07-scenarios.md)"></a>
Прогон сценариев (переход, план, аудит, тест, MCP, доки): результаты и находки N-1..N-10.
Теги: `deepseek` `scenarios` `tests`

---

## Быстрый поиск по тегам
<a id="быстрый-поиск-по-тегам"></a>
| Тег | Документы |
|-----|-----------|
| `harness` | [01](./deepseek-harness-01-ustroystvo.md) |
| `structure` | [01](./deepseek-harness-01-ustroystvo.md) |
| `deploy` | [02](./deepseek-harness-02-ustanovka.md) |
| `setup` | [02](./deepseek-harness-02-ustanovka.md) |
| `workflow` | [03](./deepseek-harness-03-workflow.md) |
| `task` | [03](./deepseek-harness-03-workflow.md) |
| `models` | [04](./deepseek-harness-04-modeli.md) |
| `routing` | [04](./deepseek-harness-04-modeli.md) |
| `scripts` | [05](./deepseek-harness-05-skripty.md) |
| `mcp` | [05](./deepseek-harness-05-skripty.md) |
| `scenarios` | [07](./deepseek-harness-07-scenarios.md) |

---

## Статус документации
<a id="статус-документации"></a>
| Документ | Статус | Обновлён |
|----------|--------|----------|
| [01-устройство.md](./deepseek-harness-01-ustroystvo.md) | актуально | 2026-10-20 |
| [02-установка.md](./deepseek-harness-02-ustanovka.md) | актуально | 2026-10-20 |
| [03-workflow.md](./deepseek-harness-03-workflow.md) | актуально | 2026-10-20 |
| [04-модели.md](./deepseek-harness-04-modeli.md) | актуально | 2026-10-20 |
| [05-скрипты.md](./deepseek-harness-05-skripty.md) | актуально | 2026-10-20 |
| [07-сценарии.md](./deepseek-harness-07-scenarios.md) | актуально | 2026-10-20 |

---

## Связи
<a id="связи"></a>
- [Харнес (канон и среды)../index.md) - устройство всего харнеса, канон `.cursor/`
- [Состояние сред../state/01-canon-envs.md) - канон, 5 зеркал, DSH-слой, синк
- [H-тесты DSH../h-test-report.md) - исходные проверки адаптера и их статусы
- [Правила документации../doc_rules.md) - стандарт `.doc/`, читать первым
- [План DSH workflow../plan/07-dsh-final.md) - детальный план с гейтами
- [Скрипты и тестирование../plan/06b-dsh-scripts-and-testing.md) - карта скриптов, H-тесты

---

## История изменений
<a id="история-изменений"></a>
- 2026-10-20: каталог создан, документация харнеса DSH вынесена из plan/07 в отдельную папку по правилам doc_rules.md
- 2026-10-20: добавлен 07-сценарии.md, исправлены находки прогона (branchExists, exit-коды плана, digest, P7.4a, G13, ссылки в DSH-RULES)

---

#deepseek #harness #dsh #index
