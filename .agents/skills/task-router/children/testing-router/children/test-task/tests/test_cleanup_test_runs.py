#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "cleanup-test-runs.py"
NOW = "2026-11-11"


def make_run(root: Path, task: str, name: str, files: dict[str, str]) -> Path:
    run = root / ".doc" / "tasks" / task / "test-runs" / name
    run.mkdir(parents=True)
    for filename, text in files.items():
        (run / filename).write_text(text, encoding="utf-8")
    return run


def call(root: Path, *args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--now", NOW, "--json", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / ".agents").mkdir()
        old_report = make_run(root, "100", "old-report", {
            "report.md": "---\ntype: qa-test-run\nrun: 2026-01-05_101010_task-100\n---\n",
        })
        old_verdict = make_run(root, "100", "old-verdict", {
            "verdict.json": '{"created_at": "2026-01-06T10:00:00Z"}',
        })
        old_name = make_run(root, "100", "2026-01-07_manual", {"note.txt": "no date"})
        new_report = make_run(root, "100", "new-report", {
            "report.md": "Дата: 2026-11-10 UTC\n",
        })
        undated = make_run(root, "100", "undated", {"note.txt": "no date"})
        other_task = make_run(root, "101", "2026-11-10_task-101", {
            "report.md": "Дата: 2026-11-10 UTC\n",
        })
        loose = root / ".doc" / "tasks" / "100" / "test-runs" / "2026-01-09_loose.md"
        loose.write_text("Дата: 2026-01-09 UTC\n", encoding="utf-8")
        reports = root / ".doc" / "tasks" / "100" / "reports" / "change-report"
        reports.mkdir(parents=True)
        (reports / "report-model.json").write_text(
            json.dumps({"sources": [".doc/tasks/100/test-runs/old-report/report.md"]}),
            encoding="utf-8",
        )

        dry = call(root, "--days", "14")
        assert dry["dry_run"] is True
        assert len(dry["candidates"]) == 2, dry["candidates"]
        assert {item["path"] for item in dry["candidates"]} == {
            str(old_verdict), str(old_name),
        }
        assert [item["path"] for item in dry["protected"]] == [str(old_report)]
        assert old_report.exists() and old_verdict.exists() and old_name.exists()
        assert any(item["path"] == str(undated) for item in dry["undated"])

        applied = call(root, "--days", "14", "--apply")
        assert applied["removed"] == 2, applied
        assert not old_verdict.exists() and not old_name.exists()
        assert old_report.exists()
        assert new_report.exists() and undated.exists() and other_task.exists()

        unprotected = call(root, "--days", "14", "--ignore-reports", "--apply")
        assert unprotected["removed"] == 1, unprotected
        assert not old_report.exists()

        make_run(root, "101", "2026-01-08_task-101", {"report.md": "Дата: 2026-01-08 UTC\n"})
        scoped = call(root, "--days", "14", "--task", "101", "--apply")
        assert scoped["removed"] == 1, scoped
        assert not (root / ".doc" / "tasks" / "101" / "test-runs" / "2026-01-08_task-101").exists()
        assert other_task.exists()

        with_files = call(root, "--days", "14", "--include-files", "--apply")
        assert with_files["removed"] == 1, with_files
        assert not loose.exists()

    print("cleanup-test-runs tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
