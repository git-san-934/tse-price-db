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
- [x] GitHub Actions上での実機動作確認 → run #30成功(約13分で完了)。
      `data/prices_weekly.db`=63MB、`data/prices.db`=48MB(いずれも100MB制限内)。
      `data/history_weekly/`に4,430銘柄分のJSON生成、1銘柄あたり261件(約5年分、
      2021-09-20〜2026-08-31)。codes_with_data 4440/4449(日次と同水準)。
      `index.html`に期間切り替えボタン・Yahoo Finance表記を確認済み。

## 完了条件
- [x] GitHub Actionsが正常終了し、`data/prices_weekly.db`・`data/history_weekly/*.json`が
  生成・pushされる。
- [x] `data/prices_weekly.db`がGitHubの100MB制限内に収まる(実測63MB)。
- [x] サイトの配信HTMLに「5年」ボタンと週次JSONが存在することを確認(実際のクリック動作は
  ブラウザ操作環境がないため未検証。JSON形式・ボタンマークアップの存在で代替確認)。
