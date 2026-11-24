#!/usr/bin/env python3
"""Minimal Jira task.md exporter (fallback when php/docker unavailable)."""
import base64
import json
import os
import re
import sys
import urllib.error
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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def download_attachment(cfg, content_url, dest):
    """Jira answers 303 to a signed media URL; auth must not follow it."""
    auth = base64.b64encode(f"{cfg['JIRA_EMAIL']}:{cfg['JIRA_API_TOKEN']}".encode()).decode()
    opener = urllib.request.build_opener(_NoRedirect)
    req = urllib.request.Request(
        content_url,
        headers={"User-Agent": "jira-task-export/1.0", "Authorization": f"Basic {auth}"},
    )
    try:
        resp = opener.open(req, timeout=120)
        body = resp.read()
        resp.close()
    except urllib.error.HTTPError as err:
        location = err.headers.get("Location") if err.headers else None
        err.close()
        if err.code not in (301, 302, 303, 307, 308) or not location:
            raise RuntimeError(f"HTTP {err.code}")
        with urllib.request.urlopen(location, timeout=120) as media:
            body = media.read()
    if not body:
        raise RuntimeError("empty response")
    dest.write_bytes(body)
    return len(body)


def safe_filename(filename, att_id, with_id=False):
    name = os.path.basename(str(filename or "").replace("\\", "/"))
    name = re.sub(r"[^\w.-]+", "-", name, flags=re.UNICODE)
    name = re.sub(r"-+\.", ".", name).strip("-._")
    if not name:
        name = f"attachment-{att_id}"
    if with_id:
        stem, ext = os.path.splitext(name)
        name = f"{stem}-{att_id}{ext}"
    return name


def download_attachments(cfg, fields, task_dir):
    items = fields.get("attachment") or []
    if not items:
        return []
    target_dir = Path(task_dir) / "attachments"
    target_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for item in items:
        if not isinstance(item, dict):
            continue
        att_id = str(item.get("id") or "")
        filename = str(item.get("filename") or "")
        size = int(item.get("size") or 0)
        content = str(item.get("content") or "")
        record = {
            "id": att_id,
            "filename": filename,
            "size": size,
            "path": "",
            "status": "failed",
        }
        if not att_id or not content:
            records.append(record)
            continue
        if size > 50 * 1024 * 1024:
            record["status"] = "too_large"
            records.append(record)
            continue
        name = safe_filename(filename, att_id)
        target = target_dir / name
        if target.is_file() and (size == 0 or target.stat().st_size == size):
            record["path"] = f"attachments/{name}"
            record["status"] = "existing"
            records.append(record)
            continue
        if target.is_file():
            name = safe_filename(filename, att_id, True)
            target = target_dir / name
        try:
            download_attachment(cfg, content, target)
            record["path"] = f"attachments/{name}"
            record["status"] = "downloaded"
        except Exception as exc:  # noqa: BLE001 - export must not fail on one file
            print(f"attachment failed: {filename}: {exc}", file=sys.stderr)
        records.append(record)
    return records


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


def build_markdown(issue, comments, histories, browse_url, attachments=None):
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
    attachment_lines = []
    for item in attachments or []:
        path = item.get("path") or ""
        if path:
            label = item.get("filename") or os.path.basename(path)
            attachment_lines.append(f"- [{label}]({path})")
    if attachment_lines:
        lines += ["", "## Attachments", ""] + attachment_lines
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
    out = REPO / ".doc" / "tasks" / issue_id / "task.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    attachments = download_attachments(cfg, issue.get("fields") or {}, out.parent)
    md = build_markdown(issue, comments, histories, browse, attachments)
    out.write_text(md, encoding="utf-8")
    print(f"Saved: {out}")
    print(f"Key: {issue_key}")
    print(f"Title: {(issue.get('fields') or {}).get('summary', '')}")
    print(f"Comments: {len(comments)}")
    print(f"Changes: {len(histories)}")
    print(f"Attachments: {len(attachments)}")


if __name__ == "__main__":
    main()
