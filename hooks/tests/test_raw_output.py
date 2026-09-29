import hashlib
import tempfile
import unittest
from pathlib import Path

from hooks.raw_output import save_raw


class TestRawOutput(unittest.TestCase):
    def test_saves_unchanged_with_hash_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            text = '{"objections": ["日本語の反論"]}\n'
            first, digest = save_raw(text, root=root, run_id="RUN-20260929-0001", attempt=1, role="critic")
            second, _ = save_raw("second", root=root, run_id="RUN-20260929-0001", attempt=1, role="critic")
            self.assertEqual(first.name, "critic-01.txt")
            self.assertEqual(second.name, "critic-02.txt")
            self.assertEqual(first.read_bytes(), text.encode("utf-8"))
            self.assertEqual(digest, hashlib.sha256(text.encode("utf-8")).hexdigest())
            sums = (first.parent / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
            self.assertEqual(sums[0], f"{digest}  critic-01.txt")

    def test_rejects_unsafe_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                save_raw("x", root=root, run_id="RUN-2026-0003", attempt=1, role="critic")
            with self.assertRaises(ValueError):
                save_raw("x", root=root, run_id="RUN-20260929-0001", attempt=1, role="../chair")
            with self.assertRaises(ValueError):
                save_raw("  ", root=root, run_id="RUN-20260929-0001", attempt=1, role="chair")


if __name__ == "__main__":
    unittest.main()
