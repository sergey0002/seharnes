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

def enable_discovery(root, *envs):
    """Write a local registry that enables the given environments.

    The project registry disables qwen and dsh, so qwen/dsh discovery wrappers
    are generated only when the test says so.
    """
    import json
    registry = root / '.agents/skills/harness-router/children/harness-core/assets/environments.json'
    registry.parent.mkdir(parents=True, exist_ok=True)
    ids = ('cursor', 'codex', 'kilo', 'qoder', 'qwen', 'agents', 'dsh', 'opencode', 'omp')
    registry.write_text(json.dumps({'schema': 1, 'environments': [
        {'id': env, 'enabled': env in envs} for env in ids
    ]}), encoding='utf-8')


class NestedDiscoveryTest(unittest.TestCase):
    def test_nested_wrapper_registration_and_removal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            enable_discovery(root, 'qwen', 'dsh')
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
            enable_discovery(root, 'qwen', 'dsh')
            canon = root / '.agents/skills/router/children/child/SKILL.md'
            canon.parent.mkdir(parents=True)
            canon.write_text('---\nname: child\ndescription: Nested workflow\n---\nBody\n')
            generator.sync_discovery(root)
            wrapper = root / '.qwen/skills/child/SKILL.md'
            wrapper.write_text('local change')
            with self.assertRaises(ValueError):
                generator.sync_discovery(root)
            self.assertEqual(wrapper.read_text(), 'local change')
