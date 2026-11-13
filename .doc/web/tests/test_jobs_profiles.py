import json
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

WEB = Path(__file__).resolve().parents[1]


@contextmanager
def panel(profile):
    with tempfile.TemporaryDirectory(prefix="panel-profile-test-") as directory:
        root = Path(directory)
        web = root / ".doc/web"
        web.parent.mkdir(parents=True)
        shutil.copytree(WEB, web, ignore=shutil.ignore_patterns(
            "state", ".env", "*.local.*", "__pycache__", "*.log"))
        service = web / "config/service.json"
        data = json.loads(service.read_text(encoding="utf-8"))
        data["profile"] = profile
        service.write_text(json.dumps(data), encoding="utf-8")
        script = root / ".agents/skills/task-router/children/analytics/scripts/task-analytics.py"
        script.parent.mkdir(parents=True)
        script.write_text("from pathlib import Path\nPath('marker').write_text('ran')\n", encoding="utf-8")
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        process = subprocess.Popen(["php", "-S", f"127.0.0.1:{port}", "-t", str(web), str(web / "router.php")],
                                   cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(50):
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                        break
                except OSError:
                    time.sleep(0.1)
            else:
                raise RuntimeError("PHP test server did not start")
            yield root, port
        finally:
            process.terminate()
            process.wait(timeout=5)


def start(port, action):
    request = Request(f"http://127.0.0.1:{port}/jobs", data=json.dumps({"action": action}).encode(),
                      headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"}, method="POST")
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


def visible(root):
    result = subprocess.run(["php", "-r", "require $argv[1]; echo json_encode(jobs_visible_actions());",
                             str(root / ".doc/web/app/jobs.php")],
                            capture_output=True, text=True, check=True, timeout=5)
    return {row["id"] for row in json.loads(result.stdout)}


@unittest.skipUnless(shutil.which("php"), "PHP CLI is unavailable")
class JobsProfileTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which('setsid') and shutil.which('python3'), 'runner dependencies unavailable')
    def test_core_strict_structure_action_exposes_failed_findings(self):
        with panel('core') as (root, port):
            script = root / '.agents/skills/harness-router/children/harness-core/scripts/harness_cli.py'
            script.parent.mkdir(parents=True)
            script.write_text("import sys\nprint('JUNK fixture.tmp', flush=True)\nsys.exit(1)\n", encoding='utf-8')
            self.assertIn('harness_structure_strict', visible(root))
            status, data = start(port, 'harness_structure_strict')
            self.assertEqual(status, 202, data)
            for _ in range(100):
                with urlopen(f'http://127.0.0.1:{port}' + data['poll'], timeout=5) as response:
                    current = json.load(response)
                if current.get('status') in ('failed', 'done', 'completed', 'success'):
                    break
                time.sleep(0.1)
            self.assertEqual(current.get('status'), 'failed')
            self.assertEqual(current.get('exit_code'), 1)
            self.assertIn('JUNK fixture.tmp', '\n'.join(current.get('log_tail', [])))
            job_file = root / '.doc/web/state/jobs' / data['id'] / 'job.json'
            job = json.loads(job_file.read_text(encoding='utf-8'))
            self.assertEqual(job['argv'][-5:], ['doctor', '--mode', 'strict', '--checks', 'structure'])

    def test_core_rejects_full_actions_before_creating_jobs(self):
        with panel("core") as (root, port):
            self.assertNotIn("analytics_scan", visible(root))
            for action in ("analytics_scan", "sync_views", "task_diff"):
                with self.subTest(action=action):
                    status, data = start(port, action)
                    self.assertEqual(status, 403)
                    self.assertEqual(data["error"], "action unavailable for profile")
            self.assertFalse((root / ".doc/web/state/jobs").exists())
            self.assertFalse((root / "marker").exists())

    def test_unknown_profile_does_not_enable_actions(self):
        with panel("developer") as (root, port):
            self.assertEqual(visible(root), set())
            status, data = start(port, "analytics_scan")
            self.assertEqual(status, 403)
            self.assertEqual(data["error"], "action unavailable for profile")
            self.assertFalse((root / ".doc/web/state/jobs").exists())

    @unittest.skipUnless(shutil.which("setsid"), "legacy full-profile runner requires setsid")
    def test_legacy_full_can_still_run_enabled_analytics(self):
        with panel("full") as (root, port):
            self.assertIn("analytics_scan", visible(root))
            status, data = start(port, "analytics_scan")
            self.assertEqual(status, 202, data)
            for _ in range(50):
                if (root / "marker").is_file():
                    break
                time.sleep(0.1)
            self.assertEqual((root / "marker").read_text(encoding="utf-8"), "ran")


if __name__ == "__main__":
    unittest.main()
