# Runtime Hardening Design Proposal

状態: 提案

この文書は、既存の評議会PoCを壊さずに、実行制御、成果物検査、証跡、Provider差し替えを段階的に強化するための設計案です。

この文書自体は正式決定ではありません。

## 1. 対象範囲

対象は次の4領域です。

1. Council RUNの状態遷移と審議予算
2. JSON成果物と工程間参照
3. RUNおよび監査の改ざん検知可能な証跡
4. Claude Code以外へ差し替え可能な実行Adapter

対象外は、独立Subagentの新設、正式決定の自動化、外部送信の自動化です。

## 2. 現状から維持する契約

- 評議会は推奨を生成し、正式採否は人間が決める。
- `WAITING_FOR_HUMAN`は限定された人間固有条件だけで使用する。
- `content-audit`の判定は監査役自身の出力を正とする。
- 正式台帳は人間承認後だけ更新する。
- 機密本文と公開可能な実行メタデータを分離する。

## 3. 目標アーキテクチャ

```text
User request
    |
    v
Deterministic Runner
    |  state, budget, retry, artifact contract
    +--> Provider Adapter
    |       +--> Claude Code role invocation
    |       +--> Other provider role invocation
    |
    +--> Schema Validator
    +--> Provenance Ledger
    +--> Human-approved Memory Updater
```

Runnerが工程遷移を所有し、LLMは各役の成果物を生成します。

Provider Adapterは、役割名、入力参照、出力参照、失敗、再試行を共通契約へ変換します。

## 4. 成果物の不変条件

各JSON成果物は次を満たします。

- `schema_version`、`skill`、`issue_id`、`run_id`、`attempt`、`current_stage`、`status`、`next_action`を持つ。
- `input_refs`と`output_refs`は同一RUNの許可された領域を指す。
- `issue_id`と`run_id`はactive runと一致する。
- 工程ごとの必須フィールドを満たす。
- CLAIM、SOURCE、DECISION参照は台帳または同一RUN成果物で解決できる。
- 監査パスの結果を過去に遡って書き換えない。

## 5. RUN証跡

RUNごとに次のメタデータを追跡します。

- RUN設定、ルール版、Skill版、Subagent版
- Provider、モデル識別子、プロンプト版
- 工程開始時刻、終了時刻、再試行回数、予算消化
- 各成果物のSHA-256
- 監査パスの順序と判定

機密な本文はprivate領域に残し、追跡対象には匿名化済みメタデータとハッシュだけを保存します。

## 6. 段階的コミット境界

1. 設計契約と索引を追加する。
2. 成果物Schemaと工程間参照を検査する。
3. 原子的なID発行を追加する。
4. 監査パスを追記専用にする。
5. RUNマニフェストとハッシュ証跡を追加する。
6. 決定論的Runnerを追加する。
7. Claude Code実行Adapterを追加する。
8. 正式記録更新経路と差分検査を強化する。
9. 出典スナップショットとCLAIM対応を追加する。
10. 通し試験、README、正本、MANIFESTを同期する。

各段階は、既存27件のHook単体テスト、追加した回帰テスト、pre-run、pre-decisionを通過した状態で次へ進みます。

## 7. 人間判断が必要な項目

次の項目は実装前に人間の裁定が必要です。

- private本文の保存期間と削除方法
- 追跡対象メタデータを公開Gitへ置くか、別の非公開台帳へ置くか
- 最初に対応するProviderの範囲
- RUNマニフェストへ保存するモデル・コスト情報の粒度
- 既存の正式文書を更新する変更範囲

これらが未決の間は、実装は設計提案とローカル検証用の範囲に限定します。

## 8. 採用済み設計判断

2026-08-24、人間の判断によりRUN証跡はハイブリッド方式を採用します。

- 公開Gitには匿名化済みRUNメタデータと成果物ハッシュだけを保存します。
- 非公開領域には本文、プロンプト、モデル入出力、費用、証拠参照などの詳細を保存します。
- 公開マニフェストは非公開マニフェストのSHA-256を保持します。
- 公開側のフィールドは許可リストで制限し、機密情報を含むキーを拒否します。
