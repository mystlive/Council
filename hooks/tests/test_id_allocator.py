import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from hooks.id_allocator import allocate


class TestIdAllocator(unittest.TestCase):
    def project(self, root: Path) -> None:
        (root / ".council").mkdir()
        (root / "id_registry.json").write_text(
            json.dumps({"ISSUE": 2, "RUN": 2, "SOURCE": 42, "DECISION": 1, "CLAIM": 30}),
            encoding="utf-8",
        )

    def test_allocates_and_persists_next_number(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.project(root)
            value = allocate("source", root=root, now=datetime(2026, 8, 24, tzinfo=timezone.utc))
            self.assertEqual(value, "SRC-2026-0043")
            registry = json.loads((root / "id_registry.json").read_text(encoding="utf-8"))
            self.assertEqual(registry["SOURCE"], 43)

    def test_allocations_are_independent_by_kind(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.project(root)
            self.assertEqual(allocate("issue", root=root), "ISSUE-2026-0003")
            self.assertEqual(allocate("claim", root=root), "CLAIM-2026-0031")

    def test_unknown_kind_is_rejected_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.project(root)
            before = (root / "id_registry.json").read_bytes()
            with self.assertRaises(ValueError):
                allocate("unknown", root=root)
            self.assertEqual((root / "id_registry.json").read_bytes(), before)

    def test_invalid_registry_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".council").mkdir()
            (root / "id_registry.json").write_text("[]", encoding="utf-8")
            with self.assertRaises(ValueError):
                allocate("issue", root=root)


if __name__ == "__main__":
    unittest.main()
