# tse-price-db

東証銘柄の日次株価(始値・高値・安値・終値・出来高)を毎日自動取得し、
25日/75日移動平均つきで蓄積するデータベース型のWebダッシュボードです。

**投資助言ではありません。** 表示される内容を参考に、最終的な売買判断はご自身で行ってください。

## 公開URL

GitHub Pages を有効にすると、次のURLで見られます:

https://git-san-934.github.io/tse-price-db/

## 仕組み

- 平日17時(JST)頃、GitHub Actions が [yfinance](https://github.com/ranaroussi/yfinance) 経由で
  `data/universe.csv` に登録した銘柄の日次OHLCVを取得します。
- 取得結果は `data/prices.db`(SQLite)に蓄積され、25日/75日移動平均も計算して保存します。
- 同時に、Webページ用の軽い `data/latest.json` / `data/history.json` を書き出し、コミット・pushします。
- `index.html` はこの2つのJSONを読み込んで、一覧・ソート・絞り込み・銘柄別詳細を表示します(サーバー不要)。

## 銘柄の追加・削除

`data/universe.csv` を編集して、`code,name,market` の形式で行を追加/削除してください。
次回のデータ更新(定期実行、または手動実行)で反映されます。

## 手動でデータを更新したいとき

GitHubの「Actions」タブ → 「株価データ更新」→「Run workflow」から手動実行できます。

ローカルで試す場合:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windowsは .venv\Scripts\activate
pip install -r scripts/requirements.txt
python scripts/fetch_prices.py
python -m http.server
```

## 高値圏/安値圏の判定ロジック

- 終値が25日移動平均・75日移動平均の**両方を上回っている** → 高値圏
- 終値が25日移動平均・75日移動平均の**両方を下回っている** → 安値圏
- どちらか一方だけ上回っている(綱引き状態) → 中立
- データ不足でMA25/MA75が計算できない → 判定不可

## ファイル構成

- `index.html` / `assets/` — 一覧・詳細画面(素のHTML/CSS/JS)
- `scripts/fetch_prices.py` — 取得・移動平均計算・SQLite更新・JSON書き出し
- `data/universe.csv` — 銘柄マスタ(手動管理)
- `data/prices.db` — 蓄積用SQLiteデータベース(Actionsが自動更新)
- `data/latest.json` / `data/history.json` — フロントエンド表示用(Actionsが自動生成)
- `.github/workflows/update-data.yml` — 定期実行(平日17時JST)・手動実行
- `docs/` — 永続的な設計ドキュメント
- `.steering/` — 開発作業ごとの記録
