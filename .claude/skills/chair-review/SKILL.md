---
name: chair-review
description: 評議会システムの chair-review 手続きを実行する。
---

# SKILL.md

## 目的
論点整理・調査区分判定

## 入力
ISSUE-ID、議題内容、AGENTS.md、STATE.md、関連DECISION-ID

## 出力
論点一覧、調査区分、必要資料、仮説、仮回答、反証点

## 必須処理
- 主題と横道を分離する
- 調査区分NONE/LOCAL/WEBを選ぶ。人間固有情報はescalation候補として分離する
- ユーザー前提とモデル仮説を分ける
- 未確認事項を独立項目にする

## 禁止
- 未検証事項を断定する
- 採用・保留・否定を決定する

## 共通契約

- リポジトリ直下の `SKILL_CONTRACT.md` に従う。
- JSON正本とMarkdown表示を同時生成する。
- 保存先、終了状態、attempt番号を必ず記録する。
