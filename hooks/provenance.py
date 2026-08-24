#!/usr/bin/env python3
"""Hybrid public/private RUN provenance manifests."""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

try:
    from id_allocator import _exclusive_lock
except ModuleNotFoundError:  # pragma: no cover - supports package imports in tests
    from hooks.id_allocator import _exclusive_lock


RUN_RE = re.compile(r"^RUN-\d{8}-\d{4}$")
ISSUE_RE = re.compile(r"^ISSUE-\d{4}-\d{4}$")
PUBLIC_ALLOWED_KEYS = {
    "runner_version",
    "provenance_version",
    "status",
    "current_stage",
    "next_action",
    "budget",
    "counters",
    "audit_result",
    "artifact_hashes",
    "generated_at",
}
FORBIDDEN_PUBLIC_TOKENS = {
    "prompt",
    "model",
    "input",
    "output",
    "cost",
    "evidence",
    "secret",
    "token",
    "personal",
    "private",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_identity(run_id: str, issue_id: str, attempt: int) -> None:
    if not RUN_RE.fullmatch(run_id):
        raise ValueError("run_id has an invalid format")
    if not ISSUE_RE.fullmatch(issue_id):
        raise ValueError("issue_id has an invalid format")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ValueError("attempt must be a positive integer")


def _contains_forbidden_key(value: Any) -> str | None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            lowered = str(key).lower()
            if any(token in lowered for token in FORBIDDEN_PUBLIC_TOKENS):
                return str(key)
            found = _contains_forbidden_key(nested)
            if found:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _contains_forbidden_key(nested)
            if found:
                return found
    return None


def sanitize_public_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("public manifest payload must be an object")
    unknown = set(payload) - PUBLIC_ALLOWED_KEYS
    if unknown:
        raise ValueError(f"public manifest contains undeclared fields: {sorted(unknown)}")
    forbidden = _contains_forbidden_key(payload)
    if forbidden:
        raise ValueError(f"public manifest contains a forbidden field: {forbidden}")
    result = dict(payload)
    hashes = result.get("artifact_hashes", [])
    if not isinstance(hashes, list):
        raise ValueError("artifact_hashes must be an array")
    for item in hashes:
        if not isinstance(item, Mapping) or set(item) != {"name", "sha256"}:
            raise ValueError("artifact_hashes entries must contain only name and sha256")
        if not isinstance(item["name"], str) or not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("artifact_hashes entries must contain a name and lowercase SHA-256")
    return result


def _write_exclusive(path: Path, value: Mapping[str, Any]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_manifests(
    *,
    root: Path,
    issue_id: str,
    run_id: str,
    attempt: int,
    public_payload: Mapping[str, Any],
    private_payload: Mapping[str, Any],
    generated_at: str | None = None,
) -> tuple[Path, Path]:
    """Create immutable public and private manifests as one logical operation."""
    _validate_identity(run_id, issue_id, attempt)
    if not isinstance(private_payload, Mapping):
        raise ValueError("private manifest payload must be an object")
    public = sanitize_public_payload(public_payload)
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    root = root.resolve()
    public_dir = root / "runs" / "public"
    private_dir = root / "runs" / "private" / run_id / f"attempt-{attempt:02d}"
    public_dir.mkdir(parents=True, exist_ok=True)
    private_dir.mkdir(parents=True, exist_ok=True)
    public_path = public_dir / f"{run_id}.json"
    private_path = private_dir / "run_manifest.json"
    lock_path = root / ".council" / "provenance.lock"
    with _exclusive_lock(lock_path):
        if public_path.exists() or private_path.exists():
            raise FileExistsError("RUN manifest already exists and is immutable")
        private_record = dict(private_payload)
        private_record.update({
            "schema_version": "1.0",
            "manifest_type": "private-run-manifest",
            "issue_id": issue_id,
            "run_id": run_id,
            "attempt": attempt,
            "generated_at": timestamp,
        })
        temporary = private_path.with_name(f".{private_path.name}.{os.getpid()}.tmp")
        _write_exclusive(temporary, private_record)
        try:
            public_record = dict(public)
            public_record.update({
                "schema_version": "1.0",
                "manifest_type": "public-run-manifest",
                "issue_id": issue_id,
                "run_id": run_id,
                "attempt": attempt,
                "generated_at": timestamp,
                "private_manifest_sha256": sha256_file(temporary),
            })
            _write_exclusive(public_path, public_record)
            os.replace(temporary, private_path)
        finally:
            if temporary.exists():
                temporary.unlink()
    return public_path, private_path
