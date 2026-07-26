# Hook最小実装

- `validate.py pre-run`: 必須設計、STATE正本、privateディレクトリ、Git除外
- `validate.py pre-tool-use`: 保護ファイル、秘密情報、破壊的コマンド
- `validate.py pre-decision`: active_runがある場合のみ成果物検査

```powershell
python -m unittest discover -s hooks/tests -v
python hooks/validate.py pre-run --root . --json
```

意味監査は`content-auditor`が担当する。
