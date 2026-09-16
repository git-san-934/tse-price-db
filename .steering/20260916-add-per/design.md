# 設計 — PER(株価収益率)の追加

## 実装アプローチ

### 1. EPSの取得(既存の低頻度個別取得スクリプトに相乗り)
- `stocks`テーブルに列を追加する(`db_common.ensure_schema`をALTER TABLE対応に拡張)。
  - `trailing_eps REAL`(未取得はNULL)
  - 取得日時は既存の`shares_updated_at`を流用する(発行済株式数と同じ処理・
    同じタイミングでまとめて取得するため、専用カラムは追加しない)。
- `scripts/fetch_shares_outstanding.py`を拡張する。
  - これまで`fast_info`(軽量)を優先し失敗時のみ`info`にフォールバックしていたが、
    EPS(`trailingEps`)は`info`にしか含まれないため、`info`の1回の個別リクエストで
    `sharesOutstanding`と`trailingEps`を両方まとめて取得する方式に変更する
    (`fetch_shares`→`fetch_fundamentals`にリネーム)。
  - DB更新はCOALESCEを使い、取得できた項目のみ上書きする(片方だけ取得できた
    場合も既存値を保持し、上書き・削除しない。既存方針を踏襲)。
- `fetch_prices.py`(日次)は一切変更しない・追加の個別リクエストを行わない。

### 2. GitHub Actionsワークフロー
既存の`.github/workflows/update-shares.yml`をそのまま使う(新規ワークフローは
不要。名称・コミットメッセージのみ「発行済株式数・EPS更新」に更新)。

### 3. 算出ロジック(`db_common.export_json`)
- 一覧生成時、銘柄ごとに以下を算出し`latest.json`の各itemに追加する。
  - `per` = `close / trailing_eps`(小数点1桁に丸め)。
    `trailing_eps`が未取得(NULL)または0以下(赤字)の場合は`null`
    (PERの意味をなさないため)。
- 銘柄マスタSELECT文に`trailing_eps`を追加する。
- 詳細パネル(`data/history/<code>.json` / `data/history_weekly/<code>.json`)は
  **変更しない**(時価総額・売買代金と同じく、今回のスコープは一覧行のみ)。

### 4. latest.json スキーマ変更
`items[]`に以下を追加(既存フィールドは変更なし)。
| フィールド | 型 | 説明 |
|---|---|---|
| per | number\|null | PER(株価収益率、倍)。終値÷EPS。EPS未取得または0以下の場合null |

### 5. フロントエンド(`index.html` / `assets/app.js`)
- 列追加位置: 「売買代金」の直後、「MA25」の直前に「PER(倍)」を追加する
  (価格・出来高・売買代金・時価総額・PERをひとまとまりにし、その後に移動平均・判定)。
- `index.html`:
  - `<thead>`に `<th data-key="per">PER(倍)</th>` を追加。
  - `colspan`を13→14に更新(読み込み中/該当なし行)。
- `assets/app.js`:
  - `per`はJSONのキー名がそのままcamelCase互換のため、`marketCap`のような
    明示的なマッピングは不要(`...item`のスプレッドでそのまま持つ)。
  - 表示フォーマット: `perFmt = n => n==null ? "―" : n.toLocaleString("ja-JP", {minimumFractionDigits:1, maximumFractionDigits:1}) + "倍"`。
  - `render()`の行テンプレートに1セル追加。CSVエクスポートにも列を追加。

## 変更するコンポーネント
- `scripts/db_common.py`: スキーマ拡張(`ensure_schema`)、`export_json`の算出・出力追加。
- `scripts/fetch_shares_outstanding.py`: EPS取得を追加(`fetch_fundamentals`にリネーム)。
- `.github/workflows/update-shares.yml`: 名称・コミットメッセージ更新のみ。
- `assets/app.js`: 表示・フォーマット・CSVエクスポート追加。
- `index.html`: 列見出し・colspan追加。
- `docs/functional-design.md`: データモデル(`stocks`・`latest.json`)、画面構成に追記。
- `docs/architecture.md`: 「発行済株式数・EPS・時価総額・PER」セクションに追記
  (fast_info→infoへの変更理由を含む)。

## データ構造の変更
- `stocks`テーブル: `trailing_eps REAL` を追加(既存行はNULLから開始し、
  `fetch_shares_outstanding.py`の次回実行で順次埋まる)。
- `latest.json`の`items[]`: `per` を追加。

## 影響範囲の分析
- 既存の日次バッチ(`fetch_prices.py`)・既存カラム・既存の判定ロジック・
  時価総額/売買代金機能には影響しない。
- `data/history/<code>.json` / `data/history_weekly/<code>.json`のスキーマは変更しない。
- 初回は`trailing_eps`が全銘柄NULLのため、`update-shares.yml`が次回実行
  (月次または手動実行)されるまでは一覧のPER列は全銘柄「―」表示となる。
- SQLiteスキーマ変更は`ALTER TABLE ... ADD COLUMN`(NULL許容)のみなので、
  既存の`data/prices.db`に対して非破壊的に適用できる。
- `fetch_shares_outstanding.py`が`fast_info`優先から`info`に一本化されることで、
  1銘柄あたりのリクエストがやや重くなるが、リクエスト回数自体は従来の
  「基本1回(fast_info成功時)、稀に2回(フォールバック時)」から「常に1回」に
  単純化されるため、実行時間への影響は限定的と見込む。
