<!-- generated from architecture:deepseek-harness-04-modeli by doc_render.py; do not edit -->

# что доступно и как включить остальное

task unknown - status unknown - branch unknown - release unknown

# Модели: что доступно и как включить остальное
<a id="модели:-что-доступно-и-как-включить-остальное"></a>
<!-- meta
type: config
status: actual
updated: 2026-10-20
tags: [deepseek, models, routing]
-->

---

## Суть
<a id="суть"></a>
Сейчас профиль DSH работает на одной модели: `deepseek-account` /
`deepseek-flash`. Плагин `llm-pi-ai`, который даёт xai, anthropic и google, в
патч не входит, поэтому `list_subagent_models` пуст и выбрать grok, claude или
gemini в subagent нельзя. Ниже - как это проверено и как включить обратно.

> **AI:** читай этот doc перед тем, как обещать мультимодельный маршрут.
> **Сначала:** [03-workflow.md](./deepseek-harness-03-workflow.md) - шаги цикла.
> **Не читай целиком:** блок включения нужен только при переключении моделей.
> **См. также:** [02-установка.md](./deepseek-harness-02-ustanovka.md) - проверка после запуска.

---

## Факт
<a id="факт"></a>
| Роль | Модель | Как идёт работа |
|---|---|---|
| gototask, классификация | deepseek-flash | ведущий |
| план любого размера | deepseek-flash | ведущий или subagent без выбора модели |
| аудит плана | deepseek-flash | ведущий, один проход |
| реализация | deepseek-flash | ведущий |
| тест | deepseek-flash | ведущий или subagent |

Подтверждение (2026-10-20):

```
list_subagent_models                          -> (no LLM providers)
grep -c "llm-pi-ai" .dsh/project.patch.yml    -> 0
grep -n "agent-default-model" ~/.dsh/profiles/web/cordis.patch.yml
                                              -> provider: deepseek-account, model: deepseek-flash
```

Модель по умолчанию задаётся в профиле DSH, а не в проектном патче. Поэтому
`deepseek-flash` виден агенту, хотя в overlay он описан как `llm-pi-ai` провайдер
`deepseek`.

---

## Почему так
<a id="почему-так"></a>
`llm-pi-ai` был в патче (`.dsh/project.patch.yml.bak-dsh`), затем вырезан
вручную. Строка `subagent-model-selection-settings` при старте даёт warning:
`standing modelSelectionSettings requires a scoped preset Context`, поэтому
`modelSelectionSettings` выставлен в `false`.

Чтобы патч перестал быть правленым руками, генератор получил флаги:

```bash
python3 .agents/skills/harness-management/children/environment-sync/scripts/generate-dsh-config.py --root . --no-llm --no-model-selection
```

Такой запуск побайтно воспроизводит текущий `.dsh/project.patch.yml`.
`smoke.sh` это сверяет.

---

## Как включить переключение моделей
<a id="как-включить-переключение-моделей"></a>
1. Ключи провайдеров: `DEEPSEEK_API_KEY`, `XAI_API_KEY`, `ANTHROPIC_API_KEY`,
   `GOOGLE_API_KEY` в окружении DSH или в `~/.dsh/.credentials.yaml`.
2. Перегенерировать патч без `--no-llm`:

   ```bash
   python3 .agents/skills/harness-management/children/environment-sync/scripts/generate-dsh-config.py --root . --no-model-selection
   ```

3. Перезапустить:

   ```bash
   dsh --patch .dsh/project.patch.yml web --no-open
   ```

4. Проверить `list_subagent_models`: должны появиться deepseek, xai, anthropic,
   google. Если пусто - смотреть stderr на `did not activate`.

5. После зелёной проверки вернуть в `dsh-router` маршрут:
   план - xai/grok-4.7, аудиторы - anthropic/claude-sonnet-5-5 и
   google/gemini-3.8-flash.

Ожидаемая цена включения: при старте возможен warning про
`modelSelectionSettings` (не критичен) и рост расхода токенов на тяжёлых ролях.

---

## Fallback, если провайдер недоступен
<a id="fallback,-если-провайдер-недоступен"></a>
| Роль | Fallback |
|---|---|
| план | deepseek-flash + полный канон prepare-plan |
| аудит плана | структурные гейты P7.0/P7.8/P7.9/G13 вместо второго мнения |
| диагностика ошибок | deepseek-flash + MCP-трассировка (CBM, sourcegraph) |

Guard: если аудитор вернул null, помечай `finalStatus: failed`,
`reason: provider_unavailable`. Один null не считается успешным аудитом.

---

## Связи
<a id="связи"></a>
- [Workflow](./deepseek-harness-03-workflow.md) - где модель участвует
- [Установка](./deepseek-harness-02-ustanovka.md) - проверка после перезапуска
- [Скрипты](./deepseek-harness-05-skripty.md) - оболочка
- `.dsh/adapters/models.md` - рабочая памятка по ролям

---

## Известные проблемы и ограничения
<a id="известные-проблемы-и-ограничения"></a>
- `grok-4.7`, `claude-sonnet-5-5`, `gemini-3.8-flash` - намерения из overlay.
- Проверка только через `list_subagent_models` после включения `llm-pi-ai`.


- Settings -> Models показывает только зарегистрированные маршруты.
- Без `llm-pi-ai` там один deepseek-account.


- В headless строка `modelSelectionSettings` не активируется, warning в stderr.
- На работу web-профиля это не влияет, но логи читать надо.

---

## История изменений
<a id="история-изменений"></a>
- 2026-10-20: создан
- 2026-10-20: переписан по факту: одна модель, флаги генератора, инструкция включения

#deepseek #models #routing
