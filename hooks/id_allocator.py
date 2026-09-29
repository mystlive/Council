#!/usr/bin/env python3
"""Atomic CouncilSystem identifier allocation."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator


KINDS = {
    "ISSUE": "ISSUE",
    "RUN": "RUN",
    "SOURCE": "SRC",
    "DECISION": "DEC",
    "CLAIM": "CLAIM",
}
REGISTRY_NAME = "id_registry.json"
LOCK_RELATIVE = Path(".council") / "id_registry.lock"
COUNT_RE = re.compile(r"^[A-Z]+$")


@contextmanager
def _exclusive_lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0)
        handle.write(b"0")
        handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _load_registry(path: Path) -> dict[str, int]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"registry does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"registry is invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError("registry root must be an object")
    registry: dict[str, int] = {}
    for key, count in value.items():
        if not isinstance(key, str) or not COUNT_RE.fullmatch(key):
            raise ValueError(f"registry key is invalid: {key!r}")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise ValueError(f"registry count is invalid for {key}")
        registry[key] = count
    return registry


def _atomic_write(path: Path, value: dict[str, int]) -> None:
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _allocate_run(registry: dict[str, int], root: Path, moment: datetime) -> str:
    """RUN-IDs use the local date and a per-day sequence (RUN-YYYYMMDD-NNNN), matching the
    format that validate.py, artifact_schema.py, audit_store.py and provenance.py require.
    ``RUN`` keeps the all-time count; ``RUNDAY``/``RUNSEQ`` hold the per-day sequence."""
    day = int(moment.strftime("%Y%m%d"))
    sequence = registry.get("RUNSEQ", 0) if registry.get("RUNDAY") == day else 0
    while True:
        sequence += 1
        run_id = f"RUN-{day:08d}-{sequence:04d}"
        if not (root / "runs" / "private" / run_id).exists():
            break
    registry["RUNDAY"] = day
    registry["RUNSEQ"] = sequence
    registry["RUN"] = registry.get("RUN", 0) + 1
    return run_id


def allocate(kind: str, *, root: Path = Path("."), now: datetime | None = None) -> str:
    """Allocate and persist the next identifier for ``kind``."""
    normalized = kind.upper()
    if normalized not in KINDS:
        raise ValueError(f"unknown identifier kind: {kind}")
    root = root.resolve()
    registry_path = root / REGISTRY_NAME
    lock_path = root / LOCK_RELATIVE
    moment = now or datetime.now(timezone.utc).astimezone()
    with _exclusive_lock(lock_path):
        registry = _load_registry(registry_path)
        if normalized == "RUN":
            run_id = _allocate_run(registry, root, moment)
            _atomic_write(registry_path, registry)
            return run_id
        next_number = registry.get(normalized, 0) + 1
        registry[normalized] = next_number
        _atomic_write(registry_path, registry)
    prefix = KINDS[normalized]
    return f"{prefix}-{moment.year:04d}-{next_number:04d}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Allocate a CouncilSystem identifier.")
    parser.add_argument("kind", choices=sorted(KINDS), help="identifier kind")
    parser.add_argument("--root", type=Path, default=Path("."), help="CouncilSystem root")
    args = parser.parse_args(argv)
    try:
        print(allocate(args.kind, root=args.root))
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
