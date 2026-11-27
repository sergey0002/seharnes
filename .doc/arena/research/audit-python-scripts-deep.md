# Углубленный анализ всех Python-скриптов harness

**Проект:** `seharnes`
**Дата:** 2026-11-26
**Объект:** **полный углубленный анализ всех Python-скриптов репозитория** — не только CLI-поверхность, а код, архитектура, паттерны, качество, зависимости, потенциальные дефекты.
**Образ:** ветка `arena/7bf00d32-seharnes`, commit `408da959`.
**Метод:** пересчёт, статический анализ, compile-проверка всех файлов, импорт-анализ, паттерн-анализ, просмотр ключевых архитектурных модулей.

---

## 1. Введение и методология

Задача — «учесть все Python-скрипты в harness и углублить анализ». В предыдущих шагах был собран CLI-справочник (поверхность команд). Здесь — **анализ кода вглубь**: структура, архитектура, паттерны, зависимости, метрики качества, дефекты.

**Метод:**
1. Полный пересчёт `.py` в repo (без node_modules/.git), разбивка production/tests.
2. Импорт-анализ: выявление третьих библиотек.
3. compile-проверка **каждого** production- и test-скрипта (`py_compile`).
4. Паттерн-анализ: argparse, exit-коды, атомарные записи, валидация, fail-closed.
5. Просмотр ключевых архитектурных модулей (adapters, transfer engine, render).
6. Поиск системных проблем (SyntaxError, dead-арги, env-зависимости, coupling).

---

## 2. Полный пересчёт Python-файлов

| Размер | Количество | Строк |
|--------|------------|-------|
| Все `.py` (repo) | **309** | — |
| Production (без tests) | **209** | **66 889** |
| Tests | **100** | 17 821 |
| из них harness-router (всё) | — | 31 346 |
| harness-router production | — | 22 161 |

**Размерность:** ~67k строк production-кода, ~18k строк тестов. Test-соотношение ≈ **1 : 3.7** (test-строк на production-строку).

**Entrypoint vs library:**
- **110** entrypoint (`__main__`) — вызываемые команды.
- **99** library-модуль (функции/классы, без прямого запуска) — включая `new-project/lib`, `harness-core/lib`, `adapters`, `tdcore`.

**Самые большие production-модули (всё repo):**
1. `todone/scripts/tdcore/autodoc.py` — 5899 л.
2. `mirror/scripts/harness_mirror.py` — 2713 л.
3. `skill-auditor/scripts/static_audit.py` — 2648 л.
4. `todone/scripts/tdcore/flow.py` — 1933 л.
5. `todone/scripts/tdcore/task_cli.py` — 1777 л.

**Наибольшие в harness-router:** `harness_mirror.py` (2713), `doc_script.py` (1744), `harness_transfer.py` (1161).

---

## 3. Зависимости: 100% standard library

**Главный архитектурный вывод: в репозитории нет третьих Python-библиотек.** Все импорты — из stdlib:

| Импорт | Частота | | Импорт | Частота |
|--------|---------|-|--------|---------|
| pathlib | 154 | | tempfile | 19 |
| json | 141 | | transfer_inventory | 15 |
| sys | 103 | | stat | 15 |
| re | 98 | | transfer_plan | 13 |
| argparse | 96 | | dataclasses | 13 |
| os | 86 | | transfer_diff | 11 |
| hashlib | 45 | | copy | 11 |
| shutil | 43 | | urllib | 10 |
| subprocess | 41 | | importlib | 10 |
| datetime | 29 | | typing | 6 |

- Нет `requests`, `click`, `typer`, `yaml`, `pydantic`, `pytest` (в production) — **только stdlib**.
- `hashlib` (45) — честность/хэши (manifest, parity, receipt).
- `sqlite3` (transfer_journal) — встроенная БД для state-machine.
- Собственные модули (`transfer_*`, `rule_model`, `tdcore`) — внутренняя координация.

**Оценка: отличная портативность.** Скрипты работают на любом Python 3 без `pip install`. Это сильный工程质量-фактор для распределённого harness.

---

## 4. Архитектура по секциям

### 4.1 Harness core (`harness-router/children/harness-core`)
- **`harness_cli.py`** (539 л.) — orchestrator: `doctor/setup-hooks/sync/export/setup/mcp-audit/verify`.
- **`adapters/`** (10 файлов) — **единый контракт адаптера среды**:
  ```python
  class BaseAdapter:
      name = "base"
      def check(self, root: Path) -> list[str]: ...
      def sync(self, root: Path, dry_run: bool = False) -> list[str]: ...
  ```
  9 адаптере: cursor, codex, kilo, opencode, omp, qoder, qwen, agents, dsh. `harness_cli` динамически грузит `adapters/{env['adapter']}.py`. **Open-closed pattern** — новая среда = новый адаптер, без изменения orchestrator.
- **`lib/`** — config, paths, ports, mcp, manifest, report, artifact_status, prompt_budget.
- **`canon_paths.py`** (342 л.) — канонические пути.
- **`rebuild-routers.py`, `render_policy_docs.py`**.

### 4.2 Transfer engine (`new-project/scripts/lib/`) — 20 модулей
Собран как **композитный engine с чётким разделением**:

| Модуль | Роль (из docstring) |
|--------|----------------------|
| `transfer_inventory.py` | рид-only снапшот выбранных регулярных файлов |
| `transfer_diff.py` | рид-only трёхсторонняя классификация для preview |
| `transfer_plan.py` | рид-only предложения обновления |
| `transfer_modes.py` | semantics `install/update/mirror` |
| `transfer_journal.py` | **SQLite state machine** для future writer |
| `transfer_process_lock.py` | process-lock |
| `transfer_backup.py` / `transfer_recovery.py` / `transfer_rollback.py` | backup/recovery/rollback |
| `transfer_apply.py` | применение + откат approved-плана |
| `transfer_replace.py` / `transfer_merge.py` | атомарная замена/слияние |
| `transfer_receipt.py` | provisional receipt (недоверенный) |
| `transfer_tree.py` | TreeSnapshot |
| `transfer_local.py` | локальные политики цели |
| `transfer_prepare.py` / `transfer_report.py` | подготовка/отчёт |
| `kit_selection.py` | разбор набора файлов кита по profile из kit.json |
| `kit_adapt.py` | адаптации цели после помещения файлов |

**Архитектура journal (state machine):**
```
locked → backed_up → replacing → validating → committed
                    ↘ rolling_back → rolled_back | needs_manual_recovery
```
С прогрессией `PRAGMA synchronous=FULL`, lease (run_id/generation/token), `takeover_for_recovery`. **Глубоко продуманная, безопасная механика** — не блоковое копирование, а состояние с откатом.

**Honest contract:** docstring явно гласит — journal **не** backup/recovery engine, callers должны защищать independently. Это корректный, непереоценённый контракт.

### 4.3 environment-sync (19 скриптов)
- **`render_agent_views.py`** — trusted-generator dispatch (никогда не запускает скрипты из render-root).
- **`environment_policy.py`** — registry + `safe_path` (path-traversal/symlink guards).
- **`rule_model.py`** — единая модель правил (4 kind).
- **`generate-*-config.py`** — 9 генераторов по средам (атомарные записи, `--check`).
- **`verify_*.py`** — parity/triggers/generated_copies.
- **`compact_agent_views.py`** — осторожная уборка (Qoder-дерево только при точном совпадении).
- **`sync-agent-views.sh`** — orchestrator.

### 4.4 Управление скилами (add/remove/create/audit/scan/skill-creator/skill-auditor)
- `add_skill.py` (502), `remove_skill.py` (418), `create_skill.py` (216), `audit_skill.py` (314), `scan_local_skills.py` (326).
- skill-creator: `scaffold_skill.py`, `package_and_verify.py` (17-agent portability).
- skill-auditor: `static_audit.py` (2648 л.), `eval_runner.py`, `score_aggregator.py`, `self_test.py`.

### 4.5 task-router, documentation-router, todone
- task-router: intake, task_spec, analytics, testing-router (21 скрипт), reporting.
- documentation-router: `jsondoc.py` + 14 модулей, project-doc (check-links, check-doc-text, task-identity).
- todone: `tdcore` (33 модуля) — трекер с общим контрактом вывода.

---

## 5. Ключевые архитектурные паттерны

1. **Adapter pattern (open-closed).** `BaseAdapter.check/sync`; новые среды — новые адаптере. orchestrator не меняется.
2. **Transfer state machine.** SQLite-journal с lease + transition + recovery. Не «скрипт-копироточка», а аккуратный engine с откатом.
3. **Trusted-generator execution.** `render_agent_views` вызывает генераторы из install, **никогда** не с render-root — защита от execution-injection.
4. **Atomic writes.** `NamedTemporaryFile` + `os.fsync` + `os.replace`, сохранение `st_mode` (34 скрипта).
5. **fail-closed guards.** `safe_path` (traversal/symlink), linked-output rejection, `_must_check`, receipt-validation.
6. **read-only vs mutating разделение.** `inventory/plan/verify` — только чтение; `apply/export` — запись через approved-план.
7. **Единый контракт вывода** (todone): одна строка на объект, срезы `--json/--fields/--quiet/--limit`, ошибка — одна строка из 4 частей.
8. **Повторяющиеся «интерфейсы» CLI:** 99 argparse-entrypoint, но единые общие флаги (`--root/--json/--check/--dry-run/--yes`).

---

## 6. Метрики качества

| Метрика | Результат | Оценка |
|----------|-----------|--------|
| Module docstring | **205 / 209** (98%) | отлично |
| Type hints | 165 скриптов | хорошо |
| try/except | 143 скрипта | нормально |
| **assert в production** | **только 2** | **хорошо** — валидация не через assert |
| `__main__` entrypoint | 110 | — |
| json.dumps | 118 скриптов | machine-readable-first |
| Функций всего | 2495 | — |
| Третья библиотека | **0** | отличная портативность |

**Комментарий:** 98% docstring-покрытие и отсутствие third-party-зависимостей — высокий уровень инженерной культуры. Использование `assert` в production почти отсутствует — валидация идёт через явные проверки и fail-closed, что правильно для production (assert теряется при `-O`).

---

## 7. Нахождения (deep findings)

### Ф-П-1. **2 production-скрипта не компилируются** (f-string с backslash)
- `.agents/skills/task-router/children/jira/scripts/export_task.py:280`
- `.agents/skills/task-router/children/reporting-router/children/task-change-report/scripts/generate_report.py:540`
**Причина:** `f"...{val.replace('|', '\\|')}"` — backslash внутри f-string expression, **запрещён в Python < 3.12**. Эти скрипты **не запускаются вообще** (SyntaxError при import).
**Класс:** дефект (блокирующий). **Лечение:** вынести выражение в переменную или использовать `.format`/сплит.

### Ф-П-2. **todone: точки входа с relative-import** (не запускаются напрямую)
`tdcore/cli.py`, `task_cli.py` — `from . import schema` → ImportError при прямом `python3 cli.py`.
**Класс:** фрагментация входа. **Лечение:** вызывать как модуль (`python3 -m tdcore.task_cli`) или добавить `sys.path` bootstrap в thin-обёртки (`ttask.py`/`tqueue.py` уже делают `sys.path.insert`).

### Ф-П-3. **dead-аргументы** в engine
`harness_transfer.py` (и `export` subcommand) declare `--non-interactive`/`--yes` как «accepted; engine never prompts» — флагами заявлен интерфейс, который engine не использует. Не ошибка, но **ложный интерфейс** (порождает ожидание, что что-то может запросить подтверждение).
**Класс:** UX/contract-noise.

### Ф-П-4. **env-зависимость без fallback**
`setup-workspace.py` hard-требует `rsync`/`node` (exit 78 без retry/cleanup). `collect-shots.py`/`collect-data-test.py` требуют контекст корня.
**Класс:** портативность (не дефект логики).

### Ф-П-5. **cross-skill coupling**
`sync-agent-views.sh` опирается на `mirror/`, `mcp-audit/`, `add-skill/` — единая точка ломания при переносе соседних скилов.
**Класс:** архитектурная связность (по проектной метро).

### Ф-П-6. **Без-argparse скрипты**
`collect-data-test.py`, `collect-shots.py` — конфигурируются через контекст/SCAN_DIRS, не argparse.
**Класс:** неоднородность входа (не дефект).

### Ф-П-7. **Огромные модули**
`tdcore/autodoc.py` (5899 л.), `harness_mirror.py` (2713 л.), `static_audit.py` (2648 л.) — огромные single-file-модули. Не ошибка, но снижает читаемость/сопровождение; возможен split.
**Класс:** maintainability.

### Ф-П-8. **TODO-«ложные срабатывания»**
453 попадания `TODO/FIXME` — но подавляющее большинство в **строковых шаблонах** (шаблоны Cest-тестов, PLACEHOLDERS-множества, regex), а не в коде-comment. Реальных незавершённых кусков мало.
**Класс:** false-positive (не проблема кода).

---

## 8. Compile-проверка (всё repo)

- **Production:** 207 / 209 compile OK; **2 SyntaxError** (Ф-П-1).
- **Tests:** 100 / 100 compile OK (SyntaxError в tests **нет**).

**Вывод:** дефекты синтаксиса сосредоточены в **двух leaf-скриптах task-router** (jira export, change-report), не в core-harness. Core (harness-router, environment-sync, new-project engine, todone) **полностью compile-чист**.

---

## 9. Вердикт

**Python-код harness — зрелый, хорошо структурированный, портативный.**

**Сильные стороны:**
- **100% stdlib** — без `pip install`, работа на любом Python 3.
- **98% docstring**, type-hints, явные exit-коды.
- **Глубокая архитектура:** adapter-pattern, transfer-state-machine (SQLite), trusted-generator-exec, atomic-writes, fail-closed.
- **Чёткое разделение** read-only / mutating, inventory/plan/verify vs apply/export.
- **Валидация без assert** (production-безопасно).
- Core-harness compile-чист.

**Неровности (peripheral, не ядро):**
- **2 блокирующих SyntaxError** (leaf task-router) — реальный, но локальный дефект.
- todone-фрагментация входа (relative-import).
- dead-аргументы, env-зависимость, cross-skill coupling, огромные модули.

**Общая оценка: 8.5–9 из 10.** Ядро harness — высокого качества; шероховатости на периферии (task-router leaf, invocation-конвенции), без системных дефектов ядра.

---

## 10. Рекомендации (по приоритету)

1. **Ф-П-1 (блокирующий):** исправить f-string-backslash в `export_task.py` и `generate_report.py` (вынести в переменную / `.format`). Это чинит два полностью-неработающих скрипта.
2. **Ф-П-2:** либо документировать `python3 -m tdcore.*` как единственный вход, либо добавить `sys.path`-bootstrap в все thin-обёртки todone.
3. **Ф-П-7:** рассмотреть split огромных модулей (`autodoc.py`, `harness_mirror.py`, `static_audit.py`) для сопровождения.
4. **Ф-П-3:** либо реализовать, либо убрать dead-аргументы `--non-interactive`/`--yes`, где engine не использует их.
5. **Ф-П-4:** задокументировать rsync/node как hard-contract или добавить fallback в `setup-workspace.py`.
6. **Ф-П-5:** задокументировать или вынести shared-verify из соседних скилов.

---

## 11. Связи

- CLI-справочник (поверхность): `.doc/arena/research/cli-reference-all-commands.md`.
- Аудит transfer-quality: `.doc/arena/research/audit-harness-transfer-quality.md`.
- Аудит environment-sync: `.doc/arena/research/audit-environment-sync.md`.
- CLI-аудит: `.doc/arena/research/audit-harness-transfer-cli.md`.
- Canonical: `.doc/harnes/seharnes-transfer.md`.

*Анализ выполнен по статическому анализу всех Python-файлов, compile-проверке и чтению ключевых архитектурных модулей.*
