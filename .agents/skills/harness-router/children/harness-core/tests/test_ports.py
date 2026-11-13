import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import ports


class PortsTest(unittest.TestCase):
    def test_free_port(self):
        port = ports.first_free(9300, 9399)
        self.assertGreaterEqual(port, 9300)
        self.assertLessEqual(port, 9399)


if __name__ == "__main__":
    unittest.main()
