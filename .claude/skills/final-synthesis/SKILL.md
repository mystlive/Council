---
name: final-synthesis
description: 評議会システムの final-synthesis 手続きを実行する。
---

# SKILL.md

## 目的

議事録、反証、監査結果から、評議会としての最終推奨を生成する。

## 入力

issue-intake、chair-review、devil-advocate、secretary、formal-validation。researchは調査発動時のみ、content-auditは監査発動時のみ入力する。

## 出力

第一推奨、採用条件、条件別代替案、非推奨案、残存リスク、UNKNOWN、結論反転条件、確信度。

## 必須処理

- 正式決定と評議会推奨を区別する。
- 一意に決められない場合は条件別意思決定地図を返す。
- UNKNOWNの影響を重大・中・軽微に分類する。
- 未確認事項を断定へ変換しない。
- 人間へ求めるのは最終採否または限定された権限行使だけとする。

## 禁止

- 正式台帳を更新する。
- 多数決だけで結論を作る。
- 少数意見を削除する。

## 共通契約

- リポジトリ直下の `SKILL_CONTRACT.md` に従う。
- JSON正本とMarkdown表示を同時生成する。
- 保存先、終了状態、attempt番号を必ず記録する。
