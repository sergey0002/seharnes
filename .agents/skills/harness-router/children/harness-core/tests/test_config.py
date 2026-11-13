import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import config


class ConfigTest(unittest.TestCase):
    def test_assets_exist_and_validate(self):
        root = ROOT.parents[4]
        envs = config.load_environments(root)
        kit = config.load_kit(root)
        self.assertEqual(envs["schema"], 1)
        self.assertTrue(envs["environments"])
        self.assertEqual(config.validate(envs, kit, root), [])


if __name__ == "__main__":
    unittest.main()
