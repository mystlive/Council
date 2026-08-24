#!/usr/bin/env python3
"""Provider-neutral Council RUN transition kernel."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

try:
    from id_allocator import _exclusive_lock
except ModuleNotFoundError:  # pragma: no cover - supports package imports in tests
    from hooks.id_allocator import _exclusive_lock


STAGES = {
    "issue-intake",
    "chair-review",
    "research",
    "research-revision",
    "devil-advocate",
    "devil-advocate-revision",
    "secretary",
    "formal-validation",
    "content-audit",
    "final-synthesis",
}
COMPLETION_STATUSES = {"COMPLETED", "CONDITIONAL_COMPLETION", "BOUNDED_COMPLETION", "DEGRADED_COMPLETION"}
REVISION_COUNTERS = {
    "research-revision": ("research_revisions", "max_research_revisions"),
    "devil-advocate-revision": ("recritiques", "max_recritiques"),
    "content-audit": ("audit_revisions", "max_audit_revisions"),
}


class TransitionError(ValueError):
    pass


def _require_state(state: Mapping[str, Any]) -> None:
    for field in ("issue_id", "run_id", "research_mode", "current_stage", "status", "next_action"):
        if field not in state:
            raise TransitionError(f"state is missing {field}")
    if state["current_stage"] not in STAGES:
        raise TransitionError(f"unknown current stage: {state['current_stage']}")
    if state["research_mode"] not in {"NONE", "LOCAL", "WEB"}:
        raise TransitionError("research_mode must be NONE, LOCAL, or WEB")


def allowed_next_stages(
    current: str,
    *,
    research_mode: str,
    content_audit_required: bool,
    audit_result: str | None = None,
) -> set[str]:
    """Return the deterministic next-stage set for one completed stage."""
    if current == "issue-intake":
        return {"chair-review"}
    if current == "chair-review":
        return {"research"} if research_mode in {"LOCAL", "WEB"} else {"devil-advocate"}
    if current == "research":
        return {"devil-advocate"}
    if current == "devil-advocate":
        return {"research-revision", "devil-advocate-revision", "secretary"}
    if current == "research-revision":
        return {"devil-advocate"}
    if current == "devil-advocate-revision":
        return {"secretary"}
    if current == "secretary":
        return {"formal-validation"}
    if current == "formal-validation":
        return {"content-audit"} if content_audit_required else {"final-synthesis"}
    if current == "content-audit":
        if audit_result in {"REVISE", "BLOCK"}:
            return {"secretary", "research", "devil-advocate"}
        return {"final-synthesis"}
    return set()


def validate_counters(state: Mapping[str, Any]) -> None:
    budget = state.get("deliberation_budget", {})
    counters = state.get("counters", {})
    if not isinstance(budget, Mapping) or not isinstance(counters, Mapping):
        raise TransitionError("deliberation_budget and counters must be objects")
    for counter, limit in REVISION_COUNTERS.values():
        used = counters.get(counter, 0)
        maximum = budget.get(limit)
        if not isinstance(used, int) or isinstance(used, bool) or used < 0:
            raise TransitionError(f"counter is invalid: {counter}")
        if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0:
            raise TransitionError(f"budget is invalid: {limit}")
        if used > maximum:
            raise TransitionError(f"budget exceeded: {counter}")


def validate_transition(before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    _require_state(before)
    _require_state(after)
    if before["issue_id"] != after["issue_id"] or before["run_id"] != after["run_id"]:
        raise TransitionError("issue_id and run_id cannot change during a RUN")
    if before["research_mode"] != after["research_mode"]:
        raise TransitionError("research_mode cannot change during a RUN")
    if before.get("content_audit_required", False) != after.get("content_audit_required", False):
        raise TransitionError("content_audit_required cannot change during a RUN")
    validate_counters(after)
    current = before["current_stage"]
    next_stage = after["current_stage"]
    if next_stage == current:
        return
    allowed = allowed_next_stages(
        current,
        research_mode=before["research_mode"],
        content_audit_required=bool(before.get("content_audit_required", False)),
        audit_result=before.get("audit_result"),
    )
    if next_stage not in allowed:
        raise TransitionError(f"invalid transition: {current} -> {next_stage}")
    if next_stage in REVISION_COUNTERS:
        counter, _ = REVISION_COUNTERS[next_stage]
        if after.get("counters", {}).get(counter, 0) <= before.get("counters", {}).get(counter, 0):
            raise TransitionError(f"revision transition must increment {counter}")
    if after["status"] in COMPLETION_STATUSES:
        if next_stage != "final-synthesis" or after["next_action"] != "COMPLETE":
            raise TransitionError("completion requires final-synthesis and COMPLETE")
    elif after["next_action"] == "COMPLETE":
        raise TransitionError("COMPLETE requires a completion status")


def load_state(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TransitionError("state root must be an object")
    return value


def save_state(path: Path, state: Mapping[str, Any]) -> None:
    if not isinstance(state, Mapping):
        raise TransitionError("state must be an object")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with _exclusive_lock(path.parent / "runner.lock"):
        temporary.write_text(json.dumps(dict(state), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Council RUN state transition.")
    parser.add_argument("before", type=Path)
    parser.add_argument("after", type=Path)
    args = parser.parse_args(argv)
    try:
        validate_transition(load_state(args.before), load_state(args.after))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[BLOCK] {exc}", file=sys.stderr)
        return 2
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
