# 技術仕様書 — 東証株価データベース

## テクノロジースタック
| 層 | 技術 | 備考 |
|---|---|---|
| ホスティング | GitHub Pages(main / root を配信) | 静的のみ。ビルド工程なし |
| フロントエンド | 素の HTML / CSS / JavaScript(ES2020) | フレームワーク・外部チャートライブラリ不使用(SVGを直接生成) |
| 定期バッチ | GitHub Actions + Python 3.12 | `.github/workflows/update-data.yml` |
| 株価取得 | yfinance(Yahoo Finance非公式) | pandas依存 |
| 蓄積用データベース | SQLite(`data/prices.db`) | Pythonの標準ライブラリ `sqlite3` で読み書き |
| フロントエンド用データ | JSON(`data/latest.json` / `data/history.json`) | Actionsが `prices.db` から生成。ブラウザはこの2ファイルのみ読む |
| 銘柄マスタ | `data/universe.csv`(静的) | 追加・削除は手動でこのCSVを編集 |

## なぜ SQLite + JSON の二段構成か
- GitHub Pages は静的配信のみでサーバーサイド実行環境を持てないため、ブラウザから直接SQLiteファイルへSQLを発行する仕組み(sql.js等)を使うことも可能だが、追加の依存(wasm配信)が増える。
- 一方で「日々蓄積するデータベースが欲しい」という要求には応えたいため、Actions側(Pythonが動く場所)では標準の `sqlite3` で実データベース(`data/prices.db`)を作り、リポジトリに蓄積し続ける。
- ブラウザ表示用には、そのDBから軽量な JSON を書き出して配信することで、フロントエンドをシンプルに保つ。
- 将来、蓄積したデータをより高度に分析したくなった場合は、ローカルにリポジトリを clone して `data/prices.db` をそのまま SQLite クライアントや pandas で読める。

## 開発ツールと手法
- ドキュメント先行(`docs/` と `.steering/`)。CLAUDE.md のワークフローに従う。
- ビルド/バンドラなし。ファイルをそのまま配置。
- ローカル確認は `python -m http.server`。
- ローカルでのデータ更新確認: `pip install -r scripts/requirements.txt && python scripts/fetch_prices.py`

## 技術的制約
- サーバーサイドの実行環境を持てない(GitHub Pages は静的配信のみ)。
  → 動的データは Actions が生成した JSON を介してのみ供給する。
- Actions のスケジュール実行は数分〜十数分遅延しうる。分単位の精度は保証しない。
- Yahoo Finance は非公式。銘柄によっては一時的に欠損・取得失敗しうる前提で設計する(該当銘柄のみ「取得失敗」表示)。
- ブラウザから外部APIを直接叩かない(CORS・レート制限・鍵管理を避けるため)。
- 銘柄数が増えるとActionsの実行時間・`prices.db` のファイルサイズが線形に増える。数百銘柄程度を目安とする。

## パフォーマンス要件
- 初回表示: JSON 2ファイルの取得・描画を数秒以内に完了することを目標とする(登録銘柄数百件程度を想定)。
- 列ソート・検索絞り込み: 体感遅延なし(クライアント側の配列操作のみ)。

## セキュリティ / プライバシー
- 個人情報・認証情報を一切扱わない。Cookie・localStorage も未使用。
- Actions は `contents: write` 権限のみ。`GITHUB_TOKEN` で自リポジトリへ push。
