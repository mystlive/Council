# Claude Code 最小PoC実装設計

## 確定条件

- 環境: Claude Desktop for Windowsから利用するClaude Code
- 初期モデル: Claude Code標準モデル
- Hook: Python
- 初回評価: 未調査の小規模OSSの導入可否調査
- ローカルLLM: 第二段階

## 配置

```text
project/
├─ CLAUDE.md
├─ .claude/
│  ├─ agents/
│  │  ├─ chair.md
│  │  ├─ researcher.md
│  │  ├─ critic.md
│  │  ├─ secretary.md
│  │  └─ content-auditor.md
│  ├─ skills/
│  └─ settings.example.json
├─ hooks/
│  └─ validate.py            # 次工程
├─ decisions/
├─ pending/
├─ rejected/
├─ minutes/
├─ evidence/
├─ runs/
└─ 既存設計文書
```

## 責務

- `CLAUDE.md`: Claude Codeが毎セッション読む短い運用規則。
- `.claude/agents/`: 独立コンテキストが必要な役職。
- `.claude/skills/`: 再利用する定型手続き。
- `hooks/`: LLMの意思と無関係に形式を検査。
- 正式記録: 人間承認後だけ更新。

## 最小PoCフロー

```text
議題受付Skill
→ chair
→ researcher（WEB/LOCALのみ）
→ critic
→ secretary
→ Python形式検査
→ content-auditor
→ 評議会最終推奨 → 人間による正式採否
→ 承認済み記録更新Skill
```

## 実装順

1. Python Hookの形式検査
2. settings.jsonへのHook登録
3. Subagent単体試験
4. Skill単体試験
5. OSS調査の通し試験
6. 通常Claude Code回答との比較

## 非採用

- 自由会話型マルチエージェント
- 自動裁定
- 初期段階のローカルLLM
- MCP、ベクトルDB、LangGraph
