# J-Quants切り替え・全銘柄・長期履歴対応 設計

## 実装アプローチ
`scripts/jquants_client.py` に J-Quants API の認証(メール+パスワード→リフレッシュトークン→IDトークン)と
`/listed/info`・`/prices/daily_quotes` の呼び出し(ページネーション対応)をまとめる。

`scripts/fetch_prices.py` は以下の順で処理する:
1. 銘柄マスタを `/listed/info` で同期(`stocks`テーブル、既存の`backfilled`フラグは維持)。
2. `stocks.backfilled = 0` の銘柄が残っていれば、最大 `BACKFILL_BATCH_SIZE` 件だけ
   `/prices/daily_quotes?code=...` で全期間取得 → `prices` に upsert → 移動平均再計算 → `backfilled=1`。
   1銘柄処理するごとにcommitし、失敗しても他銘柄の進捗は失わない。
3. バックフィル未処理銘柄がなければ、直近6日分を `/prices/daily_quotes?date=...` で取得し、
   影響を受けた銘柄だけ移動平均を再計算する(祝日・取得漏れの自己修復も兼ねる)。
4. `data/latest.json`(全銘柄の最新値+バックフィル進捗)と
   `data/history/<code>.json`(銘柄ごと直近300営業日)を書き出す。

## 変更するコンポーネント
- 新規: `scripts/jquants_client.py`
- 変更: `scripts/fetch_prices.py`(全面書き換え)
- 変更: `scripts/requirements.txt`(yfinance削除、requests追加)
- 変更: `.github/workflows/update-data.yml`(JQUANTS_MAIL/JQUANTS_PASSWORD環境変数、working-directory、timeout延長)
- 変更: `assets/app.js`(history.json一括読み込み→銘柄クリック時の個別fetchに変更、バックフィル進捗表示、検索デバウンス)
- 削除: `data/universe.csv`、旧`data/prices.db`・`data/latest.json`・`data/history.json`(yfinance時代のデータ。J-Quantsで作り直す)

## データ構造の変更
`docs/functional-design.md` のデータモデルを参照。
主な変更点: `stocks.backfilled` カラム追加、`data/history.json`(全銘柄まとめ)を廃止し
`data/history/<code>.json`(銘柄ごと)に分割。

## 影響範囲の分析
- 既存のyfinanceベースのデータ(103銘柄・1年分)は破棄し、J-Quantsで全銘柄・全期間を取り直す。
- `portal`リポジトリへの導線・URLは変更なし。
- フロントエンドのURL構造(`index.html`)・見た目は既存踏襲、データ取得ロジックのみ変更。
