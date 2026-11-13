import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lib"))
from transfer_inventory import InventoryError, snapshot_files
from transfer_plan import plan_selected_update


def put(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def files(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class TransferPlanTest(unittest.TestCase):
    def test_preview_compares_receipt_and_preserves_both_trees(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source", root / "target"
            source.mkdir(); target.mkdir()
            put(target, "owned.txt", b"base")
            put(target, "deleted-upstream.txt", b"base")
            receipt = snapshot_files(target, ["owned.txt", "deleted-upstream.txt"], max_file_bytes=100)
            put(target, "owned.txt", b"local")
            put(target, "custom.txt", b"custom")
            put(target, "collision.txt", b"local")
            put(target, "unowned.txt", b"same")
            put(source, "owned.txt", b"upstream")
            put(source, "new.txt", b"new")
            put(source, "collision.txt", b"incoming")
            put(source, "unowned.txt", b"same")
            names = ["owned.txt", "deleted-upstream.txt", "custom.txt", "new.txt", "collision.txt", "unowned.txt"]
            before = (files(source), files(target))
            result = plan_selected_update(source=source, target=target, paths=names, receipt=receipt,
                                          local_paths=["custom.txt", "collision.txt"], max_file_bytes=100)
            self.assertEqual(result["scope"], "explicit_paths_only")
            actions = {row["path"]: row["proposal"] for row in result["files"]}
            self.assertEqual(actions["owned.txt"]["status"], "both_modified")
            self.assertEqual(actions["deleted-upstream.txt"]["action"], "propose_delete")
            self.assertTrue(actions["deleted-upstream.txt"]["requires_review"])
            self.assertEqual(actions["custom.txt"]["action"], "keep")
            self.assertEqual(actions["new.txt"]["action"], "add")
            self.assertEqual(actions["collision.txt"]["status"], "local_path_collision")
            self.assertEqual(actions["unowned.txt"]["status"], "same_path_collision")
            self.assertEqual(before, (files(source), files(target)))
            self.assertEqual([row["path"] for row in result["files"]], sorted(names))

    def test_absent_target_is_not_created(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            put(source, "new.txt", b"new")
            target = root / "not-created" / "project"
            result = plan_selected_update(source=source, target=target, paths=["new.txt"], receipt=None,
                                          local_paths=[], max_file_bytes=100)
            self.assertFalse(target.exists())
            self.assertFalse(target.parent.exists())
            self.assertEqual(result["files"][0]["proposal"]["action"], "add")

    def test_receipt_coverage_and_ownership_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source", root / "target"
            source.mkdir(); target.mkdir()
            put(target, "owned.txt", b"base")
            receipt = snapshot_files(target, ["owned.txt"], max_file_bytes=100)
            for paths, local in (([], []), (["owned.txt"], ["owned.txt"]), (["owned.txt"], ["other.txt"])):
                with self.subTest(paths=paths, local=local), self.assertRaises(ValueError):
                    plan_selected_update(source=source, target=target, paths=paths, receipt=receipt,
                                         local_paths=local, max_file_bytes=100)
            with self.assertRaises(InventoryError):
                plan_selected_update(source=source, target=target, paths=[".cursor/mcp.env"], receipt=None,
                                     local_paths=[], max_file_bytes=100)

    def test_same_and_nested_roots_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            for target in (source, source / "new-target", root):
                with self.subTest(target=target), self.assertRaises(ValueError):
                    plan_selected_update(source=source, target=target, paths=[], receipt=None,
                                         local_paths=[], max_file_bytes=100)

    def test_target_under_regular_file_is_rejected_without_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            blocked = root / "file"
            blocked.write_bytes(b"unchanged")
            with self.assertRaises(ValueError):
                plan_selected_update(source=source, target=blocked / "new", paths=[], receipt=None,
                                     local_paths=[], max_file_bytes=100)
            self.assertEqual(blocked.read_bytes(), b"unchanged")

    def test_linked_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            link = root / "link"
            try:
                link.symlink_to(source, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks unavailable")
            with self.assertRaises(ValueError):
                plan_selected_update(source=link, target=root / "target", paths=[], receipt=None,
                                     local_paths=[], max_file_bytes=100)

    def test_reparse_attribute_rejected_even_without_is_junction_support(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'source'
            source.mkdir()
            original = Path.lstat
            def fake_lstat(path, *args, **kwargs):
                info = original(path, *args, **kwargs)
                if path == source:
                    return SimpleNamespace(st_mode=info.st_mode, st_file_attributes=0x400)
                return info
            with patch.object(Path, 'lstat', fake_lstat):
                with self.assertRaises(ValueError):
                    plan_selected_update(source=source, target=root / 'target', paths=[], receipt=None,
                                         local_paths=[], max_file_bytes=100)


if __name__ == "__main__":
    unittest.main()
