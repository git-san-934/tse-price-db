# tse-price-db

東証の全上場銘柄(プライム・スタンダード・グロース、約4,000銘柄)の日次株価
(始値・高値・安値・終値・出来高)を毎日自動取得し、25日/75日移動平均つきで
蓄積するデータベース型のWebダッシュボードです。過去分は取得可能な最大期間
(J-Quants APIの提供範囲。最大で2008年5月7日以降)を蓄積します。

**投資助言ではありません。** 表示される内容を参考に、最終的な売買判断はご自身で行ってください。

## 公開URL

GitHub Pages を有効にすると、次のURLで見られます:

https://git-san-934.github.io/tse-price-db/

## セットアップ(初回のみ)

1. https://jpx-jquants.com/register で J-Quants API に登録し、メールアドレス・パスワードを用意する。
   - 無料プランは直近データに遅延あり。遅延なしで毎日最新まで使いたい場合は有料プランを検討してください。
2. このリポジトリの Settings → Secrets and variables → Actions で、次の2つを登録する:
   - `JQUANTS_MAIL` : J-Quantsに登録したメールアドレス
   - `JQUANTS_PASSWORD` : J-Quantsのパスワード
3. Settings → Pages で GitHub Pages を有効化する(Source: Deploy from a branch, Branch: main / root)。

## 仕組み

- 平日17時(JST)頃、GitHub Actions が [J-Quants API](https://jpx-jquants.com/)(JPX公式)経由で
  全上場銘柄の一覧と日次OHLCV(株式分割等調整済み)を取得します。
- 取得結果は `data/prices.db`(SQLite)に蓄積され、25日/75日移動平均も計算して保存します。
- 銘柄数が多いため、初回は「バックフィルモード」で1回の実行につき一部の銘柄ずつ
  全期間分を取り込みます。全銘柄が完了すると自動的に「日次更新モード」(直近数日分だけの軽い更新)
  に切り替わります。トップページの見出し下に進捗が表示されます。
- 同時に、Webページ用の軽い `data/latest.json`(全銘柄の最新値)と、銘柄クリック時にだけ取得する
  `data/history/<code>.json`(直近300営業日)を書き出し、コミット・pushします。
- `index.html` はこれらを読み込んで、一覧・ソート・絞り込み・銘柄別詳細を表示します(サーバー不要)。

## 銘柄の追加・削除

銘柄マスタはJ-Quantsの上場銘柄一覧から毎回自動同期されるため、手動管理は不要です。
新規上場・上場廃止は次回の実行で自動的に反映されます。

## 手動でデータを更新・バックフィルを早めたいとき

GitHubの「Actions」タブ → 「株価データ更新」→「Run workflow」から手動実行できます。
バックフィル中は、これを何度か連続で実行すると早く終わります(1回につき既定500銘柄ずつ進みます)。

ローカルで試す場合:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windowsは .venv\Scripts\activate
pip install -r scripts/requirements.txt
cd scripts
JQUANTS_MAIL=your@mail.example JQUANTS_PASSWORD=yourpassword python fetch_prices.py
cd ..
python -m http.server
```

## 高値圏/安値圏の判定ロジック

- 終値が25日移動平均・75日移動平均の**両方を上回っている** → 高値圏
- 終値が25日移動平均・75日移動平均の**両方を下回っている** → 安値圏
- どちらか一方だけ上回っている(綱引き状態) → 中立
- データ不足でMA25/MA75が計算できない → 判定不可

## ファイル構成

- `index.html` / `assets/` — 一覧・詳細画面(素のHTML/CSS/JS)
- `scripts/jquants_client.py` — J-Quants API認証・呼び出しの薄いクライアント
- `scripts/fetch_prices.py` — 取得・移動平均計算・SQLite更新・JSON書き出し
- `data/prices.db` — 蓄積用SQLiteデータベース(Actionsが自動更新。銘柄マスタも含む)
- `data/latest.json` — 一覧表示用(Actionsが自動生成)
- `data/history/<code>.json` — 銘柄別詳細表示用(Actionsが自動生成。クリック時にのみ読み込まれる)
- `.github/workflows/update-data.yml` — 定期実行(平日17時JST)・手動実行
- `docs/` — 永続的な設計ドキュメント
- `.steering/` — 開発作業ごとの記録
