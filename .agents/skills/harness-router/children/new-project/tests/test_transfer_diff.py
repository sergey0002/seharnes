import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts/lib"))
from transfer_diff import FileState, classify_update

A = FileState("a" * 64, 0o644)
B = FileState("b" * 64, 0o644)
C = FileState("c" * 64, 0o644)


class TransferDiffTest(unittest.TestCase):
    def test_unknown_or_absent_base_never_claims_target(self):
        for base_known in (False, True):
            with self.subTest(base_known=base_known):
                result = classify_update(base_known=base_known, base=None, target=A, incoming=A)
                self.assertEqual((result.status, result.action, result.requires_review),
                                 ("same_path_collision", "review", True))
                self.assertIn("adopt", result.choices)
                unknown = classify_update(base_known=base_known, base=None, target=A, incoming=None)
                self.assertEqual((unknown.status, unknown.action, unknown.requires_review),
                                 ("unexpected_unclassified", "review", True))
                self.assertIn("mark_local", unknown.choices)
                self.assertEqual(classify_update(base_known=base_known, base=None, target=None, incoming=A).status,
                                 "new_from_release")
                self.assertEqual(classify_update(base_known=base_known, base=None, target=None, incoming=None).action,
                                 "none")

    def test_owned_three_way_matrix(self):
        cases = [
            (A, A, "unchanged", "none", False),
            (A, B, "modified_upstream", "replace", True),
            (B, A, "local_modified", "keep", False),
            (B, B, "already_applied", "none", False),
            (B, C, "both_modified", "review", True),
            (A, None, "deleted_upstream", "propose_delete", True),
            (B, None, "orphan_local_modified", "keep", False),
            (None, A, "locally_deleted", "keep_deleted", False),
            (None, B, "delete_modify_conflict", "review", True),
            (None, None, "both_deleted", "none", False),
        ]
        for target, incoming, status, action, review in cases:
            with self.subTest(status=status):
                result = classify_update(base_known=True, base=A, target=target, incoming=incoming)
                self.assertEqual((result.status, result.action, result.requires_review), (status, action, review))

    def test_deletion_and_conflict_require_per_file_decision(self):
        deleted = classify_update(base_known=True, base=A, target=A, incoming=None)
        self.assertEqual(deleted.choices, ("keep", "delete"))
        conflict = classify_update(base_known=True, base=A, target=B, incoming=C)
        self.assertEqual(conflict.choices, ("keep", "replace", "edited", "skip"))
        self.assertTrue(conflict.requires_review)

    def test_mode_changes_are_not_ignored(self):
        changed_mode = FileState(A.sha256, 0o755)
        result = classify_update(base_known=True, base=A, target=changed_mode, incoming=C)
        self.assertEqual(result.status, "both_modified")

    def test_local_and_secret_paths_are_never_automatic_replacements(self):
        result = classify_update(base_known=True, base=A, target=A, incoming=B, ownership="local")
        self.assertEqual(result.status, "local_path_collision")
        self.assertNotIn("replace", result.choices)
        with self.assertRaises(ValueError):
            classify_update(base_known=True, base=A, target=A, incoming=B, ownership="secret")

    def test_invalid_state_and_ambiguous_ownership_rejected(self):
        for digest, mode in (("A" * 64, 0o644), ("a" * 63, 0o644), ("a" * 64, True), ("a" * 64, 0o10000)):
            with self.subTest(digest=digest, mode=mode), self.assertRaises(ValueError):
                FileState(digest, mode)
        with self.assertRaises(ValueError):
            classify_update(base_known=False, base=A, target=A, incoming=B)
        with self.assertRaises(ValueError):
            classify_update(base_known=True, base=A, target=A, incoming=B, ownership="unknown")


if __name__ == "__main__":
    unittest.main()
