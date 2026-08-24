import tempfile
import unittest
from pathlib import Path

from hooks.source_snapshot import (
    SourceSnapshotError,
    create_snapshot,
    link_claim,
    sha256_bytes,
    validate_source_record,
)


class TestSourceSnapshot(unittest.TestCase):
    def test_snapshot_is_immutable_and_hashable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.txt"
            first = create_snapshot(path, b"version one", source_id="SRC-2026-0005",
                                    title="Test source", retrieved_at="2026-08-24T10:00:00+00:00")
            self.assertEqual(first.content_hash, sha256_bytes(b"version one"))
            create_snapshot(path, b"version one", source_id="SRC-2026-0005",
                            title="Test source", retrieved_at="2026-08-24T10:00:00+00:00")
            with self.assertRaises(SourceSnapshotError):
                create_snapshot(path, b"version two", source_id="SRC-2026-0005",
                                title="Test source", retrieved_at="2026-08-24T10:00:00+00:00")

    def test_source_record_and_claim_link_require_valid_ids(self):
        record = {
            "source_id": "SRC-2026-0005",
            "title": "Test source",
            "retrieved_at": "2026-08-24T10:00:00+00:00",
            "content_hash": sha256_bytes(b"content"),
            "verification_status": "UNCHECKED",
        }
        self.assertEqual(validate_source_record(record)["source_id"], "SRC-2026-0005")
        link = link_claim("CLAIM-2026-0005", "The source supports the claim.", ["SRC-2026-0005"], "SUPPORTS_CLAIM")
        self.assertEqual(link.source_ids, ("SRC-2026-0005",))
        with self.assertRaises(SourceSnapshotError):
            link_claim("CLAIM-2026-0005", "Claim", [], "SUPPORTS_CLAIM")
        with self.assertRaises(SourceSnapshotError):
            validate_source_record({**record, "content_hash": "not-a-hash"})


if __name__ == "__main__":
    unittest.main()
