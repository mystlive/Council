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
- Refreshing the protected-file hash baseline (changes since the previous session are warned)
- Recording the running Claude Code version, entrypoint, session effort, and each Subagent's model/effort (`.council/runtime_fingerprint.json`); a version change and `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` are warned

### pre-tool-use (PreToolUse: Write/Edit family, Bash, PowerShell)
- Changes to protected files via Write/Edit-family tools
- Writes to protected files via Bash and PowerShell, judged by redirection targets and write commands (cp, mv, Copy-Item, Set-Content, shutil, write_text, git checkout, etc.); read commands and `2>/dev/null` are not treated as writes
- Overwriting content-audit artifacts (`content_audit*.json`)
- Secret patterns, and writes to `.env` and `.env.*` (except .example etc.)
- Destructive commands
- Running the protected-file baseline refresh (`refresh-baseline`)

### post-tool-use (PostToolUse: Write/Edit family, Bash, PowerShell)
- Completing the record of a maintenance-approved change
- Comparing protected files with the baseline (tool-independent tamper detection; approved changes are folded into the baseline)
- Validating changes to `active_run.json` with the runner's transition rules and appending to `runs/private/<RUN-ID>/transition_log.jsonl`

### pre-decision (Stop)
- Comparing protected files with the baseline
- The form of `active_run.json`
- The required deliverables for the step reached so far, and that artifact paths match their attempt number
- Missing stage-specific output keys from ROLE_RULES.md (warning)
- An invalid WAITING_FOR_HUMAN
- Completion before final-synthesis
- Deliverables required when a content audit is needed, and that `outputs.content_audit` points to the newest audit pass in the same attempt
- Stopping while RUNNING: blocked, except that a repeated stop without progress in the same continuation chain (`stop_hook_active`) and a RUN unchanged for 24 hours are allowed with a warning

### Human-only operation
- `python hooks/validate.py refresh-baseline --root .`: refresh the protected-file baseline; running it from Claude is blocked

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

## 7. Limits

Hooks cannot fully prevent tampering by a process running with the same privileges. Protected-file integrity checks aim at detection.
