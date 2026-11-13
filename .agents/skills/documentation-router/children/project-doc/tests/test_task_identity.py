import importlib.util
import json
import pathlib
import tempfile
import unittest


SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "task-identity.py"
spec = importlib.util.spec_from_file_location("task_identity", SCRIPT)
identity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(identity)


class TaskIdentityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.task = pathlib.Path(self.temp.name) / "2070"
        self.task.mkdir()
        self.heading = "# Issue #2070: Новый заказ удаления ОИС\n"
        self.data = {
            "id": "task:2070",
            "metadata": {"task_id": "2070", "title": "Новый заказ удаления ОИС"},
            "tracker": {"issue_key": "CT-2070", "snapshot": {
                "issue_key": "CT-2070", "summary": "Новый заказ удаления ОИС"}},
            "git": {"branch": "bugfixes/#2070_for5606"},
        }

    def run_check(self):
        (self.task / "task.md").write_text(self.heading, encoding="utf-8")
        (self.task / "task.json").write_text(json.dumps(self.data), encoding="utf-8")
        return identity.check(self.task)

    def test_valid_and_stale_metadata_title(self):
        self.data["metadata"]["title"] = "Другая старая тема"
        result = self.run_check()
        self.assertTrue(result["ok"])
        self.assertEqual(result["status"], "ok")
        self.assertTrue(any("metadata.title" in warning for warning in result["warnings"]))

    def test_structural_mismatches(self):
        cases = [("id", "task:2071"), ("task_id", "2071"),
                 ("issue_key", "CT-2071"), ("snapshot_issue_key", "CT-2071"),
                 ("task_md_id", "2071")]
        for name, value in cases:
            with self.subTest(name=name):
                original = json.loads(json.dumps(self.data))
                if name == "id":
                    self.data["id"] = value
                elif name == "task_id":
                    self.data["metadata"]["task_id"] = value
                elif name == "issue_key":
                    self.data["tracker"]["issue_key"] = value
                elif name == "snapshot_issue_key":
                    self.data["tracker"]["snapshot"]["issue_key"] = value
                else:
                    self.heading = "# Issue #2071: Новый заказ удаления ОИС\n"
                result = self.run_check()
                self.assertEqual(result["status"], "mismatch")
                self.assertFalse(next(c for c in result["checks"] if c["check"] == name)["ok"])
                self.data = original
                self.heading = "# Issue #2070: Новый заказ удаления ОИС\n"

    def test_missing_sources_are_not_confirmed(self):
        for field in ("id", "task_id", "issue_key", "snapshot_issue_key", "summary"):
            with self.subTest(field=field):
                original = json.loads(json.dumps(self.data))
                if field == "id":
                    del self.data["id"]
                elif field == "task_id":
                    del self.data["metadata"]["task_id"]
                elif field == "issue_key":
                    del self.data["tracker"]["issue_key"]
                else:
                    del self.data["tracker"]["snapshot"]["issue_key" if field == "snapshot_issue_key" else field]
                result = self.run_check()
                self.assertFalse(result["ok"])
                self.assertEqual(result["status"], "incomplete")
                self.data = original
        self.heading = "## Description\n"
        self.assertEqual(self.run_check()["status"], "incomplete")
        (self.task / "task.json").unlink()
        self.assertEqual(identity.check(self.task)["status"], "incomplete")

    def test_snapshot_title_mismatch_blocks(self):
        self.data["tracker"]["snapshot"]["summary"] = "Совершенно другая тема"
        self.assertEqual(self.run_check()["status"], "mismatch")

    def test_branch_number_boundaries(self):
        for branch, expected in [("features/#2070", True), ("bugfixes/#2070_for_5.6.0.6", True),
                                 ("features/#12070", False), ("features/#20701", False),
                                 ("release/20701_207", False)]:
            with self.subTest(branch=branch):
                self.data["git"]["branch"] = branch
                self.assertEqual(self.run_check()["ok"], expected)

    def test_metadata_branch_is_checked(self):
        self.data["metadata"]["branch"] = "features/#20701"
        self.assertEqual(self.run_check()["status"], "mismatch")
        self.data["metadata"]["branch"] = "features/#2070"
        self.assertEqual(self.run_check()["status"], "ok")

    def test_invalid_json_does_not_crash(self):
        (self.task / "task.md").write_text(self.heading, encoding="utf-8")
        for value in ("{", "[]", "null"):
            with self.subTest(value=value):
                (self.task / "task.json").write_text(value, encoding="utf-8")
                self.assertFalse(identity.check(self.task)["ok"])


if __name__ == "__main__":
    unittest.main()
