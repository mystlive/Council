# HOOKS.md

> **Note:** This is a reference translation. The Japanese original ([`HOOKS.md`](HOOKS.md)) is the authoritative source. In case of any discrepancy between this translation and the Japanese original, the Japanese version governs.

## 1. Purpose

Mechanically check required deliverables, state transitions, limited human stops, secrets, protected files, and official-ledger updates, without relying on the LLM's self-reporting. A Hook does not, by itself, guarantee that the content is correct.

## 2. Implemented Hooks

### pre-run (SessionStart)
- Required design files
- The private directories
- The ignore state when Git is in use
- The ID registry

### pre-tool-use (PreToolUse)
- Changes to protected files via Write/Edit-family tools
- Writes to protected files via Bash
- Secret patterns
- Destructive commands

### pre-decision (Stop)
- The form of `active_run.json`
- The required deliverables for the step reached so far
- An invalid WAITING_FOR_HUMAN
- Completion before final-synthesis
- Deliverables required when a content audit is needed

## 3. Designed but Not Yet Implemented

- A dedicated post-role Hook
- A dedicated pre-memory-update Hook
- A dedicated post-memory-update Hook

A Hook that is not yet implemented is never treated as if it were. At this stage, official-ledger updates are constrained by Skill rules and human approval instead.

## 4. Verdicts

- PASS
- PASS_WITH_WARNINGS
- FAIL
- BLOCK

FAIL/BLOCK is never treated as complete. A WARNING may be carried forward once its concrete impact has been confirmed.

## 5. Allowed Reasons for a Human Stop

- HUMAN_ONLY_INFORMATION
- CONSTRAINT_CONFLICT
- IRREVERSIBLE_ACTION
- LEGAL_OR_ORGANIZATIONAL_AUTHORITY
- VALUE_CONFLICT

UNKNOWN, conflicting evidence, lack of real-machine verification, or low confidence, alone, never justify stopping.

## 6. Content Audit

Required when a trigger condition in `ROLE_RULES.md` applies, or when `active_run.json` has `content_audit_required: true`. It may be omitted for an ordinary case.
