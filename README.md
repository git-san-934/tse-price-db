# tse-price-db

東証の全上場銘柄(プライム・スタンダード・グロース、約4,449銘柄)の日次株価
(始値・高値・安値・終値・出来高)を毎日自動取得し、25日/75日移動平均つきで
蓄積するデータベース型のWebダッシュボードです。データ取得元は
[Yahoo Finance](https://finance.yahoo.com/)(yfinance経由)で、登録・費用不要、
遅延もほぼありません。

**投資助言ではありません。** 表示される内容を参考に、最終的な売買判断はご自身で行ってください。

## 公開URL

GitHub Pages を有効にすると、次のURLで見られます:

https://git-san-934.github.io/tse-price-db/

## セットアップ(初回のみ)

登録・APIキーの類は一切不要です。Settings → Pages で GitHub Pages を有効化するだけです
(Source: Deploy from a branch, Branch: main / root)。

## 仕組み

- 平日17時(JST)頃、GitHub Actions が yfinance(Yahoo Finance)経由で全銘柄の直近6か月分の
  日次OHLCV(株式分割等調整済み)を取得します。レート制限がないため、毎回全銘柄を
  一括更新できます(200銘柄ずつバッチ処理)。
- 取得結果は `data/prices.db`(SQLite)に蓄積され、25日/75日移動平均も計算して保存します。
  GitHubの1ファイル100MB制限を超えないよう、約200日より古いデータは毎回自動削除しています
  (全銘柄×2年分だと約227MBになり上限を超えるため)。
- 同時に、Webページ用の軽い `data/latest.json`(全銘柄の最新値)と、銘柄クリック時にだけ取得する
  `data/history/<code>.json`(直近120営業日)を書き出し、コミット・pushします。
- `index.html` はこれらを読み込んで、一覧・ソート・絞り込み・銘柄別詳細を表示します(サーバー不要)。

## 銘柄マスタについて

銘柄一覧(約4,449銘柄・日本語社名つき)は、開発時にJ-Quants API(JPX公式)から一度取得した
ものを `stocks` テーブルの土台として使っています。yfinance自体には全銘柄一覧を取得する
機能がないためです。新規上場銘柄は自動追加されません。追加したい場合は
`data/prices.db` の `stocks` テーブルに手動で行を追加してください(次回の株価更新で
自動的にデータが埋まります)。

## 注目銘柄だけさらに新鮮にする(SBI証券などのCSV取り込み)

yfinanceは通常翌営業日には反映されますが、それでも特定の銘柄をより新しい情報で
上書きしたい場合、証券会社(SBI証券など)からダウンロードした個別銘柄の株価CSVを
`data/manual_csv/` フォルダにアップロードすると、その銘柄のデータが上書きされます。

1. SBI証券のサイトで、個別銘柄の「株価CSVダウンロード」を行う
   (ファイル名は "TimeChart証券コードyyyymmdd.csv" の形式。リネーム不要)
2. このリポジトリの `data/manual_csv/` フォルダを開き、「Add file」→「Upload files」で
   ダウンロードしたCSVをドラッグ&ドロップし、コミットする
3. 自動的にGitHub Actionsが動き、数分後にその銘柄の最新データがサイトに反映される

詳しくは `data/manual_csv/README.md` を参照してください。

## 手動でデータを更新したいとき

GitHubの「Actions」タブ → 「株価データ更新」→「Run workflow」から手動実行できます。

ローカルで試す場合:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windowsは .venv\Scripts\activate
pip install -r scripts/requirements.txt
cd scripts
python fetch_prices.py
cd ..
python -m http.server
```

## 高値圏/安値圏の判定ロジック

- 終値が25日移動平均・75日移動平均の**両方を上回っている** → 高値圏
- 終値が25日移動平均・75日移動平均の**両方を下回っている** → 安値圏
- どちらか一方だけ上回っている(綱引き状態) → 中立
- データ不足でMA25/MA75が計算できない → 判定不可

## yfinanceについての注意

yfinanceはYahoo Financeの非公式ラッパーです。Yahoo側の仕様変更やアクセス制限により、
予告なく動かなくなる可能性があります。個人利用の範囲では広く使われていますが、
その点は許容した上でご利用ください。動かなくなった場合の代替として、
`data/manual_csv/`(SBI証券等のCSV取り込み)や、J-Quants APIへの再切り替え
(過去の実装は `git log` で辿れます)を検討してください。

## ファイル構成

- `index.html` / `assets/` — 一覧・詳細画面(素のHTML/CSS/JS)
- `scripts/db_common.py` — SQLiteスキーマ・移動平均計算・JSON書き出し(共通ロジック)
- `scripts/fetch_prices.py` — yfinanceからの自動取得・SQLite更新
- `scripts/import_manual_csv.py` — SBI証券等の手動CSV取り込み
- `data/prices.db` — 蓄積用SQLiteデータベース(Actionsが自動更新。銘柄マスタも含む)
- `data/latest.json` — 一覧表示用(Actionsが自動生成)
- `data/history/<code>.json` — 銘柄別詳細表示用(Actionsが自動生成。クリック時にのみ読み込まれる)
- `data/manual_csv/` — 手動CSVのアップロード先(利用者が配置。README参照)
- `.github/workflows/update-data.yml` — 定期実行(平日17時JST)・手動実行
- `.github/workflows/import-manual-csv.yml` — 手動CSVアップロード時の自動取り込み
- `docs/` — 永続的な設計ドキュメント
- `.steering/` — 開発作業ごとの記録
