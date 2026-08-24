#!/usr/bin/env python3
"""Retention evaluation and human-approved deletion for private artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


RUN_RE = re.compile(r"^RUN-\d{8}-\d{4}$")
ALLOWED_KINDS = {"detail", "manifest"}
TERMINAL_STATUSES = {"COMPLETED", "CONDITIONAL_COMPLETION", "BOUNDED_COMPLETION", "DEGRADED_COMPLETION", "FAILED", "BLOCKED"}
PRIVATE_ROOTS = (Path("runs/private"), Path("evidence/private"))
PUBLIC_RECEIPT_ROOT = Path("runs/public/retention")


class RetentionError(RuntimeError):
    """A retention target, plan, or approval failed validation."""


@dataclass(frozen=True)
class RetentionPolicy:
    detail_days: int = 90
    manifest_days: int = 365

    def __post_init__(self) -> None:
        if self.detail_days < 1 or self.manifest_days < 1:
            raise ValueError("retention periods must be positive")

    def days_for(self, kind: str) -> int:
        if kind == "detail":
            return self.detail_days
        if kind == "manifest":
            return self.manifest_days
        raise RetentionError(f"unsupported retention kind: {kind}")


@dataclass(frozen=True)
class RetentionTarget:
    relative_path: str
    run_id: str
    completed_at: str
    kind: str
    status: str
    legal_hold: bool = False


@dataclass(frozen=True)
class DeletionPlan:
    created_at: str
    targets: tuple[RetentionTarget, ...]
    plan_hash: str


def _parse_dt(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, ValueError) as exc:
        raise RetentionError("timestamp must be ISO-8601") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _target_path(root: Path, relative_path: str) -> Path:
    path = (root / relative_path).resolve()
    allowed = [(root / value).resolve() for value in PRIVATE_ROOTS]
    if not any(path != base and base in path.parents for base in allowed):
        raise RetentionError("deletion target must be below runs/private or evidence/private")
    if path.name in {"private", "runs", "evidence"}:
        raise RetentionError("deletion target is too broad")
    return path


def _target_dict(target: RetentionTarget) -> dict[str, Any]:
    return {
        "relative_path": target.relative_path,
        "run_id": target.run_id,
        "completed_at": target.completed_at,
        "kind": target.kind,
        "status": target.status,
        "legal_hold": target.legal_hold,
    }


def _canonical_targets(targets: Sequence[RetentionTarget]) -> bytes:
    return json.dumps([_target_dict(value) for value in targets], ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_deletion_plan(targets: Sequence[RetentionTarget], *, policy: RetentionPolicy, now: datetime | None = None) -> DeletionPlan:
    current = now or datetime.now(timezone.utc)
    normalized = tuple(targets)
    if not normalized:
        raise RetentionError("deletion plan must contain at least one target")
    for target in normalized:
        if not RUN_RE.fullmatch(target.run_id):
            raise RetentionError("target run_id has an invalid format")
        if target.kind not in ALLOWED_KINDS:
            raise RetentionError("target kind is not allowed")
        if target.status not in TERMINAL_STATUSES:
            raise RetentionError("only terminal RUNs may be deleted")
        if target.legal_hold:
            raise RetentionError(f"legal hold blocks deletion: {target.relative_path}")
        _parse_dt(target.completed_at)
        if current < _parse_dt(target.completed_at) + timedelta(days=policy.days_for(target.kind)):
            raise RetentionError(f"retention period has not elapsed for {target.relative_path}")
    created_at = current.astimezone(timezone.utc).isoformat()
    digest = hashlib.sha256(_canonical_targets(normalized)).hexdigest()
    return DeletionPlan(created_at, normalized, digest)


def execute_approved_deletion(root: Path, plan: DeletionPlan, approval: Mapping[str, Any], *, now: datetime | None = None) -> dict[str, Any]:
    """Delete only an eligible, exact plan approved by a human.

    This function deliberately does not discover targets or decide policy.
    The caller must provide a precomputed plan and a separate approval object.
    """
    if approval.get("used") is not False:
        raise RetentionError("deletion approval must be unused")
    if approval.get("plan_hash") != plan.plan_hash:
        raise RetentionError("deletion approval does not match the plan")
    if not isinstance(approval.get("approved_by"), str) or not approval["approved_by"].strip():
        raise RetentionError("approved_by is required")
    if not isinstance(approval.get("reason"), str) or not approval["reason"].strip():
        raise RetentionError("deletion reason is required")
    expires_at = _parse_dt(approval.get("expires_at", ""))
    current = now or datetime.now(timezone.utc)
    if current >= expires_at:
        raise RetentionError("deletion approval has expired")
    deleted: list[str] = []
    for target in plan.targets:
        if target.legal_hold:
            raise RetentionError(f"legal hold blocks deletion: {target.relative_path}")
        _target_path(root, target.relative_path)
        path = (root / target.relative_path).resolve()
        if not path.exists():
            raise RetentionError(f"deletion target is missing: {target.relative_path}")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        deleted.append(target.relative_path)
    return {
        "event_type": "PRIVATE_RETENTION_DELETION",
        "created_at": current.astimezone(timezone.utc).isoformat(),
        "plan_hash": plan.plan_hash,
        "approved_by": approval["approved_by"],
        "target_paths": deleted,
        "target_run_ids": sorted({target.run_id for target in plan.targets}),
    }


def write_public_receipt(root: Path, receipt: Mapping[str, Any]) -> Path:
    """Persist a sanitized deletion receipt without private content."""
    required = {"event_type", "created_at", "plan_hash", "approved_by", "target_paths", "target_run_ids"}
    if not required.issubset(receipt):
        raise RetentionError("deletion receipt is incomplete")
    if receipt["event_type"] != "PRIVATE_RETENTION_DELETION":
        raise RetentionError("invalid deletion receipt type")
    plan_hash = receipt["plan_hash"]
    if not isinstance(plan_hash, str) or not re.fullmatch(r"[0-9a-f]{64}", plan_hash):
        raise RetentionError("deletion receipt plan_hash must be SHA-256")
    receipt_root = root / PUBLIC_RECEIPT_ROOT
    receipt_root.mkdir(parents=True, exist_ok=True)
    path = receipt_root / f"{plan_hash[:16]}.json"
    payload = json.dumps(dict(receipt), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if path.exists():
        if path.read_text(encoding="utf-8") != payload:
            raise RetentionError("deletion receipt is immutable")
        return path
    path.write_text(payload, encoding="utf-8")
    return path
