"""Qwen's shallow discovery must reach nested canon without personal-scope imports."""
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('discovery_generator', SCRIPTS / 'generate-agent-configs.py')
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)

class NestedDiscoveryTest(unittest.TestCase):
    def test_nested_wrapper_registration_and_removal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            canon = root / '.agents/skills/router/children/child/SKILL.md'
            canon.parent.mkdir(parents=True)
            canon.write_text('---\nname: child\ndescription: Nested workflow\n---\nBody\n')
            generator.sync_discovery(root)
            for view in ('.qwen', '.dsh'):
                wrapper = root / view / 'skills/child/SKILL.md'
                self.assertIn(canon.relative_to(root).as_posix(), wrapper.read_text())
                self.assertNotIn('Body', wrapper.read_text())
            self.assertEqual(generator.sync_discovery(root, check=True), [])
            canon.unlink()
            generator.sync_discovery(root)
            self.assertFalse((root / '.qwen/skills/child/SKILL.md').exists())

    def test_edited_wrapper_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            canon = root / '.agents/skills/router/children/child/SKILL.md'
            canon.parent.mkdir(parents=True)
            canon.write_text('---\nname: child\ndescription: Nested workflow\n---\nBody\n')
            generator.sync_discovery(root)
            wrapper = root / '.qwen/skills/child/SKILL.md'
            wrapper.write_text('local change')
            with self.assertRaises(ValueError):
                generator.sync_discovery(root)
            self.assertEqual(wrapper.read_text(), 'local change')
