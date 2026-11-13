import os
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import urlopen

WEB = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("php"), "PHP CLI is unavailable")
class FilesRouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="panel-files-test-")
        root = Path(cls.temp.name)
        cls.doc = root / ".doc"
        cls.web = cls.doc / "web"
        shutil.copytree(WEB, cls.web, ignore=shutil.ignore_patterns(
            "state", ".env", "*.local.*", "__pycache__", "*.log"))
        report = cls.doc / "tasks/123/reports/change-report"
        (report / "assets").mkdir(parents=True)
        (report / "report.html").write_text("public report", encoding="utf-8")
        (report / "assets/style.css").write_text("body {}", encoding="utf-8")
        (report / "private.php").write_text("SECRET_SOURCE", encoding="utf-8")
        (cls.web / "state/jobs/job_1").mkdir(parents=True)
        (cls.web / "state/jobs/job_1/log.txt").write_text("SECRET_LOG", encoding="utf-8")
        (cls.doc / "skil_data").mkdir()
        (cls.doc / "skil_data/key.json").write_text("SECRET_DATA", encoding="utf-8")
        if hasattr(os, "symlink"):
            (report / "escape.txt").symlink_to(cls.web / "state/jobs/job_1/log.txt")
            link_parent = cls.doc / "tasks/124/reports"
            link_parent.mkdir(parents=True)
            (link_parent / "change-report").symlink_to(cls.web / "state", target_is_directory=True)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        cls.proc = subprocess.Popen(
            ["php", "-S", f"127.0.0.1:{cls.port}", "-t", str(cls.web), str(cls.web / "router.php")],
            cwd=root, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", cls.port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            cls.proc.terminate()
            cls.temp.cleanup()
            raise RuntimeError("PHP test server did not start")

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=5)
        cls.temp.cleanup()

    def request(self, path):
        try:
            with urlopen(f"http://127.0.0.1:{self.port}{path}", timeout=5) as response:
                return response.status, response.read(), response.headers
        except HTTPError as error:
            with error:
                return error.code, error.read(), error.headers

    def test_report_and_assets_remain_available(self):
        for path, body in (("report.html", b"public report"), ("assets/style.css", b"body {}")):
            status, data, headers = self.request("/files/tasks/123/reports/change-report/" + path)
            self.assertEqual((status, data), (200, body))
            self.assertEqual(headers.get("X-Content-Type-Options"), "nosniff")

    def test_private_and_traversal_paths_are_denied(self):
        for path in (
            "/files/web/state/jobs/job_1/log.txt",
            "/files/skil_data/key.json",
            "/files/tasks/123/reports/change-report/%2e%2e/%2e%2e/%2e%2e/web/state/jobs/job_1/log.txt",
            "/files/tasks/123/reports/change-report/%5c..%5cprivate.txt",
            "/files/tasks/123/reports/change-report/escape.txt",
            "/files/tasks/123/reports/change-report/private.php",
            "/files/tasks/124/reports/change-report/jobs/job_1/log.txt",
            "/files/tasks/abc/reports/change-report/report.html",
        ):
            with self.subTest(path=path):
                status, body, _ = self.request(path)
                self.assertEqual(status, 404)
                self.assertNotIn(b"SECRET_", body)


if __name__ == "__main__":
    unittest.main()
