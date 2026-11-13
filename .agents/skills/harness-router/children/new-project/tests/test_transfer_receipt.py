import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts/lib'))
from transfer_receipt import read_preview_receipt, receipt_paths_in_roots


class ReceiptTest(unittest.TestCase):
    def test_root_selection_rejects_portable_path_mismatch(self):
        self.assertEqual(receipt_paths_in_roots(['kit/a', 'else/b'], ['kit']), ['kit/a'])
        with self.assertRaises(ValueError):
            receipt_paths_in_roots(['KIT/a'], ['kit'])
        with self.assertRaises(ValueError):
            receipt_paths_in_roots(['é/a'], ['e\u0301'])

    def receipt(self):
        return {'schema_version': 1, 'release_url': 'https://example.invalid/repo', 'commit': 'a' * 40,
                'profile': 'core', 'files': {'kit/a': {'installed_hash': 'b' * 64, 'mode': 420,
                                                        'role': 'owned', 'decision': 'installed'}}}

    def test_schema_path_and_duplicate_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            value = self.receipt()
            path.write_text(json.dumps(value))
            states, info = read_preview_receipt(path)
            self.assertEqual(states['kit/a'].sha256, 'b' * 64)
            self.assertNotIn('release_url', info)
            for mutate in ('version', 'private', 'mode', 'role', 'extra'):
                value = self.receipt()
                if mutate == 'version': value['schema_version'] = True
                if mutate == 'private': value['files'] = {'.cursor/mcp.env': value['files']['kit/a']}
                if mutate == 'mode': value['files']['kit/a']['mode'] = True
                if mutate == 'role': value['files']['kit/a']['role'] = 'local'
                if mutate == 'extra': value['arbitrary'] = 1
                path.write_text(json.dumps(value))
                with self.subTest(mutate=mutate), self.assertRaises(ValueError):
                    read_preview_receipt(path)
            path.write_text('{"schema_version":1,"schema_version":1}')
            with self.assertRaises(ValueError):
                read_preview_receipt(path)

    def test_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'receipt.json'
            actual = Path(directory) / 'actual.json'
            actual.write_text(json.dumps(self.receipt()))
            try:
                os.symlink(actual, path)
            except (OSError, NotImplementedError):
                self.skipTest('symlink unavailable')
            with self.assertRaises(ValueError):
                read_preview_receipt(path)


if __name__ == '__main__':
    unittest.main()
