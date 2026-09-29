#!/usr/bin/env python3
"""Provider-neutral adapters for Codex CLI and OrcaRouter.

The runner owns retries, budgets, and state transitions.
Adapters perform exactly one provider invocation and return an in-memory
response without writing prompts, tokens, or provider output to public files.
"""
from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping


class AdapterError(RuntimeError):
    """A provider invocation or response could not satisfy the adapter contract."""


class ProviderConfigurationError(AdapterError):
    """Required provider configuration is absent or invalid."""


@dataclass(frozen=True)
class ProviderRequest:
    """The single invocation contract shared by all provider adapters."""

    issue_id: str
    run_id: str
    attempt: int
    role: str
    prompt: str
    model: str | None = None
    system_prompt: str | None = None
    cwd: Path | None = None
    timeout_sec: float = 300.0
    output_schema: Path | None = None
    expect_json: bool = True

    def __post_init__(self) -> None:
        if not self.issue_id or not self.run_id or not self.role:
            raise ValueError("issue_id, run_id, and role are required")
        if not self.prompt.strip():
            raise ValueError("prompt must not be empty")
        if self.attempt < 1:
            raise ValueError("attempt must be positive")
        if self.timeout_sec <= 0:
            raise ValueError("timeout_sec must be positive")


@dataclass(frozen=True)
class ProviderResponse:
    """Normalized in-memory result of one provider invocation."""

    provider: str
    status: str
    text: str
    structured: Any = None
    model: str | None = None
    exit_code: int | None = None
    usage: Mapping[str, Any] = field(default_factory=dict)
    event_count: int = 0


def _parse_structured(text: str, expect_json: bool) -> Any:
    if not expect_json:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise AdapterError("provider response was not valid JSON") from exc


def _content_to_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, Mapping) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _extract_codex_event(event: Mapping[str, Any]) -> str:
    """Extract visible assistant text from known Codex JSONL event shapes."""
    event_type = event.get("type")
    item = event.get("item")
    if isinstance(item, Mapping) and item.get("type") in {"agent_message", "message", "assistant_message"}:
        text = _content_to_text(item.get("text", item.get("content")))
        if text:
            return text
    if event_type in {"message", "assistant", "agent_message", "final"}:
        text = _content_to_text(event.get("text", event.get("content", event.get("message"))))
        if text:
            return text
    if event_type in {"result", "turn.completed"}:
        for key in ("output", "result", "final_message", "text"):
            text = _content_to_text(event.get(key))
            if text:
                return text
    return ""


CODEX_SANDBOX_MODES = {"read-only", "workspace-write"}


class CodexAdapter:
    """Invoke the installed Codex CLI through its non-interactive exec mode.

    The prompt is passed on stdin (``-``) rather than argv, so long RUN context is not limited by the
    Windows command-line length and does not appear in process listings. The sandbox is always
    explicit; ``danger-full-access`` is not accepted.
    """

    provider_name = "codex"

    def __init__(self, executable: str = "codex", *, sandbox: str = "read-only",
                 runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run) -> None:
        if sandbox not in CODEX_SANDBOX_MODES:
            raise ProviderConfigurationError(f"unsupported Codex sandbox: {sandbox}")
        self.executable = executable
        self.sandbox = sandbox
        self._runner = runner

    def build_command(self, request: ProviderRequest) -> list[str]:
        command = [self.executable, "exec", "--json", "--ephemeral", "--sandbox", self.sandbox]
        if request.output_schema is not None:
            command.extend(["--output-schema", str(request.output_schema)])
        if request.model:
            command.extend(["--model", request.model])
        if request.cwd is not None:
            command.extend(["--cd", str(request.cwd)])
        command.append("-")
        return command

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        try:
            completed = self._runner(self.build_command(request), cwd=str(request.cwd) if request.cwd is not None else None,
                                     input=request.prompt, capture_output=True, text=True,
                                     timeout=request.timeout_sec, check=False)
        except (OSError, subprocess.SubprocessError) as exc:
            raise AdapterError(f"Codex invocation failed: {exc.__class__.__name__}") from exc
        if completed.returncode != 0:
            raise AdapterError(f"Codex exited with code {completed.returncode}")
        texts: list[str] = []
        event_count = 0
        usage: Mapping[str, Any] = {}
        for line in (completed.stdout or "").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, Mapping):
                continue
            event_count += 1
            text = _extract_codex_event(event)
            if text:
                texts.append(text)
            if isinstance(event.get("usage"), Mapping):
                usage = dict(event["usage"])
        text = texts[-1] if texts else (completed.stdout or "").strip()
        return ProviderResponse(provider=self.provider_name, status="COMPLETED", text=text,
                                structured=_parse_structured(text, request.expect_json), model=request.model,
                                exit_code=completed.returncode, usage=usage, event_count=event_count)


class OrcaRouterAdapter:
    """Call OrcaRouter's OpenAI-compatible chat completions endpoint.

    Frozen (ISSUE-2026-0003, HD-6): kept for compatibility but not extended. The operator entity and
    privacy policy could not be confirmed, request metadata is retained for 13 months, and upstream
    provider terms apply on top.
    """

    provider_name = "orcarouter"

    def __init__(self, *, api_key: str | None = None, api_key_env: str = "ORCAROUTER_API_KEY",
                 base_url: str = "https://api.orcarouter.ai/v1", model: str | None = None,
                 opener: Callable[..., Any] = urllib.request.urlopen) -> None:
        self.api_key = api_key or os.environ.get(api_key_env)
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._opener = opener
        if not self.api_key:
            raise ProviderConfigurationError(f"missing API key in {api_key_env}")

    def build_payload(self, request: ProviderRequest) -> dict[str, Any]:
        model = request.model or self.model
        if not model:
            raise ProviderConfigurationError("OrcaRouter model is required")
        messages: list[dict[str, str]] = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        messages.append({"role": "user", "content": request.prompt})
        return {"model": model, "messages": messages, "stream": False}

    def execute(self, request: ProviderRequest) -> ProviderResponse:
        payload = json.dumps(self.build_payload(request)).encode("utf-8")
        http_request = urllib.request.Request(f"{self.base_url}/chat/completions", data=payload,
                                               headers={"Authorization": f"Bearer {self.api_key}",
                                                        "Content-Type": "application/json"}, method="POST")
        try:
            response = self._opener(http_request, timeout=request.timeout_sec)
            try:
                body = response.read()
            finally:
                close = getattr(response, "close", None)
                if close:
                    close()
        except (urllib.error.URLError, OSError) as exc:
            raise AdapterError(f"OrcaRouter request failed: {exc.__class__.__name__}") from exc
        try:
            document = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
            message = document["choices"][0]["message"]
            text = _content_to_text(message.get("content"))
            if not text:
                raise KeyError("choices[0].message.content")
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise AdapterError("OrcaRouter response did not match chat completion shape") from exc
        usage = document.get("usage") if isinstance(document.get("usage"), Mapping) else {}
        return ProviderResponse(provider=self.provider_name, status="COMPLETED", text=text,
                                structured=_parse_structured(text, request.expect_json),
                                model=document.get("model") or request.model or self.model,
                                usage=dict(usage), event_count=1)


def provider_from_name(name: str, **kwargs: Any) -> CodexAdapter | OrcaRouterAdapter:
    """Construct one of the explicitly supported adapters."""
    normalized = name.strip().lower()
    if normalized == "codex":
        return CodexAdapter(**kwargs)
    if normalized in {"orca", "orcarouter"}:
        return OrcaRouterAdapter(**kwargs)
    raise ProviderConfigurationError(f"unsupported provider: {name}")
