import json
import tempfile
import unittest
from pathlib import Path

from hooks.audit_store import append_audit, audit_result_was_rewritten


class TestAuditStore(unittest.TestCase):
    def test_appends_numbered_records_without_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = append_audit({'result': 'REVISE', 'findings': ['x']}, root=root, run_id='RUN-20260722-0001', attempt=1)
            second = append_audit({'result': 'PASS_WITH_WARNINGS', 'findings': []}, root=root, run_id='RUN-20260722-0001', attempt=1)
            self.assertEqual(first.name, 'content_audit-01.json')
            self.assertEqual(second.name, 'content_audit-02.json')
            self.assertEqual(json.loads(first.read_text(encoding='utf-8'))['result'], 'REVISE')
            self.assertTrue(json.loads(second.read_text(encoding='utf-8'))['append_only'])

    def test_rejects_invalid_audit_result(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                append_audit({'result': 'UNKNOWN'}, root=Path(directory), run_id='RUN-20260722-0001', attempt=1)

    def test_detects_legacy_rewritten_result(self):
        self.assertTrue(audit_result_was_rewritten({'result': 'PASS', 'audit_passes': [{'result': 'BLOCK'}]}))
        self.assertFalse(audit_result_was_rewritten({'result': 'PASS', 'audit_passes': [{'result': 'PASS'}]}))


if __name__ == '__main__':
    unittest.main()
