# 5年分チャート表示 設計

## 方針
日次DB(`data/prices.db`)とは別に、週次(終値・出来高のみ)の
`data/prices_weekly.db` を新設する。ファイルを分離することでサイズ予算を独立させ、
既存の日次パイプラインには影響を与えない。

## データベース
- `prices_weekly(code, date, close, volume)`、主キー `(code, date)`。
- 取得: `yf.download(period="5y", interval="1wk", auto_adjust=True, threads=True)`を
  既存と同じ200銘柄バッチで実行。
- 保持: `WEEKLY_RETENTION_DAYS = 1825`(約5年)より古い行を毎回DELETE後にVACUUM
  (`prune_old_weekly_prices`)。
- 概算サイズ: 約4,449銘柄 × 約260週 ≈ 116万行。1行あたり数十バイトとして
  50〜60MB程度と見積もり、100MB制限に対して十分な余裕がある。

## JSON書き出し
- `data/history_weekly/<code>.json`: `{date, close, volume}` の配列(直近260週)。
  `data/history/<code>.json` とは別ディレクトリで、既存の6か月用ファイルと混在しない。

## フロントエンド
- 銘柄詳細パネルに「6ヶ月」/「5年」の期間切り替えボタンを追加。
- チャート(`buildChart`)は期間に応じて `data/history/<code>.json` または
  `data/history_weekly/<code>.json` を取得して再描画する。週次データは
  `ma25`/`ma75`キーを持たないため、既存の`buildChart`ロジック(undefinedのキーは
  パスを描画しない)がそのまま使え、変更不要。
- 直近20営業日テーブルは期間切り替えの影響を受けず、常に日次(`data/history/<code>.json`)
  を表示する。

## ワークフロー
- `.github/workflows/update-data.yml` の commit ステップに
  `data/prices_weekly.db` と `data/history_weekly` を追加。
- 週次取得が加わることで実行時間がほぼ倍(日次バッチ+週次バッチ)になるため、
  `timeout-minutes` を90→120に引き上げる。
