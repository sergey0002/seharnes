import hashlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lib"))
import transfer_inventory as inventory


class TransferInventoryTest(unittest.TestCase):
    def test_reads_only_selected_files_and_leaves_tree_unchanged(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            selected = root / ".agents/skills/demo/SKILL.md"
            selected.parent.mkdir(parents=True)
            selected.write_bytes(b"hello\n")
            other = root / "untouched.txt"
            other.write_bytes(b"private")
            before = {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}
            result = inventory.snapshot_files(root, [".agents/skills/demo/SKILL.md", "missing.txt"], max_file_bytes=6)
            self.assertEqual(set(result), {".agents/skills/demo/SKILL.md"})
            self.assertEqual(result[".agents/skills/demo/SKILL.md"].sha256, hashlib.sha256(b"hello\n").hexdigest())
            self.assertEqual(before, {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()})

    def test_unsafe_paths_rejected_before_any_file_is_opened(self):
        paths = ["../outside", "/absolute", "C:/windows", "a\\b", "a/../b", "a//b", "a:stream.txt",
                 "a/CON.txt", "a/COM¹.txt", "a/name. ", ".git/config", ".cursor/mcp.env",
                 ".env.production", ".doc/web/state/jobs/log.txt", ".doc/skil_data/key.json", "x/local.local.json",
                 "x/api_token.txt", "secrets/config.json", "x/user-password.json", "x/credentials.backup"]
        with tempfile.TemporaryDirectory() as directory, patch.object(inventory.os, "open", side_effect=AssertionError("opened")):
            for path in paths:
                with self.subTest(path=path), self.assertRaises(inventory.InventoryError):
                    inventory.snapshot_files(Path(directory), ["safe.txt", path], max_file_bytes=100)

    def test_windows_and_unicode_collisions_rejected(self):
        for paths in (["Rules/A.md", "rules/a.md"], ["café.md", "cafe\u0301.md"], ["a", "a"],
                      ["a", "A/b"], ["a/b", "A"], ["Rules/a", "rules/b"],
                      ["café/a", "cafe\u0301/b"]):
            with self.subTest(paths=paths), self.assertRaises(inventory.InventoryError) as error:
                inventory.validate_paths(paths)
            self.assertEqual(error.exception.reason, "path_collision")
        self.assertEqual(inventory.validate_paths(["Rules/a", "Rules/b"]), ("Rules/a", "Rules/b"))
        self.assertEqual(inventory.validate_paths(["scripts/tokenizer.py"]), ("scripts/tokenizer.py",))

    def test_size_type_and_root_gates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "large.txt").write_bytes(b"12345")
            (root / "folder").mkdir()
            with self.assertRaises(inventory.InventoryError) as error:
                inventory.snapshot_files(root, ["large.txt"], max_file_bytes=4)
            self.assertEqual(error.exception.reason, "file_too_large")
            with self.assertRaises(inventory.InventoryError):
                inventory.snapshot_files(root, ["folder"], max_file_bytes=100)
            with self.assertRaises(inventory.InventoryError):
                inventory.snapshot_files(root, [], max_file_bytes=0)
            with self.assertRaises(inventory.InventoryError):
                inventory.snapshot_files(root / "missing-root", [], max_file_bytes=1)

    def test_discovery_lists_protected_path_without_opening_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'kit/secrets').mkdir(parents=True)
            (root / 'kit/secrets/password.txt').write_text('not read', encoding='utf-8')
            (root / 'kit/safe.txt').write_text('safe', encoding='utf-8')
            original_scandir = os.scandir
            def guarded_scandir(path):
                if Path(path).name == 'secrets':
                    raise AssertionError('protected directory was traversed')
                return original_scandir(path)
            with patch.object(inventory.os, 'scandir', side_effect=guarded_scandir):
                files, protected = inventory.discover_target_paths(root, ['kit'])
            self.assertEqual(files, ['kit/safe.txt'])
            self.assertEqual(protected, ['kit/secrets'])

    def test_hardlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("safe", encoding="utf-8")
            hard = root / "hard.txt"
            try:
                os.link(source, hard)
            except (OSError, NotImplementedError):
                self.skipTest("hardlinks unavailable")
            with self.assertRaises(inventory.InventoryError) as error:
                inventory.snapshot_files(root, ["hard.txt"], max_file_bytes=100)
            self.assertEqual(error.exception.reason, "hardlink")

    def test_symlink_file_is_not_followed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.txt"
            source.write_text("safe", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(inventory.InventoryError):
                inventory.snapshot_files(root, ["link.txt"], max_file_bytes=100)
            self.assertEqual(source.read_text(encoding="utf-8"), "safe")

    def test_modification_during_read_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "file.txt"
            source.write_bytes(b"first")
            original_read = os.read
            changed = False

            def racing_read(fd, size):
                nonlocal changed
                data = original_read(fd, size)
                if data and not changed:
                    changed = True
                    source.write_bytes(b"second")
                return data

            with patch.object(inventory.os, "read", side_effect=racing_read):
                with self.assertRaises(inventory.InventoryError) as error:
                    inventory.snapshot_files(root, ["file.txt"], max_file_bytes=100)
            self.assertEqual(error.exception.reason, "file_changed")

    def test_symlink_directory_does_not_escape_root(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            root = Path(directory)
            (Path(external) / "secret.txt").write_text("do not read", encoding="utf-8")
            try:
                (root / "escape").symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable")
            with self.assertRaises(inventory.InventoryError):
                inventory.snapshot_files(root, ["escape/secret.txt"], max_file_bytes=100)

    def test_target_discovery_rejects_linked_subdirectory(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as external:
            root = Path(directory)
            (root / 'kit').mkdir()
            try:
                (root / 'kit/link').symlink_to(external, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('symlink unavailable')
            with self.assertRaises(inventory.InventoryError):
                inventory.discover_target_paths(root, ['kit'])

    def test_known_secret_across_read_boundary_does_not_produce_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            synthetic = b'gh' + b'p_' + b'abcdefgh12345678'
            (root / 'ordinary.txt').write_bytes(b'x' * (1024 * 1024 - 3) + synthetic)
            with self.assertRaises(inventory.InventoryError) as error:
                inventory.snapshot_files(root, ['ordinary.txt'], max_file_bytes=2 * 1024 * 1024)
            self.assertEqual(error.exception.reason, 'sensitive_content')
            self.assertNotIn(synthetic.decode(), str(error.exception))

    def test_hardlink_created_during_read_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "file.txt"
            source.write_bytes(b"content")
            original_read = os.read
            linked = False

            def racing_read(fd, size):
                nonlocal linked
                data = original_read(fd, size)
                if data and not linked:
                    try:
                        os.link(source, root / "second.txt")
                    except (OSError, NotImplementedError):
                        self.skipTest("hardlinks unavailable")
                    linked = True
                return data

            with patch.object(inventory.os, "read", side_effect=racing_read):
                with self.assertRaises(inventory.InventoryError) as error:
                    inventory.snapshot_files(root, ["file.txt"], max_file_bytes=100)
            self.assertEqual(error.exception.reason, "file_changed")


if __name__ == "__main__":
    unittest.main()
