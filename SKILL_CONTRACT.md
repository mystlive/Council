# SKILL_CONTRACT.md

## 共通入出力

各SkillはJSONを正本として次を返す。

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

## 保存先

- JSON正本: `runs/private/<RUN-ID>/attempt-<NN>/<skill>.json`
- Markdown表示: `runs/private/<RUN-ID>/attempt-<NN>/<skill>.md`
- status: COMPLETED / CONDITIONAL_COMPLETION / BOUNDED_COMPLETION / DEGRADED_COMPLETION / FAILED / BLOCKED / WAITING_FOR_HUMAN
- next_action: CONTINUE / RESEARCH / RECRITIQUE / AUDIT / SYNTHESIZE / COMPLETE / ESCALATE
- `WAITING_FOR_HUMAN` は、限定された escalation 条件を満たす場合だけ使用する。UNKNOWNや証拠不足だけでは使用しない。
- JSON Schema不一致はformal-validationでFAIL。
