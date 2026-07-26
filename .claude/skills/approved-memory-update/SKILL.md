---
name: approved-memory-update
description: 評議会システムの approved-memory-update 手続きを実行する。
---

# SKILL.md

## 目的
承認済み正式記録更新

## 入力
人間承認、DECISION-ID、ISSUE-ID、承認状態、議事録、検査結果

## 出力
更新先、更新内容、Git差分、更新結果

## 必須処理
- 承認内容と更新内容を照合する
- 1決定1ファイルを状態ディレクトリへ保存・移動する
- 同一DECISION-IDを維持する
- 更新後にGit差分とSTATEを確認する

## 禁止
- 人間承認を推測する
- 承認範囲を超える
- 複数状態へ同時登録する
- 旧履歴を消す

## 共通契約

- リポジトリ直下の `SKILL_CONTRACT.md` に従う。
- JSON正本とMarkdown表示を同時生成する。
- 保存先、終了状態、attempt番号を必ず記録する。
