# MINUTES_TEMPLATE.md

## 1. 目的

評議会の各役が出した意見、根拠、反対意見、未確認事項、人間が判断すべき点を、改変せず追跡可能な形で保存する。

議事録は正式決定ではない。

## 2. ファイル名

```text
MINUTES_<ISSUE-ID>_<RUN-ID>.md
```

例:

```text
MINUTES_ISSUE-2026-0001_RUN-20260722-0001.md
```

## 3. 必須メタデータ

```yaml
---
record_type: minutes
issue_id: ISSUE-YYYY-NNNN
run_id: RUN-YYYYMMDD-NNNN
title:
created_at:
updated_at:
secretary:
research_mode: NONE
related_source_ids: []
related_decision_ids: []
formal_validation:
content_audit:
human_decision:
status: DRAFT
---
```


## 3.1 議事録状態

- DRAFT: 作成中
- READY_FOR_REVIEW: 書記整理済み
- REVISE: 差し戻し
- FINALIZED: 人間裁定を記録済み
- ARCHIVED: 正式記録更新後に保管済み

FINALIZEDは正式決定を意味しない。正式決定は各正式台帳を正本とする。

## 4. 議題

### 元の依頼

ユーザーの依頼を要約しすぎず記録する。

### 目的

今回の評議会で判断または整理する対象。

### 対象範囲

含むもの、含まないものを記録する。

### 制約

環境、予算、期限、法令、契約、利用可能ツールなど。

## 5. 主査

### 論点

- 

### 調査区分

- NONE
- LOCAL
- WEB

### 仮説

- 

### 仮回答

- 

### 主査が認識した未確認事項

- 

## 6. 調査役

調査区分がNONEの場合は「調査不要」と記録する。

### 調査項目

- 

### 確認できた事実

- CLAIM-ID:
  - 内容:
  - SOURCE-ID:
  - support_level:

### 矛盾または反証された事項

- 

### 古い、限定的、利用不能な出典

- 

### 未確認事項

- 

## 7. 反対役

### ユーザー前提への反論

- 

### 主査案への反論

- 

### 調査結果への疑義

- 

### 見落とし

- 

### 代替案

- 

### 最悪ケース

- 

### 再調査要求

- 

## 8. 書記整理

### 確認済み事実

- 

### 推測

- 

### 提案

- 

### 一致点

- 

### 対立点

- 

### 未確認事項

- 

### 議題から外れた事項

- 

## 9. 状態候補

人間裁定前の候補であり、正式決定ではない。

### 採用候補

- 対象:
- 理由:
- 根拠:
- リスク:

### 保留候補

- 対象:
- 理由:
- 不足情報:
- 再検討条件:

### 否定候補

- 対象:
- 理由:
- 根拠:
- 再検討可能性:

候補がない欄は「なし」と記録する。

## 10. 人間が判断すべき点

- 判断項目:
- 選択肢:
- 各選択肢の影響:
- 書記による推奨:
- 推奨の不確実性:

書記の推奨は人間の決定ではない。

## 11. 形式検査

- result:
- hook_name:
- violations:
- warnings:
- checked_at:

## 12. 内容監査

必要な場合だけ記録する。

- result:
- 指摘箇所:
- 修正目標:
- 影響範囲:
- audited_at:


## 13. 最終集約

- recommendation:
- adoption_conditions:
- alternatives:
- non_recommended_options:
- remaining_unknowns:
- decision_reversal_conditions:
- confidence:
- completion_status:

最終集約は評議会の推奨であり、正式台帳上の採否ではない。

## 14. 人間裁定

人間が明示した内容だけを記録する。

- decision_status:
- approved_scope:
- approved_by:
- approved_at:
- approval_reference:
- comments:

人間裁定前は空欄にする。

## 15. 正式記録更新

- update_required:
- target_ledger:
- decision_id:
- updated_by:
- updated_at:
- git_diff_reference:

人間承認前は実行しない。

## 16. 禁止事項

- 議事録を正式決定として扱う
- 反対意見を都合よく短縮または削除する
- 未確認事項を確認済みに移す
- 人間の判断を推測して記入する
- SOURCE-IDなしに重要事実を確定する
- 元の依頼と異なる議題へ変更する
- 複数状態を1つのDECISION-IDへ混在させる

## 17. 完了条件

次をすべて満たすまで議事録を完了扱いにしない。

- ISSUE-IDとRUN-IDがある
- 主査出力がある
- 必要時の調査結果がある
- 反対役出力がある
- 一致点、対立点、未確認事項がある
- 人間が判断すべき点が明確
- 形式検査結果がある
- statusに応じて、正式決定前か裁定記録済みかが明確
