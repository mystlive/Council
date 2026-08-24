import hashlib
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hooks.record_update import RecordUpdateError, apply_approved_update, inspect_change, validate_record_text


def record(status="PENDING", record_id="DEC-2026-0004"):
    return f'''---
id: {record_id}
record_type: decision
status: {status}
issue_id: ISSUE-2026-0003
title: "Test decision"
scope: "Test scope"
created_at: 2026-08-24T10:00:00+09:00
updated_at: 2026-08-24T10:00:00+09:00
approved_by: human
approved_at: 2026-08-24T10:00:00+09:00
---

### 決定内容

テスト記録。
'''


class TestRecordUpdate(unittest.TestCase):
    def test_validates_state_and_filename_contract(self):
        fields = validate_record_text(record(), state_dir="pending", expected_id="DEC-2026-0004")
        self.assertEqual(fields["status"], "PENDING")
        with self.assertRaises(RecordUpdateError):
            validate_record_text(record(status="ADOPTED"), state_dir="pending", expected_id="DEC-2026-0004")

    def test_inspects_update_and_rejects_id_change(self):
        change = inspect_change(record(), record().replace("Test scope", "Changed scope"),
                                source="records/pending/DEC-2026-0004.md",
                                destination="records/pending/DEC-2026-0004.md", root=Path("."))
        self.assertEqual(change.operation, "update")
        self.assertIn("Changed scope", change.diff)
        with self.assertRaises(RecordUpdateError):
            inspect_change(record(), record(record_id="DEC-2026-0005"),
                           source="records/pending/DEC-2026-0004.md",
                           destination="records/pending/DEC-2026-0004.md", root=Path("."))

    def test_apply_requires_and_consumes_human_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "records/pending/DEC-2026-0004.md"
            target.parent.mkdir(parents=True)
            before = record()
            target.write_text(before, encoding="utf-8")
            after = before.replace("Test scope", "Changed scope")
            with self.assertRaises(RecordUpdateError):
                apply_approved_update(root, "records/pending/DEC-2026-0004.md",
                                      "records/pending/DEC-2026-0004.md", after)
            expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            approval = {
                "record_id": "DEC-2026-0004",
                "operation": "update",
                "source_path": "records/pending/DEC-2026-0004.md",
                "destination_path": "records/pending/DEC-2026-0004.md",
                "expected_source_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
                "approved_by": "human",
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": expires,
                "reason": "test approval",
                "used": False,
            }
            approval_path = root / ".council/record_update_approval.json"
            approval_path.parent.mkdir()
            approval_path.write_text(json.dumps(approval), encoding="utf-8")
            change = apply_approved_update(root, target.relative_to(root), target.relative_to(root), after)
            self.assertEqual(change.operation, "update")
            self.assertIn("Changed scope", target.read_text(encoding="utf-8"))
            self.assertTrue(json.loads(approval_path.read_text(encoding="utf-8"))["used"])


if __name__ == "__main__":
    unittest.main()
