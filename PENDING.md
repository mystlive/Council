# PENDING.md

## 1. 目的

人間が保留と判断した事項だけを保存する正式台帳の索引・仕様。

未整理のメモ、単なる候補、モデルの推測は保存しない。

## 2. 登録条件

次をすべて満たす場合のみ登録する。

- 人間が保留を明示している
- DECISION-IDが発行されている
- ISSUE-IDと関連付いている
- 保留理由が明確である
- 不足情報または待機条件が明確である
- 再検討条件が記録されている
- 同一DECISION-IDが他の正式台帳の索引・仕様で有効状態になっていない
- 形式検査を通過している

## 2.1 保存単位

- 正式レコードは `records/pending/<DECISION-ID>.md` に1決定1ファイルで保存する。
- このファイルは索引とSchema定義であり、複数レコードのYAML frontmatterを直接格納しない。
- 状態変更時は同一ファイルを別状態ディレクトリへ移動する。
- 移動履歴はGit renameとして追跡し、複製や参照スタブを残さない。

## 3. 必須項目

```yaml
---
id: DEC-YYYY-NNNN
issue_id: ISSUE-YYYY-NNNN
record_type: decision
status: PENDING
title:
scope:
pending_reason:
missing_information:
waiting_for:
next_action:
reconsider_condition:
reconsider_due:
source_ids: []
author:
created_at:
updated_at:
approved_by:
approved_at:
supersedes:
moved_from:
---
```

## 4. 本文構成

### 保留内容

何を保留したかを具体的に記録する。

### 保留理由

判断できない理由を記録する。

### 不足情報

採用または否定に必要な情報を記録する。

### 待機条件

相手方回答、公開情報、予算、時期、検証結果などを記録する。

### 次の行動

誰が何を確認するかを記録する。

### 再検討条件

再検討を開始する明確な条件を記録する。

### 主要リスク

保留期間中に生じる可能性がある問題を記録する。

### 関連記録

- ISSUE-ID
- SOURCE-ID
- RUN-ID
- 関連DECISION-ID

## 5. 状態変更

### PENDINGからADOPTED

- 同一DECISION-IDを維持する
- DECISIONS.mdへ移動する
- 同一ファイルを移動し、本文の変更履歴欄へ移動日と理由を追記する
- 人間の採用承認を必須とする

### PENDINGからREJECTED

- 同一DECISION-IDを維持する
- REJECTED.mdへ移動する
- 同一ファイルを移動し、本文の変更履歴欄へ移動日と理由を追記する
- 人間の否定承認を必須とする

### PENDINGからSUPERSEDEDまたはEXPIRED

- 置換先または失効理由を記録する
- 元記録を削除しない
- 必要に応じて新DECISION-IDを発行する

## 6. 禁止事項

- 「後で考える」だけの保留
- 不足情報が不明な保留
- 再検討条件がない保留
- 人間承認前の登録
- モデルが自動判断した保留の正式登録
- 同一DECISION-IDの重複登録
- 保留事項を採用済み方針として参照すること
- 期限切れ情報を未確認のまま維持すること

## 7. 定期確認

保留事項には可能な限り再検討期限を設定する。

期限到来時は次のいずれかを行う。

- 再調査
- 人間へ再確認
- 採用
- 否定
- 期限延長
- 失効

期限延長時は理由を記録する。

## 8. 初期状態

現在、正式に承認された保留事項はない。
