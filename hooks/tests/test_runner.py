import copy
import tempfile
import unittest
from pathlib import Path

from hooks.runner import TransitionError, save_state, validate_transition


class TestRunner(unittest.TestCase):
    def state(self, stage='issue-intake', **overrides):
        value = {
            'issue_id': 'ISSUE-2026-0003',
            'run_id': 'RUN-20260824-0001',
            'research_mode': 'LOCAL',
            'current_stage': stage,
            'status': 'RUNNING',
            'next_action': 'CONTINUE',
            'content_audit_required': True,
            'deliberation_budget': {'max_research_revisions': 2, 'max_recritiques': 2, 'max_audit_revisions': 1},
            'counters': {'research_revisions': 0, 'recritiques': 0, 'audit_revisions': 0},
        }
        value.update(overrides)
        return value

    def test_validates_normal_transition(self):
        before = self.state('issue-intake')
        after = self.state('chair-review')
        validate_transition(before, after)

    def test_skips_research_when_mode_none(self):
        before = self.state('chair-review', research_mode='NONE')
        after = self.state('devil-advocate', research_mode='NONE')
        validate_transition(before, after)

    def test_rejects_invalid_stage_jump(self):
        with self.assertRaises(TransitionError):
            validate_transition(self.state('issue-intake'), self.state('secretary'))

    def test_revision_must_consume_budget(self):
        after = self.state('research-revision')
        with self.assertRaises(TransitionError):
            validate_transition(self.state('devil-advocate'), after)
        after['counters']['research_revisions'] = 1
        validate_transition(self.state('devil-advocate'), after)

    def test_completion_requires_final_synthesis(self):
        after = self.state('chair-review', status='COMPLETED', next_action='COMPLETE')
        with self.assertRaises(TransitionError):
            validate_transition(self.state('issue-intake'), after)

    def test_save_state_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.council' / 'active_run.json'
            state = self.state()
            save_state(path, state)
            self.assertEqual(path.read_text(encoding='utf-8').count('RUN-20260824-0001'), 1)


if __name__ == '__main__':
    unittest.main()
