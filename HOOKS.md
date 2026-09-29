# HOOKS.md

## 1. 目的

LLMの自己申告に依存せず、必須成果物、状態遷移、限定的人間停止、秘密情報、保護ファイル、正式台帳更新を機械的に検査する。Hookは内容の正しさそのものを保証しない。

## 2. 実装済みHook

### pre-run（SessionStart）
- 必須設計ファイル
- privateディレクトリ
- Git利用時のignore
- IDレジストリ
- 保護ファイルのハッシュ基準線の更新（前セッションからの変更は警告）
- 実行中のClaude Codeの版、entrypoint、session effort、各Subagentのmodel/effortの記録（`.council/runtime_fingerprint.json`）。版の変化と`CLAUDE_CODE_SUBAGENT_MODEL_FORCE`の設定を警告する

### pre-tool-use（PreToolUse: Write/Edit系、Bash、PowerShell）
- Write/Edit系による保護ファイル変更
- BashとPowerShellによる保護ファイル書込み。リダイレクト先と書込み系コマンド（cp、mv、Copy-Item、Set-Content、shutil、write_text、git checkout等）で判定し、読取コマンドや`2>/dev/null`は書込みとみなさない
- content-audit成果物（`content_audit*.json`）の上書き
- 秘密情報パターン、`.env`と`.env.*`（.example等を除く）への書込み
- 破壊的コマンド
- 保護ファイル基準線の更新（`refresh-baseline`）の実行

### post-tool-use（PostToolUse: Write/Edit系、Bash、PowerShell）
- maintenance approval による変更の完了記録
- 保護ファイルと基準線の照合（ツールに依存しない改変検知。承認済み変更は基準線へ取り込む）
- `active_run.json`の変更をrunnerの遷移規則で検証し、`runs/private/<RUN-ID>/transition_log.jsonl`へ履歴を追記する

### pre-decision（Stop）
- 保護ファイルと基準線の照合
- active_run.jsonの形式
- 現工程までの必須成果物、成果物パスのattempt番号との一致
- ROLE_RULES.mdの工程別出力キーの欠落（警告）
- 不正なWAITING_FOR_HUMAN
- final-synthesis前の完了
- 内容監査が必要な場合の成果物。`outputs.content_audit`が同一attemptの最新の監査パスを指していること
- RUNNING中の停止。BLOCKするが、同じ継続連鎖（`stop_hook_active`）で前回BLOCKから進展のない再停止と、24時間更新のないRUNは警告で許可する

### 人間専用操作
- `python hooks/validate.py refresh-baseline --root .`: 保護ファイル基準線の更新。Claudeからの実行はBLOCKする

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

## 7. 限界

Hookは同じ権限で動くプロセスによる改ざんを完全には防げない。保護ファイルの完全性照合は検知を目的とする。
