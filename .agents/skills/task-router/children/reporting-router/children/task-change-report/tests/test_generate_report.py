import hashlib
import html
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/generate_report.py"
sys.path.insert(0, str(SCRIPT.parent))
from generate_report import validate_mermaid_diagram


class RendererTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.task = self.root / ".doc/tasks/42"
        self.task.mkdir(parents=True)
        self.output = self.task / "reports/change-report"
        self.put("lib/file.php", "new\n")
        self.put(".doc/tasks/42/task.md", "# Example\nVersion 1.2\n")
        self.diff = "diff --git a/lib/file.php b/lib/file.php\n--- a/lib/file.php\n+++ b/lib/file.php\n@@ -1 +1 @@\n-old\n+new\n"
        self.put(".doc/tasks/42/diff.md", self.diff)
        self.evidence = ".doc/tasks/42/task.md"
        self.model = {
            "schema_version": "2.0", "task": {"id": "42", "title": "Example"},
            "summary": dict.fromkeys(("spoken_summary", "problem", "solution", "result"), "Explanation"),
            "logic": {key: {"text": key, "source": self.evidence} for key in ("before", "after", "delta")},
            "changes": [{"title": "Fix", "before": "old", "after": "new", "rationale": "reason", "source": self.evidence}],
            "diagrams": [{"title": name, "text": "flowchart LR\nA-->B", "source": self.evidence} for name in ("Before", "After")],
            "tests": [], "teamlead_questions": [], "timeline": [], "risks": [],
            "evidence": [self.evidence], "file_roles": {"lib/file.php": "Explicit role"}}
        self.model_path = self.root / "model.json"
        self.save_model()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)

    def put(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return target

    def save_model(self):
        self.model_path.write_text(json.dumps(self.model), encoding="utf-8")

    def run_cli(self, *flags, expected=0):
        result = subprocess.run([sys.executable, str(SCRIPT), "--task", "42", "--project-root", str(self.root),
                                 "--model", str(self.model_path), "--offline", *flags], capture_output=True, text=True)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def context(self, stage=False, allowed=None):
        roles = [(self.evidence, "task"), (".doc/tasks/42/diff.md", "diff")]
        if stage:
            self.put(".doc/tasks/42/stage2/diff.md", self.diff)
            self.put(".doc/tasks/42/stage2/test.md", "- [ ] Not run\n")
            roles[1] = (".doc/tasks/42/stage2/diff.md", "diff")
            roles.append((".doc/tasks/42/stage2/test.md", "test"))
            self.model["task"]["stage"] = "stage2"
            self.save_model()
        data = {"version": 1, "task_id": "42", "scope": {"kind": "stage" if stage else "task", "id": "stage2" if stage else "42", "files": ["lib/file.php"], "commits": []},
                "allowed_steps": allowed if allowed is not None else ["html"], "refresh_authorized": False,
                "sources": [{"path": path, "role": role, "sha256": hashlib.sha256((self.root / path).read_bytes()).hexdigest()} for path, role in roles],
                "facts": [{"id": "F1", "text": "Evidence", "evidence": [self.evidence]}], "steps": {}}
        self.put("context.json", json.dumps(data))
        return data

    def test_unconfirmed_rules_rendered_with_metrics(self):
        self.put(".doc/tasks/42/task.json", json.dumps({
            "business_logic": {
                "facts": [], "linked_rule_ids": [],
                "unconfirmed": [{
                    "id": "BQ-42-01",
                    "candidate_id": "RC-42-01",
                    "title": "Лимит субъектов",
                    "statement": "В форму можно добавить не более 12 субъектов.",
                    "reason": "no_anchor",
                    "anchor_status": "missing",
                    "test_status": "planned",
                    "metrics": {
                        "result": "quarantined",
                        "score": 0.65,
                        "checks": {"quote_exists": True,
                                   "code_anchor_exists": False},
                        "next_check_at": "2026-11-01T00:00:00Z",
                    },
                }],
            }
        }, ensure_ascii=False))
        payload = self.run_cli()
        self.assertEqual(payload["status"], "generated")
        html_text = (self.output / "report.html").read_text(encoding="utf-8")
        self.assertIn("Неподтвержденные правила", html_text)
        self.assertIn("не подтверждено", html_text)
        self.assertIn("no_anchor", html_text)
        self.assertIn("0.65", html_text)
        self.assertIn("quote_exists: ok", html_text)

    def test_happy_reuse_and_stale(self):
        self.assertEqual(self.run_cli()["status"], "generated")
        before = (self.output / "report.html").read_bytes()
        self.assertEqual(self.run_cli()["status"], "reused")
        self.put("lib/file.php", "changed again")
        self.run_cli(expected=2)
        self.assertEqual((self.output / "report.html").read_bytes(), before)
        self.assertEqual(self.run_cli("--force")["status"], "generated")

    def test_missing_model_or_input_does_not_create_output(self):
        self.model_path.unlink()
        self.run_cli(expected=2)
        self.assertFalse(self.output.exists())
        self.save_model()
        (self.task / "diff.md").unlink()
        self.run_cli(expected=2)
        self.assertFalse(self.output.exists())

    def test_comma_separated_source_names_model_field(self):
        self.model["evidence"] = [self.evidence + ", .doc/tasks/42/diff.md"]
        self.save_model()
        payload = self.run_cli(expected=2)
        self.assertEqual(payload["status"], "blocked")
        message = payload["errors"][0]
        self.assertIn("model field evidence/source", message)
        self.assertIn("one existing relative path", message)

    def test_existing_no_force_skip_force_and_invalid_preserves(self):
        self.output.mkdir(parents=True)
        report = self.output / "report.html"
        report.write_text("old")
        self.run_cli(expected=2)
        self.assertEqual(self.run_cli("--if-missing")["status"], "skipped")
        self.model["task"]["id"] = "43"
        self.save_model()
        self.run_cli("--force", expected=2)
        self.assertEqual(report.read_text(), "old")
        self.model["task"]["id"] = "42"
        self.save_model()
        self.run_cli("--force")
        self.assertIn("<!doctype", report.read_text())

    def test_role_and_screenshot_invariants(self):
        self.model["file_roles"] = {}
        self.save_model()
        self.run_cli(expected=2)
        self.model["file_roles"] = {"lib/file.php": "Role"}
        for path in ("missing.png", "../escape.png", "/etc/passwd"):
            self.model["screenshots"] = [{"path": path, "title": "shot", "caption": "proof"}]
            self.save_model()
            self.run_cli(expected=2)
        self.assertFalse(self.output.exists())

    def test_stage_limits_diff_and_tests(self):
        self.context(stage=True)
        self.put(".doc/tasks/42/diff.md", self.diff + self.diff.replace("lib/file.php", "lib/other.php"))
        self.put(".doc/tasks/42/test.md", "- [x] WHOLE TASK SUCCESS")
        self.run_cli("--context", str(self.root / "context.json"))
        data = json.loads((self.output / "report-data.json").read_text())
        self.assertEqual(len(data["files"]), 1)
        self.assertEqual(data["git"]["added"], 1)
        self.assertNotIn("WHOLE TASK SUCCESS", (self.output / "report.html").read_text())
        self.assertEqual(data["test_data"]["checklist"][0]["mark"], " ")

    def test_stage_root_artifacts_and_missing_context_fail(self):
        data = self.context(stage=True)
        self.run_cli(expected=2)
        data["sources"][1] = {"path": ".doc/tasks/42/diff.md", "role": "diff", "sha256": hashlib.sha256(self.diff.encode()).hexdigest()}
        self.put("context.json", json.dumps(data))
        self.run_cli("--context", str(self.root / "context.json"), expected=2)

    def test_context_stale_and_disallowed(self):
        self.context(allowed=["documentation"])
        self.run_cli("--context", str(self.root / "context.json"), expected=2)
        self.context()
        self.put(self.evidence, "stale")
        self.run_cli("--context", str(self.root / "context.json"), expected=2)

    def test_jira_preservation_and_html_escape(self):
        data = self.context(allowed=["html", "jira"])
        text = 'Exact "quotes" <script>alert(1)</script>\nsecond line\nрелиз 1.2'
        shot = {"path": "shot.png", "title": '\" onerror=alert(1)', "caption": "Exact caption"}
        self.put("shot.png", "image bytes")
        data["sources"].append({"path": "shot.png", "role": "screenshot", "sha256": hashlib.sha256(b"image bytes").hexdigest()})
        data["jira"] = {"text": text, "release": "1.2", "release_source": self.evidence, "evidence": [self.evidence], "shots": [shot], "limitations": []}
        self.put("context.json", json.dumps(data))
        self.run_cli("--context", str(self.root / "context.json"))
        result = json.loads((self.output / "report-data.json").read_text())
        self.assertEqual(result["jira_reply"], text)
        self.assertEqual(result["jira"], data["jira"])
        page = (self.output / "report.html").read_text()
        self.assertIn(html.escape(text, quote=True), page)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertNotIn("securityLevel:'loose'", page)
        self.assertIn("cloneNode()", page)
        data["allowed_steps"] = ["html"]
        self.put("context.json", json.dumps(data))
        self.run_cli("--context", str(self.root / "context.json"), "--force", expected=2)

    def test_mermaid_unit_validation(self):
        # Valid cases
        validate_mermaid_diagram("Flow", "flowchart TD\n  A[\"Node 1: Start\"] --> B[\"Node 2: End\"]")
        validate_mermaid_diagram("Sequence", "sequenceDiagram\n  Client->>Server: Request\n  Server-->>Client: Response")
        validate_mermaid_diagram("State", "stateDiagram-v2\n  [*] --> State1\n  State1 --> State2: Transition")

        # Invalid cases
        with self.assertRaises(ValueError) as cm:
            validate_mermaid_diagram("Empty", "")
        self.assertIn("is empty", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            validate_mermaid_diagram("Unknown", "unknownType LR\n  A --> B")
        self.assertIn("starts with unknown diagram type", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            validate_mermaid_diagram("Quotes", 'flowchart TD\n  A["Unclosed quote] --> B')
        self.assertIn("unclosed double quotes", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            validate_mermaid_diagram("Brackets", 'flowchart TD\n  A["Ok"] --> B[Unclosed bracket')
        self.assertIn("unbalanced square brackets", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            validate_mermaid_diagram("StateColons", 'stateDiagram-v2\n  Step1: Шаг 1: Ввод данных')
        self.assertIn("line with multiple colons", str(cm.exception))

        with self.assertRaises(ValueError) as cm:
            validate_mermaid_diagram("FlowUnquotedColon", 'flowchart TD\n  A --> B(Шаг 1: Ошибка)')
        self.assertIn("unquoted colon inside parentheses", str(cm.exception))

    def test_mermaid_cli_blocks_invalid_model(self):
        self.model["diagrams"] = [
            {"title": "Broken", "text": "stateDiagram-v2\n  [*] --> Step1: Шаг 1: Ошибка\n", "source": self.evidence},
            {"title": "Valid", "text": "flowchart LR\n  A-->B\n", "source": self.evidence}
        ]
        self.save_model()
        res = self.run_cli(expected=2)
        self.assertEqual(res["status"], "blocked")
        self.assertTrue(any("multiple colons" in err for err in res["errors"]))


if __name__ == "__main__":
    unittest.main()

