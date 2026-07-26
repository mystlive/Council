# CouncilSystem Fresh Start

新規開始用の完全版です。過去RUN、過去台帳、移行処理は含みません。

## 開始

1. `CouncilSystem` フォルダを任意の場所へ展開する。
2. フォルダ直下でClaude Codeを新規起動する。
3. 評議会で検討したい依頼を入力する。通常の評議会依頼は `council-runner` と `council-orchestrator` が最終集約まで自律進行する。

工程ごとの許可、Skill名の逐次指定、active_run.jsonの手編集は不要です。

## 配布物自己検査

```powershell
python -m unittest discover -s hooks/tests -v
python hooks/self_review.py --root . --json
python hooks/validate.py pre-run --root . --json
```

`self_review` が100、単体テストが全件OK、`pre-run` がPASSまたはGIT_NOT_INITIALIZEDだけのPASS_WITH_WARNINGSであれば開始できます。
