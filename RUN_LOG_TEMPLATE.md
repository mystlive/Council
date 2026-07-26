# RUN_LOG_TEMPLATE.md

## 1. 目的

各実行の入力、利用モデル、プロンプト版、処理順、成果物、検査結果、処理時間を保存し、後から同じ条件を再現できるようにする。

実行ログは正式決定ではない。

## 2. ファイル名

```text
<RUN-ID>.md
```

例:

```text
RUN-20260722-0001.md
```

## 3. 必須メタデータ

```yaml
---
record_type: run
run_id: RUN-YYYYMMDD-NNNN
issue_id: ISSUE-YYYY-NNNN
started_at:
finished_at:
status: RUNNING
attempt: 1
orchestrator:
execution_environment:
git_commit_before:
git_commit_after:
related_source_ids: []
related_decision_ids: []
output_files: []
---
```

## 4. 実行環境

- OS:
- shell:
- Python:
- runtime:
- GPU:
- VRAM:
- model_server:
- model_name:
- model_version:
- model_hash:
- quantization:
- context_length:
- temperature:
- seed:
- timeout:
- network_access:
- web_search_provider:

不明な項目は空欄にせず `UNKNOWN` と記録する。

## 5. 使用ルール

- MASTER_DESIGN.md:
- STATE.md:
- AGENTS.md:
- ROLE_RULES.md:
- DECISION_RULES.md:
- SKILL versions:
- Hook versions:
- prompt versions:

各ファイルは可能な限りGit commitまたはcontent hashを記録する。

## 6. 入力

### 元の依頼

- 

### 参照ファイル

- 

### 関連決定

- 

### 制約

- 

### 調査区分

- NONE
- LOCAL
- WEB

## 7. 実行工程

各工程ごとに記録する。

```yaml
step:
attempt_id: <RUN-ID>-A<NN>
role:
skill:
started_at:
finished_at:
input_files: []
output_files: []
model:
prompt_version:
result:
warnings: []
errors: []
```

標準順序:

1. issue-intake
2. chair-review
3. web-research（必要時）
4. devil-advocate
5. secretary
6. formal-validation
7. content-audit（必要時）
8. final-synthesis
9. human-decision（正式採否または不可逆操作が必要な場合のみ）
10. approved-memory-update（承認後）

## 8. 成果物

- issue-intake:
- chair-review:
- research:
- devil-advocate:
- minutes:
- formal-validation:
- content-audit:
- final-synthesis:
- human-decision:
- memory-update:

各成果物は相対パスとハッシュを記録する。

## 9. 検査結果

### 形式検査

- result:
- hook_name:
- checked_at:
- violations:
- warnings:

### 内容監査

- result:
- audited_at:
- findings:
- revision_required:

### 人間裁定

- status:
- approved_by:
- approved_at:
- approval_reference:

## 10. エラーと復旧

### エラー

- step:
- error_type:
- message:
- affected_files:
- stopped_at:

### 復旧

- recovery_action:
- resumed_from:
- resumed_at:
- rerun_steps:
- data_loss:
- human_approval:

途中成果物は削除せず、同一RUN-IDのattempt番号を増やして追記する。各attemptは別ファイルまたは追記専用セクションとし、元attemptを上書きしない。

## 11. 性能

- total_duration:
- model_calls:
- prompt_tokens:
- completion_tokens:
- total_tokens:
- estimated_cost:
- local_gpu_time:
- web_requests:
- cache_hits:
- retries:

値を取得できない場合は `UNKNOWN` と記録する。

## 12. キャッシュ

- inference_cache_key:
- web_cache_keys:
- embedding_cache_keys:
- cache_policy:
- cache_invalidated:
- invalidation_reason:

正式記録とキャッシュを混同しない。

## 13. 変更差分

- changed_files:
- unexpected_changes:
- git_diff_reference:
- git_status_before:
- git_status_after:

正式台帳更新時は、承認範囲外の変更がないことを確認する。

## 14. 最終状態

status:

- RUNNING
- COMPLETED
- CONDITIONAL_COMPLETION
- BOUNDED_COMPLETION
- DEGRADED_COMPLETION
- FAILED
- BLOCKED
- WAITING_FOR_HUMAN
- CANCELLED

完了時に記録する。

- final_status:
- completed_steps:
- skipped_steps:
- skip_reasons:
- next_action:
- state_updated:
- minutes_path:
- decision_candidate:
- formal_record_updated:

## 15. 禁止事項

- 実行条件を記録せず結果だけ保存する
- モデル名やバージョンを推測で記録する
- エラーを削除して成功扱いにする
- 再実行時に元ログを上書きする
- 秘密情報の実値をログへ保存する
- モデル出力を正式事実として扱う
- 人間承認前に正式記録更新済みと記録する

## 16. 完了条件

次をすべて満たすまでRUNをCOMPLETEDにしない。

- RUN-IDとISSUE-IDがある
- 実行環境が記録されている
- 使用ルールとSkill版が記録されている
- 各工程の開始・終了・結果が記録されている
- 成果物パスが記録されている
- 検査結果が記録されている
- エラーと復旧履歴が保存されている
- 最終状態と次の行動が記録されている
