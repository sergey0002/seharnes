import json
import os
import shutil
import subprocess
import unittest
from pathlib import Path

WEB = Path(__file__).resolve().parents[1]


class ComposeBindTest(unittest.TestCase):
    @unittest.skipUnless(shutil.which("docker"), "docker CLI is unavailable")
    def test_published_ports_are_loopback_only(self):
        for compose, service in (("compose.tools.yml", "tools"), ("docker-compose.yml", "web-panel")):
            with self.subTest(compose=compose):
                env = dict(os.environ, WEB_PANEL_PORT="18987")
                result = subprocess.run(
                    ["docker", "compose", "-f", str(WEB / compose), "config", "--format", "json"],
                    cwd=WEB, env=env, capture_output=True, text=True, check=True,
                )
                ports = json.loads(result.stdout)["services"][service]["ports"]
                self.assertEqual(len(ports), 1)
                self.assertEqual(ports[0]["host_ip"], "127.0.0.1")
                self.assertEqual(str(ports[0]["published"]), "18987")
                self.assertEqual(ports[0]["target"], 8077)


if __name__ == "__main__":
    unittest.main()
