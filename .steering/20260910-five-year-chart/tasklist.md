# 5年分チャート表示 タスクリスト

- [x] `scripts/db_common.py`: `prices_weekly`テーブル・`ensure_weekly_schema`・
      `prune_old_weekly_prices`・`export_weekly_json`を追加
- [x] `scripts/fetch_prices.py`: `sync_weekly_prices()`(yf.download period=5y interval=1wk)を
      追加し、`main()`から日次処理の後に呼び出す
- [x] `.github/workflows/update-data.yml`: `data/prices_weekly.db`・`data/history_weekly`を
      commit対象に追加、timeout-minutesを90→120に引き上げ
- [x] `assets/app.js`: 期間切り替えボタン(6ヶ月/5年)、`fetchHistory(code, period)`化、
      `loadDetailChart`/`loadDetailTable`分離
- [x] `index.html`: 期間切り替えボタンUI追加、凡例にMA25/MA75の表示切り替え用id追加
- [x] `assets/style.css`: `.period-toggle`/`.period-btn`のスタイル追加
- [x] 併せて`index.html`フッターの「データ提供元: J-Quants API」という古い記述を
      「Yahoo Finance(yfinance)」に修正(yfinance切り替え時の更新漏れ)
- [x] 併せて`scripts/import_manual_csv.py`の`export_json`呼び出しの`source`文字列を
      「Yahoo Finance (yfinance) + 手動CSV」に修正(同じく更新漏れ)
- [x] `README.md` / `docs/*.md`更新
- [ ] GitHub Actions上での実機動作確認(`data/prices_weekly.db`のサイズ、
      `data/history_weekly/*.json`の生成、フロントエンドでの5年チャート表示)

## 完了条件
- GitHub Actionsが正常終了し、`data/prices_weekly.db`・`data/history_weekly/*.json`が
  生成・pushされる。
- `data/prices_weekly.db`がGitHubの100MB制限内に収まる。
- サイト上で銘柄詳細を開き「5年」ボタンを押すと、週次の終値チャートが表示される。
