#!/usr/bin/env python3
"""Append-only storage for Subagent raw returns.

The Council Runner saves each Subagent's returned text unchanged before summarizing or wrapping it
into a stage artifact, so later transcription can be checked against the original by SHA-256.

  python hooks/raw_output.py --run RUN-YYYYMMDD-NNNN --attempt 1 --role critic < returned.txt
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from pathlib import Path

try:
    from id_allocator import _exclusive_lock
except ModuleNotFoundError:  # pragma: no cover - supports package imports in tests
    from hooks.id_allocator import _exclusive_lock


RUN_RE = re.compile(r"^RUN-\d{8}-\d{4}$")
ROLE_RE = re.compile(r"^[a-z][a-z0-9-]{0,40}$")


def save_raw(text: str, *, root: Path, run_id: str, attempt: int, role: str) -> tuple[Path, str]:
    """Write ``text`` to runs/private/<RUN>/attempt-NN/raw/<role>-NN.txt without overwriting."""
    if not RUN_RE.fullmatch(run_id):
        raise ValueError("run_id has an invalid format")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    if not ROLE_RE.fullmatch(role):
        raise ValueError("role must be lowercase letters, digits or hyphens")
    if not text.strip():
        raise ValueError("raw output is empty")
    directory = root.resolve() / "runs" / "private" / run_id / f"attempt-{attempt:02d}" / "raw"
    directory.mkdir(parents=True, exist_ok=True)
    data = text.encode("utf-8")
    digest = hashlib.sha256(data).hexdigest()
    with _exclusive_lock(directory / ".raw.lock"):
        sequence = 1
        while True:
            destination = directory / f"{role}-{sequence:02d}.txt"
            try:
                descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
            except FileExistsError:
                sequence += 1
                continue
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(data)
            break
        with (directory / "SHA256SUMS").open("a", encoding="utf-8") as sums:
            sums.write(f"{digest}  {destination.name}\n")
    return destination, digest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Save a Subagent raw return (append-only).")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--run", required=True)
    parser.add_argument("--attempt", type=int, default=1)
    parser.add_argument("--role", required=True)
    parser.add_argument("--file", type=Path, help="read from this file instead of stdin")
    args = parser.parse_args(argv)
    try:
        # Read bytes: on Windows sys.stdin decodes with the console code page, not UTF-8.
        text = args.file.read_text(encoding="utf-8") if args.file else sys.stdin.buffer.read().decode("utf-8")
        path, digest = save_raw(text, root=args.root, run_id=args.run, attempt=args.attempt, role=args.role)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2
    print(f"{digest}  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
