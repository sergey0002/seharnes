#!/usr/bin/env python3
"""Build a deterministic, evidence-first task change cheat sheet."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

SECRET = re.compile(r"(?i)(password|passwd|secret|token|api[_-]?key|cookie|authorization)\s*[:=]\s*([^\s,;]+)")
PATH_RE = re.compile(r"(?:(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+\.[A-Za-z0-9_.-]+)")
HUNK_RE = re.compile(r"^@@ -(?P<old>\d+)(?:,(?P<old_len>\d+))? \+(?P<new>\d+)(?:,(?P<new_len>\d+))? @@ ?(?P<context>.*)$")


def clean(value: str) -> str:
    return SECRET.sub(lambda match: f"{match.group(1)}: [REDACTED]", value)


def safe(value: object) -> str:
    return html.escape(clean(str(value)), quote=True)


MERMAID_TYPES = (
    "flowchart", "graph", "sequenceDiagram", "classDiagram",
    "stateDiagram", "stateDiagram-v2", "erDiagram", "journey",
    "gantt", "pie", "gitGraph", "mindmap", "timeline",
    "quadrantChart", "c4Context", "requirementDiagram"
)


def validate_mermaid_diagram(title: str, text: str) -> None:
    raw = (text or "").strip()
    if not raw:
        raise ValueError(f"Mermaid diagram '{title}' is empty")

    lines = [line.strip() for line in raw.splitlines() if line.strip() and not line.strip().startswith("%%")]
    if not lines:
        raise ValueError(f"Mermaid diagram '{title}' contains no active statements")

    first_token = lines[0].split()[0]
    if not any(lines[0].startswith(mtype) for mtype in MERMAID_TYPES):
        raise ValueError(
            f"Mermaid diagram '{title}' starts with unknown diagram type '{first_token}'. "
            f"Must start with one of: {', '.join(sorted(MERMAID_TYPES))}"
        )

    # Check unescaped double quotes parity
    unescaped_quotes = len(re.findall(r'(?<!\\)"', raw))
    if unescaped_quotes % 2 != 0:
        raise ValueError(f"Mermaid diagram '{title}' has unclosed double quotes")

    # Strip quoted content for structural checking
    stripped = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', raw)

    # Check bracket balance in non-quoted structure
    for open_br, close_br, name in (("[", "]", "square brackets"), ("(", ")", "parentheses"), ("{", "}", "curly braces")):
        if stripped.count(open_br) != stripped.count(close_br):
            raise ValueError(
                f"Mermaid diagram '{title}' has unbalanced {name}: "
                f"{stripped.count(open_br)} open vs {stripped.count(close_br)} close"
            )

    diag_type = lines[0].split()[0]
    if diag_type in ("stateDiagram", "stateDiagram-v2"):
        for line in lines[1:]:
            line_stripped = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', line)
            if line_stripped.count(":") > 1:
                raise ValueError(
                    f"Mermaid stateDiagram '{title}' has line with multiple colons: '{line}'. "
                    f"Prefer 'flowchart TD' with quoted node labels instead."
                )
    elif diag_type in ("flowchart", "graph"):
        for line in lines[1:]:
            m = re.search(r'\([^\)"]*:[^\)"]*\)', line)
            if m:
                raise ValueError(
                    f"Mermaid flowchart '{title}' contains unquoted colon inside parentheses: '{m.group(0)}'. "
                    f"Wrap node labels in quotes like Node[\"Текст: продолжение\"]."
                )


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def git(root: Path, args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=root, text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return ""


def extract_paths(text: str, root: Path) -> list[str]:
    paths: list[str] = []
    for raw in PATH_RE.findall(text):
        path = raw.strip("`.,()")
        if path not in paths and (root / path).is_file():
            paths.append(path)
    return paths


def parse_diff(diff: str) -> tuple[dict[str, dict], int, int]:
    files: dict[str, dict] = {}
    current = ""
    added_total = deleted_total = 0
    old_line = new_line = 0
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            match = re.search(r" b/(.+)$", line)
            current = match.group(1) if match else ""
            files.setdefault(current, {"added": 0, "deleted": 0, "hunks": []})
            continue
        if line.startswith("@@ "):
            match = HUNK_RE.match(line)
            if not match:
                continue
            old_line = int(match.group("old"))
            new_line = int(match.group("new"))
            files.setdefault(current, {"added": 0, "deleted": 0, "hunks": []})["hunks"].append({
                "header": line,
                "context": match.group("context"),
                "old_start": old_line,
                "new_start": new_line,
                "lines": [],
            })
            continue
        if not current or not files.get(current, {}).get("hunks"):
            continue
        hunk = files[current]["hunks"][-1]
        if line.startswith("+") and not line.startswith("+++"):
            files[current]["added"] += 1
            added_total += 1
            hunk["lines"].append({"kind": "+", "old": None, "new": new_line, "text": line[1:]})
            new_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            files[current]["deleted"] += 1
            deleted_total += 1
            hunk["lines"].append({"kind": "-", "old": old_line, "new": None, "text": line[1:]})
            old_line += 1
        elif line.startswith(" "):
            hunk["lines"].append({"kind": " ", "old": old_line, "new": new_line, "text": line[1:]})
            old_line += 1
            new_line += 1
    return files, added_total, deleted_total


def first_heading(text: str, fallback: str) -> str:
    for line in text.splitlines():
        if line.startswith("#"):
            return line.lstrip("# ").strip()
    return fallback


def module_name(path: str) -> str:
    parts = path.replace("\\", "/").split("/")
    if path.startswith("tests/") or "/tests/" in path:
        return "Tests"
    if path.startswith("scripts/") or path.startswith("assets/") or path.startswith("styles/"):
        return "Frontend"
    if path.startswith("sql/"):
        return "Database"
    if path.startswith("lib/"):
        return "Backend"
    return parts[0] if parts else "Unmapped"


def get_git_release_info(root: Path, task_id: str) -> dict:
    tid = str(task_id).lstrip("#")
    merges_raw = git(root, ["log", f"--grep={tid}", "--merges", "-n", "10", "--format=%H|%s|%cd", "--date=format:%Y-%m-%d %H:%M"])
    target_release = ""
    merge_commit = ""
    merge_date = ""
    pr_num = ""
    merge_msg = ""
    for line in merges_raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("|", 2)
        h = parts[0]
        subj = parts[1] if len(parts) > 1 else ""
        dt = parts[2] if len(parts) > 2 else ""
        m = re.search(r"в\s+(releases/[^\s]+|master|main)", subj)
        if m:
            target_release = m.group(1)
            merge_commit = h[:10]
            merge_date = dt
            merge_msg = subj
            pr_match = re.search(r"#(\d+)", subj)
            if pr_match:
                pr_num = f"PR #{pr_match.group(1)}"
            break

    commits_raw = git(root, ["log", f"--grep={tid}", "-n", "10", "--format=%H"])
    all_releases = set()
    for c in commits_raw.splitlines():
        c = c.strip()
        if not c:
            continue
        branches_raw = git(root, ["branch", "-a", "--contains", c])
        for b in branches_raw.splitlines():
            clean_b = b.strip().replace("remotes/origin/", "").replace("* ", "")
            if clean_b.startswith("releases/"):
                all_releases.add(clean_b)

    is_merged = bool(target_release or all_releases)
    if not target_release and all_releases:
        target_release = sorted(all_releases)[0]

    return {
        "is_merged": is_merged,
        "target_release": target_release,
        "all_releases": sorted(all_releases),
        "merge_commit": merge_commit,
        "merge_date": merge_date,
        "pr_num": pr_num,
        "merge_msg": merge_msg,
    }


def get_file_timestamp(root: Path, path: str, branch_hint: str = "") -> str:
    if branch_hint and branch_hint != "unavailable":
        ts = git(root, ["log", "-1", "--format=%ad", "--date=format:%Y-%m-%d %H:%M", branch_hint, "--", path]).strip()
        if ts:
            return ts
    ts = git(root, ["log", "-1", "--format=%ad", "--date=format:%Y-%m-%d %H:%M", "--", path]).strip()
    if ts:
        return ts
    full = root / path
    if full.is_file():
        try:
            return datetime.fromtimestamp(full.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
        except Exception:
            pass
    return "—"


def parse_test_data(task_dir: Path, selected: dict | None = None) -> dict:
    res = {
        "verdict": None,
        "test_files": [],
        "logic_branches": [],
        "checklist": [],
        "restrictions": ""
    }

    tr_dir = task_dir / "test-runs"
    if selected is not None:
        if selected.get("verdict"):
            v_file = selected["verdict"][0]
            res["verdict"] = json.loads(v_file.read_text(encoding="utf-8"))
            res["verdict"]["run_id"] = v_file.parent.name
        res["test_files"] = [str(f.relative_to(task_dir)) if f.is_relative_to(task_dir) else f.name
                             for f in selected.get("test_file", [])]
    elif tr_dir.is_dir():
        runs = sorted(
            [d for d in tr_dir.iterdir() if d.is_dir() and ("task-" in d.name or "_" in d.name)],
            key=lambda x: x.name,
            reverse=True
        )
        for r in runs:
            v_file = r / "verdict.json"
            if v_file.is_file():
                try:
                    data = json.loads(read(v_file))
                    data["run_id"] = r.name
                    res["verdict"] = data
                    break
                except Exception:
                    pass

    t_dir = task_dir / "tests"
    if selected is None and t_dir.is_dir():
        res["test_files"] = [f.name for f in t_dir.iterdir() if f.is_file()]

    test_md = selected.get("test", [None])[0] if selected is not None else task_dir / "test.md"
    if test_md is not None and test_md.is_file():
        content = read(test_md)
        table_lines = []
        in_table = False
        for line in content.splitlines():
            s = line.strip()
            if s.startswith("| ID |") or s.startswith("|ID|"):
                in_table = True
            if in_table:
                if s.startswith("|"):
                    table_lines.append(s)
                else:
                    in_table = False
        if len(table_lines) >= 3:
            headers = [h.strip() for h in table_lines[0].strip("|").split("|")]
            for row in table_lines[2:]:
                cols = [c.strip() for c in row.strip("|").split("|")]
                if len(cols) == len(headers):
                    res["logic_branches"].append(dict(zip(headers, cols)))

        for line in content.splitlines():
            m = re.match(r"^-\s*\[([ x~-])\]\s*(.*)$", line.strip())
            if m:
                res["checklist"].append({"mark": m.group(1), "text": m.group(2)})

        if "## Ограничения" in content:
            res["restrictions"] = content.split("## Ограничения", 1)[1].strip()

    return res


def parse_doc_md(task_dir: Path, doc_file: Path | None = None) -> dict:
    doc_file = doc_file or task_dir / "doc.md"
    if not doc_file.is_file():
        return {"pitfalls": [], "decisions": [], "arch_links": []}

    content = read(doc_file)
    arch_links = []
    if re.search(r"##\s*(?:🗺️\s*)?(?:Архитектурный контекст|Связи)\s*$", content, re.M):
        raw = re.split(r"##\s*(?:🗺️\s*)?(?:Архитектурный контекст|Связи)\s*$", content, maxsplit=1, flags=re.M)[1]
        raw = re.split(r"\n##\s+", raw, maxsplit=1)[0]
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("- ["):
                m = re.match(r"- \[([^\]]+)\]\(([^)]+)\)(?:\s*—\s*(.*))?", line)
                if m:
                    arch_links.append({"title": m.group(1), "url": m.group(2), "desc": m.group(3) or ""})

    pitfalls = []
    if re.search(r"##\s*(?:⚠️\s*)?(?:Подводные камни|Известные проблемы и ограничения)\s*$", content, re.M):
        raw = re.split(r"##\s*(?:⚠️\s*)?(?:Подводные камни|Известные проблемы и ограничения)\s*$", content, maxsplit=1, flags=re.M)[1]
        raw = re.split(r"\n##\s+", raw, maxsplit=1)[0]
        blocks = re.split(r"\n###\s+", raw)
        for b in blocks:
            b = b.strip()
            if not b:
                continue
            lines = b.splitlines()
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            symptom = reason = solution = files = ""
            m_s = re.search(r"\*\*(?:Симптом|Проблема):\*\*\s*(.*)", body)
            if m_s:
                symptom = m_s.group(1).strip()
            m_r = re.search(r"\*\*(?:Причина):\*\*\s*(.*)", body)
            if m_r:
                reason = m_r.group(1).strip()
            m_sol = re.search(r"\*\*(?:Решение|Ограничение или решение):\*\*\s*(.*)", body)
            if m_sol:
                solution = m_sol.group(1).strip()
            m_f = re.search(r"\*\*(?:Файлы):\*\*\s*(.*)", body)
            if m_f:
                files = m_f.group(1).strip()
            pitfalls.append({
                "title": title,
                "symptom": symptom,
                "reason": reason,
                "solution": solution,
                "files": files,
                "raw": body
            })

    decisions = []
    if re.search(r"##\s*(?:🔀\s*)?(?:Принятые решения|Решения и обоснования)\s*$", content, re.M):
        raw = re.split(r"##\s*(?:🔀\s*)?(?:Принятые решения|Решения и обоснования)\s*$", content, maxsplit=1, flags=re.M)[1]
        raw = re.split(r"\n##\s+", raw, maxsplit=1)[0]
        blocks = re.split(r"\n###\s+", raw)
        for b in blocks:
            b = b.strip()
            if not b:
                continue
            lines = b.splitlines()
            title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            context = approach = alternatives = ""
            m_c = re.search(r"\*\*Контекст:\*\*\s*(.*)", body)
            if m_c:
                context = m_c.group(1).strip()
            m_a = re.search(r"\*\*Подход:\*\*\s*(.*)", body)
            if m_a:
                approach = m_a.group(1).strip()
            m_alt = re.search(r"\*\*(?:Альтернативы которые не подошли|Альтернативы):\*\*\s*(.*)", body)
            if m_alt:
                alternatives = m_alt.group(1).strip()
            decisions.append({
                "title": title,
                "context": context,
                "approach": approach,
                "alternatives": alternatives,
                "raw": body
            })

    return {
        "pitfalls": pitfalls,
        "decisions": decisions,
        "arch_links": arch_links
    }


def get_file_role(path: str, metrics: dict, model: dict) -> str:
    file_roles = model.get("file_roles", {})
    if isinstance(file_roles, dict) and path in file_roles and file_roles[path]:
        return file_roles[path]

    model_files = model.get("files", [])
    if isinstance(model_files, list):
        for item in model_files:
            if isinstance(item, dict) and item.get("path") == path and item.get("role"):
                return item["role"]

    filename = os.path.basename(path)
    if "Service.php" in filename:
        return f"Сервис бизнес-логики ({filename[:-4]})"
    if "Command.php" in filename:
        return f"Класс выполнения команды ({filename[:-4]})"
    if "Controller.php" in filename:
        return f"Контроллер обработки запросов ({filename[:-4]})"
    if "MVC.php" in filename:
        return f"Модель и логика представления ({filename[:-4]})"
    if "Version" in filename and path.startswith("sql/"):
        return "SQL-миграция структурирования и обновления БД"
    if filename.endswith(".tpl"):
        return f"Frontend-шаблон отображения ({filename})"
    if path.startswith("tests/"):
        return f"Автотест проверки функционала ({filename})"
    if path.startswith("lib/"):
        return f"Компонент backend ядра ({filename})"
    return f"Файл компонента {filename}"


def parse_task_md(text: str) -> dict:
    meta = {}
    jira_url = ""
    jm = re.search(r"\*\*Jira:\*\*\s*<([^>]+)>", text)
    if jm:
        jira_url = jm.group(1).strip()

    for line in text.splitlines():
        m = re.match(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|$", line)
        if m:
            k = m.group(1).strip()
            v = m.group(2).strip()
            if k not in ("Field", "---", ":---"):
                meta[k] = v

    comments = []
    if "## Comments" in text:
        raw_parts = text.split("## Comments", 1)[1]
        blocks = re.split(r"\n---\n", raw_parts)
        for b in blocks:
            b = b.strip()
            if not b:
                continue
            head = re.search(r"\*\*([^*]+)\*\*\s*·\s*([^\n]+)", b)
            if head:
                author = head.group(1).strip()
                date = head.group(2).strip()
                body = b[head.end():].strip()
                changes = []
                clean_lines = []
                for bline in body.splitlines():
                    if bline.startswith("*Changed:*"):
                        changes.append(bline.replace("*Changed:*", "").strip())
                    else:
                        clean_lines.append(bline)

                if comments and comments[-1]["author"] == author and comments[-1]["date"] == date:
                    comments[-1]["changes"].extend(changes)
                    added_text = "\n".join(clean_lines).strip()
                    if added_text:
                        comments[-1]["text"] = (comments[-1]["text"] + "\n\n" + added_text).strip()
                else:
                    comments.append({
                        "author": author,
                        "date": date,
                        "changes": changes,
                        "text": "\n".join(clean_lines).strip()
                    })

    return {
        "jira_url": jira_url,
        "meta": meta,
        "comments": comments
    }


def render_file_diff(file_item: dict) -> str:
    hunks = file_item.get("hunks", [])
    if not hunks:
        return '<div class="diff-empty">Файл контекстный (прямых изменений строк в diff задачи нет)</div>'

    hunk_blocks = []
    for h in hunks:
        header = safe(h.get("header", ""))
        ctx = safe(h.get("context", ""))
        lines_html = []
        for line in h.get("lines", []):
            kind = line.get("kind", " ")
            old_no = str(line["old"]) if line.get("old") is not None else ""
            new_no = str(line["new"]) if line.get("new") is not None else ""
            code_text = safe(line.get("text", ""))

            if kind == "+":
                cls = "diff-line-add"
                marker = "+"
            elif kind == "-":
                cls = "diff-line-del"
                marker = "-"
            else:
                cls = "diff-line-ctx"
                marker = " "

            lines_html.append(
                f'<tr class="diff-row {cls}">'
                f'<td class="diff-num diff-num-old">{old_no}</td>'
                f'<td class="diff-num diff-num-new">{new_no}</td>'
                f'<td class="diff-marker">{marker}</td>'
                f'<td class="diff-code"><code>{code_text}</code></td>'
                f'</tr>'
            )

        hunk_blocks.append(
            f'<div class="diff-hunk">'
            f'<div class="diff-hunk-bar"><code>{header}</code>'
            f'{f" <span class=\"diff-hunk-ctx\">{ctx}</span>" if ctx else ""}</div>'
            f'<div class="diff-scroll-box">'
            f'<table class="diff-code-table"><tbody>'
            f'{"".join(lines_html)}'
            f'</tbody></table>'
            f'</div></div>'
        )

    return f'<div class="diff-viewer">{"".join(hunk_blocks)}</div>'


CSS = '''*{box-sizing:border-box}body{margin:0;background:#101827;color:#e9eef8;font:16px/1.55 Inter,system-ui,sans-serif}main{max-width:1180px;margin:auto;padding:28px 18px}header,section,.stats,nav{background:#172235;border:1px solid #2a3a54;border-radius:18px;margin:0 0 16px;padding:22px;box-shadow:0 12px 35px #07101f55}h1{font-size:clamp(30px,6vw,62px);line-height:1.02;margin:8px 0 14px;max-width:900px}h2{margin-top:0;color:#8ed6ff}h3{color:#a5d6ff;margin:18px 0 10px}.eyebrow{color:#71e0ba;font-weight:800;letter-spacing:.16em}.lead{font-size:20px;color:#a9bad4}.hero,.answer,.jira{border-left:4px solid #71e0ba;background:#102b35;padding:15px;border-radius:8px}.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;text-align:center;background:#20304a}.stats b{font-size:34px;color:#71e0ba}.stats small{display:block;font-size:13px;color:#a9bad4;font-weight:400}nav{display:flex;gap:18px;flex-wrap:wrap;position:sticky;top:8px;z-index:2}nav a{color:#8ed6ff;text-decoration:none;font-weight:700}.diagram-grid,.compare,.screens{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.diagram,.compare article{background:#101a2b;border:1px solid #314766;padding:16px;border-radius:12px}.diagram{overflow:auto;cursor:pointer;transition:transform .2s,box-shadow .2s}.diagram:hover{transform:translateY(-2px);box-shadow:0 8px 24px #71e0ba22}.mermaid{background:#f8fafc;color:#172033;padding:10px;border-radius:8px;cursor:pointer}.changes article{border-top:1px solid #314766;padding:14px 0}.business-changes article{border-left:3px solid #71e0ba;background:#102b35;border-radius:8px;padding:12px 14px;margin:10px 0}.business-changes h3{color:#71e0ba}.changes article:first-child{border-top:0}.stages{padding-left:24px}.stages li{margin:10px 0}.badge{display:inline-block;padding:2px 8px;border-radius:20px;font-size:12px;background:#36506c}.badge.done,.badge.passed,.badge.covered{background:#176b55;color:#b6ffe6}.badge.failed,.badge.blocked,.badge.red{background:#7c3540;color:#ffd2d8}.badge.partial,.badge.pending{background:#6b4d17;color:#ffe6b6}.badge.skipped{background:#2a3a54;color:#94a3b8}table{width:100%;border-collapse:collapse}th,td{text-align:left;vertical-align:top;border-bottom:1px solid #314766;padding:10px}code{color:#d6a8ff}details{margin:8px 0}pre{white-space:pre-wrap;background:#0c1422;padding:10px;overflow:auto}.screens figure{margin:0;background:#101a2b;border:1px solid #314766;border-radius:12px;overflow:hidden;cursor:pointer;transition:transform .2s,box-shadow .2s}.screens figure:hover{transform:translateY(-2px);box-shadow:0 8px 24px #71e0ba22}.screens img{width:100%;display:block}.screens figcaption{padding:12px;color:#bdcce0}.jira{white-space:pre-wrap}footer{color:#8093af;font-size:13px;padding:10px 0}.action-btn-group{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.jira-link-btn{display:inline-flex;align-items:center;gap:8px;background:#0052cc;color:#fff!important;padding:8px 18px;border-radius:24px;font-size:13px;font-weight:700;text-decoration:none;transition:all .2s;box-shadow:0 4px 14px rgba(0,82,204,.4);flex-shrink:0}.jira-link-btn:hover{background:#0747a6;transform:translateY(-1px)}.print-btn,.copy-btn{display:inline-flex;align-items:center;gap:6px;background:#20304a;color:#8ed6ff;border:1px solid #314766;padding:8px 16px;border-radius:20px;font-size:13px;font-weight:600;cursor:pointer;transition:all .2s}.print-btn:hover,.copy-btn:hover{background:#2b4266;color:#fff;border-color:#3b82f6}.task-meta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;margin:16px 0;background:#101a2b;padding:14px;border-radius:14px;border:1px solid #2a3a54}.meta-item{display:flex;flex-direction:column;gap:3px}.meta-label{font-size:11px;color:#8093af;text-transform:uppercase;letter-spacing:.05em}.meta-val{font-size:13.5px;color:#e9eef8;font-weight:600}.release-merged{color:#7ee787!important;font-weight:700}.release-pending{color:#e3b341!important;font-weight:700}.file-date{font-size:12px;color:#8093af;font-family:ui-monospace,monospace;white-space:nowrap}.jira-thread{display:flex;flex-direction:column;gap:14px;margin-top:14px}.jira-post{background:#101a2b;border:1px solid #2a3a54;border-radius:12px;padding:16px;box-shadow:0 4px 14px rgba(0,0,0,.25)}.jira-post-header{display:flex;align-items:center;gap:12px;margin-bottom:10px;border-bottom:1px solid #1c283d;padding-bottom:8px}.jira-avatar{width:34px;height:34px;border-radius:50%;background:#1e3a5f;color:#8ed6ff;display:flex;align-items:center;justify-content:center;font-weight:800;font-size:12px;border:1px solid #3b82f6;flex-shrink:0}.jira-post-meta{display:flex;flex-direction:column}.jira-author{font-weight:700;color:#e9eef8;font-size:14px}.jira-date{font-size:12px;color:#8093af}.jira-changes{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:10px}.jira-change-tag{background:#281b36;color:#e879f9;border:1px solid #6b21a8;font-size:11px;padding:2px 8px;border-radius:6px;font-family:ui-monospace,monospace}.jira-post-text{font-size:13.5px;line-height:1.55;color:#cbd5e1;white-space:pre-wrap;background:#090f19;padding:12px;border-radius:8px;border:1px solid #1c283d}.ac-table,.test-branches-table{width:100%;border-collapse:collapse;margin:12px 0 18px;font-size:13px}.ac-table th,.test-branches-table th{background:#101a2b;color:#8ed6ff;padding:8px 10px;border-bottom:1px solid #2a3a54;font-size:12px}.ac-table td,.test-branches-table td{padding:8px 10px;border-bottom:1px solid #1c283d}.git-add{color:#7ee787;font-weight:700}.git-del{color:#f85149;font-weight:700}.file-main-row:hover td{background:#152238}.file-diff-row{background:#090e17}.diff-cell{padding:0 8px 12px 8px!important;background:#090e17!important;border-bottom:2px solid #2a3a54!important}.file-summary{display:inline-flex;align-items:center;gap:8px;cursor:pointer;padding:3px 6px;border-radius:6px;transition:background .15s ease;user-select:none}.file-summary:hover{background:#1e2c42}.file-summary:hover .file-path{color:#8ed6ff;text-decoration:underline}.file-path{font-size:13.5px;word-break:break-all;color:#a5d6ff}.diff-badge{font-size:11px;padding:2px 8px;border-radius:10px;background:#1e293b;color:#94a3b8;border:1px solid #334155;margin-left:auto;white-space:nowrap;transition:all .2s;cursor:pointer}.diff-badge.active{background:#174034;color:#71e0ba;border-color:#71e0ba}.diff-viewer-wrapper{margin:6px 0 2px;animation:diffFade .2s ease-in-out;width:100%}.diff-empty{padding:10px 14px;background:#0d1420;border:1px dashed #314766;border-radius:6px;color:#8093af;font-size:13px}.diff-viewer{display:flex;flex-direction:column;gap:10px;margin-bottom:4px;width:100%}.diff-hunk{border:1px solid #2a3a54;border-radius:8px;overflow:hidden;background:#090e17;width:100%}.diff-hunk-bar{background:#131c2d;padding:6px 12px;border-bottom:1px solid #2a3a54;font-size:12px;color:#79c0ff;display:flex;align-items:center;gap:8px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}.diff-hunk-ctx{color:#8093af;font-size:11px}.diff-scroll-box{max-height:550px;overflow:auto;width:100%}.diff-code-table{width:100%;border-collapse:collapse;font-family:ui-monospace,SFMono-Regular,Menlo,Monaco,Consolas,monospace;font-size:12px;line-height:1.45}.diff-code-table tr{border-bottom:0}.diff-code-table td{padding:1px 6px;vertical-align:top;border-bottom:0}.diff-num{width:36px;min-width:36px;text-align:right;color:#52647c;user-select:none;font-size:11px;background:#0b111a;border-right:1px solid #1c2637;padding-right:8px}.diff-marker{width:18px;min-width:18px;text-align:center;user-select:none;font-weight:700}.diff-code{white-space:pre-wrap;word-break:break-word}.diff-code code{background:transparent;color:inherit;padding:0}.diff-line-add{background:rgba(46,160,67,.18)}.diff-line-add .diff-marker{color:#3fb950}.diff-line-add .diff-code{color:#aff5b4}.diff-line-add .diff-num-new{color:#3fb950}.diff-line-del{background:rgba(248,81,73,.18)}.diff-line-del .diff-marker{color:#f85149}.diff-line-del .diff-code{color:#ffdcd7}.diff-line-del .diff-num-old{color:#f85149}.diff-line-ctx .diff-code{color:#c9d1d9}.file-toolbar{display:flex;gap:12px;flex-wrap:wrap;align-items:center;margin:16px 0 14px;background:#101a2b;padding:12px;border-radius:12px;border:1px solid #2a3a54}.file-search-input{background:#090e17;border:1px solid #314766;border-radius:8px;padding:7px 12px;color:#e9eef8;font-size:13.5px;min-width:260px;flex:1}.file-search-input:focus{outline:none;border-color:#3b82f6}.module-filter-tabs{display:flex;gap:6px;flex-wrap:wrap}.filter-tab{background:#172235;border:1px solid #2a3a54;color:#94a3b8;border-radius:20px;padding:4px 12px;font-size:12px;cursor:pointer;transition:all .2s;font-weight:600}.filter-tab:hover{border-color:#3b82f6;color:#e9eef8}.filter-tab.active{background:#0052cc;color:#fff;border-color:#3b82f6}.file-count-badge{font-size:12px;color:#8093af;margin-left:auto;white-space:nowrap}.module-bar{height:8px;border-radius:4px;overflow:hidden;display:flex;margin:14px 0 8px;background:#090e17}.module-bar-segment{height:100%;transition:width .3s}.module-legend{display:flex;gap:14px;flex-wrap:wrap;font-size:12px;margin-bottom:14px}.module-legend-item{display:flex;align-items:center;gap:6px}.module-legend-dot{width:10px;height:10px;border-radius:50%}.copy-toast{position:fixed;bottom:24px;right:24px;background:#102b35;border:1px solid #71e0ba;color:#71e0ba;padding:10px 18px;border-radius:8px;font-size:13.5px;font-weight:700;box-shadow:0 8px 24px rgba(0,0,0,.5);z-index:999999;opacity:0;transform:translateY(10px);transition:all .25s ease;pointer-events:none}.copy-toast.show{opacity:1;transform:translateY(0)}.pitfall-grid,.decision-grid{display:flex;flex-direction:column;gap:12px;margin:14px 0}.pitfall-card{background:#101a2b;border:1px solid #2a3a54;border-left:4px solid #f59e0b;border-radius:10px;padding:14px 16px}.pitfall-title{font-weight:700;color:#fbbf24;font-size:14.5px;margin-bottom:8px}.pitfall-field{margin:4px 0;font-size:13.5px}.decision-card{background:#101a2b;border:1px solid #2a3a54;border-left:4px solid #3b82f6;border-radius:10px;padding:14px 16px}.decision-title{font-weight:700;color:#60a5fa;font-size:14.5px;margin-bottom:8px}.arch-links-list{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0}.arch-link-badge{background:#16243b;border:1px solid #2a3a54;padding:6px 12px;border-radius:8px;font-size:12.5px;color:#8ed6ff;text-decoration:none;display:inline-flex;align-items:center;gap:6px;transition:all .2s}.arch-link-badge:hover{background:#1e3557;border-color:#3b82f6}.test-verdict-box{background:#101a2b;border:1px solid #2a3a54;border-radius:14px;padding:18px;margin-bottom:20px}.verdict-banner{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:12px 18px;border-radius:10px;margin-bottom:14px;font-weight:700;font-size:15px}.verdict-banner.green{background:#0d3326;color:#71e0ba;border:1px solid #176b55}.verdict-banner.red{background:#3d141a;color:#ff7b8c;border:1px solid #7c3540}.gates-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:12px 0}.gate-item{background:#090e17;border:1px solid #1c283d;border-radius:8px;padding:8px 12px;text-align:center}.gate-label{font-size:11px;color:#8093af;display:block;text-transform:uppercase}.gate-status{font-size:12.5px;font-weight:700}.testcases-table{width:100%;border-collapse:collapse;margin-top:12px;font-size:12.5px}.testcases-table th{background:#0b1320;color:#8ed6ff;padding:7px 10px;border-bottom:1px solid #2a3a54;font-size:11.5px}.testcases-table td{padding:6px 10px;border-bottom:1px solid #1c283d;vertical-align:middle}.checklist-grid{display:flex;flex-direction:column;gap:6px;margin:12px 0}.check-item{display:flex;align-items:flex-start;gap:10px;font-size:13.5px;background:#090e17;padding:8px 12px;border-radius:8px;border:1px solid #1c283d}.check-icon{font-weight:800;font-size:14px;width:20px;text-align:center;flex-shrink:0}.check-icon.done{color:#7ee787}.check-icon.partial{color:#e3b341}.check-icon.skip{color:#6e7681}.modal-overlay{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(8,14,26,.88);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);z-index:99999;align-items:center;justify-content:center;padding:20px;opacity:0;transition:opacity .25s ease}.modal-overlay.active{display:flex;opacity:1}.modal-container{position:relative;max-width:92vw;max-height:92vh;background:#172235;border:1px solid #314766;border-radius:16px;box-shadow:0 20px 50px rgba(0,0,0,.6);display:flex;flex-direction:column;overflow:hidden;width:100%}.modal-header{display:flex;justify-content:space-between;align-items:center;padding:14px 20px;background:#101a2b;border-bottom:1px solid #2a3a54}.modal-title{font-weight:700;color:#8ed6ff;font-size:16px}.modal-close{background:#20304a;border:1px solid #314766;color:#e9eef8;font-size:18px;width:34px;height:34px;border-radius:50%;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:background .2s}.modal-close:hover{background:#7c3540;color:#fff}.modal-body{padding:20px;overflow:auto;display:flex;align-items:center;justify-content:center;max-height:calc(92vh - 65px);background:#0b1320}.modal-body img{max-width:100%;max-height:82vh;object-fit:contain;border-radius:8px}.modal-body svg{width:100%!important;height:auto!important;max-height:82vh;background:#f8fafc;border-radius:8px;padding:12px}@media(max-width:800px){main{padding:12px 8px}.stats{grid-template-columns:repeat(2,1fr);padding:14px}.compare,.diagram-grid,.screens{grid-template-columns:1fr}nav{position:static}section,header,nav{padding:15px}}@media print{body{background:#fff;color:#172033}nav,.action-btn-group,.file-toolbar,.diff-badge{display:none!important}section,header,.stats{break-inside:avoid;box-shadow:none;border-color:#ccc;background:#fff;color:#000}h1,h2,h3{color:#000}.hero,.answer{background:#f0fdf4;border-color:#16a34a;color:#000}table,th,td{border-color:#ddd;color:#000}pre,code{background:#f8fafc;color:#000}.diff-viewer-wrapper{display:block!important}.file-diff-row{display:table-row!important}.diff-cell{display:table-cell!important}}'''


def _unconfirmed_block(model: dict) -> str:
    """Render unconfirmed business rules with all quarantine metrics."""
    task_id = str(model["task"]["id"])
    path = model["_root"] / ".doc" / "tasks" / task_id / "task.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    items = ((doc.get("business_logic") or {}).get("unconfirmed") or [])
    if not items:
        return ""
    rows = []
    for item in items:
        metrics = item.get("metrics") or {}
        checks = metrics.get("checks") or {}
        check_text = ", ".join(
            f"{name}: {'ok' if value else 'fail'}" for name, value in checks.items()
        ) or "нет данных"
        rows.append(
            "<tr>"
            f'<td><span class="badge partial">не подтверждено</span></td>'
            f'<td><b>{safe(item.get("title") or item.get("candidate_id") or "")}</b><br>'
            f'{safe(item.get("statement") or "")}</td>'
            f'<td><b>{safe(str(item.get("reason") or ""))}</b><br>'
            f'score {safe(str(metrics.get("score")))}<br>'
            f'<small>{safe(check_text)}</small></td>'
            f'<td>якорь: {safe(str(item.get("anchor_status") or "missing"))}<br>'
            f'тест: {safe(str(item.get("test_status") or "missing"))}<br>'
            f'след. проверка: {safe(str(metrics.get("next_check_at") or "не назначена"))}</td>'
            "</tr>"
        )
    return (
        '<div class="business-changes"><h3>Неподтвержденные правила</h3>'
        '<p><small>Эти правила не попали в подтвержденную бизнес-логику. '
        'Показаны метрики последней проверки и причина карантина.</small></p>'
        '<table><thead><tr><th>Статус</th><th>Правило</th>'
        '<th>Причина и метрики</th><th>Якорь и тест</th></tr></thead><tbody>'
        + "".join(rows) + '</tbody></table></div>'
    )


def _render(model: dict, offline: bool) -> str:
    """Render a compact presentation. The model remains the source of truth."""
    summary = model["summary"]
    before = safe(model["logic"]["before"]["text"])
    after = safe(model["logic"]["after"]["text"])
    delta = safe(model["logic"]["delta"]["text"])
    stages = "".join(
        f'<li><b>{safe(item["name"])}</b> <span class="badge {safe(item["status"])}">{safe(item["status"])}</span><br>{safe(item["summary"])}</li>'
        for item in model.get("stages", [])
    ) or "<li>Стадии не указаны</li>"
    diagrams = "".join(
        f'<article class="diagram"><h3>{safe(item["title"])}</h3><div class="mermaid">{safe(item["text"])}</div><small>{safe(item["source"])}</small></article>'
        for item in model["diagrams"]
    )
    business_changes = "".join(
        f'<article><h3>{safe(item["title"])}</h3><p>{safe(item["statement"])}</p><p><small>Код: {safe(", ".join(item.get("code", [])))} · Тесты: {safe(", ".join(item.get("tests", [])))}</small></p></article>'
        for item in model.get("business_changes", [])
    )
    business_changes_block = f'<div class="business-changes"><h3>Что меняется для бизнеса</h3>{business_changes}</div>' if business_changes else ""
    unconfirmed_block = _unconfirmed_block(model)
    changes = "".join(
        f'<article><h3>{safe(item["title"])}</h3><p><b>Было:</b> {safe(item["before"])}</p><p><b>Стало:</b> {safe(item["after"])}</p><p><b>Почему:</b> {safe(item["rationale"])}</p><small>{safe(item["source"])}</small></article>'
        for item in model["changes"]
    )
    questions = "".join(
        f'<details><summary>{safe(item["question"])}</summary><p>{safe(item["answer"])}</p><small>{safe(item["source"])}</small></details>'
        for item in model["teamlead_questions"]
    )
    out_dir = model["_output"] if hasattr(model["_output"], "is_dir") and model["_output"].is_dir() else (model["_output"].parent if hasattr(model["_output"], "parent") else Path(model["_output"]).parent)
    screenshots = "".join(
        f'<figure><img src="{safe(os.path.relpath(model["_root"] / item["path"], out_dir))}" alt="{safe(item["title"])}"><figcaption><b>{safe(item["title"])}</b><br>{safe(item["caption"])}</figcaption></figure>'
        for item in model.get("screenshots", [])
    ) or "<p>Скриншоты не прикреплены.</p>"

    # Module progress bar and counts
    module_counts = {}
    module_lines = {}
    for item in model["files"]:
        mod = item["module"]
        module_counts[mod] = module_counts.get(mod, 0) + 1
        lines_cnt = item["added"] + item["deleted"]
        module_lines[mod] = module_lines.get(mod, 0) + lines_cnt

    total_diff_lines = sum(module_lines.values()) or 1
    mod_colors = {
        "Backend": "#3b82f6",
        "Frontend": "#10b981",
        "Database": "#f59e0b",
        "Tests": "#a855f7",
        "Unmapped": "#64748b"
    }

    bar_segments = []
    legend_items = []
    for mod, cnt in sorted(module_counts.items()):
        color = mod_colors.get(mod, "#64748b")
        pct = round(module_lines.get(mod, 0) / total_diff_lines * 100, 1)
        bar_segments.append(f'<div class="module-bar-segment" style="width:{pct}%;background:{color}" title="{safe(mod)}: {pct}% ({module_lines.get(mod,0)} строк)"></div>')
        legend_items.append(f'<div class="module-legend-item"><span class="module-legend-dot" style="background:{color}"></span><b>{safe(mod)}:</b> {cnt} файлов ({pct}%)</div>')

    module_bar_html = f'<div class="module-bar">{"".join(bar_segments)}</div><div class="module-legend">{"".join(legend_items)}</div>' if len(module_counts) > 1 else ""

    filter_tab_btns = [f'<button class="filter-tab active" onclick="setModuleFilter(\'all\', this)">Все ({len(model["files"])})</button>']
    for mod, cnt in sorted(module_counts.items()):
        filter_tab_btns.append(f'<button class="filter-tab" data-module="{safe(mod)}" onclick="setModuleFilter(this.dataset.module, this)">{safe(mod)} ({cnt})</button>')

    file_rows_list = []
    for idx, item in enumerate(model["files"]):
        diff_html = render_file_diff(item)
        badge_text = f"{len(item['hunks'])} фрагм." if item.get("hunks") else "контекст"
        diff_row_id = f"diff-row-{idx}"
        file_cell = (
            f'<div class="file-summary" onclick="toggleFileDiff(\'{diff_row_id}\', this)" title="Показать / скрыть изменения файла">'
            f'<code class="file-path">{safe(item["path"])}</code>'
            f'<button class="copy-btn" data-path="{safe(item["path"])}" style="padding:2px 8px;font-size:11px;margin-left:6px" onclick="event.stopPropagation();copyText(this.dataset.path)" title="Скопировать путь">📋</button>'
            f'<span class="diff-badge">{badge_text} ▾</span>'
            f'</div>'
        )
        git_badge = f'<span class="git-add">+{item["added"]}</span> <span class="git-del">-{item["deleted"]}</span>'
        file_rows_list.append(
            f'<tr class="file-main-row" data-module="{safe(item["module"])}" data-diff-id="{diff_row_id}">'
            f'<td><b>{safe(item["module"])}</b></td>'
            f'<td>{file_cell}</td>'
            f'<td><span class="file-date">{safe(item.get("updated_at", "—"))}</span></td>'
            f'<td>{git_badge}</td>'
            f'<td>{safe(item["role"])}</td>'
            f'</tr>'
            f'<tr id="{diff_row_id}" class="file-diff-row" data-module="{safe(item["module"])}" style="display:none">'
            f'<td colspan="5" class="diff-cell">'
            f'<div class="diff-viewer-wrapper">{diff_html}</div>'
            f'</td>'
            f'</tr>'
        )
    file_rows = "".join(file_rows_list) or '<tr><td colspan="5">Файлы не найдены</td></tr>'

    meta = model.get("task_meta", {})
    jira_url = model.get("jira_url", "")
    jira_btn = f'<a href="{safe(jira_url)}" target="_blank" class="jira-link-btn" title="Открыть в Jira">🔗 Задача в Jira CT-{safe(model["task"]["id"])}</a>' if jira_url else ""
    print_btn = '<button class="print-btn" onclick="window.print()" title="Распечатать или сохранить как PDF">🖨️ Печать / PDF</button>'

    meta_items = []
    rel = model.get("git_release", {})
    if rel.get("is_merged"):
        rel_txt = f'✅ Влита в {safe(rel.get("target_release"))}'
        if rel.get("pr_num"):
            rel_txt += f' ({safe(rel.get("pr_num"))}'
            if rel.get("merge_date"):
                rel_txt += f', {safe(rel.get("merge_date"))}'
            rel_txt += ')'
        meta_items.append(f'<div class="meta-item"><span class="meta-label">🚀 Git Релиз</span><span class="meta-val release-merged">{rel_txt}</span></div>')
    else:
        meta_items.append('<div class="meta-item"><span class="meta-label">🚀 Git Релиз</span><span class="meta-val release-pending">⏳ Ветка разработки (ещё не в релизе)</span></div>')

    if meta.get("Created"):
        meta_items.append(f'<div class="meta-item"><span class="meta-label">📅 Создана</span><span class="meta-val">{safe(meta["Created"])}</span></div>')
    if meta.get("Updated"):
        meta_items.append(f'<div class="meta-item"><span class="meta-label">🔄 Обновлена</span><span class="meta-val">{safe(meta["Updated"])}</span></div>')
    if meta.get("Version"):
        meta_items.append(f'<div class="meta-item"><span class="meta-label">📦 Версия Jira</span><span class="meta-val">{safe(meta["Version"])}</span></div>')
    if meta.get("State"):
        meta_items.append(f'<div class="meta-item"><span class="meta-label">🚦 Статус Jira</span><span class="meta-val">{safe(meta["State"])}</span></div>')
    if meta.get("Priority"):
        meta_items.append(f'<div class="meta-item"><span class="meta-label">⚡ Приоритет</span><span class="meta-val">{safe(meta["Priority"])}</span></div>')
    if meta.get("Reporter"):
        meta_items.append(f'<div class="meta-item"><span class="meta-label">👤 Автор</span><span class="meta-val">{safe(meta["Reporter"])}</span></div>')
    if meta.get("Assignee"):
        meta_items.append(f'<div class="meta-item"><span class="meta-label">🛠️ Исполнитель</span><span class="meta-val">{safe(meta["Assignee"])}</span></div>')
    meta_grid = f'<div class="task-meta-grid">{"".join(meta_items)}</div>' if meta_items else ""

    # AC Matrix
    ac_rows = []
    for req in model.get("ac_matrix", []):
        status_cls = "covered" if req.get("status") == "covered" else "passed"
        ac_rows.append(
            f'<tr><td><b>{safe(req.get("id"))}</b></td><td>{safe(req.get("text"))}<br><small style="color:#8093af">{safe(req.get("test", ""))}</small></td><td><code>{safe(req.get("layer", "test"))}</code></td><td><span class="badge {status_cls}">{safe(req.get("status", "covered"))}</span></td></tr>'
        )
    ac_matrix_html = (
        f'<h3>Матрица критериев приёмки (Acceptance Criteria)</h3><table class="ac-table"><thead><tr><th>ID</th><th>Критерий / Тест</th><th>Слой</th><th>Статус</th></tr></thead><tbody>{"".join(ac_rows)}</tbody></table>'
        if ac_rows else ""
    )

    # Test artifacts from test-runs / verdict.json
    tdata = model.get("test_data", {})
    verdict = tdata.get("verdict")
    verdict_html = ""
    if verdict:
        is_green = verdict.get("green", False)
        banner_cls = "green" if is_green else "red"
        banner_text = f"✅ VERDICT: GREEN — Все автоматические проверки успешно пройдены" if is_green else f"❌ VERDICT: RED — Обнаружены ошибки или незакрытые проверки"
        run_name = verdict.get("run_id", "latest")

        tests_info = verdict.get("tests", {})
        total_cnt = tests_info.get("total", 0)
        passed_cnt = tests_info.get("passed", 0)
        failed_cnt = tests_info.get("failures", 0) + tests_info.get("errors", 0)

        cp = verdict.get("checkpoints", {})
        console_errs = len(cp.get("consoleErrors", []))

        artifacts = verdict.get("artifacts", {})
        gate_items = []
        for gname, gstat in artifacts.items():
            gcls = "passed" if gstat == "passed" else ("failed" if gstat == "failed" else "skipped")
            gate_items.append(
                f'<div class="gate-item"><span class="gate-label">{safe(gname)}</span><span class="gate-status badge {gcls}">{safe(gstat)}</span></div>'
            )
        gates_html = f'<div class="gates-grid">{"".join(gate_items)}</div>' if gate_items else ""

        testcase_rows = []
        for tc in tests_info.get("testcases", []):
            tc_status = tc.get("status", "passed")
            tc_cls = "passed" if tc_status == "passed" else "failed"
            tc_time = f"{float(tc.get('time', 0)):.2f}s" if tc.get("time") else "—"
            testcase_rows.append(
                f'<tr><td><code>{safe(tc.get("name", ""))}</code></td><td><span class="badge {tc_cls}">{safe(tc_status.upper())}</span></td><td style="color:#8093af">{tc_time}</td></tr>'
            )
        tc_table = (
            f'<details open><summary><b>Список тест-кейсов Codeception ({len(testcase_rows)})</b></summary>'
            f'<table class="testcases-table"><thead><tr><th>Тест-кейс</th><th>Статус</th><th>Время</th></tr></thead><tbody>{"".join(testcase_rows)}</tbody></table></details>'
            if testcase_rows else ""
        )

        verdict_html = (
            f'<div class="test-verdict-box">'
            f'<div class="verdict-banner {banner_cls}">'
            f'<span>{banner_text}</span>'
            f'<small style="font-size:12px;opacity:0.85">Прогон: {safe(run_name)}</small>'
            f'</div>'
            f'<div class="stats" style="margin:12px 0 16px;background:#090e17">'
            f'<b>{total_cnt}<small>всего тестов</small></b>'
            f'<b style="color:#7ee787">{passed_cnt}<small>успешно (passed)</small></b>'
            f'<b style="color:{"#f85149" if failed_cnt else "#7ee787"}">{failed_cnt}<small>ошибок / провалов</small></b>'
            f'<b>{console_errs}<small>JS-ошибок консоли</small></b>'
            f'</div>'
            f'<h4>Качественные ворота верификации (Quality Gates)</h4>'
            f'{gates_html}'
            f'{tc_table}'
            f'</div>'
        )

    test_files_html = ""
    if tdata.get("test_files"):
        tf_badges = "".join(f'<span class="badge" style="background:#1e293b;color:#a5d6ff;margin-right:6px">🧪 {safe(f)}</span>' for f in tdata["test_files"])
        test_files_html = f'<div style="margin:12px 0 16px"><b>Тестовые наборы задачи:</b> {tf_badges}</div>'

    branches_html = ""
    if tdata.get("logic_branches"):
        b_rows = []
        for b in tdata["logic_branches"]:
            b_status = b.get("Статус", "covered").lower()
            b_cls = "covered" if b_status == "covered" else ("partial" if b_status == "partial" else "blocked")
            b_rows.append(
                f'<tr><td><b>{safe(b.get("ID", ""))}</b></td><td>{safe(b.get("Ветка", ""))}</td><td><code>{safe(b.get("Слой", ""))}</code></td><td>{safe(b.get("Тест", ""))}</td><td>{safe(b.get("Ожидание", ""))}</td><td><span class="badge {b_cls}">{safe(b.get("Статус", ""))}</span></td></tr>'
            )
        branches_html = (
            f'<details open><summary><b>Ветки бизнес-логики и сценарии (из test.md)</b></summary>'
            f'<table class="test-branches-table"><thead><tr><th>ID</th><th>Ветка логики</th><th>Слой</th><th>Тест</th><th>Ожидание</th><th>Статус</th></tr></thead><tbody>{"".join(b_rows)}</tbody></table></details>'
        )

    checklist_html = ""
    if tdata.get("checklist"):
        c_items = []
        for ci in tdata["checklist"]:
            mark = ci.get("mark", " ")
            if mark == "x":
                icon = '<span class="check-icon done">✓</span>'
            elif mark == "~":
                icon = '<span class="check-icon partial">~</span>'
            elif mark == "-":
                icon = '<span class="check-icon skip">—</span>'
            else:
                icon = '<span class="check-icon">○</span>'
            c_items.append(f'<div class="check-item">{icon}<span>{safe(ci.get("text", ""))}</span></div>')
        checklist_html = f'<details open><summary><b>Чек-лист приёмочного тестирования</b></summary><div class="checklist-grid">{"".join(c_items)}</div></details>'

    restrictions_html = ""
    if tdata.get("restrictions"):
        restrictions_html = f'<div style="background:#1b1523;border-left:4px solid #d946ef;padding:12px;border-radius:6px;margin:12px 0"><b>Ограничения тестирования:</b><p style="margin:4px 0 0;font-size:13.5px;color:#f5d0fe">{safe(tdata["restrictions"])}</p></div>'

    tests_list = "".join(
        f'<li><b>{safe(item["name"])}</b> <span class="badge {safe(item["status"])}">{safe(item["status"])}</span> - {safe(item["description"])}</li>'
        for item in model.get("tests", [])
    )
    tests_summary_list = f'<h3>Результаты проверок модели</h3><ul>{tests_list}</ul>' if tests_list else ""

    # Doc data: Pitfalls & Decisions
    doc_data = model.get("doc_data", {})
    pitfalls_list = []
    for p in doc_data.get("pitfalls", []):
        f_symptom = f'<div class="pitfall-field"><b>Симптом:</b> {safe(p["symptom"])}</div>' if p.get("symptom") else ""
        f_reason = f'<div class="pitfall-field"><b>Причина:</b> {safe(p["reason"])}</div>' if p.get("reason") else ""
        f_solution = f'<div class="pitfall-field"><b>Решение:</b> {safe(p["solution"])}</div>' if p.get("solution") else ""
        f_files = f'<div class="pitfall-field"><small style="color:#8093af"><b>Файлы:</b> {safe(p["files"])}</small></div>' if p.get("files") else ""
        pitfalls_list.append(
            f'<div class="pitfall-card">'
            f'<div class="pitfall-title">⚠️ {safe(p["title"])}</div>'
            f'{f_symptom}{f_reason}{f_solution}{f_files}'
            f'</div>'
        )

    decisions_list = []
    for d in doc_data.get("decisions", []):
        f_ctx = f'<div class="pitfall-field"><b>Контекст:</b> {safe(d["context"])}</div>' if d.get("context") else ""
        f_app = f'<div class="pitfall-field"><b>Подход:</b> {safe(d["approach"])}</div>' if d.get("approach") else ""
        f_alt = f'<div class="pitfall-field"><small style="color:#94a3b8"><b>Альтернативы:</b> {safe(d["alternatives"])}</small></div>' if d.get("alternatives") else ""
        decisions_list.append(
            f'<div class="decision-card">'
            f'<div class="decision-title">🔀 {safe(d["title"])}</div>'
            f'{f_ctx}{f_app}{f_alt}'
            f'</div>'
        )

    arch_links_badges = []
    for al in doc_data.get("arch_links", []):
        arch_links_badges.append(
            f'<a href="{safe(al["url"])}" target="_blank" class="arch-link-badge">🗺️ {safe(al["title"])}</a>'
        )

    engineering_section = ""
    if pitfalls_list or decisions_list or arch_links_badges:
        arch_links_block = f'<div style="margin-bottom:14px"><b>Каноническая архитектура:</b><div class="arch-links-list">{"".join(arch_links_badges)}</div></div>' if arch_links_badges else ""
        pitfalls_block = f'<h3>Подводные камни и критические нюансы</h3><div class="pitfall-grid">{"".join(pitfalls_list)}</div>' if pitfalls_list else ""
        decisions_block = f'<h3>Принятые архитектурные решения</h3><div class="decision-grid">{"".join(decisions_list)}</div>' if decisions_list else ""
        engineering_section = (
            f'<section id="engineering"><h2>7. Подводные камни и архитектурные решения</h2>'
            f'{arch_links_block}{pitfalls_block}{decisions_block}'
            f'</section>'
        )

    comments_list = []
    for c in model.get("jira_comments", []):
        author = c.get("author", "Пользователь")
        parts = author.split()
        initials = safe("".join(p[0] for p in parts[:2]).upper() if parts else "J")
        changes_html = "".join(f'<span class="jira-change-tag">{safe(ch)}</span>' for ch in c.get("changes", []))
        changes_block = f'<div class="jira-changes">{changes_html}</div>' if changes_html else ""
        text_block = f'<div class="jira-post-text">{safe(c.get("text", ""))}</div>' if c.get("text") else ""
        comments_list.append(
            f'<div class="jira-post"><div class="jira-post-header"><div class="jira-avatar">{initials}</div><div class="jira-post-meta"><span class="jira-author">{safe(author)}</span><span class="jira-date">{safe(c.get("date", ""))}</span></div></div>{changes_block}{text_block}</div>'
        )
    comments_section = (
        f'<section id="comments"><h2>8. Диалог и переписка в Jira</h2><div class="jira-thread">{"".join(comments_list)}</div></section>'
        if comments_list else ""
    )

    task_full = f'<details><summary>Открыть полный task.md</summary><pre>{safe(model["task"].get("full_text", ""))}</pre></details>' if model["task"].get("full_text") else ""
    
    jira_reply_html = ""
    if model.get("jira_reply"):
        jira_reply_html = (
            f'<section id="jira">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">'
            f'<h2 style="margin:0">9. Готовый ответ для Jira</h2>'
            f'<button class="copy-btn" onclick="copyJiraReply()" title="Скопировать комментарий">📋 Скопировать ответ</button>'
            f'</div>'
            f'<div id="jira-reply-box" class="jira">{html.escape(model["jira_reply"], quote=True)}</div>'
            f'</section>'
        )

    cdn = "" if offline else '<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script><script src="https://cdn.jsdelivr.net/npm/@fancyapps/ui@5.0/dist/fancybox/fancybox.umd.js"></script><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@fancyapps/ui@5.0/dist/fancybox/fancybox.css"/>'

    return f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{safe(model["task"]["title"])}</title>{cdn}<style>{CSS}</style></head><body><main><header><div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:14px"><div><p class="eyebrow">TASK CHANGE PRESENTATION</p><h1>{safe(model["task"]["title"])}</h1><p class="lead">Задача <b>#{safe(model["task"]["id"])}</b>{(' · ' + safe(model["task"].get("stage", ""))) if model["task"].get("stage") else ""}</p></div><div class="action-btn-group">{print_btn}{jira_btn}</div></div>{meta_grid}<div class="hero"><strong>Коротко:</strong> {safe(summary["spoken_summary"])}</div></header><section class="stats"><b>{len(model["files"])}<small> файлов в scope</small></b><b>+{model["git"]["added"]}<small> строк добавлено</small></b><b>-{model["git"]["deleted"]}<small> строк удалено</small></b><b>{len(model.get("stages", []))}<small> стадий</small></b></section><nav><a href="#brief">Задача</a><a href="#delta">Было / стало</a><a href="#flow">Схема</a><a href="#screens">Скрины</a><a href="#files">Файлы и diff</a><a href="#tests">Проверки</a>{('<a href="#engineering">Архитектура</a>') if engineering_section else ''}{('<a href="#comments">Диалог Jira</a>') if comments_section else ''}{('<a href="#jira">Ответ Jira</a>') if jira_reply_html else ''}</nav><section id="brief"><h2>1. В чём была задача</h2><p>{safe(summary["problem"])}</p><p>{safe(summary["solution"])}</p><div class="answer"><b>Итог:</b> {safe(summary["result"])}</div><h3>Этапы</h3><ol class="stages">{stages}</ol>{task_full}</section><section id="delta"><h2>2. Выжимка: было → изменение → стало → почему</h2><div class="compare"><article><h3>Было</h3><p>{before}</p></article><article><h3>Стало</h3><p>{after}</p></article><article><h3>Почему</h3><p>{delta}</p></article></div>{business_changes_block}{unconfirmed_block}<div class="changes">{changes}</div></section><section id="flow"><h2>3. Как работает логика</h2><div class="diagram-grid">{diagrams}</div><h3>Вопросы и ответы</h3>{questions}</section><section id="screens"><h2>4. Скриншоты и доказательства</h2><div class="screens">{screenshots}</div></section><section id="files"><h2>5. Полный scope файлов</h2>{module_bar_html}<div class="file-toolbar"><input type="text" id="file-search-input" class="file-search-input" placeholder="🔍 Быстрый поиск файла, пути или роли..." oninput="filterFiles()"><div class="module-filter-tabs">{"".join(filter_tab_btns)}<button class="filter-tab" onclick="toggleAllDiffs(this)" title="Раскрыть или свернуть все изменения файлов">Развернуть все diff</button></div><div id="file-count-badge" class="file-count-badge">Показано: {len(model["files"])} из {len(model["files"])} файлов</div></div><table><thead><tr><th>Модуль</th><th>Файл</th><th>Изменён</th><th>Git</th><th>Роль в системе</th></tr></thead><tbody id="files-table-body">{file_rows}</tbody></table></section><section id="tests"><h2>6. Проверки, автотесты и приёмка</h2>{verdict_html}{test_files_html}{ac_matrix_html}{branches_html}{checklist_html}{restrictions_html}{tests_summary_list}</section>{engineering_section}{comments_section}{jira_reply_html}<section id="risks"><h2>10. Ограничения и риски</h2><ul>{''.join(f'<li>{safe(item["text"])}</li>' for item in model["risks"])}</ul></section><footer>Branch: {safe(model["git"]["branch"])} | Commit: {safe(model["git"]["commit"])} | Generated: {safe(model["freshness"]["generated_at"])}</footer></main><div id="image-modal" class="modal-overlay" onclick="closeModal(event)"><div class="modal-container" onclick="event.stopPropagation()"><div class="modal-header"><span class="modal-title" id="modal-title">Просмотр элемента</span><button class="modal-close" onclick="closeModal()" title="Закрыть (Esc)">✕</button></div><div class="modal-body" id="modal-body"></div></div></div><div id="copy-toast" class="copy-toast">✅ Скопировано в буфер обмена!</div><script>function openModal(title,contentHtml){{const modal=document.getElementById('image-modal');document.getElementById('modal-title').textContent=title||'Просмотр элемента';document.getElementById('modal-body').innerHTML=contentHtml;modal.classList.add('active');document.body.style.overflow='hidden'}}function closeModal(e){{const modal=document.getElementById('image-modal');modal.classList.remove('active');document.body.style.overflow=''}}document.addEventListener('keydown',function(e){{if(e.key==='Escape')closeModal()}});function showToast(msg){{const t=document.getElementById('copy-toast');if(!t)return;t.textContent=msg;t.classList.add('show');setTimeout(()=>t.classList.remove('show'),2200)}}function copyText(str,msg){{navigator.clipboard.writeText(str).then(()=>showToast(msg||'✅ Скопировано!')).catch(()=>{{const ta=document.createElement('textarea');ta.value=str;document.body.appendChild(ta);ta.select();document.execCommand('copy');document.body.removeChild(ta);showToast(msg||'✅ Скопировано!')}})}}function copyJiraReply(){{const el=document.getElementById('jira-reply-box');if(!el)return;copyText(el.innerText||el.textContent,'✅ Ответ для Jira скопирован!')}}let currentModuleFilter='all';function setModuleFilter(mod,btn){{currentModuleFilter=mod;document.querySelectorAll('.filter-tab').forEach(b=>b.classList.remove('active'));btn.classList.add('active');filterFiles()}}function toggleFileDiff(diffId,triggerEl){{const diffRow=document.getElementById(diffId);if(!diffRow)return;const isHidden=(diffRow.style.display==='none');if(isHidden){{diffRow.style.display='';diffRow.classList.add('open');}}else{{diffRow.style.display='none';diffRow.classList.remove('open');}}const badge=triggerEl&&triggerEl.querySelector?triggerEl.querySelector('.diff-badge'):null;if(badge){{badge.classList.toggle('active',isHidden);badge.textContent=badge.textContent.replace(isHidden?'▾':'▴',isHidden?'▴':'▾');}}}}let allDiffsExpanded=false;function toggleAllDiffs(btn){{allDiffsExpanded=!allDiffsExpanded;const mainRows=document.querySelectorAll('#files-table-body tr.file-main-row');mainRows.forEach(row=>{{if(row.style.display==='none')return;const diffId=row.getAttribute('data-diff-id');const diffRow=document.getElementById(diffId);const badge=row.querySelector('.diff-badge');if(diffRow){{diffRow.style.display=allDiffsExpanded?'':'none';diffRow.classList.toggle('open',allDiffsExpanded);}}if(badge){{badge.classList.toggle('active',allDiffsExpanded);badge.textContent=badge.textContent.replace(allDiffsExpanded?'▾':'▴',allDiffsExpanded?'▴':'▾');}}}});if(btn)btn.textContent=allDiffsExpanded?'Свернуть все diff':'Развернуть все diff';}}function filterFiles(){{const query=(document.getElementById('file-search-input').value||'').toLowerCase().trim();const mainRows=document.querySelectorAll('#files-table-body tr.file-main-row');let visible=0;mainRows.forEach(row=>{{const mod=row.getAttribute('data-module')||'';const diffId=row.getAttribute('data-diff-id')||'';const diffRow=document.getElementById(diffId);const text=row.innerText.toLowerCase();const matchMod=(currentModuleFilter==='all'||mod===currentModuleFilter);const matchQuery=(!query||text.includes(query));if(matchMod&&matchQuery){{row.style.display='';visible++;if(diffRow&&diffRow.classList.contains('open')){{diffRow.style.display='';}}}}else{{row.style.display='none';if(diffRow){{diffRow.style.display='none';}}}}}});const badge=document.getElementById('file-count-badge');if(badge)badge.textContent=`Показано: ${{visible}} из ${{mainRows.length}} файлов`;}}function initLightbox(){{document.querySelectorAll('.screens figure').forEach(fig=>{{const img=fig.querySelector('img');const cap=fig.querySelector('figcaption');if(img){{img.addEventListener('click',()=>{{const title=cap?cap.innerText.split('\\n')[0]:'Скриншот';openModal(title,`<img src="${{img.src}}" alt="${{title}}">`)}})}}}});document.querySelectorAll('.diagram, article.diagram').forEach(diag=>{{const header=diag.querySelector('h3');const title=header?header.textContent:'Схема процесса';diag.addEventListener('click',(e)=>{{if(e.target.tagName==='A'||e.target.tagName==='SMALL')return;const mermaidDiv=diag.querySelector('.mermaid')||diag;openModal(title,mermaidDiv.innerHTML)}})}})}}window.addEventListener('DOMContentLoaded',function(){{document.querySelectorAll('.mermaid').forEach(function(el){{el.textContent=el.textContent.trim();}});if(window.mermaid){{mermaid.initialize({{startOnLoad:false,securityLevel:'loose',theme:'default'}});const mEls=document.querySelectorAll('.mermaid');let done=0;if(mEls.length===0){{initLightbox();return;}}mEls.forEach(function(el,idx){{const code=el.textContent;const cid='mermaid-svg-'+idx;mermaid.render(cid,code).then(function(res){{el.innerHTML=res.svg;done++;if(done>=mEls.length){{setTimeout(initLightbox,200);}}}}).catch(function(err){{console.error('Mermaid render error for diagram '+idx,err);const esc=code.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');el.innerHTML='<div style="background:#2a1215;border:1px solid #7c3540;color:#ffb3ba;padding:12px;border-radius:8px;font-size:13px"><b>⚠️ Ошибка рендеринга диаграммы:</b> '+(err&&err.message?err.message:'Синтаксическая ошибка')+'<details style="margin-top:8px"><summary style="cursor:pointer;color:#8ed6ff">Показать исходный код</summary><pre style="margin-top:6px;background:#0f172a;color:#cbd5e1;padding:8px;border-radius:4px;font-size:12px;overflow:auto">'+esc+'</pre></details></div>';done++;if(done>=mEls.length){{setTimeout(initLightbox,200);}}}});}});}}else{{initLightbox();}}}});</script></body></html>'''


def render(model: dict, offline: bool) -> str:
    document = _render(model, offline)
    # Lightbox attributes are DOM data, never interpolated into HTML strings.
    document = document.replace('openModal(title,`<img src="${img.src}" alt="${title}">`)',
                                "openModal(title,'');document.getElementById('modal-body').appendChild(img.cloneNode())")
    return document.replace("securityLevel:'loose'", "securityLevel:'strict'")


def checked_path(root: Path, value: str, must_exist: bool = True) -> Path:
    path = Path(value)
    resolved = (root / path).resolve()
    if path.is_absolute() or not resolved.is_relative_to(root) or "\\" in value:
        raise ValueError(f"Path must remain inside project: {value}")
    if must_exist and not resolved.is_file():
        raise ValueError(f"Required input does not exist: {value}")
    return resolved


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    started = time.perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--output")
    parser.add_argument("--model", help="Agent-written report-model.json (required unless already present)")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--context", help="Validated workflow-context.json; all paths inside project")
    parser.add_argument("--force", action="store_true", help="Allow replacing existing outputs; caller owns user consent")
    parser.add_argument("--if-missing", action="store_true", help="Skip existing HTML without validating freshness (unless --force)")
    parser.add_argument("--open", action="store_true", help="Open successfully generated or reused HTML in the default browser")
    args = parser.parse_args()
    root = Path(args.project_root).resolve()
    if not re.fullmatch(r"[0-9]+", args.task):
        parser.error("--task must contain digits only")
    task = root / ".doc" / "tasks" / args.task
    out = Path(args.output).resolve() if args.output else task / "reports" / "change-report"
    report_file = out / "report.html"
    if args.if_missing and report_file.exists() and not args.force:
        # --if-missing must mean "reuse only a report that is still current".
        # Before this check any leftover HTML short-circuited generation and a
        # stale report was returned as if it were fresh. Verification is cheap
        # here, so a mismatch falls through to a normal rebuild instead of
        # failing, which is what a caller passing --if-missing expects.
        manifest_file = out / "report-manifest.json"
        reason = "manifest_absent"
        reusable = False
        if manifest_file.is_file():
            try:
                old = json.loads(manifest_file.read_text(encoding="utf-8"))
                outputs = old.pop("output_hashes", {})
                verified = bool(outputs) and all(
                    (out / name).is_file() and digest(out / name) == value
                    for name, value in outputs.items()
                )
                reusable = verified
                reason = "fresh" if verified else "output_changed"
            except (OSError, json.JSONDecodeError, ValueError):
                reason = "manifest_unreadable"

        if reusable:
            print(json.dumps({"status": "skipped", "reason": reason, "path": str(report_file),
                              "freshness_checked": True,
                              "metrics": {"elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}}))
            return 0
        # --if-missing means "do not overwrite an existing report". A stale
        # report is still an existing report, so the documented contract is to
        # stop here and report it as skipped, not to rebuild behind the
        # caller's back. Rebuilding is what --force is for.
        print(json.dumps({"status": "skipped", "reason": reason, "path": str(report_file),
                          "freshness_checked": True, "stale": True,
                          "hint": "pass --force to rebuild a stale report",
                          "metrics": {"elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}}))
        return 0

    try:
        return generate(args, root, task, out, started)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({"status": "blocked", "errors": [clean(str(exc))],
                          "metrics": {"elapsed_ms": round((time.perf_counter() - started) * 1000, 3)}}))
        return 2


def generate(args, root: Path, task: Path, out: Path, started: float) -> int:

    import jsonschema
    schema_path = Path(__file__).resolve().parent.parent / "assets" / "report-model.schema.json"
    model_path = Path(args.model).resolve() if args.model else out / "report-model.json"
    if not model_path.is_file():
        raise ValueError(f"No report model at {model_path}; renderer never invents explanations")
    model = json.loads(model_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(model, json.loads(schema_path.read_text(encoding="utf-8")))
    except jsonschema.ValidationError as exc:
        raise ValueError(f"Invalid report model at {list(exc.path)}: {exc.message}") from exc
    if model["task"]["id"] != str(args.task):
        raise ValueError("Task ID in report model does not match --task")
    for item in model.get("diagrams", []):
        validate_mermaid_diagram(item.get("title", "Untitled"), item.get("text", ""))

    inputs = {model_path, schema_path, Path(__file__).resolve()}
    context = None
    selected = None
    if args.context:
        from workflow_contract import preflight
        context_path = Path(args.context).resolve()
        if not context_path.is_relative_to(root):
            raise ValueError("Context must remain inside project")
        context = json.loads(context_path.read_text(encoding="utf-8"))
        result = preflight(context, root)
        if result["status"] not in ("ready", "complete"):
            raise ValueError(f"Workflow context blocked: {result['errors']}")
        if context["task_id"] != args.task or "html" not in context["allowed_steps"]:
            raise ValueError("Context task mismatch or html step not allowed")
        inputs.update((context_path, Path(__file__).with_name("workflow_contract.py")))
        selected = {}
        for source in context["sources"]:
            path = checked_path(root, source["path"])
            selected.setdefault(source["role"], []).append(path)
            inputs.add(path)
        for role in ("task", "diff", "diff_files", "doc", "plan", "test", "ac", "verdict"):
            if len(selected.get(role, [])) > 1:
                raise ValueError(f"Ambiguous source role: {role}")
        if not selected.get("task") or not selected.get("diff"):
            raise ValueError("Context requires explicit task and diff source roles")
        if context["scope"]["kind"] == "stage":
            if model["task"].get("stage") != context["scope"]["id"]:
                raise ValueError("Stage model must match context scope.id")
            if not context["scope"]["files"] or not any(selected.get(r) for r in ("test", "verdict", "test_file")):
                raise ValueError("Stage requires explicit files and test sources, including not-run evidence")
            for role in ("diff", "diff_files", "test", "ac", "verdict", "test_file"):
                for path in selected.get(role, []):
                    relative = path.relative_to(task) if path.is_relative_to(task) else None
                    if relative and (len(relative.parts) == 1 or relative.parts[0] in ("tests", "test-runs")):
                        raise ValueError("Stage cannot use whole-task root diff/test artifacts")
        if "jira" in context["allowed_steps"]:
            if not context.get("jira"):
                raise ValueError("Allowed Jira step requires validated structured Jira input")
            if model.get("jira") and model["jira"] != context["jira"]:
                raise ValueError("Model Jira differs from context")
            model["jira"] = context["jira"]
        elif model.get("jira") or model.get("jira_reply") or context.get("jira"):
            raise ValueError("Jira output is not allowed by context")
    elif model["task"].get("stage"):
        raise ValueError("Stage report requires --context with explicit scope")

    candidates = ["task.md", "diff.files.md", "diff.md", "doc.md", "plan.md", "test.md"]
    role_names = {"task": "task.md", "diff": "diff.md", "diff_files": "diff.files.md", "doc": "doc.md", "plan": "plan.md", "test": "test.md"}
    source_files = ({name: selected[role][0] for role, name in role_names.items() if selected.get(role)}
                    if selected is not None else {name: task / name for name in candidates if (task / name).is_file()})
    inputs.update(source_files.values())
    sources = {name: path.read_text(encoding="utf-8") for name, path in source_files.items()}
    if not sources.get("task.md") or "diff.md" not in sources:
        raise ValueError("Nonempty task.md and explicit task-owned diff.md are required")
    model["task"]["full_text"] = sources["task.md"]
    task_info = parse_task_md(sources.get("task.md", ""))
    ac_file = selected.get("ac", [None])[0] if selected is not None else task / "ac-matrix.json"
    ac_matrix = []
    if ac_file is not None and ac_file.is_file():
        inputs.add(ac_file)
        ac_matrix = json.loads(ac_file.read_text(encoding="utf-8")).get("requirements", [])

    test_data = parse_test_data(task, selected)
    if selected is None:
        inputs.update(p for folder in (task / "tests", task / "test-runs") if folder.is_dir()
                      for p in folder.rglob("*") if p.is_file())
    doc_data = parse_doc_md(task, source_files["doc.md"]) if "doc.md" in source_files else {}
    release_info = get_git_release_info(root, args.task)

    diff = sources["diff.md"]
    source_paths = extract_paths(sources.get("diff.files.md", ""), root)
    diff_files, added, deleted = parse_diff(diff)
    for path in source_paths:
        diff_files.setdefault(path, {"added": 0, "deleted": 0, "hunks": []})
    if context:
        scoped = set(context["scope"]["files"])
        if set(diff_files) - scoped:
            raise ValueError("Scoped diff contains files outside context scope.files")
        for path in scoped:
            diff_files.setdefault(path, {"added": 0, "deleted": 0, "hunks": []})
    roles = dict(model.get("file_roles", {}))
    roles.update({item["path"]: item["role"] for item in model.get("files", [])})
    if any(not roles.get(path, "").strip() for path in diff_files):
        raise ValueError("Every scoped file requires an explicit model role")

    branch = git(root, ["branch", "--show-current"]).strip() or "unavailable"
    files = []
    for path, metrics in sorted(diff_files.items()):
        file_path = checked_path(root, path, must_exist=False)
        body = read(file_path)
        if file_path.is_file():
            inputs.add(file_path)
        updated_at = get_file_timestamp(root, path, branch_hint=f"origin/bugfixes/#{args.task}" if "bugfix" in branch else f"origin/features/#{args.task}")
        files.append({
            "path": path,
            "module": module_name(path),
            "role": get_file_role(path, metrics, model),
            "updated_at": updated_at,
            "exists": file_path.is_file(),
            "added": metrics["added"],
            "deleted": metrics["deleted"],
            "hunks": metrics["hunks"],
            "sha256": digest(file_path) if file_path.is_file() else "",
        })

    modules = sorted({item["module"] for item in files})
    tests = model.get("tests", [])
    git_head = git(root, ["rev-parse", "HEAD"]).strip() or "unavailable"
    evidence_refs = [*model["evidence"], *(test["result_file"] for test in tests if test.get("result_file"))]
    evidence_refs += [item["source"] for section in ("changes", "diagrams", "teamlead_questions", "timeline", "stages") for item in model.get(section, [])]
    evidence_refs += [item["source"] for item in model["logic"].values()]
    for evidence in evidence_refs:
        source = re.sub(r":\d+(?:-\d+)?$", "", evidence)
        try:
            inputs.add(checked_path(root, source))
        except ValueError as exc:
            raise ValueError(
                f"{exc} (model field evidence/source: {evidence!r}; "
                "each source must be one existing relative path)") from exc
    if model.get("jira"):
        from workflow_contract import SCHEMA
        contract_schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(model["jira"], {"$defs": contract_schema["$defs"], **contract_schema["properties"]["jira"]})
        except jsonschema.ValidationError as exc:
            raise ValueError("Invalid structured Jira input") from exc
        inputs.add(SCHEMA)
        for reference in [model["jira"]["release_source"], *model["jira"]["evidence"]]:
            inputs.add(checked_path(root, reference))
        for shot in model["jira"]["shots"]:
            inputs.add(checked_path(root, shot["path"]))
            if shot not in model.setdefault("screenshots", []):
                model["screenshots"].append(shot)
        text = model["jira"]["text"]
        if model.get("jira_reply") and model["jira_reply"] != text:
            raise ValueError("jira_reply differs from structured Jira text")
        model["jira_reply"] = text
    for shot in model.get("screenshots", []):
        inputs.add(checked_path(root, shot["path"]))
    for url in [task_info["jira_url"], *(link["url"] for link in doc_data.get("arch_links", []))]:
        if url and (urlsplit(url).scheme not in ("", "http", "https") or url.startswith("//")):
            raise ValueError("Unsafe link scheme in source")

    data = {
        **model,
        "git": {"branch": branch, "commit": git_head, "added": added, "deleted": deleted},
        "git_release": release_info,
        "files": files,
        "modules": modules,
        "task_meta": task_info["meta"],
        "jira_url": task_info["jira_url"],
        "jira_comments": task_info["comments"],
        "ac_matrix": ac_matrix,
        "test_data": test_data,
        "doc_data": doc_data,
        "scope": context["scope"] if context else {"kind": "task", "id": args.task, "files": list(diff_files)},
        "warnings": [name for name in ("task.md", "diff.files.md", "diff.md") if name not in sources],
        "freshness": {
            "source_hashes": {name: hashlib.sha256(value.encode()).hexdigest() for name, value in sources.items()},
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    }

    html_doc = render({**data, "_root": root, "_output": out}, args.offline)
    manifest = {
        "version": 1,
        "model_sha256": digest(model_path),
        "git_head": git_head,
        "branch": branch,
        "offline": args.offline,
        "input_hashes": {str(p): digest(p) for p in sorted(inputs)},
        "missing_scoped_files": sorted(item["path"] for item in files if not item["exists"]),
    }
    report_file = out / "report.html"
    manifest_file = out / "report-manifest.json"
    metrics = {"files": len(files), "tests": len(tests), "screenshots": len(model.get("screenshots", [])),
               "inputs": len(inputs), "input_bytes": sum(p.stat().st_size for p in inputs)}
    status = "generated"
    if report_file.exists() and not args.force and not args.if_missing:
        old = json.loads(manifest_file.read_text(encoding="utf-8")) if manifest_file.is_file() else {}
        outputs = old.pop("output_hashes", {})
        if old != manifest or not outputs or any(not (out / name).is_file() or digest(out / name) != value for name, value in outputs.items()):
            raise ValueError("Existing HTML is stale or unverified; only --force permits overwrite")
        status = "reused"
    else:
        payloads = {"report-data.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n", "report.html": html_doc}
        manifest["output_hashes"] = {name: hashlib.sha256(text.encode()).hexdigest() for name, text in payloads.items()}
        payloads["report-manifest.json"] = json.dumps(manifest, indent=2) + "\n"
        # All validation/rendering precedes mkdir. Exclusive lock serializes renderer writers.
        out.mkdir(parents=True, exist_ok=True)
        lock = out / ".report.lock"
        with lock.open("x"):
            try:
                if report_file.exists() and not args.force and not args.if_missing:
                    raise ValueError("HTML appeared during generation; refusing overwrite")
                if any((out / name).is_symlink() for name in payloads):
                    raise ValueError("Output symlinks are not permitted")
                for name, text in payloads.items():
                    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=out, delete=False) as handle:
                        temporary = Path(handle.name)
                        handle.write(text)
                    try:
                        os.replace(temporary, out / name)
                    finally:
                        temporary.unlink(missing_ok=True)
            finally:
                lock.unlink(missing_ok=True)
    metrics["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 3)
    print(json.dumps({"status": status, "path": str(report_file), "metrics": metrics}))
    if args.open:
        webbrowser.open(report_file.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
