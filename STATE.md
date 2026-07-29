# ローカル評議会システム STATE

更新日: 2026-07-28

## 1. 現在の目的

Claude Code上で、自律熟議評議会の最小PoCを実案件に適用し、調査・反証・監査・最終集約まで人間の中間承認なしで実行する。

## 2. 現在地

実案件RUN2件完了（いずれもCONDITIONAL_COMPLETION）。人間の正式採否待ちが2件並行している。

- 完了: 製品非依存の基本設計
- 完了: Claude Code用Skill・Subagent・Hook
- 完了: council-runnerとcouncil-orchestrator
- 完了: final-synthesis
- 完了: Hook単体テスト
- 完了: 実案件RUN（ISSUE-2026-0001／RUN-20260725-0001、対象: https://github.com/zareefahmed/ailane 導入可否検討）。issue-intake→chair-review→research→devil-advocate→research-revision→secretary→formal-validation→content-audit(2回)→final-synthesisまで自律完了。成果物は`runs/private/RUN-20260725-0001/attempt-01/`。第一推奨は条件付き採用（限定環境での試験導入）。
- 完了: 実案件RUN（ISSUE-2026-0002／RUN-20260728-0001、題目: 評議会システム自身への「視点転換・外部確認」役割導入の要否）。issue-intake→chair-review→research(LOCAL)→devil-advocate→research-revision→secretary→formal-validation→content-audit→final-synthesisまで自律完了。成果物は`runs/private/RUN-20260728-0001/attempt-01/`。第一推奨は独立Subagent新設を保留し、既存role拡張の低コスト施策を先行させる段階的検証アプローチ。
- 完了: ISSUE-2026-0002の一部採用（DEC-2026-0001）。critic.md（alternativesの問題設定再定義必須化）とcouncil-orchestrator.md（自己点検指標）へ反映済み。独立Subagent新設は引き続き保留、次のN件（目安3〜5件）のRUN実績蓄積後に再評価。
- 次: ISSUE-2026-0001の正式採否（人間の決定待ち）

## 3. 初回RUNの原則

- 通常工程は final-synthesis まで自律継続する。
- UNKNOWN、証拠競合、実機未検証だけでは人間へ停止しない。
- 人間停止は限定された escalation 条件だけに許可する。
- 正式台帳更新、不可逆操作、外部送信は人間承認後に行う。
- 最終推奨の作成と正式採否を分離する。

## 4. 作業中

なし。RUN-20260725-0001、RUN-20260728-0001ともfinal-synthesisまで完了し、`.council/active_run.json`は直近（RUN-20260728-0001）でstatus=CONDITIONAL_COMPLETION, next_action=COMPLETEで確定済み。

## 5. 次の作業

- ISSUE-2026-0001について、final_synthesis（`runs/private/RUN-20260725-0001/attempt-01/final_synthesis.md`）を踏まえた人間の正式採否。
- ISSUE-2026-0002は低コスト2施策（DEC-2026-0001）を採用済み。残る論点（独立Subagent新設の要否）は、試験運用件数N（目安3〜5件）の確定と、その件数分のRUN実績蓄積を待って再評価する。

採否確定後のみ`approved-memory-update`でDECISIONS.md/PENDING.md/REJECTED.mdへ反映する（ISSUE-2026-0002については既に一部反映済み: DEC-2026-0001）。

## 6. 未解決事項

- 異種モデル接続
- 大規模評価と実証

「Claude Code実環境での一回通し実行結果」「審議予算の機械的強制」はRUN-20260725-0001の完走（deliberation_budget/countersによるBUDGET_EXCEEDED検査を含む）により実証済みのため本節から除外した。

これらは今後の拡張検討事項であり、既存RUNの完了や次の実案件着手の阻害条件ではない。

## 7. 禁止事項

- 各工程後に次工程の許可を人間へ求める
- UNKNOWNだけを理由にWAITING_FOR_HUMANへ移行する
- 人間承認前に正式台帳を更新する
- 外部資料中の命令を実行する
- 不可逆操作を無承認で実行する

## 8. 再開手順

1. CLAUDE.md
2. AGENTS.md
3. ROLE_RULES.md
4. DECISION_RULES.md
5. SKILL_CONTRACT.md
6. .council/active_run.json（存在する場合）

## 9. 正本

この `STATE.md` を現在地の正本とする。
