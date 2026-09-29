import json
import tempfile
import unittest
from pathlib import Path

from hooks.runner import TransitionError, apply_transition, release_run, save_state, start_run, validate_transition


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

    def test_chair_review_sets_research_mode(self):
        validate_transition(self.state('issue-intake', research_mode='NONE'), self.state('chair-review', research_mode='WEB'))
        with self.assertRaises(TransitionError):
            validate_transition(self.state('chair-review', research_mode='WEB'), self.state('research', research_mode='LOCAL'))

    def test_first_audit_does_not_consume_budget(self):
        after = self.state('content-audit')
        validate_transition(self.state('formal-validation'), after)
        after['counters']['audit_revisions'] = 1
        with self.assertRaises(TransitionError):
            validate_transition(self.state('formal-validation'), after)

    def test_reaudit_consumes_budget(self):
        before = self.state('formal-validation', audit_result='REVISE')
        after = self.state('content-audit', audit_result='REVISE')
        with self.assertRaises(TransitionError):
            validate_transition(before, after)
        after['counters']['audit_revisions'] = 1
        validate_transition(before, after)

    def test_apply_start_and_release_write_transition_log(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            start_run(root, issue_id='ISSUE-2026-0003', run_id='RUN-20260824-0001', output='runs/private/x.json')
            with self.assertRaises(TransitionError):
                start_run(root, issue_id='ISSUE-2026-0004', run_id='RUN-20260824-0002')
            apply_transition(root, stage='chair-review', research_mode='LOCAL', outputs={'chair_review': 'runs/private/c.json'})
            with self.assertRaises(TransitionError):
                apply_transition(root, stage='secretary')
            released = release_run(root, reason='abandoned in test')
            self.assertEqual(released['status'], 'FAILED')
            log = (root / 'runs' / 'private' / 'RUN-20260824-0001' / 'transition_log.jsonl').read_text(encoding='utf-8').splitlines()
            self.assertEqual([json.loads(line)['event'] for line in log], ['start', 'transition', 'release'])
            self.assertEqual(json.loads(log[1])['outputs_changed'], {'chair_review': 'runs/private/c.json'})
            snapshot = json.loads((root / '.council' / 'active_run.snapshot.json').read_text(encoding='utf-8'))
            self.assertEqual(snapshot['status'], 'FAILED')

    def test_save_state_is_atomic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.council' / 'active_run.json'
            state = self.state()
            save_state(path, state)
            self.assertEqual(path.read_text(encoding='utf-8').count('RUN-20260824-0001'), 1)


if __name__ == '__main__':
    unittest.main()
