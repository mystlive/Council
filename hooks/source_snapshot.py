#!/usr/bin/env python3
"""Immutable source snapshots and CLAIM-to-SOURCE relationship validation."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SOURCE_RE = re.compile(r"^SRC-\d{4}-\d{4}$")
CLAIM_RE = re.compile(r"^CLAIM-\d{4}-\d{4}$")
RELATIONS = {"SUPPORTS_CLAIM", "CONTRADICTS_CLAIM", "PARTIAL", "OUTDATED"}
SOURCE_REQUIRED = {"source_id", "title", "retrieved_at", "content_hash", "verification_status"}


class SourceSnapshotError(RuntimeError):
    """A source snapshot or claim relationship failed validation."""


@dataclass(frozen=True)
class SourceSnapshot:
    source_id: str
    title: str
    retrieved_at: str
    content_hash: str
    snapshot_path: str
    verification_status: str = "UNCHECKED"


@dataclass(frozen=True)
class ClaimLink:
    claim_id: str
    claim: str
    source_ids: tuple[str, ...]
    relation: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise SourceSnapshotError("retrieved_at must be ISO-8601") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def validate_source_record(record: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted(SOURCE_REQUIRED - record.keys())
    if missing:
        raise SourceSnapshotError(f"source record is missing: {', '.join(missing)}")
    source_id = record["source_id"]
    if not isinstance(source_id, str) or not SOURCE_RE.fullmatch(source_id):
        raise SourceSnapshotError("source_id has an invalid format")
    for field in ("title", "retrieved_at", "content_hash", "verification_status"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise SourceSnapshotError(f"{field} must be a non-empty string")
    _timestamp(record["retrieved_at"])
    if not re.fullmatch(r"[0-9a-fA-F]{64}", record["content_hash"]):
        raise SourceSnapshotError("content_hash must be a SHA-256 hex digest")
    return dict(record)


def create_snapshot(path: Path, content: bytes, *, source_id: str, title: str,
                    retrieved_at: str, verification_status: str = "UNCHECKED") -> SourceSnapshot:
    """Write a snapshot once and reject any later content rewrite."""
    if not SOURCE_RE.fullmatch(source_id):
        raise SourceSnapshotError("source_id has an invalid format")
    _timestamp(retrieved_at)
    digest = sha256_bytes(content)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = path.read_bytes()
        if existing != content:
            raise SourceSnapshotError("source snapshot is immutable and already contains different content")
    else:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(content)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    return SourceSnapshot(source_id, title, retrieved_at, digest, path.as_posix(), verification_status)


def link_claim(claim_id: str, claim: str, source_ids: Sequence[str], relation: str) -> ClaimLink:
    if not CLAIM_RE.fullmatch(claim_id):
        raise SourceSnapshotError("claim_id has an invalid format")
    if not isinstance(claim, str) or not claim.strip():
        raise SourceSnapshotError("claim must be a non-empty string")
    normalized = tuple(dict.fromkeys(source_ids))
    if not normalized or any(not SOURCE_RE.fullmatch(value) for value in normalized):
        raise SourceSnapshotError("source_ids must contain at least one valid SOURCE-ID")
    if relation not in RELATIONS:
        raise SourceSnapshotError("relation is not allowed")
    return ClaimLink(claim_id, claim, normalized, relation)


def append_jsonl(path: Path, value: Mapping[str, Any]) -> None:
    """Append a validated registry event without rewriting prior events."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="") as stream:
        stream.write(json.dumps(dict(value), ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
