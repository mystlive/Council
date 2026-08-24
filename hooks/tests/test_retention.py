import hashlib
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from hooks.retention import (
    RetentionError,
    RetentionPolicy,
    RetentionTarget,
    build_deletion_plan,
    execute_approved_deletion,
    write_public_receipt,
)


class TestRetention(unittest.TestCase):
    def target(self, **overrides):
        value = {
            "relative_path": "runs/private/RUN-20260824-0001",
            "run_id": "RUN-20260824-0001",
            "completed_at": "2026-01-01T00:00:00+00:00",
            "kind": "detail",
            "status": "COMPLETED",
        }
        value.update(overrides)
        return RetentionTarget(**value)

    def test_policy_requires_terminal_run_and_elapsed_period(self):
        now = datetime(2026, 4, 2, tzinfo=timezone.utc)
        plan = build_deletion_plan([self.target()], policy=RetentionPolicy(), now=now)
        self.assertEqual(plan.targets[0].kind, "detail")
        with self.assertRaises(RetentionError):
            build_deletion_plan([self.target(status="RUNNING")], policy=RetentionPolicy(), now=now)
        with self.assertRaises(RetentionError):
            build_deletion_plan([self.target(completed_at="2026-03-15T00:00:00+00:00")], policy=RetentionPolicy(), now=now)

    def test_legal_hold_and_approval_protect_deletion(self):
        now = datetime(2026, 4, 2, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_path = root / "runs/private/RUN-20260824-0001"
            target_path.mkdir(parents=True)
            (target_path / "secret.txt").write_text("private", encoding="utf-8")
            plan = build_deletion_plan([self.target()], policy=RetentionPolicy(), now=now)
            approval = {
                "plan_hash": plan.plan_hash,
                "approved_by": "human",
                "reason": "retention test",
                "expires_at": (now + timedelta(hours=1)).isoformat(),
                "used": False,
            }
            receipt = execute_approved_deletion(root, plan, approval, now=now)
            self.assertFalse(target_path.exists())
            self.assertEqual(receipt["target_run_ids"], ["RUN-20260824-0001"])
            receipt_path = write_public_receipt(root, receipt)
            self.assertTrue(receipt_path.is_file())
            with self.assertRaises(RetentionError):
                execute_approved_deletion(root, plan, approval, now=now)

    def test_plan_hash_is_deterministic_and_holds_block_deletion(self):
        now = datetime(2026, 4, 2, tzinfo=timezone.utc)
        first = build_deletion_plan([self.target()], policy=RetentionPolicy(), now=now)
        second = build_deletion_plan([self.target()], policy=RetentionPolicy(), now=now)
        self.assertEqual(first.plan_hash, second.plan_hash)
        with self.assertRaises(RetentionError):
            build_deletion_plan([self.target(legal_hold=True)], policy=RetentionPolicy(), now=now)


if __name__ == "__main__":
    unittest.main()
