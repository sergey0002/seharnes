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
def panel():
    with tempfile.TemporaryDirectory(prefix="panel-origin-test-") as directory:
        root = Path(directory)
        web = root / ".doc/web"
        web.parent.mkdir(parents=True)
        shutil.copytree(WEB, web, ignore=shutil.ignore_patterns(
            "state", ".env", "*.local.*", "__pycache__", "*.log"))
        script = root / ".agents/skills/harness-router/children/harness-core/scripts/harness_cli.py"
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


def post(port, host, origin, xrw=True):
    headers = {"Content-Type": "application/json"}
    if host is not None:
        headers["Host"] = host
    if origin is not None:
        headers["Origin"] = origin
    if xrw:
        headers["X-Requested-With"] = "XMLHttpRequest"
    body = json.dumps({"action": "harness_audit", "params": {}}).encode()
    request = Request(f"http://127.0.0.1:{port}/jobs", data=body, headers=headers, method="POST")
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        with error:
            return error.code, json.load(error)


class OriginPolicyTest(unittest.TestCase):
    """Панель работает за обратным прокси: внешний хост не должен блокироваться."""

    def test_proxy_host_with_same_origin_is_allowed(self):
        with panel() as (root, port):
            status, data = post(port, "8077-preview.example.test", "https://8077-preview.example.test")
            self.assertEqual(status, 202, data)
            self.assertIn("id", data)
            self.assertNotEqual("origin not allowed", data.get("error"))

    def test_loopback_host_is_allowed(self):
        with panel() as (root, port):
            status, data = post(port, None, None)
            self.assertEqual(status, 202, data)

    def test_cross_origin_is_rejected(self):
        with panel() as (root, port):
            status, data = post(port, "8077-preview.example.test", "https://evil.example")
            self.assertEqual(403, status)
            self.assertEqual("origin not allowed", data.get("error"))

    def test_missing_requested_with_is_rejected(self):
        with panel() as (root, port):
            status, data = post(port, "8077-preview.example.test", "https://8077-preview.example.test", xrw=False)
            self.assertEqual(403, status)
            self.assertEqual("origin not allowed", data.get("error"))


if __name__ == "__main__":
    unittest.main()
