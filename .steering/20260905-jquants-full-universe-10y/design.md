# J-Quants切り替え・全銘柄・長期履歴対応 設計

## 実装アプローチ
J-Quantsは2025/12/22以降に登録したアカウントはV2 APIのみ利用可能(V1のトークン方式は廃止)。
`scripts/jquants_client.py` はV2の認証(APIキーを`x-api-key`ヘッダーに付与するのみ、有効期限なし)と
`/v2/equities/master`・`/v2/equities/bars/daily` の呼び出し(`{"data":[...], "pagination_key":...}`形式のページネーション対応)をまとめる。

`scripts/fetch_prices.py` は以下の順で処理する:
1. 銘柄マスタを `/v2/equities/master` で同期(`stocks`テーブル)。
2. 全銘柄について `/v2/equities/bars/daily?code=...` で「契約プランで取得可能な範囲を全部」取得
   → `prices` に upsert → 移動平均再計算。日付ベースの差分取得(プランごとの遅延日数を推測する
   方式)は採用しない(Freeは直近12週間が見えず過去2年強までのため、日付指定の差分取得は
   空振りし続けるバグになる)。
   - J-Quants v2は1分あたりのAPIリクエスト数に上限がある(Free:5, Light:60, Standard:120,
     Premium:500)。Freeで全銘柄(約4,000)を処理すると10時間以上かかるため、`sync_state`
     テーブルに前回の続きを記録し、実行時間予算(`RUN_BUDGET_MINUTES`)内で処理できるだけ
     進めるローテーション方式にする。CSV一括ダウンロードはLight以上限定のため使わない。
   - 1銘柄処理するごとにcommitし、失敗・タイムアウトしても他銘柄の進捗は失わない。
3. `data/latest.json`(全銘柄の最新値+取得済み件数)と
   `data/history/<code>.json`(銘柄ごと直近300営業日)を書き出す。

## 変更するコンポーネント
- 新規: `scripts/jquants_client.py`
- 変更: `scripts/fetch_prices.py`(全面書き換え)
- 変更: `scripts/requirements.txt`(yfinance削除、requests追加)
- 変更: `.github/workflows/update-data.yml`(JQUANTS_API_KEY環境変数、working-directory、timeout延長)
- 変更: `assets/app.js`(history.json一括読み込み→銘柄クリック時の個別fetchに変更、取得進捗表示、検索デバウンス)
- 削除: `data/universe.csv`、旧`data/prices.db`・`data/latest.json`・`data/history.json`(yfinance時代のデータ。J-Quantsで作り直す)

## データ構造の変更
`docs/functional-design.md` のデータモデルを参照。
主な変更点: `data/history.json`(全銘柄まとめ)を廃止し `data/history/<code>.json`(銘柄ごと)に分割。

## 影響範囲の分析
- 既存のyfinanceベースのデータ(103銘柄・1年分)は破棄し、J-Quantsで全銘柄・全期間を取り直す。
- `portal`リポジトリへの導線・URLは変更なし。
- フロントエンドのURL構造(`index.html`)・見た目は既存踏襲、データ取得ロジックのみ変更。
