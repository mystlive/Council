---
name: issue-intake
description: 評議会システムの issue-intake 手続きを実行する。
---

# SKILL.md

## 目的
議題受付・ISSUE-ID発行

## 入力
ユーザー依頼、MASTER_DESIGN.md、STATE.md、AGENTS.md

## 出力
ISSUE-ID、議題タイトル、目的、対象範囲、既知情報、不明点、制約、完了条件

## 必須処理
- 依頼内容を勝手に狭めない
- 既存決定との重複を確認する
- 機密情報の有無を確認する
- 人間固有情報が不可欠かを判定する。軽微な不足は合理的仮定または条件分岐で継続する
- WAITING_FOR_HUMANは限定された escalation 条件を満たす場合だけ返す

## 禁止
- 結論を先に確定する
- 正式決定を更新する
- 重大な不明点を無表示で補完する。軽微な不明点は仮定を明示して継続する

## 共通契約

- リポジトリ直下の `SKILL_CONTRACT.md` に従う。
- JSON正本とMarkdown表示を同時生成する。
- 保存先、終了状態、attempt番号を必ず記録する。
