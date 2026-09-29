import json
import subprocess
import unittest

from hooks.provider_adapter import (
    AdapterError,
    CodexAdapter,
    OrcaRouterAdapter,
    ProviderConfigurationError,
    ProviderRequest,
    provider_from_name,
)


def request(**overrides):
    value = {
        "issue_id": "ISSUE-2026-0003",
        "run_id": "RUN-20260824-0001",
        "attempt": 1,
        "role": "chair",
        "prompt": '{"status":"COMPLETED"}',
        "model": "test-model",
        "expect_json": True,
    }
    value.update(overrides)
    return ProviderRequest(**value)


class TestCodexAdapter(unittest.TestCase):
    def test_builds_noninteractive_command(self):
        adapter = CodexAdapter(executable="codex-test")
        command = adapter.build_command(request(output_schema="schema.json"))
        self.assertEqual(command[:6], ["codex-test", "exec", "--json", "--ephemeral", "--sandbox", "read-only"])
        self.assertIn("--output-schema", command)
        self.assertEqual(command[-1], "-")
        self.assertNotIn('{"status":"COMPLETED"}', command)

    def test_prompt_is_sent_on_stdin(self):
        seen = {}

        def fake_run(command, **kwargs):
            seen.update(kwargs)
            return subprocess.CompletedProcess(command, 0, '{"type":"final","text":"{}"}\n', "")

        CodexAdapter(runner=fake_run).execute(request(prompt='{"long":"context"}'))
        self.assertEqual(seen["input"], '{"long":"context"}')

    def test_full_access_sandbox_is_rejected(self):
        with self.assertRaises(ProviderConfigurationError):
            CodexAdapter(sandbox="danger-full-access")

    def test_parses_final_jsonl_event(self):
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"type":"thread.started"}\n'
            '{"type":"item.completed","item":{"type":"agent_message","text":"{\\"status\\":\\"COMPLETED\\"}"}}\n',
            stderr="",
        )
        adapter = CodexAdapter(runner=lambda *args, **kwargs: completed)
        result = adapter.execute(request())
        self.assertEqual(result.provider, "codex")
        self.assertEqual(result.structured, {"status": "COMPLETED"})
        self.assertEqual(result.event_count, 2)

    def test_nonzero_exit_does_not_expose_output(self):
        completed = subprocess.CompletedProcess([], 2, "secret output", "")
        adapter = CodexAdapter(runner=lambda *args, **kwargs: completed)
        with self.assertRaisesRegex(AdapterError, "code 2") as raised:
            adapter.execute(request())
        self.assertNotIn("secret output", str(raised.exception))


class _Response:
    def __init__(self, body):
        self.body = body
        self.closed = False

    def read(self):
        return self.body

    def close(self):
        self.closed = True


class TestOrcaRouterAdapter(unittest.TestCase):
    def test_requires_api_key(self):
        with self.assertRaises(ProviderConfigurationError):
            OrcaRouterAdapter(api_key="")

    def test_sends_openai_compatible_payload(self):
        seen = {}
        response = _Response(json.dumps({
            "model": "route-model",
            "choices": [{"message": {"content": '{"ok":true}'}}],
            "usage": {"total_tokens": 7},
        }).encode())

        def opener(http_request, timeout):
            seen["url"] = http_request.full_url
            seen["payload"] = json.loads(http_request.data.decode())
            seen["timeout"] = timeout
            return response

        adapter = OrcaRouterAdapter(api_key="do-not-log", model="fallback", opener=opener)
        result = adapter.execute(request(model=None, system_prompt="Return JSON."))
        self.assertEqual(seen["url"], "https://api.orcarouter.ai/v1/chat/completions")
        self.assertEqual(seen["payload"]["model"], "fallback")
        self.assertEqual(seen["payload"]["messages"][0]["role"], "system")
        self.assertEqual(result.structured, {"ok": True})
        self.assertEqual(result.usage["total_tokens"], 7)
        self.assertTrue(response.closed)
        self.assertNotIn("do-not-log", str(result))

    def test_rejects_malformed_response(self):
        adapter = OrcaRouterAdapter(api_key="key", model="model", opener=lambda *args, **kwargs: _Response(b"{}"))
        with self.assertRaises(AdapterError):
            adapter.execute(request())


class TestProviderFactory(unittest.TestCase):
    def test_factory_supports_two_explicit_providers(self):
        self.assertIsInstance(provider_from_name("Codex"), CodexAdapter)
        self.assertIsInstance(provider_from_name("OrcaRouter", api_key="key", model="m"), OrcaRouterAdapter)

    def test_factory_rejects_unknown_provider(self):
        with self.assertRaises(ProviderConfigurationError):
            provider_from_name("claude-code")


if __name__ == "__main__":
    unittest.main()
