# Инструкция типа `intake`: постановка и формализация задачи

## Когда применять

Используй `intake`, когда сырой вход нужно превратить в проверяемую задачу:
из сообщения человека, внешнего mirror или серии уточняющих ответов.

Триггер conversational skill: **«постановка задачи»**.
Ответ на запуск:

> Готов собирать требования. Буду уточнять по одному вопросу и сформирую задачу,
> когда вы скажете «сформулируй задачу» или «собери задачу».

## Граница диалога

Обычное обсуждение не становится нормативным фактом автоматически. В активной
сессии разделяй:

- факты и требования человека;
- открытые вопросы и неизвестное;
- предложения/варианты и их плюсы/минусы;
- решения, которые человек явно подтвердил;
- provenance: сообщение, файл, скриншот или ссылка, откуда взят факт.

Не выдумывай значения, не закрывай вопрос молча и не меняй policy workspace.
Следующий вопрос выбирай по текущему gap и контексту, а не по фиксированному
скрипту; за один ход задавай один небольшой набор связанных уточнений.

## Запасной путь

Если `code-graph` или `memory` недоступны, используй поиск по файлам, явные
refs и provenance. Не объявляй capability доступной без project binding.

## Рабочие команды

До финального подтверждения создай persistent conversational draft явным
`start` (без `--persist` typed/operational task не создаётся):

```bash
tcheck intake start --root <root> --queue <queue> \
  --title «Постановка задачи: <краткое название>» --by <actor>
tcheck intake list --root <root>
tcheck intake show --root <root> --session <session-id>
```

Входы сохраняются с provenance. Текст, файл и screenshot идут разными explicit
paths; file/screenshot bytes копируются в `inputs/` с digest:

```bash
tcheck intake capture --root <root> --session <session-id> \
  --text «Нужен CSV» --source conversation:3 \
  --source-kind message --by <actor>
tcheck intake capture --root <root> --session <session-id> \
  --file /tmp/requirements.png --by <actor>
```

Вопросы задаются последовательно, по одному открытому вопросу:

```bash
tcheck intake ask --root <root> --session <session-id> \
  --question «Какой формат?» --choices csv,json --default csv \
  --on-decline ask_again --on-disabled ask_again --by <actor>
tcheck intake answer --root <root> --session <session-id> \
  --question-id Q-001 --value csv --by <actor>
```

Фраза **«зафиксируй в задаче»** означает `tcheck intake fix`: немедленную
запись подтверждённого факта в текущий persistent draft с provenance. Если
операционная draft task действительно нужна, это отдельный opt-in:
`intake start --persist`.

## Финализация

Только после явного «сформулируй задачу»/«собери задачу»:

1. сверни требования в `problem`, goals, scope, acceptance и verify;
2. покажи пользователю краткое резюме и неизвестные;
3. получи подтверждение, если остаются неоднозначные или опасные решения;
4. создай рабочую запись выбранного типа (`feature`, `fix`, `planning` и т. п.);
5. свяжи её с intake через `parent`/`ref`, не копируя источник без provenance;
6. оставь handoff с тем, что принято и что осталось открытым.

Пример explicit finalization:

```bash
tcheck intake finalize --root <root> --queue <queue> \
  --session <session-id> --title «<заголовок>» --type <тип> \
  --problem «...» --goals «...» --acceptance «...» \
  --verify «python3 -m unittest discover tests» --by <actor>
```

Команда требует problem, acceptance и verify, создаёт typed task, сохраняет
`artifacts/intake.json` и provenance handoff. `--allow-open` — отдельное
подтверждение remaining risks; обычный finalize не закрывает открытые вопросы.

## Аудит задачи

Фраза **«проведи аудит задачи»** не означает автоматическое изменение записи.
Создай read-only audit child или запусти `issue-delivery` с `plan-audit`, затем
проверь:

- полноту и проверяемость acceptance;
- scope, dependencies и конфликт с другими задачами;
- refs на код и документацию;
- существующие flows, types и source-of-truth;
- evidence, tests и документационный impact;
- риски, неоднозначности и пропущенные negative paths.

```bash
tcheck intake audit --root <root> --queue <queue> \
  --session <session-id> --task <task-id> --by <actor>
```

Команда оставляет `TASK-AUDIT-1` в отдельном `plan-audit` child с verdict,
findings, remaining questions/risks и refs checked. Audit read-only и не меняет
исходную задачу; отдельное `ttask set` остаётся explicit write intent.

## Результат

Intake должен вернуть gaps, assumptions, refs, draft child и handoff. Рабочая
задача должна иметь явный тип, источник требований, acceptance и проверку. При
отсутствии достаточных данных остановись с вопросом, а не создавай фиктивный
нормативный факт.
