# DECISION_RULES.md

> **Note:** This is a reference translation. The Japanese original ([`DECISION_RULES.md`](DECISION_RULES.md)) is the authoritative source. In case of any discrepancy between this translation and the Japanese original, the Japanese version governs.

## 1. Purpose

Clarify the conditions for adoption, pending, rejection, revision, expiration, and supersession, and prevent the same issue or decision from being registered under multiple states at once.

## 2. Basic Principles

- The council autonomously presents a recommended state and its grounds.
- The final state in the official ledger is decided by a human.
- A single DECISION-ID holds exactly one valid state at any given time.
- The same DECISION-ID is kept when its state changes.
- The original judgment, the reason for the change, and the destination are kept traceable.
- Insufficient evidence is never papered over with a reason to adopt.
- When an unconfirmed matter is significant, move to a conditional recommendation, a recommendation to hold pending, or further investigation. Do not stop for a human on the grounds of a bare UNKNOWN alone.

## 3. States

### ADOPTED

A state approved for execution or as official policy.

### PENDING

A state where the information, conditions, timing, or human judgment needed for a decision is lacking.

### REJECTED

A state approved as "not adopted at this time."

### REVISE

A state where the minutes or decision candidate are insufficient and require further investigation or reorganization. This is never reflected in the official record as adopted, pending, or rejected.

### SUPERSEDED

A state where a prior decision has been replaced by a new one.

### EXPIRED

A state that has lost its validity due to a change in deadline, premise, version, contract, law, or environment.

## 4. Conditions for Adoption

A candidate may be treated as a candidate for adoption only if all of the following are satisfied.

- The issue and its scope are clear.
- The content to be adopted is concrete.
- The main evidence has been confirmed.
- No significant unconfirmed matter remains.
- Dissenting opinions and the main risks are recorded.
- Where a comparison against alternatives not adopted is needed, that comparison has been made.
- Formal validation has PASSed.
- For issues that require a content audit, the result is neither BLOCK nor REVISE.
- The conditions for adoption as a council recommendation are satisfied. At the time of formal ADOPTED registration, the human has explicitly stated the adoption.

At minimum, record the following at the time of adoption.

- DECISION-ID
- ISSUE-ID
- What was adopted
- Scope of application
- Reason for adoption
- Supporting SOURCE-ID
- Main risks
- Unconfirmed matters
- Approver
- Approval date/time
- Review condition or deadline

## 5. Conditions for Pending

Treat as a candidate for pending if any of the following applies.

- Necessary primary material is lacking.
- Important conditions such as version, environment, or contract terms are undetermined.
- The relative merits of multiple options cannot be judged.
- Human-specific information or a value judgment is indispensable and cannot be substituted for even with conditional branching.
- Waiting on an external condition such as timing, budget, or a counterparty's reply.
- The content audit result is REVISE.
- Whether the risk is acceptable cannot be judged.

Always record the following when pending.

- Reason for pending
- Missing information
- Next items to confirm
- Who is responsible, or whose reply is awaited
- Conditions for reconsideration
- A deadline for reconsideration, if applicable

A pending state that amounts to nothing more than "think about it later" is prohibited.

## 6. Conditions for Rejection

Treat as a candidate for rejection if any of the following applies.

- It does not fit the purpose.
- It is technically infeasible, or unreasonable in the current environment.
- It contradicts the evidence.
- There is a serious problem involving law, contract, regulation, safety, or confidentiality.
- The cost, time, or maintenance burden is excessive relative to the benefit.
- A more suitable alternative exists.
- The premise is wrong and the proposal does not hold even after correction.
- A human has explicitly stated rejection.

Always record the following at the time of rejection.

- What was rejected
- Reason for rejection
- Grounds
- Whether reconsideration is possible
- Conditions for reconsideration
- A reference to the alternative, if one exists

State explicitly whether the rejection applies to the whole or only to part of the proposal.

## 7. Conditions for Revision (REVISE)

Treat as REVISE if any of the following applies.

- A required step is missing.
- The research mode is inappropriate.
- The evidence and the conclusion do not match.
- Dissenting opinions have not been substantively considered.
- An unconfirmed matter has been asserted as fact.
- The work has strayed from the purpose of the issue.
- The final recommendation, or the conditional decision map, has not been organized through to completion.
- The content audit result is REVISE.

When sending back for revision, make explicit where to fix, the goal of the fix, and which role re-runs the step.

## 8. Conditions for BLOCK

Stop the official-decision process if any of the following applies.

- Human approval required for the official ledger update is absent.
- No ISSUE-ID or DECISION-ID exists.
- Confidential information has been included in material bound for Git.
- There is fabricated evidence, an unknown source, or an assertion of a specification that does not exist.
- The content audit result is BLOCK.
- A destructive change, automatic sending, or automatic deletion is being attempted without approval.
- The same DECISION-ID is being registered under multiple states at once.
- The change includes more than what was approved.
- The content audit's final verdict is REVISE or BLOCK, and the run is attempting to finish as COMPLETED, CONDITIONAL_COMPLETION, or DEGRADED_COMPLETION.
- After a fix, a re-audit by the content-auditor is required. Only when the re-audit budget has been exhausted may the run finish as BOUNDED_COMPLETION.
- The orchestrator, whoever performed the fix, or the role being audited, acting on behalf of content-audit to declare, override, or announce a PASS is prohibited.

Clearing a BLOCK requires fixing the root cause and re-inspecting.

## 9. State Changes

### From Adopted to Superseded

Create the new decision, and record the following on the old decision.

- status: SUPERSEDED
- superseded_by: the new DECISION-ID
- changed_at
- change_reason

### From Adopted to Expired

Record the following on the old decision.

- status: EXPIRED
- expired_at
- expiration_reason
- replacement_decision_id (if one exists)

### From Pending to Adopted or Rejected

Keep the same DECISION-ID and the same file, and move it between state directories. The move history is tracked through Git and through the change-history field in the body text.

### From Rejected to Reconsideration

Do not delete the rejection record. Record the reason for reconsideration, and either move it to PENDING under the same DECISION-ID, or, if the scope is new, issue a new DECISION-ID.

## 10. Partial Adoption

For an issue that contains multiple elements, where only part of it is adopted, split the DECISION-ID by element.

Do not mix adoption, pending, and rejection under a single DECISION-ID.

## 11. Conditional Adoption

A conditional adoption is treated as PENDING as a rule.

However, it may be marked ADOPTED only if the condition can be verified mechanically and there is a mechanism ensuring it is not executed before the condition is met. The following are then required.

- Trigger condition
- What is prohibited if the condition is not met
- How the condition is verified
- Expiration deadline
- Person responsible

## 12. Emergency Exception

When a normal step is skipped for an emergency response, the human must give explicit approval, and the following must be recorded.

- The step that was skipped
- The reason for skipping it
- The anticipated risk
- The scope of application
- The expiration date
- The deadline for a post-hoc audit

Do not reuse an emergency exception as a standing rule.

## 13. Self-Check

Before presenting a decision candidate to a human, confirm at minimum the following.

- Whether the state candidate has been narrowed to one
- Whether the scope is clear
- Whether the evidence and the conclusion match
- Whether dissenting opinions are recorded
- Whether the impact of unconfirmed matters on the judgment has been recorded
- Whether only the formal adoption decision and the exercise of authority left to the human have been made explicit
- Whether the official record has not already been updated beforehand
