# Аудит: `harness_transfer.py` — CLI движка переноса харнеса

<!-- meta
type: research
status: actual
updated: 2026-11-26
related: [../README.md, ../../harnes/doc_rules.md, ../rename-copytrust-to-seharnes.md,
../../../agents/skills/harness-router/children/new-project/README.md]
tags: [arena, research, audit, harness, transfer, cli]
-->

## Суть

`harness_transfer.py` — подготовленный CLI-движок для **переносимости харнеса** между
проектами. Это основная заявка «сделать харнес переносимым»: он умеет инвентаризовать,
предпросматривать, аппровать, применять, откатывать и сверять харнес, а также экспортировать
kit. Аудит проводит полную проверку объекта: структура, функционал всех режимов, runtime-
прогоны на реальном repo, тестовый suite и поиск системных неточностей. Код не менялся.

> **AI:** читай этот файл для понимания состояния движка переноса и его находок. Планы
> по фиксам надо согласовывать отдельно — этого документа недостаточно для правки кода.

---

## Объект аудита

| Путь | Роль | Размер |
|---|---|---|
| `.agents/skills/harness-router/children/new-project/scripts/harness_transfer.py` | Входная точка, 11 подкоманд | 1161 строка |
| `.../scripts/export_kit.py` | Экспорт kit (режим `export`) | 607 строк |
| `.../scripts/harness_wizard.py` | Мастер (заявлен, не включён в маршрут) | 143 строки |
| `.../scripts/lib/transfer_*.py` | Модули движка (18) | ~1.5k строк |
| `.../scripts/lib/kit_selection.py`, `kit_adapt.py` | Подбор состава kit и адаптация | 128 строк |
| `.../tests/test_*.py` | Тесты (24 файла) | 2880 строк |
| `.../docs/scripts/harness_transfer.py.md` | Операционная документация | 121 строка |

**Состав движка (20 модулей в `lib/`):** `transfer_apply`, `transfer_backup`,
`transfer_diff`, `transfer_git`, `transfer_inventory`, `transfer_journal`,
`transfer_local`, `transfer_merge`, `transfer_modes`, `transfer_plan`,
`transfer_prepare`, `transfer_process_lock`, `transfer_receipt`,
`transfer_recovery`, `transfer_replace`, `transfer_report`, `transfer_rollback`,
`transfer_tree`, `kit_selection`, `kit_adapt`.

**11 подкоманд:** `inventory`, `fetch`, `plan`, `verify`, `approve`, `apply`,
`rollback`, `render`, `compact`, `export`, `adopt`.

---

## Методы аудита

1. Чтение кода входной точки и всех модулей `lib/`.
2. Сборка (`py_compile`) всех скриптов — без ошибок.
3. Полный тестовый suite (`python3 -m unittest discover -s tests`).
4. Runtime-прогоны команд на реальном repo: `inventory`, `plan`, `verify`, `export --dry-run`.
5. Поиск системных неточностей (docstring vs код, check-сообщения vs реалии, dead-аргументы).

---

## Функциональный аудит команд

### read-only: `inventory`, `fetch`, `plan`, `verify`

- **`inventory`** — снимок Source/Target (SHA-256, режим, защищённые пути).
  Runtime: `inventory --source . --target . --root .agents/skills` → `source_file_count:
  1142`, check `secret_scan: passed`. Не требует receipt. ✅
- **`fetch`** — получает одну ref в локальное bare-хранилище, без checkout/hooks/filters.
  Guard: `validate_remote` (разрешённые схемы, отклоняет встроенный пароль в URL),
  `--allow-local` для абсолютного локального пути. ✅
- **`plan`** — read-only предпросмотр. Runtime: `plan --source . --target <tmp> --root
  ... --profile developer --operation update` → `status: needs_decision`,
  `source_file_count: 334`, `decisions_required: 334` (fail-closed: без receipt каждый
  файл требует решения). Guard: «source and target roots must not overlap» срабатывает
  корректно при совпадающих Source/Target. ✅
- **`verify`** — сверка Target с receipt. Runtime: без `receipt.json` → корректный
  preflight «verify requires .doc/web/state/transfer/receipt.json». ✅

### запись: `approve`, `apply`, `rollback`, `render`, `compact`, `adopt`

- **`approve`** — проверяет решения и фиксирует план в `<plan_id>.approved.json`
  (права `0600`, `plan_sha256` + `source_tree_digest`). Fail-closed по сроку плана. ✅
- **`apply`** — применяет утверждённый план: проверка плана, backup, SQLite-журнал,
  receipt последним. После commit автоматически пересобирает views, если `.agents/skills`
  есть; при failure render → `committed_render_failed`. ✅
- **`rollback`** — восстанавливает активный журнальный прогон из backup. ✅
- **`render` / `compact`** — вызывают доверенные генераторы (`render_agent_views.py`,
  `compact_agent_views.py`) как subprocess с таймаутом, parse JSON-отчёт. ✅
- **`adopt`** — предпросмотр/legacy-adopt; проверяет план и receipt, не меняет содержимое
  выбранных файлов. ✅

### экспорт: `export`

- **`export`** — вызывает `export_kit.export` (один walker с предпросмотром и переносом).
  Runtime: `export --dry-run` → `status: dry-run`, возвращает `added/deleted/kept/
  overwritten/counts/warnings`. Режимы `install/update/mirror`. ✅

---

## Тестирование

```
Ran 117 tests in 11.582s
OK
```

- 24 файла, 117 тестов — **все проходят**.
- Покрыты: безопасность путей (symlink/hardlink/коллизии/escape-корень), журнал и
  recovery (crash/fencing), backup, apply-fault, rollback, receipt, merge, экспорт и
  policy-гейты.

---

## Найденные проблемы и находки

### Н-1: Устаревший docstring модуля (P1) против реального функционала (P2)

- **Симптом:** верхний docstring `harness_transfer.py`: «Read-only harness transfer
  engine: fetch, inventory, plan and verify. This is the P1 surface… It does not
  establish release trust, approve decisions, apply changes or finalize a receipt.».
- **Причина:** документ от точки P1; с тех пор добавлены `approve`, `apply`, `rollback`,
  receipt, `render`, `compact`, `adopt`.
- **Ограничение/решение:** docstring не отражает действительный контракт. При правке
  docstring обновить описание режимов и границы. Файл:
  `.agents/skills/harness-router/children/new-project/scripts/harness_transfer.py:1-9`.

### Н-2: Противоречие check «fetch not implemented» против реальной команды `fetch`

- **Симптом:** в `plan` и `inventory` checks добавляется
  `_check("fetch", "not_run", "Git fetch is not implemented…")` (строки 788, 886),
  но команда `fetch` реализована (`_run_fetch`, строка 843; `fetch_ref`/`validate_remote`
  в `lib/transfer_git.py`).
- **Причина:** проверка-заглушка осталась от ранней стадии.
- **Ограничение/решение:** сообщить в `checks` не «not implemented», а адекватный статус
  для `plan`/`inventory` (например, `not_run` с причиной «fetch отдельный запрос»).
  Не критично по безопасности, но вводит в заблуждение. Файл:
  `scripts/harness_transfer.py:788,886`.

### Н-3: Dead-аргументы `--non-interactive` и `--yes`

- **Симптом:** `--non-interactive` добавлен в почти все подкоманды, но нигде не
  используется в логике; `--yes` для `export` тоже принимается и не читается.
- **Причина:** заявлены как «accepted for contract compatibility; engine never prompts».
- **Ограничение/решение:** не баг, но опциональные аргументы дают ложное ощущение
  настройки. Либо реализовать (явно ноль-интерактивности), либо убрать/задокументировать
  в контракте. Файл: `scripts/harness_transfer.py` (блок `_build_parser`).

### Н-4: Хардкод-списки `generated`/`defaults` в `_profile_selection`

- **Симптом:** в `_profile_selection` вписан большой список generated-paths и
  `defaults`-исключений (строки ~230-250).
- **Причина:** быстрая локальная реализация.
- **Ограничение/решение:** списки могут отстать от канона (`canon-paths.yaml`). Если
  канон изменится, профиль может выбрать неверный состав. Рекомендовать вынести в
  политику/манифест и сверять с `canon-paths.yaml`. Файл:
  `scripts/harness_transfer.py`, функция `_profile_selection`.

### Н-5: Fail-closed без baseline: все файлы → decisions

- **Симптом:** без receipt и `--base-commit` каждый существующий файл Target требует
  решения (`needs_decision`, 334/334 в прогоне).
- **Причина:** проектный choix: исторический commit/receipt не доказывают владение.
- **Ограничение/решение:** честно, но для повторных переносов это громоздко. Решение —
  всегда передавать `--base-commit`/`--use-receipt` либо подготовить baseline-receipt.
  Документировано, не баг.

### Н-6: `verify` режим не переносим между Git/Windows

- **Симптом:** `verify` сообщает различие режима как предупреждение;
  `mode_comparison: raw_os_mode_not_portable`.
- **Причина:** Git-режимы и Windows-режимы не приведены к общей модели.
- **Ограничение/решение:** ограничение по переносимости, документировано. Пока
  достаточно для SHA-256-сверки.

### Н-7: Auto-render в `apply` зависит от наличия `.agents/skills`

- **Симптом:** после commit `apply` автоматически рендерит views, только если в Target
  есть `.agents/skills`; сбой render → `committed_render_failed` (при этом commit уже
  выполнен).
- **Причина/решение:** допустимо, статус честно сигнализирует. Но auto-render можно
  отключить `--no-render`. Документировано.

---

## Позитивные проверки (что работает)

- **Безопасность путей:** symlink/hardlink/junction, escape-корень, коллизии регистра и
  юникода, абсолютные пути и `..` — отклоняются до открытия файлов (tests:
  `test_transfer_inventory`, `test_transfer_plan`, `test_transfer_safety`).
- **Policy-гейт:** Core-профиль останавливается при `POLICY_MISSING` /
  `TRUSTED_GATE_WEAKENING` до создания Target.
- **Секретный scan:** известные сигнатуры секретов (из Mirror, не из исходника кандидата).
- **Fail-closed decisions:** без baseline/receipt → все пути в решения.
- **Контроль плана:** `plan_sha256`, `source_tree_digest`, срок плана, проверка
  current-snapshot перед apply.
- **Выделение привилегий:** state-директории с `0700` (POSIX), approved-файл с `0600`.

---

## Выводы

- Движок **работает и соответствует заявленному контракту** на уровне 11 команд:
  read-only-предпросмотр, approve/apply/rollback с journal+backup+receipt, render/compact,
  экспорт kit.
- **Тесты зелёные** (117/117), static-сборка без ошибок, runtime-прогоны корректны.
- **Системные неточности** — это не баги безопасности, а **документационный и
  контрактный рассинхрон**: устаревший docstring (Н-1), противоречивый check (Н-2),
  dead-аргументы (Н-3), хардкод-списки (Н-4). Устранимы точечной правкой.
- **Ограничения по переносимости** (Н-5, Н-6, Н-7) — осознанные, документированные.

**Рекомендация:** движок готов к использованию. Перед массовым переносом:
(1) обновить docstring и check-сообщения; (2) вынести `generated/defaults` в политику;
(3) для повторных переносов использовать baseline (`--base-commit`/`--use-receipt`).
Фиксы требуют отдельного согласованного плана.

---

## Связи

- [План де-брендинга copytrust → seharnes](../rename-copytrust-to-seharnes.md) —
  связанный контур: переносимость и переименование
- [README Arena](../README.md) - точка входа
- [`new-project` SKILL.md](../../../agents/skills/harness-router/children/new-project/SKILL.md) -
  контракт навыка
- [Документация скрипта](../../../agents/skills/harness-router/children/new-project/docs/scripts/harness_transfer.py.md)
- [Правила работы с документацией](../../harnes/doc_rules.md)

---

## История изменений

- 2026-11-26: проведен аудит: структура, 11 команд, runtime-прогоны, 117 тестов.
  Зафиксированы находки Н-1..Н-7. Код не менялся.
