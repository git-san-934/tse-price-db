# 設計 — 時価総額・売買代金の追加

## 実装アプローチ

### 1. 発行済株式数の取得（新規・低頻度）
- `stocks`テーブルに列を追加する（`db_common.ensure_schema`をALTER TABLE対応に拡張）。
  - `shares_outstanding INTEGER`（未取得はNULL）
  - `shares_updated_at TEXT`（取得日、ISO8601日付。鮮度確認用）
- 新規スクリプト `scripts/fetch_shares_outstanding.py` を追加する。
  - 全銘柄について `yf.Ticker(symbol).fast_info["shares"]` を個別取得する
    （`fast_info`は`info`よりレスポンスが軽量なため採用。取得できない場合は
    `info.get("sharesOutstanding")`にフォールバック）。
  - 個別リクエストのため `concurrent.futures.ThreadPoolExecutor`（少なめの並列数、
    目安10）で並列化しつつ、Yahoo側への負荷を抑えるため小さなスリープを挟む。
  - 取得できた銘柄から順次 `stocks` テーブルをUPDATEし、定期的にcommitする
    （長時間実行中に失敗しても途中経過が失われないように）。
  - 失敗した銘柄はログに残すのみで、既存の`shares_outstanding`値を保持する
    （既存方針「取得失敗は該当銘柄のみに反映」を踏襲）。
- `fetch_prices.py`（日次）は一切変更しない・追加の個別リクエストを行わない。
  日次実行では、既に保存済みの`shares_outstanding`を読むだけ。

### 2. 新規GitHub Actionsワークフロー（低頻度実行）
`.github/workflows/update-shares.yml` を新設する。
- 実行頻度: 月次（例: 毎月1日 UTC 8時）+ `workflow_dispatch`（手動実行）。
- 日次データ更新ワークフロー（`update-data.yml`）と同じSQLiteファイル
  (`data/prices.db`)を書き換えるため、`concurrency.group`を`update-data`と
  共有し、同時実行を避ける（daily/monthlyが競合してpushが壊れないようにする）。
- 変更があった場合のみ`data/prices.db`をcommit・push。

### 3. 算出ロジック（`db_common.export_json`）
- 一覧生成時、銘柄ごとに以下を算出し`latest.json`の各itemに追加する。
  - `market_cap` = `close * shares_outstanding`（円、整数に丸め）。
    `shares_outstanding`が未取得(NULL)の場合は`null`。
  - `turnover` = `close * volume`（円、整数に丸め）。追加取得不要、既存データのみで算出。
    `close`または`volume`が欠損の場合は`null`。
- 銘柄マスタSELECT文に`shares_outstanding`を追加する。
- 詳細パネル（`data/history/<code>.json` / `data/history_weekly/<code>.json`）は
  **変更しない**（今回のスコープは一覧行のみ。要求は「一覧のデータ行」であり、
  詳細の日次テーブルは対象外とする）。

### 4. latest.json スキーマ変更
`items[]`に以下を追加（既存フィールドは変更なし）。
| フィールド | 型 | 説明 |
|---|---|---|
| market_cap | number\|null | 時価総額(円)。終値×発行済株式数。発行済株式数未取得の場合null |
| turnover | number\|null | 売買代金(円)。終値×出来高 |

### 5. フロントエンド（`index.html` / `assets/app.js`）
- 列追加位置: 「出来高」の直後、「MA25」の直前に「時価総額」「売買代金」を追加する
  （価格・出来高・売買代金・時価総額をひとまとまりにし、その後に移動平均・判定を置く）。
- `index.html`:
  - `<thead>`に `<th data-key="marketCap">時価総額(億円)</th>` と
    `<th data-key="turnover">売買代金</th>` を追加。
  - `colspan`を11→13に更新（読み込み中/該当なし行）。
- `assets/app.js`:
  - `state.items`の各要素に`marketCap`(=`market_cap`)・`turnover`(=`market_cap`同様に
    JSONのキーをそのままcamelCaseへマッピングして保持) を持たせる
    （既存の`sortedFilteredItems`はitemのキーをそのまま参照するため、`loadData()`内で
    `market_cap`→`marketCap`、`turnover`→`turnover`のマッピングを行う）。
  - 表示フォーマット:
    - 時価総額: 億円単位・小数点1桁（例 `1,234.5`）。`okuFmt = n => n==null ? "―" : (n/1e8).toLocaleString("ja-JP", {minimumFractionDigits:1, maximumFractionDigits:1})`。
      ソートは円単位の生値(`marketCap`)で行う（表示だけ億円に変換）。
    - 売買代金: 出来高と同様に円のプレーン数値（`numberFmt`を流用）。
  - `render()`の行テンプレートに2セル追加。列見出しは既存の`data-key`と対応させる
    （ソートキー名を`marketCap`/`turnover`とし、`sortedFilteredItems`は変更不要
    ―既にitem[key]を汎用的に参照する実装のため）。

## 変更するコンポーネント
- `scripts/db_common.py`: スキーマ拡張(`ensure_schema`)、`export_json`の算出・出力追加。
- `scripts/fetch_shares_outstanding.py`: 新規スクリプト。
- `.github/workflows/update-shares.yml`: 新規ワークフロー。
- `assets/app.js`: 表示・フォーマット・列マッピング追加。
- `index.html`: 列見出し・colspan追加。
- `docs/functional-design.md`: データモデル(`stocks`・`latest.json`)、画面構成に追記。
- `docs/architecture.md`: 「発行済株式数の取得（月次・個別取得）」の設計判断を追記
  （なぜ日次バッチから分離したか、というトレードオフの記録）。

## データ構造の変更
- `stocks`テーブル: `shares_outstanding INTEGER`, `shares_updated_at TEXT` を追加
  （既存行は両方NULLから開始し、`fetch_shares_outstanding.py`初回実行で順次埋まる）。
- `latest.json`の`items[]`: `market_cap`, `turnover` を追加。

## 影響範囲の分析
- 既存の日次バッチ(`fetch_prices.py`)・既存カラム・既存の判定ロジックには影響しない。
- `data/history/<code>.json` / `data/history_weekly/<code>.json`のスキーマは変更しない
  （詳細パネルの列数・チャートに影響なし）。
- 初回は`shares_outstanding`が全銘柄NULLのため、`update-shares.yml`を最低1回
  手動実行(`workflow_dispatch`)するまでは一覧の時価総額列は全銘柄「―」表示となる。
  売買代金は初回から即座に表示される（追加取得不要のため）。
- SQLiteスキーマ変更は`ALTER TABLE ... ADD COLUMN`(NULL許容)のみなので、
  既存の`data/prices.db`に対して非破壊的に適用できる。
