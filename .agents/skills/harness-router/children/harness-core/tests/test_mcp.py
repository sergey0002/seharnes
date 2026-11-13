import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import mcp


class McpTest(unittest.TestCase):
    def test_enabled_and_names(self):
        canon = {"one": {"command": "x"}, "off": {"command": "y", "disabled": True}}
        self.assertEqual(mcp.server_names(canon), ["off", "one"])
        self.assertEqual(mcp.enabled(canon), ["one"])

    def test_placeholders(self):
        self.assertEqual(mcp.scan_placeholders({"env": {"A": "${env:TOKEN}"}}), ["TOKEN"])


if __name__ == "__main__":
    unittest.main()
