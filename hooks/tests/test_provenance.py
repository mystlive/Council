import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from hooks.provenance import sanitize_public_payload, sha256_file, validate_private_payload, write_manifests


class TestProvenance(unittest.TestCase):
    def test_writes_public_manifest_and_private_manifest_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            public, private = write_manifests(
                root=root,
                issue_id='ISSUE-2026-0003',
                run_id='RUN-20260824-0001',
                attempt=1,
                public_payload={'status': 'RUNNING', 'provider': 'codex', 'artifact_hashes': []},
                private_payload={'provider': 'codex', 'model': 'gpt-5-codex', 'usage': {'input_tokens': 1},
                                 'cost': {'amount': 'UNKNOWN', 'currency': 'USD', 'estimated': True}},
                generated_at='2026-08-24T00:00:00+00:00',
            )
            public_data = json.loads(public.read_text(encoding='utf-8'))
            self.assertEqual(public_data['manifest_type'], 'public-run-manifest')
            self.assertEqual(public_data['private_manifest_sha256'], sha256_file(private))
            self.assertNotIn('model_output', public_data)

    def test_public_payload_rejects_private_fields(self):
        with self.assertRaises(ValueError):
            sanitize_public_payload({'model': 'secret-model'})

    def test_private_payload_rejects_raw_content_and_api_keys(self):
        with self.assertRaises(ValueError):
            validate_private_payload({'provider': 'codex', 'prompt_text': 'do not store'})
        with self.assertRaises(ValueError):
            validate_private_payload({'provider': 'codex', 'api_key': 'secret'})

    def test_private_metadata_accepts_usage_and_unknown_cost(self):
        value = validate_private_payload({
            'provider': 'orcarouter',
            'model': 'route-model',
            'usage': {'input_tokens': 4, 'output_tokens': 6, 'total_tokens': 10},
            'cost': {'amount': 'UNKNOWN', 'currency': 'USD', 'rate_card_version': '2026-08', 'estimated': False},
        })
        self.assertEqual(value['usage']['total_tokens'], 10)

    def test_manifest_is_immutable(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            args = dict(root=root, issue_id='ISSUE-2026-0003', run_id='RUN-20260824-0001', attempt=1,
                        public_payload={}, private_payload={'provider': 'codex'})
            write_manifests(**args)
            with self.assertRaises(FileExistsError):
                write_manifests(**args)


if __name__ == '__main__':
    unittest.main()
