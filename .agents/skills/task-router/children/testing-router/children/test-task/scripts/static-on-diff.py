#!/usr/bin/env python3
"""Статика только по правкам задачи. Всё под .doc/ → в git не попадает.

Зачем: весь монолит забагован; CI держит мягкий gate (PHPStan 0 + lint:basic).
Локально на СТРОКАХ патча гоняем максимум: PHPStan high + ESLint patch-max.

  python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py 2605
  python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py 2605 --level 9
  python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/static-on-diff.py 2605 --eslint-ci   # parity с deploy

Шкала ESLint: lint:basic (CI) < lint:strict (репо) < .doc/qa/eslint/patch-max.js
«Vue-тесты» в деплое = ESLint + yarn prod, не jest/vitest.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys
from collections import defaultdict

REPO = pathlib.Path(__file__).resolve().parents[8]
TASKS = REPO / ".doc" / "tasks"
TOOLS = REPO / ".tools"
if not (TOOLS / "phpstan").is_dir():
    TOOLS = REPO / "tools"
PHPSTAN_DIR = TOOLS / "phpstan"
PHPSTAN_REL = PHPSTAN_DIR.relative_to(REPO).as_posix()
ANALYSE = PHPSTAN_DIR / "analyse.sh"
RELEASE_CFG = REPO / ".agents" / "skills" / "task-router" / "children" / "gototask" / "config.json"
PATCH_MAX_ESLINT = REPO / ".doc" / "qa" / "eslint" / "patch-max.js"
NODE_IMAGE = "node:22-bookworm-slim"
ESLINT_VOLUME = "copytrust-eslint-nm"
# Дефолт локали: жёстко. 9 = потолок PHPStan; 8 чуть милосерднее к legacy types.
DEFAULT_LEVEL = 8


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd,
        cwd=str(REPO),
        text=True,
        capture_output=True,
        **kw,
    )


def ensure_runner_image() -> None:
    image = "copytrust-codecept:8.3"
    if run(["docker", "image", "inspect", image]).returncode == 0:
        return
    context = REPO / ".doc" / "qa" / "docker"
    build = run(["docker", "build", "-q", "-t", image, str(context)], timeout=600)
    if build.returncode != 0:
        sys.stderr.write((build.stdout or "") + (build.stderr or ""))
        raise SystemExit(2)


def release_base() -> str:
    base = "release/5.6.0.6"
    if RELEASE_CFG.exists():
        try:
            data = json.loads(RELEASE_CFG.read_text(encoding="utf-8"))
            base = data.get("releaseBranch") or base
        except json.JSONDecodeError:
            pass
    for cand in (base, f"origin/{base}"):
        r = run(["git", "rev-parse", "--verify", cand])
        if r.returncode == 0:
            return cand
    return "HEAD~50"


def task_files(task: str) -> list[str]:
    path = TASKS / task / "diff.files.md"
    if not path.exists():
        return []
    files = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^\s*[-*]?\s*`?([\w./-]+\.(?:php|js|vue|tpl))`?\s*$", line)
        if m and (REPO / m.group(1)).exists():
            files.append(m.group(1))
    return sorted(set(files))


def parse_diff_hunks(diff_text: str) -> dict[str, set[int]]:
    lines_by_file: dict[str, set[int]] = defaultdict(set)
    current: str | None = None
    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            continue
        if line.startswith("+++ /dev/null"):
            current = None
            continue
        m = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", line)
        if not m or not current:
            continue
        start = int(m.group(1))
        count = int(m.group(2) or "1")
        if count == 0:
            continue
        for n in range(start, start + count):
            lines_by_file[current].add(n)
    return lines_by_file


def task_commit_hashes(task: str, base: str) -> list[str]:
    """Коммиты задачи: subject начинается с N / #N (как в bitbucket-tasks)."""
    r = run(
        [
            "git",
            "log",
            f"{base}...HEAD",
            "--format=%H%x09%s",
        ]
    )
    out = []
    pat = re.compile(rf"^(?:#)?{re.escape(task)}\b")
    for line in (r.stdout or "").splitlines():
        if "\t" not in line:
            continue
        sha, subject = line.split("\t", 1)
        if pat.match(subject.strip()):
            out.append(sha)
    return out


def blame_lines_for_commits(files: list[str], shas: set[str]) -> dict[str, set[int]]:
    """Текущие номера строк, которые blame относит к коммитам задачи.

    `git show` даёт номера строк на момент коммита; после merge/ребейза они
    устаревают и PHPStan начинает ругаться на чужой легаси. Blame смотрит
    на текущий файл.
    """
    out: dict[str, set[int]] = defaultdict(set)
    if not files or not shas:
        return out
    for path in files:
        if not (REPO / path).is_file():
            continue
        r = run(["git", "blame", "--line-porcelain", "--", path], timeout=120)
        if r.returncode != 0:
            continue
        commit = ""
        final_line = 0
        for line in (r.stdout or "").splitlines():
            if line.startswith("\t"):
                if commit in shas and final_line > 0:
                    out[path].add(final_line)
                continue
            parts = line.split()
            if (
                len(parts) >= 3
                and len(parts[0]) == 40
                and all(c in "0123456789abcdef" for c in parts[0])
            ):
                commit = parts[0]
                try:
                    final_line = int(parts[2])
                except ValueError:
                    final_line = 0
    return out


def changed_lines(files: list[str], task: str | None = None) -> dict[str, set[int]]:
    if not files:
        return {}
    base = release_base()
    merged: dict[str, set[int]] = defaultdict(set)

    # 1) только коммиты этой задачи — через blame по текущему дереву
    if task:
        shas = set(task_commit_hashes(task, base))
        for path, lines in blame_lines_for_commits(files, shas).items():
            merged[path] |= lines

    # 2) незакоммиченное (индекс + рабочая копия) - всегда
    for cmd in (
        ["git", "diff", "--unified=0", "HEAD", "--", *files],
        ["git", "diff", "--unified=0", "--cached", "--", *files],
    ):
        r = run(cmd)
        for path, lines in parse_diff_hunks(r.stdout or "").items():
            merged[path] |= lines

    # 3) fallback: если коммитов задачи не нашли - весь base...HEAD по файлам
    if task and not any(merged.get(f) for f in files):
        r = run(["git", "diff", "--unified=0", f"{base}...HEAD", "--", *files])
        for path, lines in parse_diff_hunks(r.stdout or "").items():
            merged[path] |= lines

    return merged


def neon_for(path: str) -> str:
    if path.startswith("lib/Objects/"):
        return "phpstan.Objects.neon"
    if path.startswith("admin/"):
        return "phpstan.admin.neon"
    return "phpstan.src.neon"


def resolve_php_bin() -> str | None:
    r = run(
        [
            "bash",
            "-c",
            f"""
SCRIPT_DIR="{ANALYSE.parent}"
if [ -n "${{PHP_BIN:-}}" ] && "$PHP_BIN" "$SCRIPT_DIR/phpstan.phar" --version >/dev/null 2>&1; then
  echo "$PHP_BIN"; exit 0
fi
if command -v php >/dev/null && php "$SCRIPT_DIR/phpstan.phar" --version >/dev/null 2>&1; then
  command -v php; exit 0
fi
exit 1
""",
        ]
    )
    if r.returncode == 0:
        return (r.stdout or "").strip() or None
    return None


def run_phpstan(files: list[str], level: int) -> list[dict]:
    if not files:
        return []
    groups: dict[str, list[str]] = defaultdict(list)
    for f in files:
        groups[neon_for(f)].append(f)

    host_php = resolve_php_bin()
    errors: list[dict] = []
    for neon, group in groups.items():
        args = [
            "analyse",
            "-c",
            f"{PHPSTAN_REL}/{neon}",
            f"--level={level}",
            "--error-format=json",
            "--no-progress",
            "--no-interaction",
            *group,
        ]
        if host_php:
            r = run([host_php, str(ANALYSE.parent / "phpstan.phar"), *args], timeout=600)
        else:
            ensure_runner_image()
            r = run(
                [
                    "docker",
                    "run",
                    "--rm",
                    "-v",
                    f"{REPO}:/app",
                    "-w",
                    "/app",
                    "copytrust-codecept:8.3",
                    "php",
                    f"{PHPSTAN_REL}/phpstan.phar",
                    *args,
                ],
                timeout=600,
            )
        payload = (r.stdout or "").strip()
        if not payload:
            if r.returncode != 0:
                print(r.stderr or "phpstan failed without json", file=sys.stderr)
                raise SystemExit(2)
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            start = payload.find("{")
            if start < 0:
                print(payload[:500], file=sys.stderr)
                raise SystemExit(2)
            data = json.loads(payload[start:])
        for file_path, meta in (data.get("files") or {}).items():
            rel = file_path
            if rel.startswith(str(REPO)):
                rel = str(pathlib.Path(rel).relative_to(REPO))
            elif "/app/" in rel:
                rel = rel.split("/app/", 1)[-1]
            for msg in meta.get("messages") or []:
                errors.append(
                    {
                        "file": rel.replace("\\", "/"),
                        "line": int(msg.get("line") or 0),
                        "message": msg.get("message") or "",
                        "identifier": msg.get("identifier") or "",
                    }
                )
    return errors


def filter_to_patch(
    errors: list[dict], patch_lines: dict[str, set[int]], slack: int = 2
) -> list[dict]:
    kept = []
    for e in errors:
        f = e["file"]
        lines = patch_lines.get(f) or patch_lines.get(f.lstrip("./"))
        if not lines:
            continue
        line = e["line"]
        if any(abs(line - p) <= slack for p in lines):
            kept.append(e)
    return kept


# После blame номера строк точные: slack=0 по умолчанию (не цеплять соседний легаси).
DEFAULT_SLACK = 0


def eslint_cmd(cfg: str, files: list[str]) -> list[str]:
    return [
        "./node_modules/.bin/eslint",
        "--no-eslintrc",
        "--ext",
        ".js,.vue",
        "--config",
        cfg,
        "--max-warnings=0",
        "--no-inline-config",
        "--format",
        "json",
        *files,
    ]


def run_eslint_raw(cfg: str, files: list[str]) -> tuple[int, str, str]:
    local_bin = REPO / "node_modules" / ".bin" / "eslint"
    plugin = REPO / "node_modules" / "eslint-plugin-vue"
    if local_bin.exists() and plugin.exists():
        r = run(eslint_cmd(cfg, files), timeout=300)
        return r.returncode, r.stdout or "", r.stderr or ""

    print(f"ESLint через docker {NODE_IMAGE} (локально нет eslint-plugin-vue)", file=sys.stderr)
    # node:22 уже несёт yarn (corepack). Повторный npm i -g yarn → EEXIST.
    inner = (
        "set -euo pipefail; "
        "if ! command -v yarn >/dev/null 2>&1; then "
        "  npm install --global yarn@1.22.19 --force >/dev/null; "
        "fi; "
        "yarn install --frozen-lockfile; "
        + " ".join(eslint_cmd(cfg, files))
    )
    r = run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{REPO}:/app",
            "-v",
            f"{ESLINT_VOLUME}:/app/node_modules",
            "-w",
            "/app",
            NODE_IMAGE,
            "bash",
            "-lc",
            inner,
        ],
        timeout=900,
    )
    return r.returncode, r.stdout or "", r.stderr or ""


def parse_eslint_json(stdout: str) -> list[dict] | None:
    """None = JSON не найден/битый; [] = чистый отчёт без замечаний.

    В docker-выводе до отчёта бывает yarn `[1/4] ...`, а после отчёта —
    предупреждения yarn в stderr. Ищем массив объектов ESLint (`[{` / `[\n{`)
    и разбираем первый JSON через raw_decode, чтобы хвост после отчёта
    не ломал разбор.
    """
    text = stdout or ""
    if not text.strip():
        return None
    decoder = json.JSONDecoder()
    start = -1
    for marker in ("[{", "[\n{", "[\r\n{"):
        start = text.find(marker)
        if start >= 0:
            break
    if start < 0:
        # fallback: первый `[`, с которого начинается JSON list
        idx = text.find("[")
        while idx >= 0:
            try:
                data, _ = decoder.raw_decode(text, idx)
                if isinstance(data, list):
                    start = idx
                    break
            except json.JSONDecodeError:
                pass
            idx = text.find("[", idx + 1)
    if start < 0:
        return None
    try:
        data, _ = decoder.raw_decode(text, start)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, list):
        return None
    out = []
    for file_res in data:
        if not isinstance(file_res, dict):
            continue
        raw = (file_res.get("filePath") or "").replace("\\", "/")
        if "/app/" in raw:
            rel = raw.split("/app/", 1)[-1]
        elif raw.startswith(str(REPO)):
            rel = str(pathlib.Path(raw).relative_to(REPO))
        else:
            rel = raw
        for msg in file_res.get("messages") or []:
            out.append(
                {
                    "file": rel,
                    "line": int(msg.get("line") or 0),
                    "message": msg.get("message") or "",
                    "rule": msg.get("ruleId") or "",
                    "severity": int(msg.get("severity") or 0),
                }
            )
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("task", help="номер задачи CT-N")
    ap.add_argument(
        "--level",
        type=int,
        default=DEFAULT_LEVEL,
        help=f"PHPStan level на строках патча (дефолт {DEFAULT_LEVEL}, макс 9)",
    )
    ap.add_argument(
        "--eslint-ci",
        action="store_true",
        help="ESLint .eslintrc.basic.js как в GitVerse (не max)",
    )
    ap.add_argument(
        "--eslint-strict-repo",
        action="store_true",
        help="ESLint .eslintrc.strict.js из репо (мягче patch-max)",
    )
    ap.add_argument("--no-php", action="store_true")
    ap.add_argument("--no-eslint", action="store_true")
    ap.add_argument("--slack", type=int, default=DEFAULT_SLACK, help="допуск строк вокруг патча (после blame обычно 0)")
    args = ap.parse_args()

    files = task_files(args.task)
    if not files:
        print("нет файлов в diff.files.md — сначала «обнови диф задачи»", file=sys.stderr)
        return 2

    php = [f for f in files if f.endswith(".php")]
    js = [f for f in files if f.endswith((".js", ".vue"))]
    status = 0

    if php and not args.no_php:
        print(f"== PHPStan level {args.level} на {len(php)} php, только строки патча")
        patch = changed_lines(php, task=args.task)
        if not any(patch.get(f) for f in php):
            print("  нет git-hunks по php — невозможно доказать, что проверяется diff", file=sys.stderr)
            status = 1
        else:
            for f in php:
                print(f"  {f}: {len(patch.get(f) or [])} строк патча")
            all_err = run_phpstan(php, args.level)
            kept = filter_to_patch(all_err, patch, slack=args.slack)
            print(f"  ошибок всего {len(all_err)}, в патче (±{args.slack}) {len(kept)}")
            for e in kept:
                print(f"  {e['file']}:{e['line']}: {e['message']}")
            if kept:
                status = 1
            else:
                print("  PHPStan по патчу: ок")

    if js and not args.no_eslint:
        if args.eslint_ci:
            cfg = ".eslintrc.basic.js"
            label = "basic (CI)"
        elif args.eslint_strict_repo:
            cfg = ".eslintrc.strict.js"
            label = "strict (репо)"
        else:
            if not PATCH_MAX_ESLINT.exists():
                print(f"нет {PATCH_MAX_ESLINT}", file=sys.stderr)
                return 2
            cfg = str(PATCH_MAX_ESLINT.relative_to(REPO))
            label = "patch-max (локаль, не в git)"

        print(f"== ESLint {label} на {len(js)} js/vue, только строки патча")
        patch = changed_lines(js, task=args.task)
        for f in js:
            print(f"  {f}: {len(patch.get(f) or [])} строк патча")

        code, out, err = run_eslint_raw(cfg, js)
        if err and "ESLint couldn't find" in err:
            sys.stderr.write(err)
            return 1

        # yarn/eslint в docker часто мешают stdout/stderr — ищем JSON в обоих.
        all_msg = parse_eslint_json(out)
        if all_msg is None:
            all_msg = parse_eslint_json(err)
        if all_msg is None:
            all_msg = parse_eslint_json((out or "") + "\n" + (err or ""))
        if all_msg is None:
            sys.stderr.write(err or out or "eslint failed: no json report\n")
            return 1

        # severity 2 = error; 1 = warning (max-warnings=0 уже режет)
        errs = [m for m in all_msg if m["severity"] >= 1]
        if not any(patch.get(f) for f in js):
            # нет hunks - тогда смотрим весь результат eslint по файлам
            kept = errs
            print("  нет git-hunks по js — смотрим весь файл")
        else:
            kept = filter_to_patch(errs, patch, slack=args.slack)
            print(f"  замечаний всего {len(errs)}, в патче (±{args.slack}) {len(kept)}")

        for e in kept:
            print(f"  {e['file']}:{e['line']}: [{e['rule']}] {e['message']}")

        if kept:
            status = 1
        else:
            print("  ESLint по патчу: ок")

    return status


if __name__ == "__main__":
    raise SystemExit(main())
