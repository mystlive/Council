#!/usr/bin/env python3
"""Validate and apply explicitly human-approved formal record changes."""
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import unified_diff
from pathlib import Path
from typing import Any, Mapping


DECISION_RE = re.compile(r"^DEC-\d{4}-\d{4}$")
RECORD_ROOT = Path("records")
STATE_STATUSES = {
    "adopted": {"ADOPTED", "SUPERSEDED", "EXPIRED"},
    "pending": {"PENDING"},
    "rejected": {"REJECTED"},
}
COMMON_REQUIRED = {
    "id", "record_type", "status", "issue_id", "title", "scope",
    "created_at", "updated_at", "approved_by", "approved_at",
}
APPROVAL_REL = Path(".council/record_update_approval.json")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class RecordUpdateError(RuntimeError):
    """A formal record or approval failed deterministic validation."""


@dataclass(frozen=True)
class RecordChange:
    source: str
    destination: str
    record_id: str
    operation: str
    diff: str


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise RecordUpdateError("record must start with YAML frontmatter")
    try:
        end = next(index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---")
    except StopIteration as exc:
        raise RecordUpdateError("record frontmatter is not closed") from exc
    fields: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            raise RecordUpdateError("record frontmatter contains a malformed line")
        key, value = line.split(":", 1)
        key = key.strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            raise RecordUpdateError("record frontmatter contains an invalid key")
        if key in fields:
            raise RecordUpdateError(f"duplicate frontmatter key: {key}")
        fields[key] = value.strip().strip('"').strip("'")
    return fields


def _expected_statuses(state_dir: str) -> set[str]:
    try:
        return STATE_STATUSES[state_dir.lower()]
    except KeyError as exc:
        raise RecordUpdateError(f"unsupported record state directory: {state_dir}") from exc


def validate_record_text(text: str, *, state_dir: str, expected_id: str | None = None) -> dict[str, str]:
    fields = _parse_frontmatter(text)
    missing = sorted(COMMON_REQUIRED - fields.keys())
    if missing:
        raise RecordUpdateError(f"record is missing required fields: {', '.join(missing)}")
    record_id = fields["id"]
    if not DECISION_RE.fullmatch(record_id):
        raise RecordUpdateError("record id has an invalid format")
    if expected_id is not None and record_id != expected_id:
        raise RecordUpdateError("record id does not match the target filename")
    if fields["record_type"] != "decision":
        raise RecordUpdateError("record_type must be decision")
    if fields["status"] not in _expected_statuses(state_dir):
        raise RecordUpdateError("record status does not match its state directory")
    for key in ("issue_id", "title", "scope", "created_at", "updated_at"):
        if not fields[key].strip():
            raise RecordUpdateError(f"{key} must not be empty")
    return fields


def _safe_record_path(root: Path, value: str | Path) -> Path:
    path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    records = (root / RECORD_ROOT).resolve()
    try:
        path.relative_to(records)
    except ValueError as exc:
        raise RecordUpdateError("formal record path must stay under records/") from exc
    if path.suffix.lower() != ".md" or path.parent.name not in STATE_STATUSES:
        raise RecordUpdateError("formal record path must be records/<state>/<DECISION-ID>.md")
    if not DECISION_RE.fullmatch(path.stem):
        raise RecordUpdateError("formal record filename must contain a DECISION-ID")
    return path


def inspect_change(before: str | None, after: str, *, source: str | Path, destination: str | Path, root: Path) -> RecordChange:
    destination_path = _safe_record_path(root, destination)
    source_path = _safe_record_path(root, source)
    destination_state = destination_path.parent.name
    after_fields = validate_record_text(after, state_dir=destination_state, expected_id=destination_path.stem)
    before_fields: dict[str, str] | None = None
    if before is not None:
        before_fields = validate_record_text(before, state_dir=source_path.parent.name, expected_id=source_path.stem)
        if before_fields["id"] != after_fields["id"]:
            raise RecordUpdateError("record id cannot change during an update")
    if before is None and source_path != destination_path:
        raise RecordUpdateError("a move requires an existing source record")
    operation = "create" if before is None else "update" if source_path == destination_path else "move"
    diff = "".join(unified_diff((before or "").splitlines(True), after.splitlines(True),
                                 fromfile=str(source_path), tofile=str(destination_path)))
    source_rel = source_path.relative_to(root.resolve()).as_posix()
    destination_rel = destination_path.relative_to(root.resolve()).as_posix()
    return RecordChange(source_rel, destination_rel, after_fields["id"], operation, diff)


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _validate_approval(approval: Mapping[str, Any], change: RecordChange, source_hash: str | None) -> None:
    if approval.get("used") is not False:
        raise RecordUpdateError("record update approval must be unused")
    if approval.get("record_id") != change.record_id:
        raise RecordUpdateError("approval record_id does not match the change")
    if approval.get("operation") != change.operation:
        raise RecordUpdateError("approval operation does not match the change")
    if approval.get("source_path") != change.source or approval.get("destination_path") != change.destination:
        raise RecordUpdateError("approval paths do not match the change")
    for field in ("approved_by", "reason"):
        if not isinstance(approval.get(field), str) or not approval[field].strip():
            raise RecordUpdateError(f"approval {field} is required")
    if _parse_datetime(approval.get("approved_at")) is None or _parse_datetime(approval.get("expires_at")) is None:
        raise RecordUpdateError("approval timestamps must be valid ISO-8601 values")
    if datetime.now(timezone.utc) >= _parse_datetime(approval["expires_at"]):
        raise RecordUpdateError("record update approval has expired")
    expected = approval.get("expected_source_sha256")
    if source_hash is None:
        if expected is not None:
            raise RecordUpdateError("create approval must not contain expected_source_sha256")
    elif not isinstance(expected, str) or not SHA256_RE.fullmatch(expected) or expected.lower() != source_hash:
        raise RecordUpdateError("source hash does not match record update approval")


def apply_approved_update(root: Path, source: str | Path, destination: str | Path, after: str) -> RecordChange:
    """Apply one approved create, update, or state move atomically.

    The approval file is consumed by marking it used after the target write.
    This proves the workflow consumed an approval, but does not prove the
    identity of the person who authored the approval file.
    """
    source_path = _safe_record_path(root, source)
    destination_path = _safe_record_path(root, destination)
    source_bytes = source_path.read_bytes() if source_path.is_file() else None
    try:
        before = source_bytes.decode("utf-8") if source_bytes is not None else None
    except UnicodeDecodeError as exc:
        raise RecordUpdateError("source record must be UTF-8") from exc
    change = inspect_change(before, after, source=source_path, destination=destination_path, root=root)
    approval_path = root / APPROVAL_REL
    if not approval_path.is_file():
        raise RecordUpdateError("human record update approval is required")
    try:
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RecordUpdateError("record update approval is not valid JSON") from exc
    if not isinstance(approval, Mapping):
        raise RecordUpdateError("record update approval must be an object")
    _validate_approval(approval, change, sha256_bytes(source_bytes) if source_bytes is not None else None)
    if change.operation in {"create", "move"} and destination_path.exists():
        raise RecordUpdateError("record destination already exists")
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    if change.operation == "move":
        source_path.replace(destination_path)
    else:
        fd, temporary = tempfile.mkstemp(prefix=f".{destination_path.name}.", dir=destination_path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as stream:
                stream.write(after)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
    consumed = dict(approval)
    consumed["used"] = True
    consumed["consumed_at"] = datetime.now(timezone.utc).isoformat()
    approval_path.write_text(json.dumps(consumed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return change
