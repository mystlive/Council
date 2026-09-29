#!/usr/bin/env python3
"""Deterministic validation for CouncilSystem JSON artifact envelopes."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePath
from typing import Any, Mapping


ISSUE_RE = re.compile(r"^ISSUE-\d{4}-\d{4}$")
RUN_RE = re.compile(r"^RUN-\d{8}-\d{4}$")
ALLOWED_STAGES = {
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
ALLOWED_STATUSES = {
    "RUNNING",
    "COMPLETED",
    "CONDITIONAL_COMPLETION",
    "BOUNDED_COMPLETION",
    "DEGRADED_COMPLETION",
    "FAILED",
    "BLOCKED",
    "WAITING_FOR_HUMAN",
}
ALLOWED_NEXT_ACTIONS = {
    "CONTINUE",
    "RESEARCH",
    "RECRITIQUE",
    "AUDIT",
    "SYNTHESIZE",
    "COMPLETE",
    "ESCALATE",
}
REQUIRED_FIELDS = (
    "schema_version",
    "skill",
    "issue_id",
    "run_id",
    "attempt",
    "status",
    "current_stage",
    "next_action",
    "escalation",
    "input_refs",
    "output_refs",
    "claims",
    "unknowns",
    "warnings",
    "errors",
)
LIST_FIELDS = ("input_refs", "output_refs", "claims", "unknowns", "warnings", "errors")
# Role outputs required by ROLE_RULES.md (keyed by the artifact's skill). Reported as warnings until
# every Subagent emits them; promote to FAIL once RUN artifacts consistently carry these fields.
STAGE_FIELDS = {
    "chair-review": ("issue_summary", "scope", "assumptions", "research_mode", "escalation_candidate",
                     "research_questions", "draft_answer"),
    "web-research": ("findings", "source_records", "verified_facts", "conflicting_evidence", "freshness_notes"),
    "devil-advocate": ("objections", "challenged_assumptions", "missing_evidence", "alternatives", "worst_cases",
                       "residual_risks"),
    "secretary": ("minutes", "agreements", "disagreements", "decision_candidates", "human_decision_required",
                  "recommendation_candidates", "decision_reversal_conditions"),
    "content-audit": ("result",),
    "final-synthesis": ("primary_recommendation", "adoption_conditions", "conditional_alternatives",
                        "not_recommended", "residual_risks", "decision_reversal_conditions", "confidence"),
}


@dataclass(frozen=True)
class ArtifactIssue:
    code: str
    message: str


def _required_string(value: Any, field: str) -> ArtifactIssue | None:
    if not isinstance(value, str) or not value.strip():
        return ArtifactIssue("FIELD_INVALID", f"{field} must be a non-empty string.")
    return None


def _validate_refs(value: Any, field: str) -> list[ArtifactIssue]:
    if not isinstance(value, list):
        return [ArtifactIssue("FIELD_INVALID", f"{field} must be an array.")]
    issues: list[ArtifactIssue] = []
    for index, ref in enumerate(value):
        if not isinstance(ref, str) or not ref.strip():
            issues.append(ArtifactIssue("REF_INVALID", f"{field}[{index}] must be a non-empty string."))
            continue
        path = PurePath(ref)
        if path.is_absolute() or ":" in ref or ".." in path.parts:
            issues.append(ArtifactIssue("REF_UNSAFE", f"{field}[{index}] must be a relative path inside the project."))
    return issues


def validate_artifact(
    value: Any,
    *,
    expected_issue_id: str | None = None,
    expected_run_id: str | None = None,
    expected_attempt: int | None = None,
) -> list[ArtifactIssue]:
    """Validate the common artifact contract and optional RUN identity."""
    if not isinstance(value, Mapping):
        return [ArtifactIssue("ROOT_INVALID", "artifact root must be an object.")]

    issues: list[ArtifactIssue] = []
    for field in REQUIRED_FIELDS:
        if field not in value:
            issues.append(ArtifactIssue("FIELD_MISSING", f"missing {field}."))

    if value.get("schema_version") != "1.0":
        issues.append(ArtifactIssue("SCHEMA_VERSION_INVALID", "schema_version must be '1.0'."))
    for field in ("skill",):
        issue = _required_string(value.get(field), field)
        if issue:
            issues.append(issue)

    issue_id = value.get("issue_id")
    if not isinstance(issue_id, str) or not ISSUE_RE.fullmatch(issue_id):
        issues.append(ArtifactIssue("ISSUE_ID_INVALID", "issue_id has an invalid format."))
    elif expected_issue_id and issue_id != expected_issue_id:
        issues.append(ArtifactIssue("ISSUE_ID_MISMATCH", "issue_id does not match active_run.json."))

    run_id = value.get("run_id")
    if not isinstance(run_id, str) or not RUN_RE.fullmatch(run_id):
        issues.append(ArtifactIssue("RUN_ID_INVALID", "run_id has an invalid format."))
    elif expected_run_id and run_id != expected_run_id:
        issues.append(ArtifactIssue("RUN_ID_MISMATCH", "run_id does not match active_run.json."))

    attempt = value.get("attempt")
    if not isinstance(attempt, int) or isinstance(attempt, bool) or attempt < 1:
        issues.append(ArtifactIssue("ATTEMPT_INVALID", "attempt must be a positive integer."))
    elif expected_attempt is not None and attempt != expected_attempt:
        issues.append(ArtifactIssue("ATTEMPT_MISMATCH", "attempt does not match the artifact path."))

    if value.get("status") not in ALLOWED_STATUSES:
        issues.append(ArtifactIssue("STATUS_INVALID", "status is not an allowed artifact status."))
    if value.get("current_stage") not in ALLOWED_STAGES:
        issues.append(ArtifactIssue("STAGE_INVALID", "current_stage is not an allowed stage."))
    if value.get("next_action") not in ALLOWED_NEXT_ACTIONS:
        issues.append(ArtifactIssue("NEXT_ACTION_INVALID", "next_action is not an allowed next_action."))
    if value.get("escalation") is not None and not isinstance(value.get("escalation"), Mapping):
        issues.append(ArtifactIssue("FIELD_INVALID", "escalation must be null or an object."))

    for field in LIST_FIELDS:
        issues.extend(_validate_refs(value.get(field), field) if field in {"input_refs", "output_refs"} else (
            [] if isinstance(value.get(field), list) else [ArtifactIssue("FIELD_INVALID", f"{field} must be an array.")]
        ))
    return issues


def stage_field_warnings(value: Any) -> list[ArtifactIssue]:
    """Report ROLE_RULES.md role outputs missing from an artifact (non-blocking)."""
    if not isinstance(value, Mapping):
        return []
    required = STAGE_FIELDS.get(value.get("skill"), ())
    return [ArtifactIssue("STAGE_FIELD_MISSING", f"{value.get('skill')} output is missing {field} (ROLE_RULES.md).")
            for field in required if field not in value]
