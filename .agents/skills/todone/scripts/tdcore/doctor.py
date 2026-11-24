"""Диагностика: находки, готовые действия, слияние кодов типов, линт прозы."""

import os
import re

from . import schema
from .digest import stale_issues
from .errors import HINTS, Issue, merge_hints
from .validate import Validator

#: Невидимые вставки: человек их не видит, модель читает.
HIDDEN_PATTERNS = (
    (re.compile(r"<!--"), "скрытый HTML-комментарий"),
    (re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]"), "символ нулевой ширины"),
    # Настоящие HTML/XML-вставки в заголовках; заполнители вроде `<root>`
    # и `<id>` — обычная документационная проза и не являются атакой.
    (re.compile(r"^#{1,6}\s.*</?(?:script|style|iframe|object|embed|meta|link|form|input|img)\b[^>]*>", re.I | re.M),
     "посторонняя HTML/XML-вставка в заголовке"),
)
PROSE_SUFFIXES = (".md",)


class Doctor:
    """Сбор находок по очереди, записям, типам и прозе поставки."""

    def __init__(self, queue=None, type_index=None, prose_roots=None,
                 hints=None):
        self.queue = queue
        self.types = type_index
        self.prose_roots = [p for p in (prose_roots or []) if p]
        self.hints = merge_hints(hints or (type_index.codes() if type_index else {}))
        self.validator = Validator(type_index)

    # --- обход ---
    def run(self, strict=False, prose=True):
        issues = []
        if self.queue is not None:
            issues.extend(self.queue.sync_issues())
            for record in self.queue.records:
                issues.extend(self.validator.record(record, strict=strict))
                issues.extend(self._record_files(record))
        if self.types is not None:
            issues.extend(self.types.validate_all())
        if prose:
            issues.extend(self.prose_issues())
        issues.extend(self.coverage_issues())
        return issues

    def _record_files(self, record):
        """Факты о файлах записи: артефакты на месте, JSON цел."""
        issues = []
        if record.folder and not os.path.isfile(record.path or ""):
            issues.append(Issue("error", str(record.id),
                                "папка записи есть, а файла task.json нет",
                                "RECORD_UNLISTED"))
        stale_issues(record, issues)
        return issues

    # --- линт прозы ---
    def prose_issues(self, roots=None):
        issues = []
        for root in (roots or self.prose_roots):
            for path in _walk(root):
                try:
                    with open(path, "r", encoding="utf-8") as handle:
                        lines = handle.read().split("\n")
                except (OSError, UnicodeDecodeError):
                    continue
                for number, line in enumerate(lines, start=1):
                    # Owned Mermaid provenance wrappers are deliberate source
                    # metadata, not an invisible prompt/content injection.
                    if re.search(r"<!--\s*AUTODOC:(?:BEGIN|END)\s+diagram=", line, re.I):
                        continue
                    for pattern, what in HIDDEN_PATTERNS:
                        if pattern.search(line):
                            issues.append(Issue(
                                "error", "%s:%d" % (_short(path), number),
                                "в прозе найдена невидимая вставка: %s" % what,
                                "PROSE_HIDDEN_TEXT"))
        return issues

    # --- покрытие кодов ---
    def coverage_issues(self):
        """У каждого кода обязано быть готовое действие."""
        issues = []
        declared = set()
        if self.types is not None:
            declared = set(self.types.codes())
        for code in sorted(declared):
            if code not in self.hints:
                issues.append(Issue("error", "коды типов",
                                    "у кода «%s» нет готового действия" % code,
                                    "CHECK_CONTRACT"))
        return issues

    # --- сводка ---
    def summary(self, issues):
        errors = [i for i in issues if i.level == "error"]
        warnings = [i for i in issues if i.level == "warning"]
        return {"errors": len(errors), "warnings": len(warnings),
                "codes": sorted({i.code for i in issues}),
                "records": len(self.queue.records) if self.queue else 0}

    def next_actions(self, issues):
        """Что делать дальше: по одному действию на код, в порядке тяжести."""
        seen = []
        for issue in sorted(issues, key=lambda i: (i.level != "error", i.code)):
            action = issue.command or issue.hint
            if action and action not in seen:
                seen.append(action)
        return seen


def _walk(root):
    excluded = {"__pycache__", ".git", ".hg", ".svn", "node_modules", "vendor", ".cache", "build",
                "docs_html", "site", "dist", "out", "coverage"}
    for folder, names, files in os.walk(root):
        parts = set(os.path.normpath(folder).split(os.sep))
        if parts & excluded:
            names[:] = []
            continue
        names[:] = [name for name in names if name not in excluded]
        for name in sorted(files):
            if name.endswith(PROSE_SUFFIXES):
                yield os.path.join(folder, name)


def _short(path):
    parts = path.split(os.sep)
    return os.sep.join(parts[-3:]) if len(parts) > 3 else path


def hints_count():
    """Сколько кодов с готовым действием знает диагностика."""
    return len(HINTS)


def settings_issues(settings):
    """Настройка очереди: ключи из объявленного набора, значения — числа."""
    issues = []
    for key, value in (settings or {}).items():
        if key not in schema.SETTINGS_KEYS:
            issues.append(Issue("error", "settings.%s" % key,
                                "ключа нет в настройке очереди", "KEY_UNKNOWN"))
        elif not isinstance(value, int) or value < 0:
            issues.append(Issue("error", "settings.%s" % key,
                                "порог — целое неотрицательное число", "KEY_UNKNOWN"))
    return issues
