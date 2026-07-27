# SKILL_CONTRACT.md

> **Note:** This is a reference translation. The Japanese original ([`SKILL_CONTRACT.md`](SKILL_CONTRACT.md)) is the authoritative source. In case of any discrepancy between this translation and the Japanese original, the Japanese version governs.

## Common Input/Output

Each Skill returns the following JSON as its source of truth.

```json
{
  "schema_version": "1.0",
  "skill": "skill-name",
  "issue_id": "ISSUE-YYYY-NNNN",
  "run_id": "RUN-YYYYMMDD-NNNN",
  "attempt": 1,
  "status": "COMPLETED",
  "current_stage": "skill-name",
  "next_action": "CONTINUE",
  "escalation": null,
  "input_refs": [],
  "output_refs": [],
  "claims": [],
  "unknowns": [],
  "warnings": [],
  "errors": []
}
```

## Storage Location

- JSON source of truth: `runs/private/<RUN-ID>/attempt-<NN>/<skill>.json`
- Markdown display: `runs/private/<RUN-ID>/attempt-<NN>/<skill>.md`
- status: COMPLETED / CONDITIONAL_COMPLETION / BOUNDED_COMPLETION / DEGRADED_COMPLETION / FAILED / BLOCKED / WAITING_FOR_HUMAN
- next_action: CONTINUE / RESEARCH / RECRITIQUE / AUDIT / SYNTHESIZE / COMPLETE / ESCALATE
- `WAITING_FOR_HUMAN` is used only when a limited escalation condition is met. It is not used for a bare UNKNOWN or lack of evidence alone.
- A mismatch against the JSON Schema is a FAIL in formal-validation.
