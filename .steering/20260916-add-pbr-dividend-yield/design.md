# 設計 — PBR・配当利回りの追加

## 実装アプローチ

### 1. BPS・配当額の取得(既存の個別取得スクリプトに相乗り)
- `stocks`テーブルに列を追加する(`db_common.ensure_schema`をALTER TABLE対応に拡張)。
  - `book_value_per_share REAL`(未取得はNULL)
  - `dividend_rate REAL`(1株当たり年間配当額。未取得はNULL)
  - 取得日時は既存の`shares_updated_at`をそのまま使う(4項目とも同じ処理・
    同じタイミングでまとめて取得するため)。
- `scripts/fetch_shares_outstanding.py`を拡張する。
  - 既に`Ticker(symbol).info`を1回呼んでいるので、そのレスポンスから
    `bookValue`(BPS)・`trailingAnnualDividendRate`(実績年間配当、なければ
    `dividendRate`で代替)も追加で取り出すだけで、追加のHTTPリクエストは発生しない。
  - 戻り値をタプルからdataclass(`Fundamentals`)に変更し、4項目を保持する
    (タプルの位置引数が増えすぎて可読性が落ちるため)。
  - DB更新は引き続きCOALESCEを使い、取得できた項目のみ上書きする。

### 2. GitHub Actionsワークフロー
既存の`.github/workflows/update-shares.yml`をそのまま使う(新規ワークフローは
不要。名称・コミットメッセージのみ「発行済株式数・EPS・BPS・配当更新」に更新)。

### 3. 算出ロジック(`db_common.export_json`)
- 一覧生成時、銘柄ごとに以下を算出し`latest.json`の各itemに追加する。
  - `pbr` = `close / book_value_per_share`(小数点1桁に丸め)。
    `book_value_per_share`が未取得(NULL)または0以下(債務超過)の場合は`null`
    (PERと同じ理由でPBRの意味をなさないため)。
  - `dividend_yield` = `dividend_rate / close * 100`(小数点2桁に丸め)。
    `dividend_rate`が未取得(NULL)の場合のみ`null`。0円配当は有効な値として
    `0.0`を返す(PBR/PERと異なり、0除算のリスクがなく「無配」は意味のある
    情報のため、nullと区別する)。
- 銘柄マスタSELECT文に`book_value_per_share`, `dividend_rate`を追加する。
- 詳細パネル(`data/history/<code>.json` / `data/history_weekly/<code>.json`)は
  **変更しない**(PERと同じく、今回のスコープは一覧行のみ)。

### 4. latest.json スキーマ変更
`items[]`に以下を追加(既存フィールドは変更なし)。
| フィールド | 型 | 説明 |
|---|---|---|
| pbr | number\|null | PBR(株価純資産倍率、倍)。終値÷BPS。BPS未取得または0以下の場合null |
| dividend_yield | number\|null | 配当利回り(%)。配当額未取得の場合null。無配は0.0 |

### 5. フロントエンド(`index.html` / `assets/app.js`)
- 列追加位置: 「PER(倍)」の直後、「MA25」の直前に「PBR(倍)」「配当利回り(%)」を
  追加する(価格・出来高・売買代金・時価総額・PER・PBR・配当利回りをひとまとまりに
  し、その後に移動平均・判定)。
- `index.html`:
  - `<thead>`に `<th data-key="pbr">PBR(倍)</th>` と
    `<th data-key="dividendYield">配当利回り(%)</th>` を追加。
  - `colspan`を14→16に更新(読み込み中/該当なし行)。
  - アセットのキャッシュバスティング用クエリ文字列を更新。
- `assets/app.js`:
  - PBRの表示は既存の`perFmt`(1桁小数+「倍」)をそのまま再利用する
    (PERと同じ「倍」単位のため専用関数は不要)。
  - 配当利回り用に`dividendYieldFmt`(2桁小数+「%」)を新設する。
  - `pbr`はJSONのキー名がそのままJS側と一致するためマッピング不要。
    `dividend_yield`は`market_cap`と同様に`loadData()`内で`dividendYield`に
    マッピングする。
  - `render()`の行テンプレートに2セル追加。CSVエクスポートのヘッダー・値にも
    PBR・配当利回りを追加。

## 変更するコンポーネント
- `scripts/db_common.py`: スキーマ拡張(`ensure_schema`)、`export_json`の算出・出力追加。
- `scripts/fetch_shares_outstanding.py`: BPS・配当額の取得を追加
  (`Fundamentals`データクラス導入)。
- `.github/workflows/update-shares.yml`: 名称・コミットメッセージ更新のみ。
- `assets/app.js`: 表示・フォーマット・CSVエクスポート追加。
- `index.html`: 列見出し・colspan・アセットバージョン更新。
- `docs/functional-design.md`: データモデル(`stocks`・`latest.json`)、画面構成に追記。
- `docs/architecture.md`: 「発行済株式数・EPS・BPS・配当・時価総額・PER・PBR・
  配当利回り」セクションに追記。

## データ構造の変更
- `stocks`テーブル: `book_value_per_share REAL`, `dividend_rate REAL` を追加
  (既存行はNULLから開始し、`fetch_shares_outstanding.py`の次回実行で
  順次埋まる)。
- `latest.json`の`items[]`: `pbr`, `dividend_yield` を追加。

## 影響範囲の分析
- 既存の日次バッチ(`fetch_prices.py`)・既存カラム・既存の判定ロジック・
  時価総額/売買代金/PER機能には影響しない。
- `data/history/<code>.json` / `data/history_weekly/<code>.json`のスキーマは変更しない。
- 初回は`book_value_per_share`・`dividend_rate`が全銘柄NULLのため、
  `update-shares.yml`が次回実行(月次または手動)されるまではPBR・配当利回り
  列は全銘柄「―」表示のままとなる。
- SQLiteスキーマ変更は`ALTER TABLE ... ADD COLUMN`(NULL許容)のみなので、
  既存の`data/prices.db`に対して非破壊的に適用できる。
- `fetch_shares_outstanding.py`の`Ticker.info`呼び出し自体は1回のまま変わらない
  ため、1銘柄あたりのリクエスト数・実行時間への追加の影響はない
  (同じレスポンスから取り出すフィールドが増えるだけ)。
