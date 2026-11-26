"""Mode rules for kit export: install, update and mirror.

The three modes share one plan/approve/apply pipeline and differ only in how
proposals are resolved:

- `install` copies the kit into a project without a harness. An existing file is
  never overwritten; target-only files are untouched.
- `update` refreshes kit files over an installed harness and keeps local files
  that are not part of the kit.
- `mirror` (clean install) makes managed kit directories an exact copy of the
  source: kit files absent from the source are deleted after a backup.
"""
from __future__ import annotations

from dataclasses import dataclass, field

MODES = ("install", "update", "mirror")
KEEP = "keep"
TAKE_INCOMING = "take_incoming"
DELETE = "delete"


@dataclass
class ModeReport:
    mode: str
    notes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)


def absence(plan: dict) -> list[str]:
    """Target files with no source counterpart: candidates for mirror deletion."""
    return sorted(row["path"] for row in plan.get("files", [])
                  if isinstance(row, dict) and row.get("target") is not None
                  and row.get("incoming") is None)


def resolve(plan: dict, mode: str, decisions: dict | None = None) -> tuple[dict, ModeReport]:
    """Return the decisions to approve and the mode report."""
    if mode not in MODES:
        raise ValueError(f"unknown mode: {mode}")
    resolved = dict(decisions or {})
    report = ModeReport(mode=mode)
    rows = [row for row in plan.get("files", []) if isinstance(row, dict)]

    if mode == "install":
        for row in rows:
            path = row["path"]
            if row.get("target") is None:
                continue
            if row.get("incoming") is not None and row["target"] == row["incoming"]:
                resolved[path] = TAKE_INCOMING
            else:
                resolved[path] = KEEP
                if row.get("incoming") is not None:
                    report.warnings.append(f"existing file kept as local: {path}")
        report.notes.append("install does not overwrite existing files")
        return resolved, report

    if mode == "update":
        for row in rows:
            path = row["path"]
            if row.get("target") is not None and row.get("incoming") is None:
                resolved.setdefault(path, KEEP)
                continue
            if row.get("proposal", {}).get("requires_review"):
                resolved.setdefault(path, TAKE_INCOMING)
        report.notes.append("update takes kit files and keeps files absent from the kit")
        return resolved, report

    for path in absence(plan):
        resolved[path] = DELETE
    report.deletes = absence(plan)
    report.notes.append("mirror deletes kit files absent from the source")
    return resolved, report
