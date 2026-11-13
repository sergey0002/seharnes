"""J11 compatibility: legacy-v1 golden scoring, PS1 smoke, cwd independence."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

import support
from jsondoc import search

CLI = support.SCRIPTS_DIR / "jsondoc.py"
PS1 = support.SCRIPTS_DIR.parents[5] / ".agents" / "skills" / "documentation-router" / "children" / "doc-verify" / "scripts" / "find-related-tasks.ps1"
PWSH = ("/snap/bin/pwsh", "/usr/bin/pwsh", "pwsh")


def legacy_fixture(root):
    docs = root / ".doc"
    arch = docs / "architecture"
    arch.mkdir(parents=True, exist_ok=True)
    (arch / "orders.md").write_text(
        "# Orders\n\nФайлы: `lib/A.php`. Ссылка: [2612](../tasks/2612/)\n",
        encoding="utf-8")
    (docs / "tasks" / "_map").mkdir(parents=True, exist_ok=True)
    (docs / "tasks" / "_map" / "file-to-tasks.tsv").write_text(
        "lib/A.php\t2070,2612\t2070:t|2612:t\n"
        "lib/B.php\t2354\t2354:t\n", encoding="utf-8")
    def task(n, doc_body="", diff_files="", plan_link=False):
        base = docs / "tasks" / n
        base.mkdir(parents=True, exist_ok=True)
        (base / "task.md").write_text(f"# Issue #{n}: t", encoding="utf-8")
        if doc_body or diff_files:
            body = doc_body + "\n"
            if diff_files:
                body += f"`{diff_files}`\n"
            (base / "doc.md").write_text(body, encoding="utf-8")
        if diff_files:
            (base / "diff.files.md").write_text(
                "## All files\n" + diff_files + "\n", encoding="utf-8")
        if plan_link:
            (base / "plan.md").write_text("orders.md context\n",
                                          encoding="utf-8")
    task("2070", doc_body="`lib/A.php` role", diff_files="lib/A.php")
    task("2612", doc_body="orders.md baseline", diff_files="lib/A.php")
    task("2354", doc_body="", diff_files="lib/B.php")
    task("1800")
    return docs


class LegacyScoringTests(unittest.TestCase):
    def test_it01_golden_weights(self):
        root, _docs = support.make_docs()
        docs = legacy_fixture(root)
        result = search.related(docs, "legacy-v1", arch="orders")
        hits = {h["id"]: h for h in result["data"]}
        # 2612: tsv 40 + arch link (doc.md mentions orders.md) 50 + overlap
        # (doc.md has lib/A.php backtick + diff.files.md line) min(30,6*2)=12
        # + already in arch 10 => 112
        self.assertEqual(hits["2612"]["score"], 40 + 50 + 12 + 10)
        # 2070: tsv 40 + overlap 3 (doc.md two backticks + diff.files line)
        # = 40 + 18 = 58, no link, no already
        self.assertEqual(hits["2070"]["score"], 40 + 18)
        # 2354: not a candidate (no tsv match in arch, no link/mention/already)
        self.assertNotIn("2354", hits)
        self.assertNotIn("1800", hits)
        self.assertTrue(hits["2612"]["alreadyInArch"])
        self.assertFalse(hits["2070"]["alreadyInArch"])

    def test_sort_and_default_limit(self):
        root, _docs = support.make_docs()
        docs = legacy_fixture(root)
        result = search.related(docs, "legacy-v1", arch="orders")
        ids = [h["id"] for h in result["data"]]
        self.assertEqual(ids, ["2612", "2070"])
        self.assertLessEqual(len(ids), 8)

    def test_cardinalities(self):
        root, _docs = support.make_docs()
        docs = legacy_fixture(root)
        (docs / "architecture" / "emptydoc.md").write_text("# e\n",
                                                           encoding="utf-8")
        empty = search.related(docs, "legacy-v1", arch="emptydoc")
        self.assertEqual(empty["exit"], 0)
        self.assertEqual(empty["data"], [])
        missing = search.related(docs, "legacy-v1", arch="nope")
        self.assertEqual(missing["exit"], 1)


class PowershellSmokeTests(unittest.TestCase):
    def _pwsh(self):
        for candidate in PWSH:
            proc = subprocess.run(["which", candidate], capture_output=True)
            if proc.returncode == 0:
                return candidate
        return None

    def test_it01_ps1_script_runs_on_fixture(self):
        binary = self._pwsh()
        if binary is None:
            self.skipTest("pwsh unavailable: recorded not_run, not passed")
        root, _docs = support.make_docs()
        docs = legacy_fixture(root)
        proc = subprocess.run(
            [binary, "-NoProfile", "-NonInteractive",
             str(PS1.resolve()), "-Doc", "orders.md", "-Json"],
            cwd=str(root), capture_output=True, text=True, timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        # ConvertTo-Json does not guarantee an array envelope for 0/1 items
        if isinstance(payload, dict):
            payload = [payload]
        self.assertIsInstance(payload, list)
        self.assertGreaterEqual(len(payload), 1)
        top = payload[0]
        self.assertIn("id", top)


class CwdIndependenceTests(unittest.TestCase):
    def test_it14_same_result_from_any_cwd(self):
        root, _docs = support.make_docs()
        docs = legacy_fixture(root)
        doc = support.minimal_task("2612", "Архивация")
        support.write_canonical(docs / "tasks" / "2612" / "task.json", doc)
        outputs = []
        for cwd in (root, root / ".doc", support.SCRIPTS_DIR):
            proc = subprocess.run(
                [sys.executable, str(CLI), "--root", str(root),
                 "search", "--kind", "task", "--text", "архивация"],
                cwd=str(cwd), capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outputs.append(proc.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertEqual(outputs[1], outputs[2])


if __name__ == "__main__":
    unittest.main()
