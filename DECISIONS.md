# DECISIONS.md

## 1. 目的

人間が採用した正式決定だけを保存する台帳。
議事録、候補、保留、否定、モデル出力はここへ保存しない。

## 2. 記録原則

- 人間承認後のみ追加・更新する。
- 1件につき1つのDECISION-IDを使用する。
- 一部採用は要素ごとにDECISION-IDを分ける。
- 状態変更時も同一DECISION-IDを維持する。
- 旧記録を削除せず、SUPERSEDEDまたはEXPIREDとして残す。
- 根拠はSOURCE-IDで参照する。
- 機密情報、APIキー、認証情報、個人情報は記載しない。

## 2.1 保存単位

- 正式レコードは `records/adopted/<DECISION-ID>.md` に1決定1ファイルで保存する。
- このファイルは索引とSchema定義であり、複数レコードのYAML frontmatterを直接格納しない。
- 状態変更時は同一ファイルを別状態ディレクトリへ移動する。
- 移動履歴はGit renameとして追跡し、複製や参照スタブを残さない。

## 3. 状態

この台帳で使用できる状態は次だけとする。

- ADOPTED
- SUPERSEDED
- EXPIRED

PENDING、REJECTED、REVISE、BLOCKは別記録で管理する。

## 4. 記録テンプレート

```yaml
---
id: DEC-YYYY-NNNN
record_type: decision
status: ADOPTED
issue_id: ISSUE-YYYY-NNNN
title: ""
scope: ""
created_at: YYYY-MM-DDThh:mm:ss+09:00
updated_at: YYYY-MM-DDThh:mm:ss+09:00
approved_by: human
approved_at: YYYY-MM-DDThh:mm:ss+09:00
source_ids: []
supersedes: null
superseded_by: null
expires_at: null
review_condition: ""
---
```

### 決定内容

### 採用理由

### 適用範囲

### 主要リスク

### 未確認事項

### 不採用とした代替案

### 見直し条件

### 関連記録

- 議事録:
- 実行ログ:
- 出典:

## 5. 更新規則

### 新規採用

- statusをADOPTEDとする。
- 人間の承認内容をそのまま反映する。
- 承認範囲を超える補足や拡張を加えない。

### 置換

旧決定を次のように更新する。

- status: SUPERSEDED
- superseded_by: 新DECISION-ID
- updated_at: 変更日時

新決定には次を記録する。

- status: ADOPTED
- supersedes: 旧DECISION-ID

### 失効

- status: EXPIRED
- updated_at: 失効日時
- 失効理由を本文へ記録する。
- 代替決定がある場合は関連記録へ記載する。

## 6. 禁止事項

- 人間承認前の追加・更新
- モデル判断だけによるADOPTED化
- PENDINGまたはREJECTEDの混在
- 同一DECISION-IDの重複登録
- 旧決定の削除
- 根拠不明の追記
- 承認内容を超える解釈の追加

## 7. 現在の正式決定

- [DEC-2026-0001](records/adopted/DEC-2026-0001.md) — 評議会システムへの視点転換・自己点検の低コスト施策の部分採用（ISSUE-2026-0002）、status: ADOPTED
