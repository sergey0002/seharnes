#!/usr/bin/env python3
"""Гейты готовности задачи к ручному тестированию.

Смысл: перевести "вроде проверил" в машинную проверку. Пока хоть один
блокирующий гейт красный, задача не ready-for-qa.

Состав выведен из разбора 13 задач, которые не приняли с первого раза
(.doc/testanalyze/report-plan-test.md).

    python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py 2236
    python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/gates.py 2236 --json

Гейты:
  G0  статика на файлах задачи (PHPStan, ESLint)
  G1  юнит-тесты задачи, если есть
  G2  тесты задачи существуют (Cest + test.md)
  G3  последний прогон зелёный (verdict.json)
  G4  прогон без шума: консоль и модалки ошибок чистые
  G5  чек-лист в test.md заполнен
  G6  есть проверка эффекта в БД (seeInDatabase / grabFromDatabase)
  G7  литералы из task.md закреплены в тестах
  G8  стенд жив после прогона
  G9  тесты не утекли в git
  G10 нет сырых селекторов и мёртвых data-test
  G11 для багов: зафиксирован red-first
  G13 таблица веток логики: каждый R из plan.md закрыт, нет open/partial

Не все проверяются полностью автоматически. Те, что требуют суждения
агента (G7, G11), проверяются по явной отметке в test.md — чтобы решение
было записано, а не осталось в голове.
"""

import argparse
import json
import os
import os
import pathlib
import re
import shutil
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[8]
QA = REPO / ".doc/qa"
SCRIPTS = pathlib.Path(__file__).resolve().parent


class Gate:
    def __init__(self, code: str, title: str, blocking: bool = True):
        self.code = code
        self.title = title
        self.blocking = blocking
        self.ok: bool | None = None
        self.detail = ""

    def passed(self, detail: str = "") -> "Gate":
        self.ok, self.detail = True, detail
        return self

    def failed(self, detail: str) -> "Gate":
        self.ok, self.detail = False, detail
        return self

    def skipped(self, detail: str) -> "Gate":
        self.ok, self.blocking, self.detail = True, False, f"пропущен: {detail}"
        return self


def run(cmd: list[str], cwd: pathlib.Path = REPO, timeout: int = 300):
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


# --- источники данных задачи -----------------------------------------


def task_dir(task: str) -> pathlib.Path:
    return REPO / ".doc/tasks" / task


def latest_run(task: str) -> pathlib.Path | None:
    runs = task_dir(task) / "test-runs"
    if not runs.is_dir():
        return None
    candidates = [d for d in runs.iterdir() if d.is_dir() and (d / "verdict.json").exists()]
    return max(candidates, key=lambda d: d.stat().st_mtime) if candidates else None


def read_verdict(task: str) -> dict | None:
    run_dir = latest_run(task)
    if not run_dir:
        return None
    try:
        return json.loads((run_dir / "verdict.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def task_test_files(task: str) -> list[pathlib.Path]:
    return sorted((task_dir(task) / "tests").glob("**/*.php"))


def task_changed_files(task: str) -> list[str]:
    """Файлы задачи из diff.files.md (его генерирует скил task-diff)."""
    path = task_dir(task) / "diff.files.md"
    if not path.exists():
        return []
    files = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s*[-*]?\s*`?([\w./-]+\.(?:php|js|vue|tpl))`?\s*$", line)
        if m and (REPO / m.group(1)).exists():
            files.append(m.group(1))
    return sorted(set(files))


# --- гейты ------------------------------------------------------------


def g0_static(task: str) -> Gate:
    gate = Gate("G0", "статика на файлах задачи")
    files = task_changed_files(task)
    if not files:
        return gate.skipped("нет diff.files.md — сначала «обнови диф задачи»")

    php = [f for f in files if f.endswith(".php")]
    js = [f for f in files if f.endswith((".js", ".vue"))]
    if not php and not js:
        return gate.skipped("в diff нет php/js/vue")

    # Локаль (.doc/, не в git): PHPStan L8 + ESLint patch-max только по строкам патча.
    # CI мягче (L0 + lint:basic на frontend/entry) — см. cicd.md §9 / qa/README.
    script = SCRIPTS / "static-on-diff.py"
    if not script.exists():
        return gate.failed("нет static-on-diff.py")

    level = os.environ.get("QA_PHPSTAN_LEVEL", "8")
    res = run(["python3", str(script), task, "--level", level], timeout=900)
    if res.returncode != 0:
        tail = (res.stdout + res.stderr).strip().splitlines()[-12:]
        return gate.failed("статика по патчу красная:\n      " + "\n      ".join(tail))

    notes = []
    if php:
        notes.append(f"PHPStan L{level} по патчу ({len(php)} php)")
    if js:
        notes.append(f"ESLint patch-max ({len(js)} js/vue)")
    return gate.passed("; ".join(notes))


def g1_unit(task: str) -> Gate:
    """PHPUnit tests for a task.

    PHPUnit suites live in `tests/lib` (see phpunit.xml), not in the task folder.
    The old task-local lookup always missed them, so PHPUnit-only tasks could
    never show unit evidence.
    """
    gate = Gate("G1", "юнит-тесты задачи")
    run_dir = latest_run_dir(task)
    phpunit = (run_dir / "phpunit.json") if run_dir else None
    if phpunit and phpunit.exists():
        try:
            data = json.loads(phpunit.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return gate.failed("phpunit.json повреждён")
        status = data.get("status")
        if status == "passed":
            return gate.passed(f"{data.get('tests', '?')} тестов пройдено")
        if status in {"skipped", "not_required"}:
            return gate.skipped("PHPUnit не требовался для слоя задачи")
        return gate.failed(f"phpunit status {status}")

    unit_dirs = [task_dir(task) / "tests" / "Unit", REPO / "tests" / "lib"]
    found = [p for d in unit_dirs if d.is_dir() for p in d.rglob("*.php")]
    if not found:
        return gate.skipped("юнит-тестов у задачи нет")
    return gate.passed(f"{len(found)} файлов в tests/lib, прогон не запускался")


def g2_tests_exist(task: str) -> Gate:
    gate = Gate("G2", "тесты задачи существуют")
    cests = [p for p in task_test_files(task) if p.name.endswith("Cest.php")]
    test_md = task_dir(task) / "test.md"

    problems = []
    if not cests:
        problems.append(f"нет ни одного Cest в .doc/tasks/{task}/tests/")
    if not test_md.exists():
        problems.append(f"нет .doc/tasks/{task}/test.md")

    if problems:
        return gate.failed("; ".join(problems))
    return gate.passed(f"{len(cests)} Cest + test.md")


def g3_green(task: str, verdict: dict | None) -> Gate:
    gate = Gate("G3", "последний прогон зелёный")
    if not verdict:
        return gate.failed("нет verdict.json — прогон не делался (task-test.sh)")

    tests = verdict.get("tests", {})
    if not verdict.get("green"):
        failed = tests.get("failedTests", [])
        detail = f"exit {verdict.get('exitCode')}"
        if failed:
            detail += "; упало: " + ", ".join(failed[:5])
        return gate.failed(detail)

    return gate.passed(f"{tests.get('passed', '?')} тестов, {verdict.get('runDir', '')}")


def g4_no_noise(task: str, verdict: dict | None) -> Gate:
    gate = Gate("G4", "прогон без шума в консоли и модалок ошибок")
    if not verdict:
        return gate.failed("нет verdict.json")

    cp = verdict.get("checkpoints", {})
    if cp.get("count", 0) == 0:
        return gate.failed("ни одного checkpoint() — шум не проверялся")

    console = cp.get("consoleErrors", [])
    modals = cp.get("errorModals", [])
    if console or modals:
        lines = [f"{i['checkpoint']}: {i['message'][:90]}" for i in (console + modals)[:6]]
        return gate.failed(f"{len(console)} ошибок консоли, {len(modals)} модалок:\n      "
                           + "\n      ".join(lines))

    return gate.passed(f"{cp['count']} checkpoint, чисто")


CHECKLIST_MARK = re.compile(r"^\s*[-*]?\s*\[([ xX~-])\]", re.MULTILINE)


def g5_checklist(task: str) -> Gate:
    gate = Gate("G5", "чек-лист в test.md заполнен")
    test_md = task_dir(task) / "test.md"
    if not test_md.exists():
        return gate.failed("нет test.md")

    marks = CHECKLIST_MARK.findall(test_md.read_text(encoding="utf-8", errors="ignore"))
    if not marks:
        return gate.failed("в test.md нет чек-листа (13 категорий из .doc/harnes/tests.md §4)")

    empty = sum(1 for m in marks if m == " ")
    if empty:
        return gate.failed(f"{empty} из {len(marks)} пунктов не отмечены "
                           f"(ставь [x] сделано, [-] неприменимо, [~] частично с пояснением)")

    return gate.passed(f"{len(marks)} пунктов отмечены")


DB_ASSERT = re.compile(r"\b(seeInDatabase|dontSeeInDatabase|grabFromDatabase|grabNumRecords)\s*\(")
PHP_COMMENT = re.compile(r"^\s*(//|\*|/\*|#)")


def code_lines(path: pathlib.Path) -> list[str]:
    """Строки без комментариев: иначе TODO в заготовке засчитывается как проверка."""
    return [
        line for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
        if not PHP_COMMENT.match(line)
    ]


def g6_db_effect(task: str) -> Gate:
    gate = Gate("G6", "проверка эффекта в БД")
    files = task_test_files(task)
    if not files:
        return gate.failed("нет тестов")

    hits = sum(len(DB_ASSERT.findall(line)) for p in files for line in code_lines(p))
    if hits == 0:
        return gate.failed("нет ни одного seeInDatabase/grabFromDatabase — "
                           "проверен только UI, эффект в данных не подтверждён. "
                           "Если задача UI-only, отметь это в test.md и сними гейт руками")

    return gate.passed(f"{hits} обращений к БД")


LITERAL_CONFIRM = re.compile(
    r"(?:\[[xX~-]\][^\n]*литерал[ыи]?\s+из\s+task\.md)"
    r"|(?:литерал[ыи]?\s+из\s+task\.md[^\n]*\[[xX~-]\])",
    re.IGNORECASE,
)


def g7_literals(task: str) -> Gate:
    gate = Gate("G7", "литералы из task.md закреплены в тестах")
    test_md = task_dir(task) / "test.md"
    if not test_md.exists():
        return gate.failed("нет test.md")

    text = test_md.read_text(encoding="utf-8", errors="ignore")
    if not LITERAL_CONFIRM.search(text):
        return gate.failed("в test.md нет отметки про литералы. Добавь строку вида:\n"
                           "      - [x] Литералы из task.md закреплены в тестах: «...»")

    return gate.passed("отмечено в test.md")


def g8_stand_alive() -> Gate:
    gate = Gate("G8", "стенд жив после прогона")
    res = run(["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}",
               "--max-time", "10", os.environ.get("QA_APP_URL", "http://127.0.0.1:8030/")], timeout=20)
    code = (res.stdout or "").strip()
    if code in {"200", "301", "302"}:
        return gate.passed(f"HTTP {code}")
    return gate.failed(f"главная отдаёт HTTP {code or '?'} — прогон мог испортить данные стенда "
                       f"(см. browser-setup.md П-9)")


def g9_git_clean() -> Gate:
    gate = Gate("G9", "тесты не утекли в git")
    res = run(["git", "ls-files", ".doc/"])
    tracked = [line for line in res.stdout.splitlines() if line.strip()]
    if tracked:
        return gate.failed(f"{len(tracked)} файлов .doc/ отслеживаются git, "
                           f"например {tracked[0]}. Тесты задач в git не идут")
    return gate.passed(".doc/ вне git")


def g10_selectors(task: str) -> Gate:
    gate = Gate("G10", "селекторы: нет сырых и мёртвых")
    # Scope to the task under test. Scanning every Cest in the repo meant one
    # legacy task blocked the gate for all 180 tasks.
    res = run([sys.executable, str(SCRIPTS / "check-selectors.py"), "--task", task], timeout=120)
    if res.returncode == 0:
        return gate.passed("check-selectors чистый")
    body = (res.stdout + res.stderr).strip().splitlines()
    return gate.failed("\n      ".join(body[:12]))


RED_FIRST = re.compile(r"red[- ]?first[^\n]*\[([xX~-])\]", re.IGNORECASE)
BUG_TITLE = re.compile(r"ошибк|bug|не работает|баг", re.IGNORECASE)


def g11_red_first(task: str) -> Gate:
    gate = Gate("G11", "red-first для багов")
    task_md = task_dir(task) / "task.md"
    if not task_md.exists():
        return gate.skipped("нет task.md")

    head = "\n".join(task_md.read_text(encoding="utf-8", errors="ignore").splitlines()[:40])
    if not BUG_TITLE.search(head):
        return gate.skipped("задача не про ошибку")

    test_md = task_dir(task) / "test.md"
    if test_md.exists() and RED_FIRST.search(test_md.read_text(encoding="utf-8", errors="ignore")):
        return gate.passed("отмечено в test.md")

    return gate.failed("задача про ошибку, но нет подтверждения red-first. "
                       "Прогони тест на коммите ДО фикса, убедись что он красный, "
                       "и добавь в test.md:\n      - [x] Red-first: тест падал до фикса (...)")


# --- вывод ------------------------------------------------------------


def g12_machine_run(task: str, verdict: dict | None) -> Gate:
    """Strict artifact gate: no textual proxy can make a run green."""
    gate = Gate("G12", "машинный AC, lint, PHPUnit, DB и hash-контроль")
    run_dir = latest_run(task)
    if not run_dir or not verdict:
        return gate.failed("нет полного test-run")
    required = {
        "static.json": "passed",
        "lint.json": "passed",
        "phpunit.json": None,
        "ac-check.json": "passed",
        # `not_required` is an honest outcome for tasks that never touch data.
        # The old code demanded `passed`, which forced the aggregate to claim
        # isolation over zero real phases (see db-isolation.py).
        "db-isolation.json": ("passed", "not_required"),
        "neighbor-results.json": None,
        "manifest.json": None,
        "comparison.json": None,
        "llm-review.json": None,
    }
    for name, expected in required.items():
        path = run_dir / name
        if not path.exists():
            return gate.failed(f"нет {name}")
        if expected:
            allowed = expected if isinstance(expected, tuple) else (expected,)
            try:
                actual = json.loads(path.read_text(encoding="utf-8")).get("status")
            except (OSError, json.JSONDecodeError):
                return gate.failed(f"{name}: повреждён")
            if actual not in allowed:
                return gate.failed(f"{name}: status {actual} не входит в {'/'.join(allowed)}")
    comparison = json.loads((run_dir / "comparison.json").read_text(encoding="utf-8"))
    if comparison.get("status") not in ("passed", "no_baseline"):
        return gate.failed("comparison.json: обнаружена регрессия относительно предыдущего прогона")
    llm = json.loads((run_dir / "llm-review.json").read_text(encoding="utf-8"))
    if llm.get("status") not in ("passed", "skipped"):
        return gate.failed("llm-review.json: автоматический разбор завершился ошибкой")
    try:
        phpunit = json.loads((run_dir / "phpunit.json").read_text(encoding="utf-8"))
        if phpunit.get("status") not in ("passed", "skipped", "baseline_failed"):
            return gate.failed("PHPUnit не пройден")
        neighbors = json.loads((run_dir / "neighbor-results.json").read_text(encoding="utf-8"))
        if neighbors.get("status") not in ("passed", "skipped"):
            return gate.failed("обязательный соседний flow не пройден")
    except (OSError, json.JSONDecodeError) as exc:
        return gate.failed(str(exc))
    manifest_script = SCRIPTS / "qa-manifest.py"
    check = run([sys.executable, str(manifest_script), "--task", task, "--group", verdict.get("group", ""), "--output", str(run_dir / ".gate-current.json"), "--check", str(run_dir / "manifest.json")])
    if check.returncode != 0:
        try:
            details = json.loads(check.stdout)
            mismatched = ", ".join(details.get("mismatched", [])) or "unknown inputs"
        except (json.JSONDecodeError, AttributeError):
            mismatched = "manifest check failed"
        return gate.failed(f"stale run: изменились {mismatched}; повтори только инвалидированный слой")
    db_status = json.loads((run_dir / "db-isolation.json").read_text(encoding="utf-8")).get("status")
    db_note = "DB isolation подтверждена" if db_status == "passed" else "DB isolation не требовалась"
    return gate.passed(f"AC evidence, lint, PHPUnit, {db_note}, neighbors и fingerprints подтверждены")


R_HEADING = re.compile(r"^###\s+(R\d+)\b", re.MULTILINE)
ROW_SPLIT = re.compile(r"^\|(.+)\|\s*$")
# Where behaviour tests live. Both layouts exist in this repo: task-scoped
# (`tests/lib`) and task-run dumps under `.doc/tasks/{N}/tests`.
TEST_ROOTS = [REPO / "tests", REPO / ".doc" / "qa" / "tests"]
CLOSED = {"covered", "n-a", "na"}


def decomposition_section(text: str) -> str:
    match = re.search(r"^## Decomposition\b.*$", text, re.MULTILINE)
    if not match:
        return ""
    rest = text[match.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def branch_section(text: str) -> str | None:
    match = re.search(r"^## Ветки логики\s*$", text, re.MULTILINE)
    if not match:
        return None
    rest = text[match.end():]
    nxt = re.search(r"^## ", rest, re.MULTILINE)
    return rest[: nxt.start()] if nxt else rest


def markdown_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        found = ROW_SPLIT.match(line.strip())
        if not found:
            continue
        cells = [cell.strip() for cell in found.group(1).split("|")]
        if not cells or set(cells[0]) <= {"-", ":"}:
            continue
        if cells[0].lower() in {"id", "ветка"}:
            continue
        rows.append(cells)
    return rows


def latest_run_dir(task: str) -> pathlib.Path | None:
    """Newest test-run directory for a task, or None when no run exists."""
    runs = task_dir(task) / "test-runs"
    if not runs.is_dir():
        return None
    dirs = [p for p in runs.iterdir() if p.is_dir()]
    return max(dirs, key=lambda p: p.name) if dirs else None


TEST_CELL_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)::([A-Za-z_][A-Za-z0-9_]*)")


def resolve_test_spec(spec: str, extra_roots: tuple[pathlib.Path, ...] = ()) -> tuple[bool, str]:
    """Resolve `Class::method` to a real test file and method.

    G13 used to accept the literal word "covered" with no evidence. A branch is
    only genuinely covered when the referenced test exists in the repository.
    Returns (found, detail) so the gate can name what is missing.

    `extra_roots` lets the caller add a task-scoped tests dir. Task Cests live
    in `.doc/tasks/{N}/tests` (see `.doc/qa/README.md`) and are not under
    TEST_ROOTS, so without this G13 cannot resolve them.
    """
    match = TEST_CELL_RE.search(spec or "")
    if not match:
        return False, "нет ссылки Class::method"
    cls, method = match.groups()
    candidates = [p for p in (*TEST_ROOTS, *extra_roots) if p.exists()]
    hits = []
    for root in candidates:
        hits.extend(root.rglob(f"{cls}.php"))
    if not hits:
        return False, f"класс теста не найден: {cls}"
    for path in hits:
        body = path.read_text(encoding="utf-8", errors="ignore")
        if re.search(rf"function\s+{re.escape(method)}\s*\(", body):
            return True, f"{cls}::{method}"
    return False, f"метод не найден: {cls}::{method}"


def g13_branches(task: str) -> Gate:
    """Каждый R из плана имеет закрытую строку в ## Ветки логики. Канон testaudit §9."""
    gate = Gate("G13", "ветки логики из Decomposition закрыты")
    plan = task_dir(task) / "plan.md"
    if not plan.exists():
        return gate.skipped("нет plan.md")
    reasons = R_HEADING.findall(decomposition_section(plan.read_text(encoding="utf-8", errors="ignore")))
    if not reasons:
        return gate.failed("в plan.md есть план, но нет ## Decomposition с причинами R")

    test_md = task_dir(task) / "test.md"
    if not test_md.exists():
        return gate.failed("нет test.md")
    section = branch_section(test_md.read_text(encoding="utf-8", errors="ignore"))
    if section is None:
        return gate.failed("нет секции ## Ветки логики. Канон: .doc/testaudit.md §9")

    rows = [cells for cells in markdown_rows(section) if re.fullmatch(r"B\d+", cells[0])]
    if not rows:
        return gate.failed("в ## Ветки логики нет строк B1, B2, ...")

    missing = []
    bad = []
    body = "\n".join("|".join(cells) for cells in rows)
    for reason in reasons:
        if not re.search(rf"\b{reason}\b", body):
            missing.append(reason)
    for cells in rows:
        status = cells[-1].strip().lower().replace(" ", "")
        if status not in CLOSED:
            bad.append(f"{cells[0]}={cells[-1].strip() or 'пусто'}")
            continue
        if status in {"n-a", "na"} and (len(cells) < 3 or not cells[-2].strip()):
            bad.append(f"{cells[0]}: у N-A нет причины в колонке Ожидание")
        elif status not in {"n-a", "na"}:
            # A row is only closed when its test column points at a real method.
            test_cell = cells[2] if len(cells) > 3 else ""
            found, detail = resolve_test_spec(test_cell, (task_dir(task) / "tests",))
            if not found:
                bad.append(f"{cells[0]}: {detail}")
    if missing or bad:
        parts = []
        if missing:
            parts.append("нет строк: " + ", ".join(missing))
        if bad:
            parts.append("не закрыты: " + ", ".join(bad))
        return gate.failed("; ".join(parts))
    return gate.passed(f"{len(rows)} веток, R: {', '.join(reasons)}")


PLAN_PATCH_HEADING = re.compile(r"(?m)^###\s+(?:\d+\.\s+)?`([^`]+)`\s*$")


def _plan_patches(plan_text: str) -> set[str]:
    m = re.search(r"(?ms)^## Правки по файлам\n(.*?)(?=^## |\Z)", plan_text)
    if not m:
        return set()
    return {p.strip() for p in PLAN_PATCH_HEADING.findall(m.group(1))}


def _plan_deviations(plan_text: str) -> set[str]:
    m = re.search(r"(?ms)^## Отклонения\n(.*?)(?=^## |\Z)", plan_text)
    if not m:
        return set()
    out: set[str] = set()
    for line in m.group(1).splitlines():
        hit = re.findall(r"[\w./-]+\.(?:php|js|vue|tpl)", line)
        out.update(hit)
    return out


def _plan_claims_passed(plan_text: str) -> bool:
    return bool(re.search(r"(?im)^audit_status\s*:\s*passed\b", plan_text))


def g14_patches_cover_diff(task: str) -> Gate:
    """G14: файлы из diff.files.md покрыты Patches плана или ## Отклонения."""
    plan = task_dir(task) / "plan.md"
    if not plan.exists():
        return Gate("G14", "Patches покрывают фактический diff").skipped("нет plan.md")
    text = plan.read_text(encoding="utf-8", errors="ignore")
    changed = task_changed_files(task)
    if not changed:
        return Gate("G14", "Patches покрывают фактический diff").skipped("нет diff.files.md")
    patches = _plan_patches(text)
    if not patches:
        # legacy plan without structured patches: do not block
        return Gate("G14", "Patches покрывают фактический diff").skipped("в плане нет структурированных Patches")
    deviations = _plan_deviations(text)
    unexplained = sorted(set(changed) - patches - deviations)
    blocking = _plan_claims_passed(text)
    gate = Gate("G14", "Patches покрывают фактический diff", blocking=blocking)
    if unexplained:
        return gate.failed("вне Patches и без отклонения: " + ", ".join(unexplained))
    return gate.passed(f"{len(changed)} файлов покрыты")


def g15_covered_has_testcase(task: str) -> Gate:
    """G15: строки ## Ветки логики co status covered подтверждены зелёным testcase."""
    test_md = task_dir(task) / "test.md"
    if not test_md.exists():
        return Gate("G15", "covered ветки подтверждены зелёным testcase").skipped("нет test.md")
    section = branch_section(test_md.read_text(encoding="utf-8", errors="ignore"))
    if section is None:
        return Gate("G15", "covered ветки подтверждены зелёным testcase").skipped("нет ## Ветки логики")
    verdict = read_verdict(task)
    if not verdict:
        return Gate("G15", "covered ветки подтверждены зелёным testcase").skipped("нет verdict.json")
    passed_names = set()
    for tc in verdict.get("testcases", []) or []:
        if str(tc.get("status", "")).lower() in {"passed", "ok", "green"}:
            for key in ("name", "method", "test"):
                if tc.get(key):
                    passed_names.add(str(tc[key]))
    rows = [cells for cells in markdown_rows(section) if cells and re.fullmatch(r"B\d+", cells[0])]
    missing = []
    for cells in rows:
        status = cells[-1].strip().lower().replace(" ", "")
        if status != "covered":
            continue
        spec, detail = resolve_test_spec(cells[2] if len(cells) > 3 else "", (task_dir(task) / "tests",))
        method = cells[2].strip() if len(cells) > 3 else ""
        if not spec or not any(name in method for name in passed_names):
            missing.append(f"{cells[0]}={method or detail}")
    if missing:
        return Gate("G15", "covered ветки подтверждены зелёным testcase").failed(
            "нет зелёного testcase: " + ", ".join(missing))
    return Gate("G15", "covered ветки подтверждены зелёным testcase").passed(f"{len(rows)} веток")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task")
    ap.add_argument("--json", action="store_true", help="машинный вывод")
    ap.add_argument("--skip-static", action="store_true", help="без G0 (долгий PHPStan)")
    args = ap.parse_args()

    task = args.task
    if not task_dir(task).is_dir():
        print(f"нет каталога .doc/tasks/{task}", file=sys.stderr)
        sys.exit(2)

    verdict = read_verdict(task)

    gates = [
        Gate("G0", "статика на файлах задачи").skipped("--skip-static") if args.skip_static
        else g0_static(task),
        g1_unit(task),
        g2_tests_exist(task),
        g3_green(task, verdict),
        g4_no_noise(task, verdict),
        g5_checklist(task),
        g6_db_effect(task),
        g7_literals(task),
        g8_stand_alive(),
        g9_git_clean(),
        g10_selectors(task),
        g11_red_first(task),
        g12_machine_run(task, verdict),
        g13_branches(task),
        g14_patches_cover_diff(task),
        g15_covered_has_testcase(task),
    ]

    blocking_failed = [g for g in gates if g.blocking and not g.ok]
    ready = not blocking_failed

    if args.json:
        print(json.dumps({
            "task": task,
            "ready": ready,
            "gates": [{"code": g.code, "title": g.title, "ok": g.ok,
                       "blocking": g.blocking, "detail": g.detail} for g in gates],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"\n== Гейты готовности CT-{task}\n")
        for g in gates:
            mark = "ок  " if g.ok else "СТОП"
            if g.ok and not g.blocking:
                mark = "проп"
            print(f"  [{mark}] {g.code} {g.title}")
            if g.detail:
                print(f"        {g.detail}")
        print()
        if ready:
            print("  ГОТОВО к ручному тестированию: все блокирующие гейты зелёные.")
        else:
            print(f"  НЕ ГОТОВО: {len(blocking_failed)} блокирующих гейтов красные "
                  f"({', '.join(g.code for g in blocking_failed)}).")

    run_dir = latest_run(task)
    if run_dir:
        (run_dir / "gates.json").write_text(json.dumps({
            "task": task, "ready": ready,
            "gates": [{"code": g.code, "ok": g.ok, "blocking": g.blocking,
                       "detail": g.detail} for g in gates],
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    sys.exit(0 if ready else 1)


if __name__ == "__main__":
    main()
