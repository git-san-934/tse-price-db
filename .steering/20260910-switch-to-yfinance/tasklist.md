# yfinanceへの切り替え(J-Quants撤去) タスクリスト

- [x] `scripts/fetch_prices.py`をyfinanceベースに全面書き換え(200銘柄バッチ、2年分取得)
- [x] `scripts/jquants_client.py`の削除
- [x] `scripts/db_common.py`から未使用の`sync_state`テーブル作成を削除
- [x] `scripts/requirements.txt`更新(yfinance追加)
- [x] `.github/workflows/update-data.yml`更新(J-Quants関連設定を削除)
- [x] `README.md` / `docs/*.md`更新
- [ ] GitHub Actions上での実機動作確認(この開発環境からはYahoo Financeへの
      アクセスがブロックされておりローカル検証不可のため)
- [ ] （不要になった）`JQUANTS_API_KEY`シークレットの削除(ユーザー作業、任意)

## 完了条件
- GitHub Actionsが正常終了し、`data/prices.db`・`data/latest.json`・
  `data/history/*.json`が更新され、翌営業日の株価が反映される。
