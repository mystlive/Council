---
name: council-runner
description: 評議会システムの council-runner 手続きを実行する。
---

# SKILL.md

## 目的

評議会RUNを受付から最終推奨まで自律進行する。

## 入力

ユーザー依頼、RUN設定、審議予算、利用可能なSubagent・Skill、既存正本。

## 出力

各工程成果物、工程遷移履歴、最終推奨、停止理由、残存UNKNOWN。

## 必須処理

- 一回の依頼内で通常フローを連続実行する。
- 各工程後に次工程の人間承認を要求しない。
- 反証による追加調査要求を、結論影響度と取得可能性で選別する。
- 取得可能で重要な不足は自動再調査する。
- 取得不能な不足は条件付き結論へ反映する。
- 形式検査・内容監査のREVISEは対象工程へ自動差し戻す。
- content-auditがREVISEの場合、修正後にcontent-auditを新規コンテキストで再実行し、その再確認結果だけをもって解消済みとする。
- 監査差戻し予算（audit_revisions）を使い切った時点でcontent-auditの最終判定がなおREVISEまたはBLOCKである場合、COMPLETED・CONDITIONAL_COMPLETIONとしない。BOUNDED_COMPLETIONとし、未解消の指摘内容と実施した修正をfinal-synthesisへ明記する。
- 修正上限または審議予算到達時はBOUNDED_COMPLETIONとする。
- 人間停止条件は`council-orchestrator.md`の限定条件に従う。

## 禁止

- UNKNOWNだけを理由に停止する。
- 中間工程ごとに「次へ進む候補」を提示する。
- 正式決定を自動登録する。
- 不可逆操作を無承認で実行する。
- content-audit自身に代わって合否を宣言する、判定結果を書き換える、またはREVISE/BLOCKが解消していないままPASS・PASS_WITH_WARNINGSとして扱う。

## 共通契約

- リポジトリ直下の `SKILL_CONTRACT.md` に従う。
- JSON正本とMarkdown表示を同時生成する。
- 保存先、終了状態、attempt番号を必ず記録する。
