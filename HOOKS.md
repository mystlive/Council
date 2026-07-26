# HOOKS.md

## 1. 目的

LLMの自己申告に依存せず、必須成果物、状態遷移、限定的人間停止、秘密情報、保護ファイル、正式台帳更新を機械的に検査する。Hookは内容の正しさそのものを保証しない。

## 2. 実装済みHook

### pre-run（SessionStart）
- 必須設計ファイル
- privateディレクトリ
- Git利用時のignore
- IDレジストリ

### pre-tool-use（PreToolUse）
- Write/Edit系による保護ファイル変更
- Bash経由の保護ファイル書込み
- 秘密情報パターン
- 破壊的コマンド

### pre-decision（Stop）
- active_run.jsonの形式
- 現工程までの必須成果物
- 不正なWAITING_FOR_HUMAN
- final-synthesis前の完了
- 内容監査が必要な場合の成果物

## 3. 設計済み・未実装

- post-role専用Hook
- pre-memory-update専用Hook
- post-memory-update専用Hook

未実装Hookは実装済みとして扱わない。正式台帳更新は現段階ではSkill規則と人間承認で制限する。

## 4. 判定

- PASS
- PASS_WITH_WARNINGS
- FAIL
- BLOCK

FAIL/BLOCKでは完了扱いにしない。WARNINGは具体的な影響を確認して継続できる。

## 5. 人間停止の許可理由

- HUMAN_ONLY_INFORMATION
- CONSTRAINT_CONFLICT
- IRREVERSIBLE_ACTION
- LEGAL_OR_ORGANIZATIONAL_AUTHORITY
- VALUE_CONFLICT

UNKNOWN、証拠競合、実機未検証、低確信度だけでは停止しない。

## 6. 内容監査

ROLE_RULES.mdの発動条件に該当する場合、またはactive_run.jsonで`content_audit_required: true`の場合に必須とする。通常案件では省略可能である。
