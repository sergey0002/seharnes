#!/usr/bin/env python3
"""Minimal Jira task.md exporter (fallback when php/docker unavailable)."""
import base64
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
CONFIG = Path(os.environ.get("JIRA_CONFIG_FILE", BASE / "config.env"))
REPO = BASE.parents[5]
CHANGE_LABELS = {
    "assignee": "Assignee",
    "status": "State",
    "priority": "Priority",
    "issuetype": "Kind",
    "summary": "Title",
    "Fix Version": "Version",
    "fixVersions": "Version",
    "components": "Component",
    "description": "Description",
}


def load_config():
    cfg = {}
    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        cfg[k] = v
    return cfg


def jira_request(cfg, path):
    auth = base64.b64encode(f"{cfg['JIRA_EMAIL']}:{cfg['JIRA_API_TOKEN']}".encode()).decode()
    url = cfg["JIRA_BASE_URL"].rstrip("/") + path
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "jira-task-export/1.0", "Authorization": f"Basic {auth}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def paginate_comments(cfg, issue_key):
    items = []
    start = 0
    while True:
        q = urllib.parse.urlencode({"startAt": start, "maxResults": 100})
        data = jira_request(cfg, f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}/comment?{q}")
        batch = data.get("comments") or []
        items.extend(batch)
        total = int(data.get("total") or len(items))
        if not batch or len(items) >= total:
            break
        start += len(batch)
    return items


def adf_text(node):
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if not isinstance(node, dict):
        return ""
    t = node.get("type", "")
    content = node.get("content") or []
    if t == "text":
        text = node.get("text", "")
        marks = node.get("marks") or []
        for m in marks:
            if m.get("type") == "link":
                href = (m.get("attrs") or {}).get("href", "")
                if href:
                    return f"<{href}>" if href == text else f"[{text}]({href})"
            if m.get("type") == "code":
                return f"`{text}`"
            if m.get("type") == "strong":
                return f"**{text}**"
        return text
    if t == "hardBreak":
        return "\n"
    if t == "mention":
        return (node.get("attrs") or {}).get("text", "@mention")
    if t == "inlineCard":
        return (node.get("attrs") or {}).get("url", "")
    if t == "emoji":
        return (node.get("attrs") or {}).get("shortName", "")
    if t == "rule":
        return "---"
    if t == "codeBlock":
        return "```\n" + "".join(adf_text(c) for c in content) + "\n```"
    if t == "heading":
        level = max(1, min(6, int((node.get("attrs") or {}).get("level", 3))))
        return "#" * level + " " + "".join(adf_text(c) for c in content)
    if t in ("paragraph", "listItem", "blockquote", "tableCell", "tableHeader"):
        return "".join(adf_text(c) for c in content)
    if t == "bulletList":
        return "\n".join("- " + adf_text(c).strip() for c in content)
    if t == "orderedList":
        return "\n".join(f"{i}. {adf_text(c).strip()}" for i, c in enumerate(content, 1))
    if t == "doc":
        return "\n\n".join(adf_text(c) for c in content)
    return "".join(adf_text(c) for c in content)


def fmt_date(iso):
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%d.%m.%Y %H:%M UTC")
    except ValueError:
        return iso


def person_name(p):
    if not isinstance(p, dict):
        return "Unknown"
    return p.get("displayName") or p.get("name") or "Unknown"


def field_name(fields, key):
    v = fields.get(key)
    return v.get("name", "") if isinstance(v, dict) else ""


def named_list(items):
    if not isinstance(items, list):
        return ""
    return ", ".join(i.get("name", "") for i in items if isinstance(i, dict) and i.get("name"))


def format_changes(changes):
    if not changes:
        return ""
    parts = []
    for field, delta in changes.items():
        old = delta.get("old", "")
        new = delta.get("new", "")
        if not old and not new:
            continue
        label = CHANGE_LABELS.get(field, field.replace("_", " ").title())
        parts.append(f"{label}: `{old}` → `{new}`")
    return "*Changed:* " + ", ".join(parts) if parts else ""


def history_to_changes(items):
    if not items:
        return None
    changes = {}
    for item in items:
        if not isinstance(item, dict) or "field" not in item:
            continue
        changes[item["field"]] = {
            "old": item.get("fromString") or "",
            "new": item.get("toString") or "",
        }
    return changes or None


def build_markdown(issue, comments, histories, browse_url):
    fields = issue.get("fields") or {}
    issue_num = issue.get("key", "").split("-")[-1]
    title = fields.get("summary", "Untitled")
    lines = [f"# Issue #{issue_num}: {title}", ""]
    if browse_url:
        lines += [f"**Jira:** <{browse_url}>", ""]
    lines += ["| Field | Value |", "| --- | --- |"]
    for label, val in [
        ("State", field_name(fields, "status")),
        ("Kind", field_name(fields, "issuetype")),
        ("Priority", field_name(fields, "priority")),
        ("Reporter", person_name(fields.get("reporter"))),
        ("Assignee", person_name(fields.get("assignee"))),
        ("Created", fmt_date(fields.get("created"))),
        ("Updated", fmt_date(fields.get("updated"))),
        ("Version", named_list(fields.get("fixVersions"))),
        ("Component", named_list(fields.get("components"))),
    ]:
        if val:
            lines.append(f"| {label} | {str(val).replace('|', '\\|')} |")
    desc = adf_text(fields.get("description")).strip()
    if desc:
        lines += ["", "## Description", "", desc]
    entries = []
    for c in comments:
        entries.append(
            {
                "created": c.get("created", ""),
                "author": person_name(c.get("author")),
                "body": adf_text(c.get("body")),
                "changes": None,
            }
        )
    for h in histories:
        entries.append(
            {
                "created": h.get("created", ""),
                "author": person_name(h.get("author")),
                "body": "",
                "changes": history_to_changes(h.get("items")),
            }
        )
    entries.sort(key=lambda e: e["created"])
    entries = [e for e in entries if e["body"].strip() or format_changes(e["changes"])]
    if entries:
        lines += ["", "## Comments", ""]
        for i, e in enumerate(entries):
            if i:
                lines += ["---", ""]
            lines.append(f"**{e['author']}** · {fmt_date(e['created'])}")
            lines.append("")
            ch = format_changes(e["changes"])
            if ch:
                lines += [ch, ""]
            body = e["body"].strip()
            if body:
                lines += [body, ""]
    return "\n".join(lines).rstrip() + "\n"


def main():
    issue_id = re.sub(r"\D", "", sys.argv[1] if len(sys.argv) > 1 else "")
    if not issue_id:
        print("Usage: export_task.py <issue_number>", file=sys.stderr)
        sys.exit(1)
    cfg = load_config()
    project = cfg["JIRA_PROJECT_KEY"].upper()
    issue_key = f"{project}-{issue_id}"
    issue = jira_request(cfg, f"/rest/api/3/issue/{urllib.parse.quote(issue_key)}?expand=changelog")
    comments = paginate_comments(cfg, issue_key)
    histories = (issue.get("changelog") or {}).get("histories") or []
    browse = f"{cfg['JIRA_BASE_URL'].rstrip('/')}/browse/{issue_key}"
    md = build_markdown(issue, comments, histories, browse)
    out = REPO / ".doc" / "tasks" / issue_id / "task.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"Saved: {out}")
    print(f"Key: {issue_key}")
    print(f"Title: {(issue.get('fields') or {}).get('summary', '')}")
    print(f"Comments: {len(comments)}")
    print(f"Changes: {len(histories)}")


if __name__ == "__main__":
    main()
