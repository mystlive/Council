# Council

[English](README.en.md)

<p align="center">
  <img src="docs/assets/social-preview.png" alt="Council — Auditable Multi-Agent Deliberation" width="100%">
</p>

## 概要

Claude Code上で、調査・反証・追加調査・監査・条件付き結論までを自律進行させる、実験的なAI評議会フレームワーク。

## 解決したい問題

通常の対話型LLMは、時間やコンテキストの制約から、次のような工程を省略・短縮しがちである。

- ユーザー前提そのものを疑う
- 一次資料に基づく調査
- 自分の結論に対する独立した反証
- 反証を受けての追加調査
- 形式的な成果物検査と、意味内容の監査
- 未確認事項を断定に変換せず、条件付き結論として保持する
- 判断の変更理由・停止理由を後から追跡できる形で記録する

Councilは、これらの工程を「省略されうる推奨事項」ではなく、役割定義・状態遷移・Hookによる機械検査・成果物契約によって、通常運用時に強制する仕組みを提供する。

## 設計思想

Councilは、複数のAI人格を集めて多数決や討論を行うこと自体を目的としない。

目的は、通常の対話型LLMでは省略・短縮されやすい以下の工程を、明示的な役割、状態遷移、Hook、成果物契約によって強制することである。

- 入力前提の監査
- 調査課題の設定
- 一次資料を優先した調査
- 独立した反証
- 反証を受けた追加調査
- 必要に応じた再反証
- 形式監査
- 内容監査
- 条件付き結論
- 少数意見とUNKNOWNの保存
- 判断変更理由の記録
- 停止理由の記録
- 審議予算内での自律進行
- 不可逆操作だけを人間へ戻す制御

Councilの中心は、「複数AIを会話させること」ではなく、「検討工程を監査可能な手続きとして実行させること」にある。

## 一般的なマルチエージェントとの違い

実装上は複数の役割やSubagentを使用するが、研究・設計上の中心はエージェント数や人格多様性ではなく、監査可能な意思決定手続きにある。

| 観点 | 一般的なマルチエージェント構成 | Council |
|---|---|---|
| 中心 | 複数エージェントの会話・協調・討論 | 意思決定工程と権限分離 |
| 多様性 | 人格差・モデル差・役割差 | 役割責任・証拠状態・監査手続き |
| モデル構成 | 異種モデルを前提にする場合がある | 同一モデル・同一提供会社でも利用可能 |
| 出力 | 最終回答や合意結果 | 条件付き結論、代替案、UNKNOWN、少数意見 |
| 記録 | 会話履歴中心の場合がある | 主張、証拠、反論、変更理由、停止理由を構造化保存 |
| 人間介入 | 工程ごとの確認が入る場合がある | 限定的人間停止条件以外は自律進行 |
| 監査 | 任意または最終確認中心 | 形式監査と内容監査を分離 |
| 停止 | 会話回数やエージェント終了依存 | 審議予算、状態遷移、監査結果で制御 |

「Councilはマルチエージェントではない」と断定するものではない。実装は複数のSubagent・Skillに依存している。ここで強調したいのは、設計上の力点の置き所の違いである。

## 主な特徴

本プロジェクトは既存のマルチエージェント、反証、監査、Human-in-the-loop、制約付き推論の考え方を利用している。独自性を主張する場合は、個別技術ではなく、それらを実務向けの監査可能な意思決定手続きとして統合した設計にある。統合の観点として、次を挙げられる可能性がある。

- 役割とモデルを分離する
- 同一モデル構成と異種モデル構成の双方を扱う
- UNKNOWNを消さず条件付き結論へ残す
- 反証結果から追加調査を自動発動する
- 形式監査と内容監査を分離する
- content-auditの自己承認を禁止する（監査役以外が合否を代行・上書き・宣言できない）
- 審議予算を超えた場合はBOUNDED_COMPLETIONへ移行する
- 人間確認を途中工程の常態にしない
- 人間向け回答と内部判断記録を分離する
- 判断来歴を構造化して保存する
- Claude CodeのSkill、Subagent、Hookで現行環境上に実装する

完全新規、世界初、既存手法に対する優位性の証明を主張するものではない。

## 評議会の処理フロー

[`CLAUDE.md`](CLAUDE.md)が定義する標準工程は次の通り。

1. `issue-intake`（議題受付・ISSUE-ID発行）
2. 主査Subagent（`chair`、論点整理・調査区分判定）
3. 調査Subagent（`researcher`、必要時のみ・WEBまたはLOCAL）
4. 反対Subagent（`critic`、独立反証）
5. 必要なら追加調査・再反証（research-revision／devil-advocate-revision）
6. 書記Subagent（`secretary`、議事録整理）
7. `formal-validation`（形式検査）
8. `content-audit`（ROLE_RULES.mdの発動条件を満たす場合のみ、`content-auditor`による独立監査）
9. `final-synthesis`（評議会としての最終推奨生成）
10. 評議会推奨を人間へ提示
11. 人間が正式採用を決めた場合のみ`approved-memory-update`

各中間工程の終了後に人間へ次工程の許可を求めない。UNKNOWN、反対意見、証拠競合は、再調査または条件付き結論として処理する。content-auditがREVISEまたはBLOCKのまま、RUNをCOMPLETED・CONDITIONAL_COMPLETION・DEGRADED_COMPLETIONとして終了することはできない（`hooks/validate.py`のpre-decisionが機械的にBLOCKする）。修正後は`content-auditor`による再監査を要し、再監査予算（`deliberation_budget.max_audit_revisions`）を使い切った場合に限り`BOUNDED_COMPLETION`として終了できる。

### 工程フロー図

```mermaid
flowchart TD
    Start(["ユーザー依頼"]) --> Intake["issue-intake<br/>ISSUE-ID発行・議題整理・重複確認"]
    Intake --> Chair["chair-review (主査 chair)<br/>論点分解・調査区分判定<br/>research_mode: NONE / LOCAL / WEB"]
    Chair -->|research_mode = LOCAL または WEB| Research["research (調査役 researcher)<br/>一次資料優先・出典/取得日/版を記録"]
    Chair -->|research_mode = NONE| Critic
    Research --> Critic["devil-advocate (反対役 critic)<br/>ユーザー前提・主査案・調査結果への反証<br/>代替案(問題設定自体を変える案を含む)・最悪ケース"]
    Critic --> Judge{"council-orchestrator<br/>追加調査の要否判定<br/>(結論影響度・取得可能性・審議予算)"}
    Judge -->|要・予算内| ResearchRev["research-revision<br/>追加調査"]
    ResearchRev --> CriticRev["devil-advocate-revision<br/>再反証(必要時)"]
    CriticRev --> Judge
    Judge -->|不要 / 予算到達| Secretary["secretary (書記)<br/>一致点・対立点・未確認事項を整理<br/>決定権を持たない議事録案を作成"]
    Secretary --> Formal{"formal-validation<br/>形式検査<br/>(ID形式・必須項目・JSON Schema)"}
    Formal -->|FAIL / BLOCK| Secretary
    Formal -->|PASS / PASS_WITH_WARNINGS| AuditGate{"content-audit<br/>発動条件に該当するか<br/>(法務/契約/安全/実装変更/根拠競合/<br/>反対役の重大リスク提示/人間の監査要求)"}
    AuditGate -->|非該当| Synthesis
    AuditGate -->|該当| Audit["content-audit (content-auditor)<br/>独立コンテキストでの意味監査<br/>根拠支持・断定・迎合・逸脱を確認"]
    Audit -->|REVISE / BLOCK かつ 監査予算内| FixStage["指摘対象工程を修正<br/>(secretary 等)"]
    FixStage --> Audit
    Audit -->|PASS / PASS_WITH_WARNINGS| Synthesis["final-synthesis<br/>評議会としての第一推奨・採用条件・<br/>代替案・非推奨理由・残存UNKNOWNを生成"]
    Audit -->|REVISE / BLOCK かつ 監査予算枯渇| Synthesis
    Synthesis --> Human(["人間へ提示<br/>推奨・採用条件・代替案・反対意見・<br/>残存UNKNOWN・結論反転条件"])
    Human -->|正式採用/保留/否定を明示| Memory["approved-memory-update<br/>records/adopted・pending・rejectedへ反映"]
    Human -->|差し戻し等| Revisit(["対象工程へ再依頼"])
    Memory --> Done(["完了"])

    style Human fill:#f6d55c,stroke:#333,color:#000
    style Memory fill:#ef7b45,stroke:#333,color:#fff
    style Audit fill:#d1e8e2,stroke:#333,color:#000
    style Formal fill:#d1e8e2,stroke:#333,color:#000
```

### RUN状態遷移

`.council/active_run.json`の`status`は次の有限状態機械に従う。工程（stage）の前進とは別の軸であり、`status=RUNNING`のまま応答を終えること自体が`hooks/validate.py`のpre-decisionにより`RUN_INCOMPLETE`としてBLOCKされる点に注意。

```mermaid
stateDiagram-v2
    [*] --> RUNNING: issue-intake開始<br/>(ISSUE-ID/RUN-ID発行)

    RUNNING --> RUNNING: 工程前進<br/>chair-review→(research)→devil-advocate→<br/>secretary→formal-validation→<br/>(content-audit)→final-synthesis

    RUNNING --> WAITING_FOR_HUMAN: next_action=ESCALATE<br/>下記5条件のいずれかに<br/>該当する場合だけ
    WAITING_FOR_HUMAN --> RUNNING: 人間の回答後<br/>resume_stepから再開

    RUNNING --> BLOCKED: Hookが機械的にBLOCK<br/>(保護ファイル書込み・秘密情報・<br/>破壊的コマンド・成果物パス不正・<br/>content-audit未解消のまま完了・<br/>RUNNING状態のまま停止 等)
    BLOCKED --> RUNNING: 原因を修正し再実行

    RUNNING --> FAILED: 回復不能な失敗

    RUNNING --> COMPLETED: final-synthesis完了<br/>content-auditが該当する場合はPASS系
    RUNNING --> CONDITIONAL_COMPLETION: 条件付き推奨を伴う完了
    RUNNING --> DEGRADED_COMPLETION: 縮退ありの完了
    RUNNING --> BOUNDED_COMPLETION: 審議予算(研究/反証/監査差戻し)<br/>を使い切った時点で確定<br/>content-auditがなおREVISE/BLOCKでも可

    COMPLETED --> [*]
    CONDITIONAL_COMPLETION --> [*]
    DEGRADED_COMPLETION --> [*]
    BOUNDED_COMPLETION --> [*]
    FAILED --> [*]

    note right of WAITING_FOR_HUMAN
        escalation.reason_codeは次のいずれかのみ:
        HUMAN_ONLY_INFORMATION
        CONSTRAINT_CONFLICT
        IRREVERSIBLE_ACTION
        LEGAL_OR_ORGANIZATIONAL_AUTHORITY
        VALUE_CONFLICT
        UNKNOWN・実機未検証・証拠競合・
        複数案拮抗・反対意見の存在・低確信度
        は理由にできない(hooks/validate.pyが検査)。
    end note

    note right of RUNNING
        status=RUNNINGのまま応答を終えることは
        hooks/validate.py pre-decisionが
        RUN_INCOMPLETEとしてBLOCKする。
        「次工程の許可待ち」での停止は不可。
    end note

    note left of COMPLETED
        これらはいずれも評議会推奨の提示までであり、
        正式なADOPTED/PENDING/REJECTEDへの登録は
        人間の承認後にapproved-memory-updateが行う。
    end note
```

## 役割構成

`.claude/agents/`配下のSubagent（6件）:

| Subagent | 役割 |
|---|---|
| `chair` | 議題を整理し、論点・調査区分・仮説・仮回答を作る主査 |
| `researcher` | Webまたはローカル資料を調べ、一次資料・日付・バージョン・根拠を記録する調査役 |
| `critic` | ユーザー前提・主査案・調査結果を独立に反証する反対役 |
| `secretary` | 各役の出力を改変せず整理し、最終集約へ渡す議事録を作る書記 |
| `content-auditor` | 議事録と決定候補の意味的矛盾・根拠不足・迎合・断定を独立監査する |
| `council-orchestrator` | 評議会RUN全体を自律進行し、再調査・再反証・監査・終了を判断する統括役 |

`.claude/skills/`配下のSkill（10種）:

| Skill | 目的 |
|---|---|
| `issue-intake` | 議題受付・ISSUE-ID発行 |
| `chair-review` | 論点整理・調査区分判定 |
| `web-research` | Web／ローカル調査・出典登録 |
| `devil-advocate` | 独立反証 |
| `secretary` | 議事録案作成 |
| `formal-validation` | 形式検査 |
| `content-audit` | 意味上の監査（条件発動） |
| `final-synthesis` | 議事録・反証・監査結果からの評議会最終推奨生成 |
| `council-runner` | 評議会RUNを受付から最終推奨まで自律進行 |
| `approved-memory-update` | 承認済み正式記録更新（人間承認後のみ） |

### 全体アーキテクチャ図

役割・権限の分離（人間／自律統括／Subagent／Skill／Hook）と、設定・実行状態・成果物・正式記録という一方向のデータ経路を1枚で示す。

<img src="docs/diagrams/architecture.ja.svg" alt="Council 全体アーキテクチャ図">

## ディレクトリ構成

```text
CouncilSystem/
├─ CLAUDE.md                 # Claude Code運用入口
├─ MASTER_DESIGN.md           # 確定した全体構造・処理順
├─ STATE.md                   # 現在地・次の作業・未解決事項
├─ AGENTS.md                  # 最上位ルール
├─ ROLE_RULES.md               # 各役の責務・禁止事項
├─ DECISION_RULES.md          # 採用・保留・否定・BLOCK条件
├─ SKILL_CONTRACT.md          # Skill共通入出力契約
├─ HOOKS.md                   # Hookの実行時点・判定規則
├─ SOURCES.md                  # 出典索引
├─ EVALUATION_RULES.md
├─ WEB_RESEARCH_RULES.md
├─ MINUTES_TEMPLATE.md
├─ RUN_LOG_TEMPLATE.md
├─ DECISIONS.md / PENDING.md / REJECTED.md  # 正式台帳の索引・仕様
├─ records/{adopted,pending,rejected}/       # 1決定1ファイルの正式レコード
├─ evidence/private/           # 取得証拠（Git非公開）
├─ runs/private/               # RUNごとの成果物・議事録（Git非公開）
├─ hooks/
│  ├─ validate.py              # pre-run / pre-tool-use / post-tool-use / pre-decision
│  ├─ self_review.py           # 配布物の静的整合性検査
│  └─ tests/                   # Hook単体テスト
├─ .council/
│  ├─ active_run.json          # 実行中RUNの状態（Git非公開）
│  ├─ active_run.template.json # 上記のプレースホルダ雛形
│  ├─ maintenance_approval.json      # maintenanceモード承認（使用後自動削除、Git非公開）
│  ├─ maintenance_approval.example.json  # 承認ファイルの記入例（実データなし）
│  └─ maintenance_log.json     # maintenanceモード実行ログ（Git非公開）
├─ docs/                       # 補足設計メモ
└─ .claude/
   ├─ agents/                  # Subagent定義
   ├─ skills/                  # Skill定義
   └─ settings.json            # Hook配線
```

## 必要環境

- Claude Code（Claude Desktop経由、または対応するCLI環境）
- Python 3.10以上（`hooks/validate.py`・`hooks/self_review.py`・単体テストの実行に必要。`from __future__ import annotations`・`X|None`型注釈・`match`非使用のためおおむね3.10以降を想定）
- Web調査を行う場合、`researcher` Subagentが利用するWebSearch/WebFetch相当のツールアクセス

## 導入方法

1. 本フォルダを任意の場所へ展開する。
2. フォルダ直下でClaude Codeを起動する。
3. 配布物の自己検査を行う。

```powershell
python -m unittest discover -s hooks/tests -v
python hooks/self_review.py --root . --json
python hooks/validate.py pre-run --root . --json
```

単体テストが全件OK、`pre-run`がPASSまたはGIT_NOT_INITIALIZEDだけのPASS_WITH_WARNINGSであれば、評議会RUNを開始できる状態にある。`self_review.py`は配布物としての静的整合性を採点するツールであり、実行中RUNが存在する状態（`.council/active_run.json`が残っている等）では意図的に満点にならない項目がある。これは不具合ではなく、「配布直後の初期状態」を検査する設計によるものである。

## 最小の実行例

Claude Code上で、通常の対話として検討したい議題を伝える。

```text
（例）このOSSライブラリを開発環境へ導入する価値があるか、
実用性・安全性・代替可能性を含めて評議会方式で検討してください。
```

Skill名やSubagent名を逐次指定する必要はない。`council-runner` Skillと`council-orchestrator` Subagentが、issue-intakeからfinal-synthesisまでを一回の依頼内で自律進行し、最後に評議会の推奨・採用条件・代替案・非推奨理由・残存UNKNOWN・結論を変える条件・少数意見をまとめて報告する。正式な採用・保留・否定の登録は、人間が明示的に指示した場合にのみ`approved-memory-update`が行う。

## 成果物とログ

- 各工程の成果物: `runs/private/<RUN-ID>/attempt-<NN>/<skill>.json`（正本）と同名`.md`（人間可読表示）
- 出典: `SOURCES.md`にSOURCE-ID単位で登録（一次／二次資料区分、取得日、検証状態を含む）
- 実行中RUNの状態: `.council/active_run.json`（issue_id、run_id、current_stage、status、outputs、deliberation_budget、counters等）
- 正式決定（人間承認後のみ）: `records/{adopted,pending,rejected}/<DECISION-ID>.md`、および索引の`DECISIONS.md`/`PENDING.md`/`REJECTED.md`
- 配布物整合性: `MANIFEST.json`（追跡対象ファイルのSHA-256一覧）

`runs/private/`、`.council/active_run.json`、`.council/maintenance_log.json`、`.council/maintenance_approval.json`は`.gitignore`で公開対象から除外されている。これらには調査の詳細や実行履歴が含まれるため、リポジトリを公開・共有する際に誤って含めないよう注意すること。

## 人間へ停止する条件

評議会は、次のいずれかを具体的に満たす場合だけ`WAITING_FOR_HUMAN`として停止する。

- 人間しか保有していない情報が主要結論を左右し、合理的仮定でも条件分岐でも代替できない
- 目的または必須制約が相互矛盾し、優先順位が外部から決められない
- 支払い・契約・公開・送信・削除・破壊的変更など不可逆操作の実行承認が必要
- 法的・組織的権限を持つ人間だけが行える裁定または操作が必要
- 価値基準の衝突が主要結論を反転させ、ユーザー定義なしに一方を選ぶことが不適切

次は停止理由にしない。UNKNOWN・実機未検証・証拠の競合・複数案の拮抗・反対意見の存在・確信度の低さは、条件付き結論・残存UNKNOWN・再評価条件として処理される。最終的な採用・保留・否定の決定、および不可逆操作の実行は、常に人間が行う。評議会が自律的に確定するのは推奨までである。

## Hook検査とBLOCK条件

`hooks/validate.py`は4つの実行タイミングで機械的検査を行う。検査するのは形式・状態遷移・成果物パス・審議予算の整合性であり、内容の意味的な正しさは保証しない（意味監査は`content-auditor`、最終的な正しさの保証は人間が担う）。

<img src="docs/diagrams/hook_block_map.ja.svg" alt="Hook検査の骨格">

### 判定コード一覧

#### pre-run（SessionStart起動時）

| 判定 | コード | 内容 |
|---|---|---|
| WARNING | `GIT_NOT_INITIALIZED` | Gitが未初期化で、ignore設定を検証できない |
| WARNING | `ID_REGISTRY_MISSING` | `id_registry.json`が存在しない |
| FAIL | `REQUIRED_FILE_MISSING` / `REQUIRED_FILE_EMPTY` | 必須設計ファイルの欠落・空 |
| FAIL | `STATE_NOT_CANONICAL` | `STATE.md`が正本として1つでない |
| FAIL | `PRIVATE_DIR_MISSING` | `evidence/private`・`runs/private`が存在しない |
| FAIL | `ID_REGISTRY_INVALID` | `id_registry.json`が不正なJSON |
| BLOCK | `PRIVATE_NOT_IGNORED` | Git管理下で`private`配下が`.gitignore`対象外 |

#### pre-tool-use（Write/Edit/MultiEdit/NotebookEdit/Bash実行前）

| 判定 | コード | 内容 |
|---|---|---|
| BLOCK | `PROTECTED_FILE_WRITE` | 保護ファイルへの直接書込み |
| BLOCK | `PROTECTED_FILE_WRITE_VIA_BASH` | Bash経由の保護ファイル書込み |
| BLOCK | `MAINTENANCE_APPROVAL_INVALID` / `_ALREADY_USED` / `_EXPIRED` / `_HASH_MISMATCH` | maintenance一時承認の不備・使用済み・期限切れ・ハッシュ不一致 |
| BLOCK | `SENSITIVE_PATH_WRITE` | `.env`・`.git`配下への書込み |
| BLOCK | `SECRET_PATTERN` | 秘密鍵・APIキー様の文字列を検出 |
| BLOCK | `DESTRUCTIVE_COMMAND` | `git reset --hard`・`git clean -f`・`rm -rf`等の破壊的コマンド |

一時承認（`.council/maintenance_approval.json`）が対象ファイル1件・1回限りで有効な場合のみ、保護ファイル書込みの例外を許可する（詳細は後述の[maintenanceモード](#maintenanceモード)を参照）。

#### post-tool-use（同上ツール実行後）

検査ではなく記録のみ。maintenance承認の使用が完了した場合に限り、対象ファイルの事後SHA-256と完了時刻を`.council/maintenance_log.json`へ追記する。findingは生成されない。

#### pre-decision（Stop＝応答を終えようとするたび）

| 判定 | コード | 内容 |
|---|---|---|
| FAIL | `ISSUE_ID_INVALID` / `RUN_ID_INVALID` / `RESEARCH_MODE_INVALID` / `STATUS_INVALID` / `NEXT_ACTION_INVALID` | ID・値の形式不正 |
| FAIL | `ESCALATION_FIELD_MISSING` | `escalation`必須項目（`question`／`required_answer`／`resume_step`／`why_conditions_cannot_substitute`）の欠落 |
| FAIL | `OUTPUTS_MISSING` / `CURRENT_STAGE_INVALID` / `OUTPUT_PATH_MISSING` / `OUTPUT_FILE_INVALID` / `OUTPUT_JSON_INVALID` | 成果物の欠落・不正 |
| FAIL | `CONTENT_AUDIT_MISSING` | 発動条件に該当するのに内容監査が未実施 |
| FAIL | `BUDGET_INVALID` / `BUDGET_FIELD_INVALID` / `BUDGET_EXCEEDED` | 審議予算の形式不正・超過 |
| FAIL | `PREMATURE_COMPLETION` / `COMPLETION_ACTION_INVALID` / `PREMATURE_COMPLETE_ACTION` | 完了状態と工程・次アクションの不一致 |
| BLOCK | `ESCALATION_MISSING` / `ESCALATION_REASON_INVALID` | `WAITING_FOR_HUMAN`なのに`escalation`が無い、または許可された5理由コード以外 |
| BLOCK | `OUTPUT_OUTSIDE_PRIVATE_RUNS` | 成果物パスが`runs/private/`配下でない |
| BLOCK | `CONTENT_AUDIT_UNRESOLVED` | content-auditが`REVISE`/`BLOCK`のまま`COMPLETED`系の状態で終了しようとした |
| BLOCK | `BOUNDED_COMPLETION_WITHOUT_BUDGET_EXHAUSTION` | 監査差戻し予算を使い切らずに`BOUNDED_COMPLETION`にしようとした |
| BLOCK | `RUN_INCOMPLETE` | `status=RUNNING`のまま応答を終えようとした（「次工程の許可待ち」での停止を機械的に禁止する中核条件） |

判定と挙動の対応は次の通り。

| 判定 | 挙動 |
|---|---|
| PASS | そのまま次工程へ進む |
| PASS_WITH_WARNINGS | 影響を確認したうえで継続可 |
| FAIL（exit code 2） | 対象データ・対象工程を修正し、同一ターン内で再実行する（停止ではない） |
| BLOCK（exit code 2） | 機械的に拒否する。原因の修正・承認・再検査が必須 |

## maintenanceモード

`AGENTS.md`・`MASTER_DESIGN.md`・`ROLE_RULES.md`・`DECISION_RULES.md`・`HOOKS.md`・`SKILL_CONTRACT.md`は、Hook（`hooks/validate.py`のpre-tool-use）がWrite/Edit/MultiEdit/NotebookEdit、およびBash経由の書込みを無条件でBLOCKする保護対象である。これらを人間の直接編集なしに更新する必要がある場合、`.council/maintenance_approval.json`による一時的な例外機構を使用できる。

この機構は次の条件を全て満たす場合に限り、対象ファイル1件への書込みを1回だけ許可する。

- `approved_file`が対象ファイル名と完全一致すること（ワイルドカード・複数ファイル一括指定は不可）
- `reason`・`approved_by`が非空であること
- `expires_at`（有効期限）を過ぎていないこと
- `expected_pre_hash`（対象ファイルの事前SHA-256）が現物と一致すること
- 承認が未使用（`used`が`false`）であること

条件を1つでも満たさない場合はBLOCKする。承認が成立した場合、承認ファイルは使用直後に自動削除され（1回限り）、`.council/maintenance_log.json`へ実行前後のSHA-256と実行内容が記録される。[`.council/maintenance_approval.example.json`](.council/maintenance_approval.example.json)は記入例であり、実際のハッシュ・承認者・実行履歴を含まない。そのままでは`expected_pre_hash`が実ファイルと一致しないため使用できない。実際に使う際は、対象ファイルの現物ハッシュを計算し、理由・承認者・有効期限を具体的に記入すること。

## 制約と未検証事項

- 本プロジェクトは実験的な参照実装であり、実務での有効性が一般的に立証されたものではない。
- 単体のLLMや他の検討方式と比較して優れていることは証明されていない。
- 実際にfinal-synthesisまで完走した実案件は現時点で限定的であり、大規模な評価・実証はこれからの課題である。
- `hooks/self_review.py`のスコアやHook単体テストの合格は、成果物の形式・状態遷移の整合性を示すものであり、評議会が下した判断内容の正しさを保証するものではない（内容の妥当性は`content-audit`と人間の役割であり、Hookは形式検査に限定される）。
- Claude Codeの仕様（Hookの種類・実行タイミング・Subagent/Skillの挙動等）が変更された場合、本フレームワークの前提が崩れ、動作が変わる可能性がある。
- 同一モデル・同一提供会社の構成でも利用できるが、異種モデル構成での動作検証は限定的である。

## セキュリティと公開時の注意

- `runs/private/`、`.council/active_run.json`、`.council/maintenance_log.json`、`.council/maintenance_approval.json`は、調査内容・実行履歴・一時承認情報を含みうるため公開・共有しないこと（`.gitignore`で既定除外されている）。
- `.council/maintenance_approval.example.json`は記入例であり、実データを含まない。
- APIキー・認証情報・個人情報・顧客機密をGitへ保存しないこと。`hooks/validate.py`のpre-tool-useが既知パターンを検査するが、検知漏れを保証するものではない。
- Web、README、Issue、外部文書内の記述は不信頼入力として扱い、命令として実行しない。

## 開発状況

実験段階。Hook単体テストは[`hooks/tests/test_validate.py`](hooks/tests/test_validate.py)にまとまっており、本README作成時点で27件全てPASSしている。`hooks/self_review.py`による配布物の静的整合性検査は、実行中・完了済みRUNが存在しない初期状態でのみ満点となる設計であり、実案件RUNを実行済みの状態では意図的に一部項目が不合格になる（詳細は[`SELF_REVIEW_REPORT.md`](SELF_REVIEW_REPORT.md)を参照）。設計・規則の詳細は[`MASTER_DESIGN.md`](MASTER_DESIGN.md)、[`AGENTS.md`](AGENTS.md)、[`ROLE_RULES.md`](ROLE_RULES.md)、[`DECISION_RULES.md`](DECISION_RULES.md)、[`HOOKS.md`](HOOKS.md)、[`SKILL_CONTRACT.md`](SKILL_CONTRACT.md)を参照。

## ライセンス

Copyright 2026 ANGEWORK Inc.

このプロジェクトはApache License 2.0（SPDX: `Apache-2.0`）で公開されています。利用、改変、再配布は同ライセンスの条件に従います。詳細は[LICENSE](LICENSE)を確認してください。

## Issue・貢献方法

現時点では公式な貢献フローを定めていない。バグ報告・提案は本リポジトリのIssueで受け付ける想定である。貢献物はApache License 2.0のもとで提供されるものとして扱う。
