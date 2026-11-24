"""Выгрузка большого чтения: производный markdown-файл в папке записи.

Источник правды — запись. Файл — кэш для чтения: пересоздаётся той же командой,
устаревает при любой правке записи, читается частями.
"""

import os

from . import schema
from .errors import Issue
from .record import now_stamp
from .store import modified_at

DIGEST_FILENAME = "digest.md"
PARTS = ("body", "toc", "comments")


def build(record, settings=None):
    """Собрать текст выгрузки: весь таск, вся лента дословно, оглавление реплик."""
    settings = settings or schema.DEFAULT_SETTINGS
    sizes = record.sizes()
    lines = [
        "# Выгрузка записи %s — %s" % (record.id, record.title),
        "",
        "Файл производный: источник правды `task.json`, пересоздаётся командой "
        "`ttask digest %s`." % record.id,
        "Собрано: %s. Размеры: тело %d зн. / %d Б, лента %d зн. / %d Б, реплик %d."
        % (now_stamp(), sizes["body_chars"], sizes["body_bytes"],
           sizes["comments_chars"], sizes["comments_bytes"],
           sizes["comments_count"]),
        "",
        "## Оглавление",
        "",
        "- [Тело записи](#тело-записи) — %d зн." % sizes["body_chars"],
        "- [Оглавление ленты](#оглавление-ленты) — %d реплик"
        % sizes["comments_count"],
        "- [Лента дословно](#лента-дословно) — %d зн." % sizes["comments_chars"],
        "",
        "## Части выгрузки",
        "",
        "Читать частями: `ttask digest %s --part body|toc|comments[:N-M]`."
        % record.id,
        "Навигация по записи: `ttask show %s/C-N` — одна реплика, "
        "`ttask show %s/AC-N` — один элемент, `ttask show %s` — тело, "
        "`ttask show %s --mode comments` — лента дословно, "
        "`ttask tree %s` — дерево детей." % ((record.id,) * 5),
        "",
        "## Тело записи",
        "",
        "```json",
        record.body_text(),
        "```",
        "",
        "## Оглавление ленты",
        "",
    ]
    for item in record.comments:
        lines.append("- [%s](#%s) %s" % (item.get("id"),
                                         str(item.get("id")).lower(),
                                         record.toc_line(item)))
    lines += ["", "## Лента дословно", ""]
    for item in record.comments:
        lines += ["### %s" % item.get("id"),
                  "Время %s, автор %s, род %s." % (item.get("at"),
                                                   item.get("by"),
                                                   item.get("kind")),
                  "", str(item.get("text")), ""]
    return "\n".join(lines).rstrip() + "\n"


def write(record, settings=None):
    """Записать выгрузку в папку записи и объявить её производным артефактом."""
    text = build(record, settings)
    path = os.path.join(record.folder, DIGEST_FILENAME)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)
    for art in record.artifacts:
        if isinstance(art, dict) and art.get("path") == DIGEST_FILENAME:
            art.update({"kind": "digest", "derived": True,
                        "note": "выгрузка тела и ленты для чтения"})
            break
    else:
        record.artifacts.append({"kind": "digest", "derived": True,
                                 "path": DIGEST_FILENAME,
                                 "note": "выгрузка тела и ленты для чтения"})
    return path, text


def part(record, name, settings=None):
    """Часть выгрузки: тело, оглавление ленты или лента по диапазону реплик."""
    text = build(record, settings)
    if name in ("body", "toc", "comments"):
        heading = {"body": "## Тело записи", "toc": "## Оглавление ленты",
                   "comments": "## Лента дословно"}[name]
        return _slice(text, heading)
    if name.startswith("comments:"):
        span = name.split(":", 1)[1]
        start, _, end = span.partition("-")
        picked = []
        for item in record.comments:
            number = int(str(item.get("id", "C-0")).split("-", 1)[-1] or 0)
            if int(start or 1) <= number <= int(end or start or 10 ** 9):
                picked.append(item)
        return "\n\n".join("%s %s %s %s\n%s" % (i.get("id"), i.get("at"),
                                                i.get("by"), i.get("kind"),
                                                i.get("text")) for i in picked)
    return text


def _slice(text, heading):
    if heading not in text:
        return text
    tail = text.split(heading, 1)[1]
    for marker in ("\n## ",):
        if marker in tail:
            tail = tail.split(marker, 1)[0]
    return (heading + tail).strip() + "\n"


def stale_issues(record, issues=None):
    """Выгрузка устарела, если запись правили после неё."""
    issues = issues if issues is not None else []
    path = os.path.join(record.folder or "", DIGEST_FILENAME)
    if not record.folder or not os.path.isfile(path):
        return issues
    if not any(isinstance(a, dict) and a.get("path") == DIGEST_FILENAME
               for a in record.artifacts):
        issues.append(Issue("warning", "%s.artifacts" % record.id,
                            "файл выгрузки есть, а производным артефактом не объявлен",
                            "DIGEST_STALE"))
    digest_at = modified_at(path)
    record_at = modified_at(record.path)
    if digest_at and record_at and record_at > digest_at:
        issues.append(Issue("error", "%s.digest" % record.id,
                            "выгрузка устарела: запись правили после неё",
                            "DIGEST_STALE"))
    return issues


class Digest:
    """Производная выгрузка для полного чтения: источник правды — task.json."""

    def __init__(self, record, settings=None):
        self.record = record
        self.settings = settings or schema.DEFAULT_SETTINGS

    def build(self):
        return build(self.record, self.settings)

    def write(self):
        return write(self.record, self.settings)

    def part(self, name):
        return part(self.record, name, self.settings)

    def stale(self, issues=None):
        return stale_issues(self.record, issues)
