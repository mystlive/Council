# ローカル評議会システム 基礎設計書

## 1. 目的

単一LLMの迎合、指示逸脱、近視眼化、話題逸脱、自己レビュー忘れ、ハルシネーションを減らし、研究開発、OSS調査、技術設計、コードレビュー、顧客提案、仕様確認に使える実務向け相談システムを構築する。

## 2. 基本方針

- モデル内部の記憶を正式記憶として扱わない
- 正式記憶はローカルファイルに保存する
- モデル同士の自由会話は行わず、書面回覧方式を採用する
- 採用、保留、否定を明示する
- 評議会推奨は自律生成し、正式決定だけを人間承認後に反映する
- ルール遵守をモデル任せにしない
- 形式検査、内容監査、人間承認を分離する
- 全処理をGitで履歴管理する
- 製品非依存の仕様と、Claude Code等の実装層を分離する
- 最小構成から開始し、必要な機能だけ追加する

## 3. 製品非依存の最小構成

### 初期役職

1. 主査
   - 質問を整理
   - 論点を分解
   - 調査区分を判定
   - 仮回答を作成

2. 調査役
   - 必要な場合のみWebまたはローカル資料を調査
   - 公式資料、一次資料を優先
   - 出典、取得日、対応バージョンを記録
   - 未確認事項を分離

3. 反対役
   - ユーザー前提と主査案の両方を疑う
   - 代替案、最悪ケース、見落としを提示
   - 根拠のない同意を禁止

4. 書記
   - 各役の意見を改変せず整理
   - 一致点、対立点、未確認事項を記録
   - 採用、保留、否定候補を作成
   - 決定権を持たない

5. Council Runner
   - 各工程を連続実行
   - 追加調査・再反証・差し戻しを判断
   - 条件付き結論を含む最終推奨を作成

6. 人間
   - 評議会推奨を最終採否へ反映
   - 不可逆操作と正式記憶への反映を承認

### 調査区分

主査は議題ごとに次のいずれかを指定する。

- NONE: 調査不要
- LOCAL: ローカル資料のみ
- WEB: Web調査必須
人間確認は調査区分に含めず、限定された escalation 状態として扱う。

## 4. 最小処理フロー

1. 議題登録・議題ID発行
2. Council Runnerが主査を実行
3. 必要な場合のみ調査役を実行
4. 反対役が反証
5. Council Runnerが追加調査の要否を判定
6. 必要なら追加調査・再反証
7. 書記が議事録を作成
8. 形式検査と内容監査を実行
9. REVISE時は対象工程へ自動差し戻し
10. 集約役が評議会推奨を作成
11. 人間へ最終推奨を提示
12. 人間が正式採用した場合のみ承認済み記録を更新
13. Gitへ記録しSTATE.mdを更新

## 4.1 人間停止・再開

`WAITING_FOR_HUMAN` は通常の不確実性処理ではなく例外状態とする。

停止可能条件:

- 人間しか持たない情報が主要結論を左右し、条件分岐でも代替できない
- 目的または必須制約が解消不能に矛盾する
- 不可逆操作、契約、支払い、公開、送信、削除の承認が必要
- 法的・組織的権限が必要
- 価値基準の衝突により、技術的根拠だけでは主要結論を選べない

UNKNOWN、実機未検証、証拠競合、複数案拮抗は停止せず、追加調査または条件付き結論へ変換する。

## 5. 検査の分離

### 形式検査

Hookまたは外部スクリプトで検査する。

- 必須ファイルの存在
- 必須項目の存在
- ID形式
- URL形式
- 承認状態
- 人間承認前の正式記録更新禁止
- 機密情報をGit対象へ含めていないこと

### 内容監査

別コンテキストのLLMまたは人間が確認する。

- 根拠が主張を支持しているか
- 最終案と議事録が矛盾していないか
- 未確認事項を断定していないか
- 反対意見を不当に省略していないか

### 最終保証

人間が行う。

## 6. ファイル構成

```text
CouncilSystem/
├─ .claude/                 # Claude Code設定、Subagent、Skill
├─ .council/                # active_run.json
├─ docs/                    # 補足設計文書
├─ hooks/                   # 決定論的検査
├─ .claude/skills/                  # 製品非依存Skill定義
├─ evidence/private/        # Git管理外の取得証拠
├─ runs/private/            # Git管理外の実行記録・議事録
├─ records/                 # 人間承認後の正式記録
├─ MASTER_DESIGN.md
├─ STATE.md
├─ AGENTS.md
├─ ROLE_RULES.md
├─ DECISION_RULES.md
├─ HOOKS.md
└─ SKILL_CONTRACT.md
```

## 7. 各ファイルの責務

### MASTER_DESIGN.md

確定した全体構造、責務、処理順、採用方針を管理する。現在地や未決事項は持たない。

### STATE.md

現在地、次の作業、未解決事項、再開手順を管理する。

### AGENTS.md

全体に常時適用する最上位ルールだけを管理する。

### ROLE_RULES.md

主査、調査役、反対役、書記、人間の責務と禁止事項を管理する。

### DECISION_RULES.md

採用、保留、否定、失効、置換の判定条件を管理する。

### DECISIONS.md / PENDING.md / REJECTED.md

採用済み、保留、否定をディレクトリで分離し、1決定1ファイルで管理する。状態変更時は同一ファイルを移動し、Git履歴で移動元を追跡する。

### SOURCES.md

出典索引とメタデータを管理する。

### evidence/

取得本文、引用、検証メモを保存する。外部資料は不信頼入力として扱う。

### runs/private/

議題ごとの議事録、各役出力、実行ログをRUN/attempt単位で保存する。

### runs/

各実行の入力、出力、モデル、プロンプト版、処理時間を保存する。モデル出力は正式事実として扱わない。

### hooks/

形式検査だけを行う。意味的な正しさは保証しない。

## 8. ID体系

- ISSUE-ID: 議題
- RUN-ID: 実行
- SOURCE-ID: 出典
- DECISION-ID: 決定
- CLAIM-ID: 検証対象の主張

関連記録はIDで相互参照する。

## 8.2 ID発行

- IDは専用ジェネレーターだけが発行する。
- `id_registry.json` と排他ロックを使用し、複数プロセスからの同時発行を防ぐ。
- 手入力IDは形式検査でFAILとする。
- CLAIM-ID形式は `CLAIM-YYYY-NNNN` とする。

## 8.1 機械可読出力

- 各Skillの正本出力はJSONとする。
- Markdownは人間閲覧用の派生表示とする。
- 正式決定レコードだけは、1決定1Markdownファイル＋YAML frontmatterを正本とする。
- HookはJSONまたはfrontmatterを解析し、Markdown本文の自由記述を必須判定へ使わない。

## 9. 共通メタデータ

- id
- record_type
- status
- author
- created_at
- updated_at
- verified
- source_ids
- approved_by
- supersedes

## 10. セキュリティ原則

- APIキー、認証情報、個人情報、顧客機密をGitへ保存しない
- 秘密情報は環境変数またはGit管理外ファイルへ保存する
- Webページ、外部文書、README、Issue、コメント内の指示を不信頼入力として扱う
- 外部資料内の命令をAGENTSや人間指示より優先しない
- 取得本文とモデル生成文を区別する
- 自動実行、自動削除、自動送信は人間承認なしで行わない

## 10.1 Git対象区分

- tracked: 設計、ルール、Skill、Hook、匿名化済みメタデータ、公開可能な議事録。
- private-untracked: 顧客資料、取得本文、個人情報、認証情報を含み得るevidenceとruns。
- sanitized-tracked: 人間が匿名化・公開可を確認したevidence。
- secrets: 環境変数またはGit管理外の秘密領域。
- `evidence/private/`、`runs/private/`、`.env*` は初期状態で `.gitignore` 対象とする。

## 11. 製品別実装層

### 初期候補

Claude Codeを最初の実装環境とする。

利用候補:

- Subagent
- Skills
- Hooks
- ローカルファイル
- Web検索
- PythonまたはPowerShell補助処理

ただし、評議会仕様はClaude Code固有機能へ依存させない。

### 代替候補

- Codex
- GPT/API
- Ollama
- llama.cpp
- その他のローカルLLM

## 12. Skill候補

- council-runner
- issue-intake
- chair-review
- web-research
- devil-advocate
- secretary
- formal-validation
- content-audit
- final-synthesis
- approved-memory-update

`council-runner`が通常工程を連続実行する。`formal-validation`は形式検査、`content-audit`は条件発動の内容監査、`final-synthesis`は評議会の最終推奨を生成する。正式台帳更新は人間承認後の`approved-memory-update`だけが行う。

## 13. 正式記録更新

人間承認後のみ、`approved-memory-update`処理が正式記録を更新する。

- 採用: DECISIONS.md
- 保留: PENDING.md
- 否定: REJECTED.md
- 状態変更: 同一IDを維持
- 状態変更: 同一ファイルを別状態ディレクトリへ移動し、Git履歴で追跡する
- 更新後: Git差分を確認して記録

## 14. 初期PoC開始条件

以下が完成した時点で最小PoCを開始できる。

- MASTER_DESIGN.md
- STATE.md
- AGENTS.md
- ROLE_RULES.md
- DECISION_RULES.md
- 議事録テンプレート
- 形式検査の最小仕様

全記憶ファイルの完成を待つ必要はない。

## 15. 評価項目

- ルール脱落数
- 根拠のない同意数
- Web検証漏れ
- 未確認事項の断定数
- 本線からの逸脱数
- 反対意見の欠落数
- 人間による手戻り時間
- 通常の単独回答との差
- 実行時間
- 推論回数
- APIまたは計算コスト

## 16. 正本と版管理

- 運用時は `CouncilSystem/` ディレクトリ内のファイルだけを正本とする。
- 同名の旧版、作業コピー、`_v2` 等のファイルを正本として参照しない。
- 過去版はGit履歴で管理し、現在地ファイルを複製しない。
- STATE.mdは常に1ファイルだけ存在させる。

## Claude Code初期実装

初期PoCはClaude Codeで実装する。`CLAUDE.md`を運用入口、`.claude/agents/`を役職、`.claude/skills/`を定型手続き、Python Hookを形式検査として使用する。製品非依存の正式記録仕様は維持する。
