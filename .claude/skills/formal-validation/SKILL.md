---
name: formal-validation
description: 評議会システムの formal-validation 手続きを実行する。
---

# SKILL.md

## 目的
形式検査

## 入力
対象JSON、frontmatter、AGENTS.md、DECISION_RULES.md、SKILL_CONTRACT.md

## 出力
PASS/FAIL/BLOCK、欠落項目、不正ID、重複状態、未承認更新、機密情報疑い

## 必須処理
- JSON Schemaと必須項目を検査する
- ID参照先を検査する
- 正式レコード排他を検査する
- 正式台帳更新時だけ人間承認を検査する
- 中間成果物や評議会推奨に人間承認を要求しない

## 禁止
- 内容の正しさを保証する
- 自動で正式記録を修正する

## 共通契約

- リポジトリ直下の `SKILL_CONTRACT.md` に従う。
- JSON正本とMarkdown表示を同時生成する。
- 保存先、終了状態、attempt番号を必ず記録する。
