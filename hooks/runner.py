#!/usr/bin/env python3
"""Provider-neutral Council RUN transition kernel.

Usage:
  runner.py BEFORE.json AFTER.json            validate one transition (legacy form)
  runner.py start --issue-id ISSUE-... --run-id RUN-... [--research-mode NONE|LOCAL|WEB]
  runner.py apply --stage STAGE [--output KEY=PATH] [--increment COUNTER] [--status S]
                  [--next-action A] [--audit-result R] [--research-mode M]
  runner.py release --reason TEXT             mark a stuck RUNNING run as FAILED
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone
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
DEFAULT_BUDGET = {"max_research_revisions": 2, "max_recritiques": 2, "max_audit_revisions": 2}
ACTIVE_RUN_RELATIVE = Path(".council") / "active_run.json"
SNAPSHOT_RELATIVE = Path(".council") / "active_run.snapshot.json"
TRANSITION_LOG_NAME = "transition_log.jsonl"


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
    current = before["current_stage"]
    next_stage = after["current_stage"]
    # The chair selects the research mode (ROLE_RULES.md §2), so it may be set on the
    # issue-intake -> chair-review transition and is fixed afterwards.
    mode_locked = not (current == "issue-intake" and next_stage == "chair-review")
    if mode_locked and before["research_mode"] != after["research_mode"]:
        raise TransitionError("research_mode can only be set by chair-review")
    if before.get("content_audit_required", False) != after.get("content_audit_required", False):
        raise TransitionError("content_audit_required cannot change during a RUN")
    validate_counters(after)
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
        used_before = before.get("counters", {}).get(counter, 0)
        used_after = after.get("counters", {}).get(counter, 0)
        # audit_revisions counts re-audits after a send-back, not the first audit.
        first_audit = next_stage == "content-audit" and before.get("audit_result") is None
        if first_audit and used_after != used_before:
            raise TransitionError("the first content-audit must not consume audit_revisions")
        if not first_audit and used_after <= used_before:
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


def _claude_code_version() -> str:
    import re

    match = re.search(r"(\d+\.\d+\.\d+)", os.environ.get("CLAUDE_CODE_EXECPATH", ""))
    return match.group(1) if match else "unknown"


def append_transition_log(root: Path, before: Mapping[str, Any] | None, after: Mapping[str, Any], *,
                          event: str = "transition", note: str | None = None) -> Path:
    """Append one transition record to runs/private/<RUN-ID>/transition_log.jsonl."""
    run_id = str(after.get("run_id", ""))
    if not run_id or any(ch in run_id for ch in "/\\") or ".." in run_id:
        raise TransitionError("run_id is not usable as a directory name")
    log_path = root / "runs" / "private" / run_id / TRANSITION_LOG_NAME
    log_path.parent.mkdir(parents=True, exist_ok=True)
    before_outputs = dict(before.get("outputs", {})) if before else {}
    after_outputs = dict(after.get("outputs", {}))
    record = {
        "at": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "from": before.get("current_stage") if before else None,
        "to": after.get("current_stage"),
        "status": after.get("status"),
        "next_action": after.get("next_action"),
        "audit_result": after.get("audit_result"),
        "counters": after.get("counters"),
        "outputs_changed": {k: v for k, v in after_outputs.items() if before_outputs.get(k) != v},
        "claude_code_version": _claude_code_version(),
    }
    if note:
        record["note"] = note
    with _exclusive_lock(log_path.parent / ".transition_log.lock"):
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")
    return log_path


def _commit(root: Path, before: Mapping[str, Any] | None, after: dict[str, Any], *, event: str,
            note: str | None = None) -> None:
    save_state(root / ACTIVE_RUN_RELATIVE, after)
    save_state(root / SNAPSHOT_RELATIVE, after)
    append_transition_log(root, before, after, event=event, note=note)


def start_run(root: Path, *, issue_id: str, run_id: str, research_mode: str = "NONE",
              content_audit_required: bool = False, budget: Mapping[str, int] | None = None,
              output: str | None = None) -> dict[str, Any]:
    path = root / ACTIVE_RUN_RELATIVE
    if path.is_file():
        existing = load_state(path)
        if existing.get("status") == "RUNNING":
            raise TransitionError(f"{existing.get('run_id')} is still RUNNING; complete it or release it first")
    state: dict[str, Any] = {
        "issue_id": issue_id,
        "run_id": run_id,
        "research_mode": research_mode,
        "current_stage": "issue-intake",
        "status": "RUNNING",
        "next_action": "CONTINUE",
        "content_audit_required": content_audit_required,
        "deliberation_budget": dict(budget or DEFAULT_BUDGET),
        "counters": {"research_revisions": 0, "recritiques": 0, "audit_revisions": 0},
        "runtime": {"claude_code_version": _claude_code_version()},
        "outputs": {"issue_intake": output} if output else {},
    }
    _require_state(state)
    validate_counters(state)
    _commit(root, None, state, event="start")
    return state


def apply_transition(root: Path, *, stage: str, outputs: Mapping[str, str] | None = None,
                     increment: str | None = None, status: str | None = None, next_action: str | None = None,
                     audit_result: str | None = None, research_mode: str | None = None,
                     note: str | None = None) -> dict[str, Any]:
    before = load_state(root / ACTIVE_RUN_RELATIVE)
    after = copy.deepcopy(before)
    after["current_stage"] = stage
    after.setdefault("outputs", {}).update(outputs or {})
    if increment:
        after.setdefault("counters", {})[increment] = after["counters"].get(increment, 0) + 1
    if status:
        after["status"] = status
    if next_action:
        after["next_action"] = next_action
    if audit_result:
        after["audit_result"] = audit_result
    if research_mode:
        after["research_mode"] = research_mode
    validate_transition(before, after)
    _commit(root, before, after, event="transition", note=note)
    return after


def release_run(root: Path, *, reason: str) -> dict[str, Any]:
    if not reason.strip():
        raise TransitionError("a release reason is required")
    before = load_state(root / ACTIVE_RUN_RELATIVE)
    if before.get("status") != "RUNNING":
        raise TransitionError("only a RUNNING run can be released")
    after = copy.deepcopy(before)
    after.update(status="FAILED", next_action="CONTINUE", released_reason=reason,
                 released_at=datetime.now(timezone.utc).isoformat())
    _commit(root, before, after, event="release", note=reason)
    return after


def _parse_outputs(values: list[str]) -> dict[str, str]:
    outputs = {}
    for value in values:
        key, sep, path = value.partition("=")
        if not sep or not key or not path:
            raise TransitionError(f"--output must be KEY=PATH: {value}")
        outputs[key] = path.replace("\\", "/")
    return outputs


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        if argv and argv[0] in {"start", "apply", "release"}:
            parser = argparse.ArgumentParser(description="Apply a validated Council RUN transition.")
            parser.add_argument("command", choices=("start", "apply", "release"))
            parser.add_argument("--root", type=Path, default=Path("."))
            parser.add_argument("--issue-id")
            parser.add_argument("--run-id")
            parser.add_argument("--stage")
            parser.add_argument("--output", action="append", default=[])
            parser.add_argument("--increment", choices=("research_revisions", "recritiques", "audit_revisions"))
            parser.add_argument("--status")
            parser.add_argument("--next-action")
            parser.add_argument("--audit-result", choices=("PASS", "PASS_WITH_WARNINGS", "REVISE", "BLOCK"))
            parser.add_argument("--research-mode", choices=("NONE", "LOCAL", "WEB"))
            parser.add_argument("--content-audit-required", action="store_true")
            parser.add_argument("--reason", default="")
            parser.add_argument("--note")
            args = parser.parse_args(argv)
            root = args.root.resolve()
            if args.command == "start":
                if not args.issue_id or not args.run_id:
                    raise TransitionError("start requires --issue-id and --run-id")
                outputs = _parse_outputs(args.output)
                state = start_run(root, issue_id=args.issue_id, run_id=args.run_id,
                                  research_mode=args.research_mode or "NONE",
                                  content_audit_required=args.content_audit_required,
                                  output=outputs.get("issue_intake"))
            elif args.command == "apply":
                if not args.stage:
                    raise TransitionError("apply requires --stage")
                state = apply_transition(root, stage=args.stage, outputs=_parse_outputs(args.output),
                                         increment=args.increment, status=args.status,
                                         next_action=args.next_action, audit_result=args.audit_result,
                                         research_mode=args.research_mode, note=args.note)
            else:
                state = release_run(root, reason=args.reason)
            print(f"PASS {state['current_stage']} {state['status']} {state.get('counters')}")
            return 0
        parser = argparse.ArgumentParser(description="Validate a Council RUN state transition.")
        parser.add_argument("before", type=Path)
        parser.add_argument("after", type=Path)
        args = parser.parse_args(argv)
        validate_transition(load_state(args.before), load_state(args.after))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[BLOCK] {exc}", file=sys.stderr)
        return 2
    print("PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
