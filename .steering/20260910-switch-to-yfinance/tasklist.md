# yfinanceへの切り替え(J-Quants撤去) タスクリスト

- [x] `scripts/fetch_prices.py`をyfinanceベースに全面書き換え(200銘柄バッチ)
- [x] `scripts/jquants_client.py`の削除
- [x] `scripts/db_common.py`から未使用の`sync_state`テーブル作成を削除
- [x] `scripts/requirements.txt`更新(yfinance追加)
- [x] `.github/workflows/update-data.yml`更新(J-Quants関連設定を削除)
- [x] `README.md` / `docs/*.md`更新
- [x] GitHub Actions上での実機動作確認 → 株価取得自体は成功(5分で完了)したが、
      `data/prices.db`が全銘柄×2年分で約227MBに達し、GitHubの1ファイル100MB制限で
      push が拒否される不具合を発見。
- [x] 対応: 取得期間を2年→6か月に短縮し、`db_common.prune_old_prices()`
      (`PRUNE_RETENTION_DAYS=200`日、DELETE後にVACUUM)を追加してファイルサイズを
      約60〜70MB程度に収まるよう調整。`HISTORY_ROWS`も300→120に縮小。
- [ ] 修正後の再実行でpushが成功するか確認(ユーザーへの報告待ち)
- [ ] （不要になった）`JQUANTS_API_KEY`シークレットの削除(ユーザー作業、任意)

## 完了条件
- GitHub Actionsが正常終了し、`data/prices.db`・`data/latest.json`・
  `data/history/*.json`が更新され、翌営業日の株価が反映される。
- `data/prices.db`がGitHubの100MB制限内に収まり続ける。
