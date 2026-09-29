#!/usr/bin/env python3
"""Append-only storage helpers for content-audit results."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

try:
    from id_allocator import _exclusive_lock
except ModuleNotFoundError:  # pragma: no cover - supports package imports in tests
    from hooks.id_allocator import _exclusive_lock


RUN_RE = re.compile(r"^RUN-\d{8}-\d{4}$")
AUDIT_NAME_RE = re.compile(r"^content_audit(?:-(\d{2}))?\.json$")
AUDIT_RESULTS = {"PASS", "PASS_WITH_WARNINGS", "REVISE", "BLOCK"}


def is_audit_artifact(path: Path, root: Path) -> bool:
    """Return whether ``path`` is a content-audit JSON in private RUN storage."""
    try:
        relative = path.resolve().relative_to((root / "runs" / "private").resolve())
    except ValueError:
        return False
    return bool(AUDIT_NAME_RE.fullmatch(relative.name))


def append_audit(
    payload: Mapping[str, Any],
    *,
    root: Path,
    run_id: str,
    attempt: int,
) -> Path:
    """Write a new numbered audit result without replacing an existing result."""
    if not RUN_RE.fullmatch(run_id):
        raise ValueError("run_id has an invalid format")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    if not isinstance(payload, Mapping):
        raise ValueError("audit payload must be an object")
    result = payload.get("result")
    if result not in AUDIT_RESULTS:
        raise ValueError("audit payload result is invalid")

    root = root.resolve()
    attempt_dir = root / "runs" / "private" / run_id / f"attempt-{attempt:02d}"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    lock_path = attempt_dir / ".content_audit.lock"
    with _exclusive_lock(lock_path):
        sequence = 1
        while True:
            destination = attempt_dir / f"content_audit-{sequence:02d}.json"
            try:
                descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            except FileExistsError:
                sequence += 1
                continue
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                record = dict(payload)
                record["audit_sequence"] = sequence
                record["append_only"] = True
                json.dump(record, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            return destination


def latest_audit(attempt_dir: Path) -> tuple[Path, dict[str, Any]] | None:
    """Return the newest audit pass in ``attempt_dir`` (legacy content_audit.json counts as pass 0)."""
    newest: tuple[int, Path, dict[str, Any]] | None = None
    if not attempt_dir.is_dir():
        return None
    for path in attempt_dir.iterdir():
        match = AUDIT_NAME_RE.fullmatch(path.name)
        if not match or not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        sequence = int(match.group(1)) if match.group(1) else 0
        if newest is None or sequence > newest[0]:
            newest = (sequence, path, payload)
    return (newest[1], newest[2]) if newest else None


def audit_result_was_rewritten(payload: Mapping[str, Any]) -> bool:
    """Detect a legacy record whose final result hides an unresolved last pass."""
    passes = payload.get("audit_passes")
    final_result = payload.get("result")
    if not isinstance(passes, list) or not passes or final_result not in {"PASS", "PASS_WITH_WARNINGS"}:
        return False
    last = passes[-1]
    return isinstance(last, Mapping) and last.get("result") in {"REVISE", "BLOCK"}
