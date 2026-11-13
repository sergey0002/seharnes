#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Сборка исследовательского корпуса .doc/testanalyze/

Цель: по папкам .doc/tasks/{N}/ собрать стейджи, Jira-историю (из task.md),
git-коммиты задачи и дифы между стейджами (от первого к последнему),
сопоставить со скилами тестирования/планирования.

Запуск из корня репозитория:
  python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py
  python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --staged-only --with-diffs
  python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --task 2410 --with-diffs --full-diff
  python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --refresh-jira --staged-only
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[8]
TASKS_DIR = REPO_ROOT / ".doc" / "tasks"
OUT_DIR = REPO_ROOT / ".doc" / "testanalyze"
OUT_TASKS = OUT_DIR / "tasks"
CEST_DIR = REPO_ROOT / ".tools" / "codeception" / "tests" / "Acceptance" / "Task"
JIRA_EXPORT = REPO_ROOT / ".agents" / "skills" / "task-router" / "children" / "jira" / "scripts" / "server.php"

SHA_RE = re.compile(r"\b([0-9a-f]{7,40})\b", re.I)
META_RE = re.compile(r"<!--\s*meta(.*?)-->", re.S | re.I)
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
COMMENT_HEADER_RE = re.compile(
    r"^\*\*[^*]+\*\*\s*·\s*(\d{2}\.\d{2}\.\d{4})\s+(\d{2}:\d{2})\s+UTC",
    re.M,
)
QA_HINT_RE = re.compile(
    r"(?i)("
    r"баг|ошибк|не работает|некоррект|сломал|регресс|"
    r"проверяю|проверил|ручн|тест|qa|стенд|d2|d4|"
    r"скрин|скриншот|клиент\s*\d+|под пользовател|"
    r"pre-stage|повторн|доработ|исправ"
    r")"
)

SKILLS = [
    {
        "id": "prepare-plan",
        "path": ".cursor/skills/prepare-plan/SKILL.md",
        "role": "План / stageN после бага ручного тестирования",
        "evidence": ["plan.md", "stage*/plan.md"],
    },
    {
        "id": "gototask",
        "path": ".cursor/skills/task-router/children/gototask/SKILL.md",
        "role": "Ветка 1:1 с задачей, экспорт task.md из Jira",
        "evidence": ["task.md", "gototask-state.json"],
    },
    {
        "id": "task-diff",
        "path": ".cursor/skills/task-router/children/task-diff/SKILL.md",
        "role": "diff.md / diff.files.md по коммитам с номером задачи",
        "evidence": ["diff.md", "diff.files.md"],
    },
    {
        "id": "test-task",
        "path": ".cursor/skills/task-router/children/testing-router/children/test-task/SKILL.md",
        "role": "Оркестратор «тестируй задачу»",
        "evidence": ["test.md", "test-runs/"],
    },
    {
        "id": "prepare-task-test",
        "path": ".cursor/skills/task-router/children/testing-router/children/prepare-task-test/SKILL.md",
        "role": "Конструктор Task Cest + test.md",
        "evidence": ["test.md", "Task/{N}_*Cest.php"],
    },
    {
        "id": "browser-verify",
        "path": ".cursor/skills/task-router/children/testing-router/children/browser-verify/SKILL.md",
        "role": "Прогон Codeception / Playwright + отчёт test-runs",
        "evidence": ["test-runs/*.md"],
    },
    {
        "id": "login-as-user",
        "path": ".cursor/skills/login-as-user/SKILL.md",
        "role": "Имперсонейт клиента из task.md",
        "evidence": ["clientId / под пользователем N в task.md|test.md"],
    },
    {
        "id": "task-doc",
        "path": ".cursor/skills/documentation-router/children/task-doc/SKILL.md",
        "role": "Живая doc.md задачи",
        "evidence": ["doc.md"],
    },
]


@dataclass
class StageInfo:
    id: str
    path: str
    title: str = ""
    status: str = ""
    updated: str = ""
    scope: str = ""
    mode: str = ""
    head: str = ""
    merged: str = ""
    problem_excerpt: str = ""
    tip_commit: str = ""
    tip_source: str = ""
    commit_shas: List[str] = field(default_factory=list)
    mentioned_shas: List[str] = field(default_factory=list)


@dataclass
class CommitInfo:
    sha: str
    date: str
    subject: str


@dataclass
class TaskReport:
    task: str
    title: str = ""
    jira_state: str = ""
    jira_kind: str = ""
    jira_version: str = ""
    jira_url: str = ""
    comment_count: int = 0
    qa_comment_hits: int = 0
    qa_comment_excerpts: List[str] = field(default_factory=list)
    artifacts: Dict[str, bool] = field(default_factory=dict)
    stages: List[StageInfo] = field(default_factory=list)
    stage_count: int = 0
    commits: List[CommitInfo] = field(default_factory=list)
    commit_count: int = 0
    first_commit: str = ""
    last_commit: str = ""
    first_to_last_stat: str = ""
    stage_diffs: List[Dict[str, Any]] = field(default_factory=list)
    testing: Dict[str, Any] = field(default_factory=dict)
    gaps: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def run_git(args: List[str], cwd: Path = REPO_ROOT) -> Tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode, proc.stdout, proc.stderr


def git_ok(args: List[str]) -> str:
    code, out, _ = run_git(args)
    return out if code == 0 else ""


def parse_meta(text: str) -> Dict[str, str]:
    m = META_RE.search(text)
    if not m:
        return {}
    meta: Dict[str, str] = {}
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        meta[k.strip().lower()] = v.strip()
    return meta


def first_heading(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def excerpt_problem(text: str, limit: int = 400) -> str:
    for marker in ("## Problem", "## Проблема", "## Context", "## Контекст"):
        idx = text.find(marker)
        if idx >= 0:
            chunk = text[idx : idx + limit]
            chunk = re.sub(r"\s+", " ", chunk).strip()
            return chunk[:limit]
    body = re.sub(r"\s+", " ", text[0:limit]).strip()
    return body[:limit]


def parse_task_md(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8", errors="replace")
    title = first_heading(text)
    fields: Dict[str, str] = {}
    for line in text.splitlines():
        m = re.match(r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|", line)
        if not m:
            continue
        k = m.group(1).strip()
        v = m.group(2).strip()
        if k.lower() in ("field", "---", ""):
            continue
        fields[k] = v
    jira_url = ""
    m = re.search(r"https://[^\s)]+/browse/CT-\d+", text)
    if m:
        jira_url = m.group(0)
    comments = []
    if "## Comments" in text:
        comments_part = text.split("## Comments", 1)[1]
        # split by --- separators under Comments
        blocks = re.split(r"\n---\n", comments_part)
        for block in blocks:
            block = block.strip()
            if not block or block.startswith("## "):
                continue
            comments.append(block)
    qa_hits = []
    for block in comments:
        if QA_HINT_RE.search(block):
            one = re.sub(r"\s+", " ", block).strip()
            qa_hits.append(one[:280])
    return {
        "title": title,
        "state": fields.get("State", ""),
        "kind": fields.get("Kind", ""),
        "version": fields.get("Version", ""),
        "jira_url": jira_url,
        "comment_count": len(comments),
        "qa_comment_hits": len(qa_hits),
        "qa_comment_excerpts": qa_hits[:12],
        "raw_len": len(text),
    }


def stage_sort_key(name: str) -> Tuple[int, str]:
    if name == "initial":
        return (0, name)
    m = re.match(r"stage(\d+)(.*)", name)
    if m:
        return (int(m.group(1)), m.group(2) or "")
    return (999, name)


def discover_stages(task_dir: Path) -> List[StageInfo]:
    stages: List[StageInfo] = []
    root_plan = task_dir / "plan.md"
    if root_plan.exists():
        stages.append(load_stage("initial", root_plan))
    for d in sorted(task_dir.iterdir(), key=lambda p: p.name):
        if not d.is_dir():
            continue
        if not re.match(r"stage", d.name, re.I):
            continue
        plan = d / "plan.md"
        if plan.exists():
            stages.append(load_stage(d.name, plan))
        else:
            # stage folder without plan - still record
            stages.append(
                StageInfo(
                    id=d.name,
                    path=str(plan.relative_to(REPO_ROOT)),
                    title="(нет plan.md)",
                )
            )
    stages.sort(key=lambda s: stage_sort_key(s.id))
    return stages


def load_stage(stage_id: str, path: Path) -> StageInfo:
    text = path.read_text(encoding="utf-8", errors="replace")
    meta = parse_meta(text)
    mentioned = []
    for sha in SHA_RE.findall(text[:8000]):
        if len(sha) >= 7 and not re.match(r"^\d{14}$", sha):
            mentioned.append(sha.lower())
    # unique preserve order
    seen = set()
    uniq = []
    for s in mentioned:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return StageInfo(
        id=stage_id,
        path=str(path.relative_to(REPO_ROOT)),
        title=first_heading(text),
        status=meta.get("status", ""),
        updated=meta.get("updated", "")[:10],
        scope=meta.get("scope", ""),
        mode=meta.get("mode", ""),
        head=meta.get("head", ""),
        merged=meta.get("merged", ""),
        problem_excerpt=excerpt_problem(text),
        mentioned_shas=uniq[:20],
    )


def resolve_sha(sha: str) -> str:
    if not sha:
        return ""
    code, out, _ = run_git(["rev-parse", "--verify", f"{sha}^{{commit}}"])
    if code == 0:
        return out.strip()
    code, out, _ = run_git(["rev-parse", "--verify", sha])
    return out.strip() if code == 0 else ""


def legacy_task_numbers(task: str, task_dir: Path) -> List[str]:
    """Номера из Bitbucket / diff.md (пример: Jira 2236 ← commits #1345)."""
    nums = {task}
    for name in ("diff.md", "task.md", "doc.md", "plan.md"):
        path = task_dir / name
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")[:50000]
        for m in re.finditer(
            r"(?i)Commit numbers\s*\|\s*([^|\n]+)", text
        ):
            for n in re.findall(r"#?(\d{3,5})", m.group(1)):
                nums.add(n)
        for m in re.finditer(
            r"(?i)(?:bitbucket\.org[^\s\]]*?/issues/|Imported from[^\n]*?#?)(\d{3,5})",
            text,
        ):
            nums.add(m.group(1))
        for m in re.finditer(
            r"(?i)legacy[^\n]{0,40}?#(\d{3,5})", text
        ):
            nums.add(m.group(1))
    return sorted(nums, key=lambda x: (0 if x == task else 1, int(x) if x.isdigit() else 0))


def subject_matches_numbers(subject: str, numbers: List[str]) -> bool:
    for n in numbers:
        if re.search(
            rf"(?i)(^|[^\d])#?{n}([^\d]|$)|CT-{n}\b",
            subject,
        ):
            # require task-like position: start or after merge words
            if re.search(
                rf"(?i)(^#?{n}\b|^CT-{n}\b|#{n}\b|CT-{n}\b|features/#{n}|bugfixes/#{n})",
                subject,
            ):
                return True
    return False


def commits_from_diff_md(task_dir: Path) -> List[str]:
    path = task_dir / "diff.md"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8", errors="replace")
    shas = []
    for m in re.finditer(r"(?im)^\*\*Commit:\*\*\s*`([0-9a-f]{7,40})`", text):
        shas.append(m.group(1))
    # also bare commit lines
    for m in re.finditer(r"(?im)^(?:Commit|commit):\s*`?([0-9a-f]{7,40})`?", text):
        shas.append(m.group(1))
    seen = set()
    out = []
    for s in shas:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def collect_task_commits(task: str, task_dir: Optional[Path] = None) -> List[CommitInfo]:
    task_dir = task_dir or (TASKS_DIR / task)
    numbers = legacy_task_numbers(task, task_dir)
    commits: List[CommitInfo] = []
    seen = set()

    for n in numbers:
        out = git_ok(
            [
                "log",
                "--all",
                "--no-merges",
                "--date=iso-strict",
                "--pretty=format:%H%x09%ad%x09%s",
                f"--grep={n}",
                "-E",
            ]
        )
        for line in out.splitlines():
            if not line.strip():
                continue
            parts = line.split("\t", 2)
            if len(parts) < 3:
                continue
            sha, date, subject = parts[0], parts[1], parts[2]
            if not subject_matches_numbers(subject, numbers):
                continue
            if sha in seen:
                continue
            seen.add(sha)
            commits.append(CommitInfo(sha=sha, date=date, subject=subject))

    # Fallback: SHAs listed in diff.md (когда subject только legacy, а grep уже отработал,
    # или объекты есть, но subject-фильтр слишком жёсткий)
    for sha_ref in commits_from_diff_md(task_dir):
        full = resolve_sha(sha_ref)
        if not full or full in seen:
            continue
        meta = git_ok(["show", "-s", "--date=iso-strict", "--format=%H%x09%aI%x09%s", full])
        if not meta.strip():
            continue
        parts = meta.strip().split("\t", 2)
        if len(parts) < 3:
            continue
        sha, date, subject = parts[0], parts[1], parts[2]
        seen.add(sha)
        commits.append(CommitInfo(sha=sha, date=date, subject=subject))

    commits.sort(key=lambda c: c.date)
    return commits


def valid_commit_set(commits: List[CommitInfo]) -> Dict[str, CommitInfo]:
    by_full = {c.sha: c for c in commits}
    by_short: Dict[str, CommitInfo] = {}
    for c in commits:
        by_short[c.sha[:7]] = c
        by_short[c.sha[:10]] = c
        by_short[c.sha] = c
    return by_short


def commit_date_map(commits: List[CommitInfo]) -> Dict[str, str]:
    return {c.sha: c.date for c in commits}


def assign_stage_tips(
    stages: List[StageInfo], commits: List[CommitInfo]
) -> None:
    if not stages:
        return
    by_short = valid_commit_set(commits)
    dates = commit_date_map(commits)

    def find_commit(ref: str) -> str:
        if not ref:
            return ""
        ref = ref.strip().lower()
        if ref in by_short:
            return by_short[ref].sha
        full = resolve_sha(ref)
        if full:
            return full
        return ""

    def sha_date(sha: str) -> str:
        if not sha:
            return ""
        if sha in dates:
            return dates[sha]
        # short / resolved outside list
        for c in commits:
            if c.sha.startswith(sha) or sha.startswith(c.sha[:7]):
                return c.date
        out = git_ok(["show", "-s", "--format=%aI", sha]).strip()
        return out

    # 1) date buckets: commit belongs to earliest stage with updated >= commit day
    dated = [(i, st) for i, st in enumerate(stages) if DATE_RE.search(st.updated or "")]
    stage_commits: Dict[str, List[str]] = {st.id: [] for st in stages}
    if commits and dated:
        bounds: List[Tuple[int, str]] = []
        for i, st in dated:
            m = DATE_RE.search(st.updated)
            if m:
                bounds.append((i, m.group(1)))
        for c in commits:
            cday = c.date[:10]
            chosen = None
            for i, day in bounds:
                if cday <= day:
                    chosen = stages[i].id
                    break
            if chosen is None and bounds:
                chosen = stages[bounds[-1][0]].id
            if chosen:
                stage_commits[chosen].append(c.sha)
        for st in stages:
            st.commit_shas = stage_commits.get(st.id, [])

    # 2) explicit head / merged (prefer as tip if resolves)
    for st in stages:
        for cand in [st.head, st.merged]:
            tip = find_commit(cand)
            if tip:
                st.tip_commit = tip
                st.tip_source = f"meta:{cand[:12]}"
                break

    # 3) mentioned SHAs that belong to this stage bucket, else any mentioned in task commits
    for st in stages:
        if st.tip_commit:
            continue
        bucket = set(st.commit_shas)
        for cand in st.mentioned_shas:
            tip = find_commit(cand)
            if not tip:
                continue
            if bucket and tip not in bucket and not any(tip.startswith(s[:7]) or s.startswith(tip[:7]) for s in bucket):
                continue
            st.tip_commit = tip
            st.tip_source = f"text:{cand[:12]}"
            break

    # 4) date-bucket last commit
    for st in stages:
        if not st.tip_commit and st.commit_shas:
            st.tip_commit = st.commit_shas[-1]
            st.tip_source = "date-bucket"

    # 5) fallback: spread by order
    if commits and any(not s.tip_commit for s in stages):
        n = len(stages)
        m = len(commits)
        for i, st in enumerate(stages):
            if st.tip_commit:
                continue
            idx = min(m - 1, max(0, round((i + 1) * m / n) - 1))
            st.tip_commit = commits[idx].sha
            st.tip_source = "order-fallback"

    # 6) enforce non-decreasing tip dates along stage order (same-day stage4/5 fix)
    if commits and len(stages) >= 2:
        prev_date = ""
        prev_sha = ""
        for st in stages:
            if not st.tip_commit:
                continue
            d = sha_date(st.tip_commit)
            if prev_date and d and d < prev_date:
                # tip went backwards: prefer last commit in this bucket that is >= prev_date
                fixed = ""
                for sha in st.commit_shas:
                    sd = sha_date(sha)
                    if sd and sd >= prev_date:
                        fixed = sha
                if not fixed:
                    # keep previous tip (no forward progress) — mark
                    st.tip_commit = prev_sha
                    st.tip_source = (st.tip_source or "") + "+clamped"
                else:
                    st.tip_commit = fixed
                    st.tip_source = (st.tip_source or "bucket") + "+chrono-fix"
                    d = sha_date(fixed)
            if d:
                prev_date = d
                prev_sha = st.tip_commit


def files_touched_by_commits(shas: List[str]) -> List[str]:
    files: List[str] = []
    seen = set()
    for sha in shas:
        if not sha:
            continue
        out = git_ok(["diff-tree", "--no-commit-id", "--name-only", "-r", sha])
        for line in out.splitlines():
            p = line.strip()
            if p and p not in seen:
                seen.add(p)
                files.append(p)
    return files


def diff_stat(a: str, b: str, path_limit: Optional[List[str]] = None) -> str:
    if not a or not b:
        return ""
    if a == b:
        return "(identical tips)"
    args = ["diff", "--stat", f"{a}..{b}"]
    if path_limit:
        args.append("--")
        args.extend(path_limit[:400])
    out = git_ok(args)
    if out.strip():
        return out.strip()
    out2 = git_ok(["diff", "--stat", f"{b}..{a}"] + (["--", *path_limit[:400]] if path_limit else []))
    if out2.strip():
        return "(reversed order)\n" + out2.strip()
    return "(empty or unreachable)"


def diff_name_status(a: str, b: str, path_limit: Optional[List[str]] = None) -> str:
    if not a or not b or a == b:
        return ""
    args = ["diff", "--name-status", f"{a}..{b}"]
    if path_limit:
        args.append("--")
        args.extend(path_limit[:400])
    return git_ok(args).strip()


def diff_patch(a: str, b: str, max_bytes: int = 2_000_000, path_limit: Optional[List[str]] = None) -> str:
    if not a or not b or a == b:
        return ""
    args = ["diff", f"{a}..{b}"]
    if path_limit:
        args.append("--")
        args.extend(path_limit[:400])
    out = git_ok(args)
    if len(out.encode("utf-8", errors="replace")) > max_bytes:
        return out[:max_bytes] + "\n\n... [truncated] ...\n"
    return out


def commits_range_stat(commits: List[CommitInfo]) -> str:
    """Сводка только по коммитам задачи (без чужого merge-релиза в дереве)."""
    if not commits:
        return ""
    lines = [f"task commits: {len(commits)}", ""]
    for c in commits:
        st = git_ok(["show", "--stat", "--format=%h %s", "--no-patch", c.sha]).strip()
        # show --stat without patch still needs different invocation
        st = git_ok(["show", "--stat", "--format=%h %ci %s%n", "-1", c.sha]).strip()
        lines.append(st)
        lines.append("")
    files = files_touched_by_commits([c.sha for c in commits])
    lines.append(f"unique files: {len(files)}")
    for f in files[:200]:
        lines.append(f"  {f}")
    if len(files) > 200:
        lines.append(f"  ... +{len(files)-200} more")
    return "\n".join(lines).strip()


def list_cests() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    if not CEST_DIR.exists():
        return mapping
    for p in CEST_DIR.glob("*Cest.php"):
        m = re.match(r"^(\d+)_", p.name)
        if m:
            mapping[m.group(1)] = str(p.relative_to(REPO_ROOT))
    return mapping


def artifact_flags(task_dir: Path, task: str, cests: Dict[str, str]) -> Dict[str, bool]:
    return {
        "task.md": (task_dir / "task.md").exists(),
        "doc.md": (task_dir / "doc.md").exists(),
        "plan.md": (task_dir / "plan.md").exists(),
        "diff.md": (task_dir / "diff.md").exists(),
        "diff.files.md": (task_dir / "diff.files.md").exists(),
        "test.md": (task_dir / "test.md").exists(),
        "test-runs": (task_dir / "test-runs").is_dir(),
        "stage_dirs": any(
            d.is_dir() and d.name.startswith("stage") for d in task_dir.iterdir()
        ),
        "cest": task in cests,
        "gototask-state.json": (task_dir / "gototask-state.json").exists(),
    }


def detect_gaps(report: TaskReport) -> List[str]:
    gaps = []
    if report.stage_count >= 2 and not report.artifacts.get("test.md"):
        gaps.append("multi-stage без test.md (ручные баги, нет зафиксированного автотеста)")
    if report.stage_count >= 2 and not report.artifacts.get("cest"):
        gaps.append("multi-stage без Task Cest (@group task-N)")
    if report.stage_count >= 2 and not report.artifacts.get("test-runs"):
        gaps.append("multi-stage без test-runs (нет отчёта browser-verify / test-task)")
    if report.qa_comment_hits >= 2 and report.stage_count <= 1 and report.artifacts.get("plan.md"):
        gaps.append("в Jira много QA-сигналов, но stage2+ папки нет (возможно правки без stage-плана)")
    if report.artifacts.get("plan.md") and not report.artifacts.get("diff.md"):
        gaps.append("есть plan.md, нет diff.md (task-diff не собирали)")
    if report.commit_count == 0 and report.artifacts.get("plan.md"):
        gaps.append("есть план, git-коммиты с номером задачи не найдены")
    if report.stage_count >= 3 and report.testing.get("verification_in_plans", 0) == 0:
        gaps.append("много стейджей, в планах не найдена секция Verification / test scenario")
    return gaps


def plan_has_verification(path: Path) -> bool:
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8", errors="replace")
    return bool(
        re.search(
            r"(?i)(##\s*Verification|per-patch test|test scenario|Acceptance criteria|Чек-лист)",
            text,
        )
    )


def analyze_task(
    task: str,
    cests: Dict[str, str],
    with_diffs: bool,
    full_diff: bool,
) -> TaskReport:
    task_dir = TASKS_DIR / task
    report = TaskReport(task=task)
    jira = parse_task_md(task_dir / "task.md")
    report.title = jira.get("title", "")
    report.jira_state = jira.get("state", "")
    report.jira_kind = jira.get("kind", "")
    report.jira_version = jira.get("version", "")
    report.jira_url = jira.get("jira_url", "") or f"https://copytrust-team.atlassian.net/browse/CT-{task}"
    report.comment_count = int(jira.get("comment_count") or 0)
    report.qa_comment_hits = int(jira.get("qa_comment_hits") or 0)
    report.qa_comment_excerpts = list(jira.get("qa_comment_excerpts") or [])

    report.artifacts = artifact_flags(task_dir, task, cests)
    report.stages = discover_stages(task_dir)
    report.stage_count = len(report.stages)
    report.commits = collect_task_commits(task, task_dir)
    report.commit_count = len(report.commits)
    legacy = legacy_task_numbers(task, task_dir)
    if len(legacy) > 1:
        report.notes.append(f"Legacy/alt номера коммитов: {', '.join('#'+n for n in legacy)}")
    if report.commits:
        report.first_commit = report.commits[0].sha
        report.last_commit = report.commits[-1].sha

    assign_stage_tips(report.stages, report.commits)

    verif = 0
    for st in report.stages:
        p = REPO_ROOT / st.path
        if plan_has_verification(p):
            verif += 1
    report.testing = {
        "cest_path": cests.get(task, ""),
        "test_md": report.artifacts.get("test.md", False),
        "test_runs": report.artifacts.get("test-runs", False),
        "test_run_files": sorted(
            [
                str(p.relative_to(REPO_ROOT))
                for p in (task_dir / "test-runs").glob("*.md")
            ]
        )
        if (task_dir / "test-runs").is_dir()
        else [],
        "verification_in_plans": verif,
        "login_as_user_hint": bool(
            re.search(
                r"(?i)(clientId|клиент\s*\d+|под пользовател|loginAsClientById)",
                (task_dir / "task.md").read_text(encoding="utf-8", errors="replace")
                if (task_dir / "task.md").exists()
                else "",
            )
            or (
                (task_dir / "test.md").exists()
                and re.search(
                    r"(?i)(clientId|loginAsClientById|клиент)",
                    (task_dir / "test.md").read_text(encoding="utf-8", errors="replace"),
                )
            )
        ),
    }

    # Дифы: только файлы, тронутые коммитами задачи (без шума merge релиза)
    if report.commits:
        all_files = files_touched_by_commits([c.sha for c in report.commits])
        report.first_to_last_stat = commits_range_stat(report.commits)
        tips = [(st.id, st.tip_commit) for st in report.stages if st.tip_commit]
        for i in range(len(tips) - 1):
            a_id, a_sha = tips[i]
            b_id, b_sha = tips[i + 1]
            # commits belonging to target stage bucket (or between tips by date)
            between: List[str] = []
            for st in report.stages:
                if st.id == b_id:
                    between = list(st.commit_shas) or []
                    break
            if not between:
                # fallback: commits with date in (a_date, b_date]
                a_date = next((c.date for c in report.commits if c.sha == a_sha or c.sha.startswith(a_sha[:10])), "")
                b_date = next((c.date for c in report.commits if c.sha == b_sha or c.sha.startswith(b_sha[:10])), "")
                for c in report.commits:
                    if a_date and b_date and a_date < c.date <= b_date:
                        between.append(c.sha)
            path_limit = files_touched_by_commits(between) if between else all_files
            if a_sha == b_sha:
                entry = {
                    "from": a_id,
                    "to": b_id,
                    "from_sha": a_sha,
                    "to_sha": b_sha,
                    "stat": "(identical tips)",
                    "name_status": "",
                    "commit_count": len(between),
                }
            else:
                entry = {
                    "from": a_id,
                    "to": b_id,
                    "from_sha": a_sha,
                    "to_sha": b_sha,
                    "stat": diff_stat(a_sha, b_sha, path_limit=path_limit or None),
                    "name_status": diff_name_status(a_sha, b_sha, path_limit=path_limit or None),
                    "commit_count": len(between),
                    "files_scoped": len(path_limit),
                }
            report.stage_diffs.append(entry)

    report.gaps = detect_gaps(report)
    if report.stage_count >= 2 and report.qa_comment_hits:
        report.notes.append(
            "Типичный паттерн: стейджи после initial часто закрывают баги из ручного QA в комментариях Jira."
        )
    return report


def write_task_outputs(report: TaskReport, with_diffs: bool, full_diff: bool) -> None:
    out = OUT_TASKS / report.task
    out.mkdir(parents=True, exist_ok=True)
    diffs_dir = out / "diffs"
    if with_diffs:
        diffs_dir.mkdir(parents=True, exist_ok=True)

    # stages.json
    (out / "stages.json").write_text(
        json.dumps(
            {
                "task": report.task,
                "stages": [asdict(s) for s in report.stages],
                "commits": [asdict(c) for c in report.commits],
                "stage_diffs": report.stage_diffs,
                "testing": report.testing,
                "gaps": report.gaps,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    # overview.md
    lines: List[str] = []
    lines.append(f"# Анализ задачи CT-{report.task}")
    lines.append("")
    lines.append("<!-- meta")
    lines.append("type: research")
    lines.append("status: draft")
    lines.append(f"updated: {datetime.now(timezone.utc).date().isoformat()}")
    lines.append("related: [../../README.md, ../../index.md]")
    lines.append("tags: [testanalyze, stages, jira]")
    lines.append("-->")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Суть")
    lines.append("")
    lines.append(
        f"Сводка стейджей, Jira и git-дифов для CT-{report.task}. "
        "Нужна для улучшения планирования и тестирования (почему появляются stage2+)."
    )
    lines.append("")
    lines.append("## Jira")
    lines.append("")
    lines.append(f"- Title: {report.title or '(нет task.md)'}")
    lines.append(f"- URL: {report.jira_url}")
    lines.append(f"- State: {report.jira_state or '-'}")
    lines.append(f"- Kind: {report.jira_kind or '-'}")
    lines.append(f"- Version: {report.jira_version or '-'}")
    lines.append(f"- Comments: {report.comment_count}")
    lines.append(f"- QA-сигналы в комментариях: {report.qa_comment_hits}")
    if report.qa_comment_excerpts:
        lines.append("")
        lines.append("### Выдержки QA-комментариев")
        lines.append("")
        for ex in report.qa_comment_excerpts:
            lines.append(f"- {ex}")
    lines.append("")
    lines.append("## Артефакты папки задачи")
    lines.append("")
    lines.append("| Файл | Есть |")
    lines.append("|---|---|")
    for k, v in report.artifacts.items():
        lines.append(f"| `{k}` | {'да' if v else 'нет'} |")
    lines.append("")
    lines.append("## Стейджи")
    lines.append("")
    if not report.stages:
        lines.append("Стейдж-планов нет (только root-артефакты или пустая папка).")
    else:
        lines.append("| Stage | Status | Updated | Tip | Source | Plan |")
        lines.append("|---|---|---|---|---|---|")
        for st in report.stages:
            tip = (st.tip_commit or "")[:10]
            lines.append(
                f"| {st.id} | {st.status or '-'} | {st.updated or '-'} | "
                f"`{tip or '-'}` | {st.tip_source or '-'} | `{st.path}` |"
            )
        lines.append("")
        for st in report.stages:
            lines.append(f"### {st.id}: {st.title or ''}")
            lines.append("")
            if st.problem_excerpt:
                lines.append(st.problem_excerpt)
                lines.append("")
            if st.commit_shas:
                lines.append("Коммиты в date-bucket:")
                for sha in st.commit_shas:
                    subj = next((c.subject for c in report.commits if c.sha == sha), "")
                    lines.append(f"- `{sha[:10]}` {subj}")
                lines.append("")
    lines.append("## Git коммиты задачи")
    lines.append("")
    lines.append(f"Всего: **{report.commit_count}**")
    lines.append("")
    for c in report.commits:
        lines.append(f"- `{c.sha[:10]}` {c.date[:10]} {c.subject}")
    lines.append("")
    lines.append("## Дифы стейджей")
    lines.append("")
    if report.first_commit and report.last_commit:
        lines.append(
            f"First→Last: `{report.first_commit[:10]}` → `{report.last_commit[:10]}`"
        )
        lines.append("")
        lines.append("```")
        lines.append(report.first_to_last_stat or "(нет stat)")
        lines.append("```")
        lines.append("")
    if report.stage_diffs:
        for d in report.stage_diffs:
            lines.append(
                f"### {d['from']} → {d['to']} (`{d['from_sha'][:10]}`..`{d['to_sha'][:10]}`)"
            )
            lines.append("")
            lines.append("```")
            lines.append(d.get("stat") or "(empty)")
            lines.append("```")
            lines.append("")
            if d.get("name_status"):
                lines.append("Файлы:")
                lines.append("")
                lines.append("```")
                lines.append(d["name_status"])
                lines.append("```")
                lines.append("")
    else:
        lines.append("Попарные дифы стейджей не собраны (нет tip-коммитов или флаг --with-diffs выключен).")
        lines.append("")

    lines.append("## Тестирование (скилы)")
    lines.append("")
    lines.append(f"- test.md: {'да' if report.testing.get('test_md') else 'нет'}")
    lines.append(f"- Cest: {report.testing.get('cest_path') or 'нет'}")
    lines.append(f"- test-runs: {'да' if report.testing.get('test_runs') else 'нет'}")
    for f in report.testing.get("test_run_files") or []:
        lines.append(f"  - `{f}`")
    lines.append(
        f"- Verification/test scenario в планах: {report.testing.get('verification_in_plans', 0)}"
    )
    lines.append(
        f"- login-as-user hint: {'да' if report.testing.get('login_as_user_hint') else 'нет'}"
    )
    lines.append("")
    lines.append("## Пробелы (gaps)")
    lines.append("")
    if report.gaps:
        for g in report.gaps:
            lines.append(f"- {g}")
    else:
        lines.append("- явных пробелов по эвристикам нет")
    lines.append("")
    if report.notes:
        lines.append("## Заметки")
        lines.append("")
        for n in report.notes:
            lines.append(f"- {n}")
        lines.append("")
    lines.append("## Связи")
    lines.append("")
    lines.append(f"- Исходники задачи: [../../tasks/{report.task}/](../../tasks/{report.task}/)")
    lines.append("- Канон QA: [../../tests.md](../../tests.md)")
    lines.append("- Индекс анализа: [../../index.md](../../index.md)")
    lines.append("")
    lines.append("## История изменений")
    lines.append("")
    lines.append(
        f"- {datetime.now(timezone.utc).date().isoformat()}: сгенерировано build-testanalyze.py"
    )
    lines.append("")
    (out / "overview.md").write_text("\n".join(lines), encoding="utf-8")

    if with_diffs and report.commits:
        all_files = files_touched_by_commits([c.sha for c in report.commits])
        if report.first_commit and report.last_commit:
            (diffs_dir / "first-to-last.stat.txt").write_text(
                report.first_to_last_stat or "", encoding="utf-8"
            )
            (diffs_dir / "first-to-last.files.txt").write_text(
                "\n".join(all_files), encoding="utf-8"
            )
            if full_diff and all_files:
                patch = diff_patch(
                    report.first_commit, report.last_commit, path_limit=all_files
                )
                (diffs_dir / "first-to-last.patch").write_text(patch, encoding="utf-8")
        for d in report.stage_diffs:
            base = f"{d['from']}-to-{d['to']}"
            (diffs_dir / f"{base}.stat.txt").write_text(d.get("stat") or "", encoding="utf-8")
            (diffs_dir / f"{base}.files.txt").write_text(
                d.get("name_status") or "", encoding="utf-8"
            )
            if full_diff and d.get("from_sha") and d.get("to_sha") and d["from_sha"] != d["to_sha"]:
                # scope to name_status paths if any
                paths = [
                    line.split("\t", 1)[-1]
                    for line in (d.get("name_status") or "").splitlines()
                    if line.strip()
                ]
                patch = diff_patch(d["from_sha"], d["to_sha"], path_limit=paths or all_files)
                (diffs_dir / f"{base}.patch").write_text(patch, encoding="utf-8")


def refresh_jira(tasks: List[str]) -> None:
    if not JIRA_EXPORT.exists():
        print(f"[warn] Jira exporter not found: {JIRA_EXPORT}", file=sys.stderr)
        return
    # Prefer host php, else docker
    php = "php"
    use_docker = False
    try:
        subprocess.run([php, "-v"], capture_output=True, check=True)
    except Exception:
        use_docker = True
    for t in tasks:
        print(f"[jira] export CT-{t} ...")
        if use_docker:
            cmd = [
                "docker",
                "exec",
                "copytrust-dev-php-apache-1",
                "php",
                "/var/www/html/.agents/skills/task-router/children/jira/scripts/server.php",
                t,
            ]
        else:
            cmd = [php, str(JIRA_EXPORT), t]
        proc = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)
        if proc.returncode != 0:
            print(f"[jira] fail {t}: {proc.stderr or proc.stdout}", file=sys.stderr)
        else:
            print((proc.stdout or "").strip() or f"[jira] ok {t}")


def write_index(reports: List[TaskReport], merge_existing: bool = False) -> None:
    now = datetime.now(timezone.utc).date().isoformat()

    if merge_existing and (OUT_DIR / "summary.json").exists():
        try:
            prev = json.loads((OUT_DIR / "summary.json").read_text(encoding="utf-8"))
            by_id = {str(t["task"]): t for t in prev.get("tasks", [])}
            fresh = {r.task: r for r in reports}
            for r in reports:
                by_id[r.task] = {
                    "task": r.task,
                    "title": r.title,
                    "stage_count": r.stage_count,
                    "commit_count": r.commit_count,
                    "qa_comment_hits": r.qa_comment_hits,
                    "gaps": r.gaps,
                    "artifacts": r.artifacts,
                    "testing": r.testing,
                    "first_commit": r.first_commit,
                    "last_commit": r.last_commit,
                }
            merged: List[TaskReport] = []
            for tid in sorted(by_id.keys(), key=lambda x: int(x) if str(x).isdigit() else 0):
                if tid in fresh:
                    merged.append(fresh[tid])
                    continue
                d = by_id[tid]
                tr = TaskReport(task=str(tid))
                tr.title = d.get("title") or ""
                tr.stage_count = int(d.get("stage_count") or 0)
                tr.commit_count = int(d.get("commit_count") or 0)
                tr.qa_comment_hits = int(d.get("qa_comment_hits") or 0)
                tr.gaps = list(d.get("gaps") or [])
                tr.artifacts = dict(d.get("artifacts") or {})
                tr.testing = dict(d.get("testing") or {})
                tr.first_commit = d.get("first_commit") or ""
                tr.last_commit = d.get("last_commit") or ""
                merged.append(tr)
            reports = merged
            print(f"[testanalyze] merged index to {len(reports)} tasks")
        except Exception as e:
            print(f"[warn] merge_existing failed: {e}", file=sys.stderr)

    multi = [r for r in reports if r.stage_count >= 2]
    with_test = [r for r in reports if r.artifacts.get("test.md") or r.artifacts.get("cest")]
    with_runs = [r for r in reports if r.artifacts.get("test-runs")]
    gap_counter: Counter = Counter()
    for r in reports:
        for g in r.gaps:
            gap_counter[g] += 1

    lines: List[str] = []
    lines.append("# Индекс testanalyze")
    lines.append("")
    lines.append("<!-- meta")
    lines.append("type: index")
    lines.append("status: draft")
    lines.append(f"updated: {now}")
    lines.append("related: [README.md, skills-map.md]")
    lines.append("tags: [testanalyze, index]")
    lines.append("-->")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Суть")
    lines.append("")
    lines.append(
        "Сводная таблица по задачам из `.doc/tasks/`: сколько стейджей, есть ли автотесты, "
        "QA-сигналы в Jira, пробелы workflow."
    )
    lines.append("")
    lines.append("## Сводка")
    lines.append("")
    lines.append(f"- Задач в прогоне: **{len(reports)}**")
    lines.append(f"- С 2+ планами/стейджами: **{len(multi)}**")
    lines.append(f"- С test.md или Cest: **{len(with_test)}**")
    lines.append(f"- С test-runs: **{len(with_runs)}**")
    lines.append("")
    lines.append("## Топ пробелов")
    lines.append("")
    if gap_counter:
        for g, n in gap_counter.most_common(12):
            lines.append(f"- ({n}) {g}")
    else:
        lines.append("- нет")
    lines.append("")
    lines.append("## Multi-stage задачи (приоритет исследования)")
    lines.append("")
    lines.append(
        "| Task | Stages | Commits | QA comments | test.md | Cest | test-runs | Gaps | Overview |"
    )
    lines.append("|---|---:|---:|---:|---|---|---|---|---|")
    for r in sorted(multi, key=lambda x: (-x.stage_count, x.task)):
        gaps_n = len(r.gaps)
        lines.append(
            f"| {r.task} | {r.stage_count} | {r.commit_count} | {r.qa_comment_hits} | "
            f"{'да' if r.artifacts.get('test.md') else 'нет'} | "
            f"{'да' if r.artifacts.get('cest') else 'нет'} | "
            f"{'да' if r.artifacts.get('test-runs') else 'нет'} | {gaps_n} | "
            f"[overview](./tasks/{r.task}/overview.md) |"
        )
    lines.append("")
    lines.append("## Все задачи прогона")
    lines.append("")
    lines.append("| Task | Title | Stages | Commits | State | Overview |")
    lines.append("|---|---|---:|---:|---|---|")
    for r in sorted(reports, key=lambda x: int(x.task) if x.task.isdigit() else 0):
        title = (r.title or "").replace("|", "/")
        if len(title) > 80:
            title = title[:77] + "..."
        ov = f"[overview](./tasks/{r.task}/overview.md)" if (OUT_TASKS / r.task / "overview.md").exists() else "-"
        lines.append(
            f"| {r.task} | {title} | {r.stage_count} | {r.commit_count} | {r.jira_state or '-'} | {ov} |"
        )
    lines.append("")
    lines.append("## Связи")
    lines.append("")
    lines.append("- [README](./README.md)")
    lines.append("- [skills-map](./skills-map.md)")
    lines.append("- [findings-seed](./findings-seed.md)")
    lines.append("- [tests.md](../tests.md)")
    lines.append("")
    lines.append("## История изменений")
    lines.append("")
    lines.append(f"- {now}: пересборка build-testanalyze.py")
    lines.append("")
    (OUT_DIR / "index.md").write_text("\n".join(lines), encoding="utf-8")

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "task_count": len(reports),
        "multi_stage_count": len(multi),
        "with_test_count": len(with_test),
        "gap_counts": dict(gap_counter),
        "tasks": [
            {
                "task": r.task,
                "title": r.title,
                "stage_count": r.stage_count,
                "commit_count": r.commit_count,
                "qa_comment_hits": r.qa_comment_hits,
                "gaps": r.gaps,
                "artifacts": r.artifacts,
                "testing": r.testing,
                "first_commit": r.first_commit,
                "last_commit": r.last_commit,
            }
            for r in reports
        ],
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_skills_map() -> None:
    now = datetime.now(timezone.utc).date().isoformat()
    lines = [
        "# Карта скилов планирования и тестирования",
        "",
        "<!-- meta",
        "type: research",
        "status: draft",
        f"updated: {now}",
        "related: [README.md, index.md, ../tests.md]",
        "tags: [testanalyze, skills]",
        "-->",
        "",
        "---",
        "",
        "## Суть",
        "",
        "Какой скил закрывает какой кусок workflow «одна задача = одна ветка, "
        "следующий стейдж = правка бага после ручного теста».",
        "",
        "## Поток (как есть)",
        "",
        "```",
        "gototask → task.md (Jira)",
        "prepare-plan → plan.md",
        "реализация + task-diff → diff.md",
        "ручное / test-task → находка бага",
        "prepare-plan (stageN) → stageN/plan.md",
        "правка на той же ветке",
        "... повтор до закрытия",
        "```",
        "",
        "## Скилы",
        "",
        "| Skill | Роль | Доказательства в `.doc/tasks/{N}/` |",
        "|---|---|---|",
    ]
    for s in SKILLS:
        ev = ", ".join(f"`{e}`" for e in s["evidence"])
        lines.append(f"| `{s['id']}` | {s['role']} | {ev} |")
    lines += [
        "",
        "## Канон",
        "",
        "- [../tests.md](../tests.md) - чек-лист и отчёты",
        "- [../qa/index.md](../qa/index.md) - UI-флоу",
        "- prepare-plan: stage после merge/incident → `stageN/plan.md` (не затирать plan.md)",
        "",
        "## Гипотезы для улучшения (исследовать по index.md)",
        "",
        "1. Multi-stage без Cest/test.md: баги ручного QA не превращаются в регрессионный тест.",
        "2. Verification в plan.md есть, но test-task не запускали → нет test-runs.",
        "3. QA-комментарии в Jira = триггер stageN; можно требовать stage-план + тест-сценарий до кода.",
        "4. First→Last diff показывает «дрейф» scope: что ушло далеко от initial plan.",
        "",
        "## Связи",
        "",
        "- [README](./README.md)",
        "- [index](./index.md)",
        "",
        "## История изменений",
        "",
        f"- {now}: первичная карта",
        "",
    ]
    (OUT_DIR / "skills-map.md").write_text("\n".join(lines), encoding="utf-8")


def write_readme() -> None:
    now = datetime.now(timezone.utc).date().isoformat()
    content = f"""# testanalyze - исследование стейджей задач для улучшения планирования и тестирования

<!-- meta
type: research
status: draft
updated: {now}
related: [index.md, skills-map.md, ../tests.md, ../harnes/doc_rules.md]
tags: [testanalyze, qa, planning, stages]
-->

---

## Суть

Отдельный исследовательский контур (не продуктовая архитектура).

В CopyTrust обычно: **одна задача Jira = одна git-ветка**. После реализации и ручного
тестирования часто находится баг → новый **стейдж** (`stage2/plan.md`, `stage3/`, …)
на той же ветке, без новой задачи.

Папка `.doc/testanalyze/` собирает по существующим `.doc/tasks/{{N}}/`:

- стейджи и их планы;
- историю/комментарии Jira из `task.md`;
- git-коммиты с номером задачи;
- дифы **между стейджами** и **от первого коммита к последнему**;
- сопоставление с скилами `prepare-plan`, `test-task`, `browser-verify`, …

Цель: потом проанализировать, где рвётся планирование и тестирование, и улучшить workflow
(чтобы меньше «сюрпризов» на ручном QA и больше регрессии в Codeception).

Это **не** замена `.doc/tasks/` и **не** канон QA (канон: [../tests.md](../tests.md)).

---

## Как устроено

```
.doc/testanalyze/
├── README.md                 ← этот файл
├── index.md                  ← сводная таблица
├── summary.json              ← машинная сводка
├── skills-map.md             ← скилы vs артефакты задачи
├── scripts/
│   ├── build-testanalyze.py  ← сборщик
│   └── build-testanalyze.sh  ← обёртка
└── tasks/{{N}}/
    ├── overview.md           ← Jira + стейджи + gaps
    ├── stages.json           ← сырые данные
    └── diffs/                ← first-to-last + stageA-to-stageB
        ├── first-to-last.stat.txt
        ├── first-to-last.files.txt
        ├── stage2-to-stage3.stat.txt
        └── ... (.patch если --full-diff)
```

Источники (только чтение продуктовых доков задачи):

| Источник | Что берём |
|---|---|
| `.doc/tasks/{{N}}/task.md` | ТЗ, State, комментарии Jira, QA-сигналы |
| `plan.md`, `stage*/plan.md` | стейджи, meta (status/updated/head), проблема |
| `doc.md`, `test.md`, `test-runs/` | документация и факты прогона |
| `diff.md` / git log | коммиты и дифы по номеру задачи |
| `.tools/codeception/.../Task/` | наличие Task Cest |

---

## Как запускать

Из **корня репозитория**:

```bash
# все папки задач: overview + index (без тяжёлых дифов)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py

# только multi-stage + дифы между tip-коммитами стейджей
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --staged-only --with-diffs

# одна задача, полный patch
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --task 2410 --with-diffs --full-diff

# обновить task.md из Jira перед сборкой (нужен PHP или docker php)
python3 .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.py --refresh-jira --staged-only --with-diffs

# обёртка
bash .agents/skills/task-router/children/testing-router/children/test-task/scripts/build-testanalyze.sh --staged-only --with-diffs
```

Флаги:

| Флаг | Смысл |
|---|---|
| `--all` | все числовые папки в `.doc/tasks/` (по умолчанию) |
| `--staged-only` | только задачи, где есть `stage*` или root `plan.md` + `stage*` |
| `--multi-stage` | только где планов/стейджей >= 2 |
| `--task N` | одна задача (можно несколько раз) |
| `--with-diffs` | писать `diffs/*.stat.txt` и `*.files.txt` |
| `--full-diff` | ещё и `*.patch` (может быть большим) |
| `--refresh-jira` | перед анализом вызвать `.agents/skills/task-router/children/jira/scripts/server.php` |
| `--limit N` | ограничить число задач (отладка) |

---

## Как читать результат

1. [index.md](./index.md) - кто multi-stage, где нет тестов, топ gaps.
2. [skills-map.md](./skills-map.md) - какой скил за что отвечает.
3. `tasks/{{N}}/overview.md` - Jira QA-комменты ↔ стейджи ↔ коммиты.
4. `tasks/{{N}}/diffs/first-to-last.*` - насколько уехал scope от первого фикса к последнему.
5. `tasks/{{N}}/diffs/stageX-to-stageY.*` - что именно дописывали после очередного ручного теста.

Эвристика tip-коммита стейджа (по убыванию надёжности):

1. `head:` / `merged:` в meta плана;
2. валидный SHA из текста плана;
3. коммиты задачи, попавшие в date-bucket по `updated:` плана;
4. fallback по порядку коммитов (помечается в overview).

---

## Зачем это для улучшения workflow

Типичный цикл сейчас:

```
plan (initial) → код → ручной тест → баг в Jira-комменте
  → stage2/plan.md → код → снова тест → stage3 → ...
```

Вопросы к данным в этой папке:

1. Сколько стейджей в среднем и какие задачи «рекордсмены»?
2. Какие баги stage2+ можно было поймать Verification / per-patch scenario в initial plan?
3. Где после бага не появился Task Cest / test-runs (дыра `test-task`)?
4. Совпадают ли QA-комментарии Jira по датам со стейджами?
5. First→Last: раздувается ли diff (признак слабого initial scope / пропущенного blast radius)?

Ответы должны вести к правкам скилов `prepare-plan` / `test-task` / `browser-verify`,
а не к копированию текста в architecture.

---

## Ограничения

- Не пишет в `.doc/architecture/` и не меняет код продукта.
- `task.md` без `--refresh-jira` может быть устаревшим.
- Grep коммитов по номеру задачи может поймать ложные совпадения (фильтр subject есть, но не идеален).
- Не все stage-планы содержат SHA: тогда tip приблизительный.
- Полные patch-файлы не хранить в git без нужды (`--full-diff` точечно).

---

## Связи

- [index.md](./index.md)
- [skills-map.md](./skills-map.md)
- [../tests.md](../tests.md)
- [../harnes/doc_rules.md](../harnes/doc_rules.md)
- Скилы: `.cursor/skills/prepare-plan`, `test-task`, `task-diff`, `gototask`

---

## История изменений

- {now}: первичная структура и сборщик
"""
    (OUT_DIR / "README.md").write_text(content, encoding="utf-8")


def select_tasks(args: argparse.Namespace) -> List[str]:
    if args.task:
        return [str(t) for t in args.task]
    all_tasks = sorted(
        [p.name for p in TASKS_DIR.iterdir() if p.is_dir() and p.name.isdigit()],
        key=lambda x: int(x),
    )
    if args.multi_stage or args.staged_only:
        selected = []
        for t in all_tasks:
            d = TASKS_DIR / t
            stages = discover_stages(d)
            if args.multi_stage and len(stages) >= 2:
                selected.append(t)
            elif args.staged_only and (
                any(x.is_dir() and x.name.startswith("stage") for x in d.iterdir())
                or (d / "plan.md").exists()
            ):
                # staged-only: has stage* dir OR we still want tasks with only plan?
                # User asked stages - prefer has stage* directory
                if any(x.is_dir() and x.name.startswith("stage") for x in d.iterdir()):
                    selected.append(t)
        return selected
    return all_tasks


def main() -> int:
    parser = argparse.ArgumentParser(description="Build .doc/testanalyze corpus")
    parser.add_argument("--all", action="store_true", help="all task folders (default)")
    parser.add_argument("--staged-only", action="store_true", help="only tasks with stage* dirs")
    parser.add_argument("--multi-stage", action="store_true", help="only >=2 plans/stages")
    parser.add_argument("--task", action="append", type=int, help="task number (repeatable)")
    parser.add_argument("--with-diffs", action="store_true", help="write stage diff stats")
    parser.add_argument("--full-diff", action="store_true", help="also write .patch files")
    parser.add_argument("--refresh-jira", action="store_true", help="export task.md via Jira PHP")
    parser.add_argument("--limit", type=int, default=0, help="limit tasks processed")
    parser.add_argument("--skip-readme", action="store_true", help="do not overwrite README.md")
    args = parser.parse_args()

    if not TASKS_DIR.is_dir():
        print(f"Tasks dir missing: {TASKS_DIR}", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_TASKS.mkdir(parents=True, exist_ok=True)

    tasks = select_tasks(args)
    if args.limit and args.limit > 0:
        tasks = tasks[: args.limit]

    if not tasks:
        print("No tasks selected.", file=sys.stderr)
        return 1

    print(f"[testanalyze] repo={REPO_ROOT}")
    print(f"[testanalyze] tasks selected: {len(tasks)}")

    if args.refresh_jira:
        refresh_jira(tasks)

    cests = list_cests()
    reports: List[TaskReport] = []

    # For index completeness: if multi/staged filter, still we only write those.
    # Optionally also build light index - user can run --all separately.
    for i, t in enumerate(tasks, 1):
        print(f"[{i}/{len(tasks)}] CT-{t}")
        report = analyze_task(
            t,
            cests=cests,
            with_diffs=args.with_diffs or args.full_diff,
            full_diff=args.full_diff,
        )
        write_task_outputs(
            report,
            with_diffs=args.with_diffs or args.full_diff,
            full_diff=args.full_diff,
        )
        reports.append(report)

    write_index(reports, merge_existing=bool(args.task))
    write_skills_map()
    if not args.skip_readme:
        write_readme()

    print(f"[testanalyze] done. index={OUT_DIR / 'index.md'}")
    print(f"[testanalyze] multi-stage in this run: {sum(1 for r in reports if r.stage_count >= 2)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
