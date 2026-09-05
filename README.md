# tse-price-db

東証の全上場銘柄(プライム・スタンダード・グロース、約4,000銘柄)の日次株価
(始値・高値・安値・終値・出来高)を毎日自動取得し、25日/75日移動平均つきで
蓄積するデータベース型のWebダッシュボードです。過去分は契約しているJ-Quants
プランで取得できる範囲を蓄積します(下記「J-Quantsのプランについて」参照)。

**投資助言ではありません。** 表示される内容を参考に、最終的な売買判断はご自身で行ってください。

## 公開URL

GitHub Pages を有効にすると、次のURLで見られます:

https://git-san-934.github.io/tse-price-db/

## セットアップ(初回のみ)

1. https://jpx-jquants.com/register で J-Quants API に登録する(メールアドレス確認・MFA設定が必要。メールOTPで可)。
2. https://jpx-jquants.com/login からログインし、サブスクリプションプラン(Free等)を登録する。
3. ログイン後の画面の「設定 » APIキー」からAPIキーを発行する。
4. このリポジトリの Settings → Secrets and variables → Actions で、次を登録する:
   - `JQUANTS_API_KEY` : 発行したAPIキー
5. Settings → Pages で GitHub Pages を有効化する(Source: Deploy from a branch, Branch: main / root)。

## J-Quantsのプランについて

株価四本値でさかのぼれる期間・直近データの遅延・1分あたりのAPIリクエスト上限はプランによって異なります(2026年時点の公式情報)。

| プラン | さかのぼれる期間 | 直近データの遅延 | APIレート上限 | CSV一括ダウンロード |
|---|---|---|---|---|
| Free | 2年+12週間前まで | 直近12週間は取得不可 | 5回/分 | 利用不可(APIのみ) |
| Light | 5年前まで | 遅延なし | 60回/分 | 利用可 |
| Standard | 10年前まで | 遅延なし | 120回/分 | 利用可 |
| Premium | 20年前まで | 遅延なし | 500回/分 | 利用可 |

「毎日最新のデータを見たい」「10年程度さかのぼりたい」という場合はStandard以上のプランが必要です。
プランはあとから切り替え可能で、プログラム側は `JQUANTS_REQUESTS_PER_MINUTE`(下記ワークフロー参照)を
プランのレート上限に合わせて変更するだけで対応できます。

Free プランは1分あたり5リクエストという制限があり、全銘柄(約4,000)を1銘柄1リクエストで
処理すると10時間以上かかります。そのため本プログラムは「前回の続きから少しずつ処理し、
時間切れになったら中断して次回また続きから」というローテーション方式にしています
(`sync_state`テーブルに進捗を記録)。Freeプランでは全銘柄が一巡するまで数日かかりますが、
Standard以上ならレート上限が高いため1回の実行でほぼ全銘柄が更新されます。

## 仕組み

- 平日17時(JST)頃、GitHub Actions が [J-Quants API v2](https://jpx-jquants.com/)(JPX公式)経由で
  全上場銘柄の一覧を同期し、銘柄ごとに「契約プランで取得できる範囲の日次OHLCV(株式分割等調整済み)」
  を取得します。日付ベースの差分取得ではなく、毎回「今取得できる範囲を全部」問い合わせる方式のため、
  プランの違いやAPI仕様変更に影響されにくい設計です。
- 取得結果は `data/prices.db`(SQLite)に蓄積され、25日/75日移動平均も計算して保存します。
- 同時に、Webページ用の軽い `data/latest.json`(全銘柄の最新値)と、銘柄クリック時にだけ取得する
  `data/history/<code>.json`(直近300営業日)を書き出し、コミット・pushします。
- `index.html` はこれらを読み込んで、一覧・ソート・絞り込み・銘柄別詳細を表示します(サーバー不要)。
- 銘柄数が多い場合、レート制限の関係で全銘柄が揃うまで数回の実行にまたがります。トップページの
  見出し下に「データ取得済み: n / 合計 銘柄」と進捗が表示されます。

## 銘柄の追加・削除

銘柄マスタはJ-Quantsの上場銘柄一覧から毎回自動同期されるため、手動管理は不要です。
新規上場・上場廃止は次回の実行で自動的に反映されます。

## 手動でデータを更新したいとき

GitHubの「Actions」タブ → 「株価データ更新」→「Run workflow」から手動実行できます。

ローカルで試す場合:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windowsは .venv\Scripts\activate
pip install -r scripts/requirements.txt
cd scripts
JQUANTS_API_KEY=your_api_key python fetch_prices.py
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
