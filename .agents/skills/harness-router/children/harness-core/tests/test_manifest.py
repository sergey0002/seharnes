import sys
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from lib import manifest


class ManifestTest(unittest.TestCase):
    def test_compare(self):
        source = {"a": "1", "b": "2"}
        target = {"a": "1", "c": "3"}
        diff = manifest.compare(source, target)
        self.assertEqual(diff.added, ["b"])
        self.assertEqual(diff.target_only, ["c"])
        self.assertEqual(diff.overwritten, [])
        self.assertEqual(diff.same, 1)

    def test_build_skips_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".cursor").mkdir()
            (root / ".cursor" / "a.md").write_text("a", encoding="utf-8")
            (root / ".cursor" / "__pycache__").mkdir()
            (root / ".cursor" / "__pycache__" / "x.pyc").write_text("x", encoding="utf-8")
            result = manifest.build(root, {"copy": [".cursor"], "skipDirs": ["__pycache__"], "skipFiles": [], "rootFiles": []})
            self.assertIn(".cursor/a.md", result)
            self.assertNotIn(".cursor/__pycache__/x.pyc", result)

    def test_default_kit_includes_policy_but_not_local_extension(self):
        kit = json.loads((ROOT / 'assets/kit.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            state = root / '.doc/harnes/state'
            state.mkdir(parents=True)
            (state / 'canon-paths.yaml').write_text('canonical', encoding='utf-8')
            (state / 'canon-paths.local.yaml').write_text('local', encoding='utf-8')
            result = manifest.build(root, kit)
            self.assertIn('.doc/harnes/state/canon-paths.yaml', result)
            self.assertNotIn('.doc/harnes/state/canon-paths.local.yaml', result)


if __name__ == "__main__":
    unittest.main()
