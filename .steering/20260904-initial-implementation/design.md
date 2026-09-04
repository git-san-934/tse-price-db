# 初回実装 設計

## 実装アプローチ
`docs/functional-design.md` および `docs/architecture.md` のとおり、
GitHub Actions(Python + yfinance) が `data/prices.db`(SQLite)を更新し、
あわせて `data/latest.json` / `data/history.json` を書き出す。
フロントエンド(素のHTML/CSS/JS)はこの2つのJSONのみを読み込んで表示する。

## 変更するコンポーネント(新規作成)
- `data/universe.csv` — 銘柄マスタ(stock-investingから流用)
- `scripts/fetch_prices.py` — 取得・移動平均計算・DB更新・JSON書き出し
- `scripts/requirements.txt` — yfinance, pandas
- `.github/workflows/update-data.yml` — 平日17時(JST)の定期実行
- `index.html` / `assets/style.css` / `assets/app.js` — 一覧・詳細画面
- `docs/*.md` — 永続的ドキュメント3種

## データ構造の変更
`docs/functional-design.md` のデータモデルを参照(新規作成のため差分なし)。

## 影響範囲の分析
新規リポジトリのため、他リポジトリへの影響はない。
`portal` リポジトリの `index.html` にカードを1つ追加する(既存カードへの影響なし)。
