# Hook最小実装

- `validate.py pre-run`（SessionStart）: 必須設計、STATE正本、privateディレクトリ、Git除外、保護ファイルのハッシュ基準線の更新（前セッションからの変更は警告）、実行中のClaude Codeの版とSubagentのmodel/effortの記録（`.council/runtime_fingerprint.json`、版が変わったら警告）
- `validate.py pre-tool-use`（PreToolUse: Write/Edit系、Bash、PowerShell）: 保護ファイル、監査成果物の上書き、秘密情報、破壊的コマンド。シェルはリダイレクト先と書込み系コマンド（cp/mv/Copy-Item/shutil/write_text 等）で書込みを判定する
- `validate.py post-tool-use`（PostToolUse）: maintenance approval の完了記録、保護ファイルの完全性照合、`active_run.json` の変更を runner の遷移規則で検証し遷移履歴へ追記
- `validate.py pre-decision`（Stop）: active_run がある場合の成果物検査、最新の監査パスの確認、工程別出力キーの警告。RUNNING 中は BLOCK するが、`stop_hook_active` かつ進展なしの再停止と24時間更新のない RUN は警告で許可
- `validate.py refresh-baseline`: 保護ファイルの基準線を人間が更新する（Claude からの実行は BLOCK）

```powershell
python -m unittest discover -s hooks/tests -v
python hooks/validate.py pre-run --root . --json
python hooks/runner.py apply --stage chair-review --output chair_review=runs/private/<RUN-ID>/attempt-01/chair_review.json --research-mode WEB
python hooks/runner.py release --reason "..."
python hooks/raw_output.py --run <RUN-ID> --attempt 1 --role critic --file returned.txt
```

意味監査は`content-auditor`が担当する。Hookは改変を検知・拒否するが、同じ権限で動くプロセスによる改ざんを完全には防げない（検知が主目的）。
