---
name: content-audit
description: 評議会システムの content-audit 手続きを実行する。
---

# SKILL.md

## 目的
意味上の監査

## 入力
元議題、確認済み証拠、議事録案、AGENTS.md、DECISION_RULES.md

## 出力
PASS/PASS_WITH_WARNINGS/REVISE/BLOCK、指摘箇所、修正目標、影響範囲

## 必須処理
- 新規コンテキストで実行する
- 人間の希望結論を与えない
- 根拠支持、未確認断定、迎合、逸脱を確認する
- 監査結果を指摘書として保存する

## 禁止
- 自己申告だけでPASSにする
- 議事録を直接上書きする
- 正式決定を更新する
- council-runnerや council-orchestrator など他の役が、content-audit自身の判定（PASS/PASS_WITH_WARNINGS/REVISE/BLOCK）を上書き・書き換え・代行して宣言すること。REVISE/BLOCKの解消は、必ずcontent-auditorを新規コンテキストで再実行した結果によってのみ確認する。

## 共通契約

- リポジトリ直下の `SKILL_CONTRACT.md` に従う。
- JSON正本とMarkdown表示を同時生成する。
- 保存先、終了状態、attempt番号を必ず記録する。
