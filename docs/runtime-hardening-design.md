# Runtime Hardening Design Proposal

状態: モジュールは実装済み。運用への接続は一部（2026-09-29、§9 参照）

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
    |       +--> Codex CLI role invocation
    |       +--> OrcaRouter role invocation
    |
    +--> Schema Validator
    +--> Provenance Ledger
    +--> Human-approved Memory Updater
```

Runnerが工程遷移を所有し、LLMは各役の成果物を生成します。

Provider Adapterは、役割名、入力参照、出力参照、失敗、再試行を共通契約へ変換します。

最初の対応ProviderはCodex CLIとOrcaRouterです。

Codexは非対話の`codex exec --json`を使い、OrcaRouterはOpenAI互換のChat Completionsエンドポイントを使います。

アダプターは1回の呼び出しだけを担当し、再試行、予算、工程遷移、公開証跡への書き込みはRunnerとProvenance層へ委譲します。

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
7. Codex CLIとOrcaRouter実行Adapterを追加する。
8. 正式記録更新経路と差分検査を強化する。
9. 出典スナップショットとCLAIM対応を追加する。
10. 通し試験、README、正本、MANIFESTを同期する。

各段階は、既存27件のHook単体テスト、追加した回帰テスト、pre-run、pre-decisionを通過した状態で次へ進みます。

## 7. 人間判断が必要な項目

次の項目は実装前に人間の裁定が必要です。

- private本文の保存期間と削除方法（解決済み。詳細90日、マニフェスト365日、削除は人間承認）
- 追跡対象メタデータを公開Gitへ置くか、別の非公開台帳へ置くか
- 最初に対応するProviderの範囲（解決済み。Codex CLIとOrcaRouter）
- RUNマニフェストへ保存するモデル・コスト情報の粒度（解決済み。公開側はProvider名、非公開側はモデル・使用量・料金情報）
- 既存の正式文書を更新する変更範囲（解決済み。README、索引、設計書、MANIFESTに限定）

保護された正式文書と正式台帳は今回の同期対象に含めません。

## 8. 採用済み設計判断

2026-08-24、人間の判断によりRUN証跡はハイブリッド方式を採用します。

- 公開Gitには匿名化済みRUNメタデータと成果物ハッシュだけを保存します。
- 非公開領域にはProvider、モデルID、入力・出力トークン数、料金、料金表バージョンだけを保存します。
- プロンプト本文、応答本文、APIキー、認証ヘッダーは保存しません。
- 公開マニフェストは非公開マニフェストのSHA-256を保持します。
- 公開側のフィールドは許可リストで制限し、機密情報を含むキーを拒否します。

出典スナップショットは取得内容をSHA-256で固定し、同一パスの異なる内容への上書きを拒否します。

CLAIMは`CLAIM-ID`と1件以上の`SOURCE-ID`、支持・反証・部分支持・旧情報の関係を持ちます。

保存先は実行時設定に委ねます。

既存の正式文書を更新する範囲はREADME、索引、設計書、MANIFESTに限定します。

この同期時点でHookテストは66件です。

第12コミットでREADME、索引、設計書、MANIFESTの同期を完了しました。

2026-08-24、人間の判断によりprivate詳細本文はRUN完了後90日、privateマニフェストは365日保持します。

公開メタデータとハッシュは無期限保持し、削除は自動化せず、期限・法務保留・対象ハッシュを含む削除計画への人間承認を必須とします。

## 9. 運用への接続状況（2026-09-29、ISSUE-2026-0003）

RUN-20260929-0001 の精査で、§3 の目標アーキテクチャは単体モジュールとテストまでで、実運用経路に接続されていないことが確認された。人間の指示（AI提案に基づく実装）により、モジュール単位で次のとおり扱う。

| モジュール | 扱い | 接続 |
|---|---|---|
| runner.py | 維持・接続 | `start/apply/release` CLI、遷移履歴 `transition_log.jsonl`、PostToolUse Hook による `active_run.json` 変更の検証 |
| audit_store.py | 維持・接続 | `content_audit-NN.json` の追記保存、pre-decision が最新の監査パスを列挙して検査 |
| artifact_schema.py | 維持・拡張 | ROLE_RULES.md の工程別出力キーの欠落を警告（STAGE_FIELDS） |
| id_allocator.py | 維持・修正 | RUN-ID を `RUN-YYYYMMDD-NNNN`（日単位採番）に統一 |
| raw_output.py | 新規 | Subagent 返却テキストの改変なし保存と SHA-256 記録 |
| provider_adapter.py | Codex のみ維持 | プロンプトを stdin 渡し、sandbox を明示（`danger-full-access` は拒否）。OrcaRouter は凍結 |
| provenance.py / retention.py / source_snapshot.py / record_update.py | 凍結 | 拡張しない（削除もしない）。provider 経路が実運用された時点で再評価 |

この同期時点でHookテストは93件です。
