# 技術仕様書 — 東証株価データベース

## テクノロジースタック
| 層 | 技術 | 備考 |
|---|---|---|
| ホスティング | GitHub Pages(main / root を配信) | 静的のみ。ビルド工程なし |
| フロントエンド | 素の HTML / CSS / JavaScript(ES2020) | フレームワーク・外部チャートライブラリ不使用(SVGを直接生成) |
| 定期バッチ | GitHub Actions + Python 3.12 | `.github/workflows/update-data.yml` |
| 株価取得 | J-Quants API(JPX公式) | `scripts/jquants_client.py`。requests依存。認証はメールアドレス+パスワード |
| 蓄積用データベース | SQLite(`data/prices.db`) | Pythonの標準ライブラリ `sqlite3` で読み書き |
| フロントエンド用データ | JSON(`data/latest.json` + `data/history/<code>.json`) | Actionsが `prices.db` から生成。一覧は`latest.json`のみ、詳細は銘柄クリック時に個別取得 |
| 銘柄マスタ | J-Quants `/listed/info`(自動同期) | 全上場銘柄(プライム・スタンダード・グロース)を毎回同期。手動管理は不要 |

## なぜ SQLite + JSON の二段構成か
- GitHub Pages は静的配信のみでサーバーサイド実行環境を持てないため、ブラウザから直接SQLiteファイルへSQLを発行する仕組み(sql.js等)を使うことも可能だが、追加の依存(wasm配信)が増える。
- 一方で「日々蓄積するデータベースが欲しい」という要求には応えたいため、Actions側(Pythonが動く場所)では標準の `sqlite3` で実データベース(`data/prices.db`)を作り、リポジトリに蓄積し続ける。
- ブラウザ表示用には、そのDBから軽量な JSON を書き出して配信することで、フロントエンドをシンプルに保つ。全銘柄(約4,000)分の全期間データを1つのJSONにまとめると数百MB級になり読み込めないため、一覧用の最新値(`latest.json`)と、銘柄クリック時だけ読み込む詳細履歴(`data/history/<code>.json`、直近300営業日)に分割している。
- 将来、蓄積したデータをより高度に分析したくなった場合は、ローカルにリポジトリを clone して `data/prices.db` をそのまま SQLite クライアントや pandas で読める(こちらは取得できる最大期間の全データを保持する)。

## 初回バックフィルと日次更新の2段階運用
- 全銘柄(約4,000)×取得可能な最大期間(J-Quantsの提供開始は2008年5月7日〜、プランにより異なる)を一度に取得すると時間がかかりすぎるため、`stocks.backfilled` フラグで銘柄ごとに管理する。
- **バックフィルモード**: `backfilled=0` の銘柄が残っている間、1回の実行(`BACKFILL_BATCH_SIZE`、既定500件)につきその件数だけ `/prices/daily_quotes?code=...` で全期間分を取得して蓄積する。銘柄数が多い場合は、定期実行(平日17時)を何度か待つか、GitHubの「Run workflow」を手動で連続実行することで早められる。
- **日次更新モード**: 全銘柄のバックフィルが完了すると自動的に切り替わり、`/prices/daily_quotes?date=...` で直近数日分をまとめて取得する軽い処理になる(祝日・取得漏れに備えて直近6日分を毎回洗い替え)。
- 進捗はトップページの見出し下(「初回データ取り込み中: n / 合計 銘柄」)で確認できる。

## 開発ツールと手法
- ドキュメント先行(`docs/` と `.steering/`)。CLAUDE.md のワークフローに従う。
- ビルド/バンドラなし。ファイルをそのまま配置。
- ローカル確認は `python -m http.server`。
- ローカルでのデータ更新確認: `pip install -r scripts/requirements.txt && JQUANTS_MAIL=... JQUANTS_PASSWORD=... python scripts/fetch_prices.py`(scriptsディレクトリ内で実行)

## 技術的制約
- サーバーサイドの実行環境を持てない(GitHub Pages は静的配信のみ)。
  → 動的データは Actions が生成した JSON を介してのみ供給する。
- Actions のスケジュール実行は数分〜十数分遅延しうる。分単位の精度は保証しない。
- J-Quantsの無料プランは直近データに遅延がある(有料プランで解消可能)。取得失敗銘柄は「取得失敗」または「未取得」表示とし、他銘柄には影響させない。
- ブラウザから外部APIを直接叩かない(CORS・レート制限・認証情報の露出を避けるため)。
- 全銘柄(約4,000)分の初回バックフィルは複数回の実行にまたがる想定。GitHub Actionsの1ジョブ上限(6時間)に収まるよう `BACKFILL_BATCH_SIZE` で調整する。

## パフォーマンス要件
- 初回表示: `latest.json`(全銘柄の最新値、数MB程度)の取得・描画を数秒以内に完了することを目標とする。
- 銘柄詳細表示: `data/history/<code>.json`(1銘柄分、数十KB)をクリック時に取得するため、一覧表示自体は軽量なまま。
- 列ソート・検索絞り込み: クライアント側の配列操作のみ。数千行規模でも体感できる遅延を抑えるため、検索欄の入力は120ms程度デバウンスする。

## セキュリティ / プライバシー
- 個人情報・認証情報を一切扱わない。Cookie・localStorage も未使用。
- Actions は `contents: write` 権限のみ。`GITHUB_TOKEN` で自リポジトリへ push。
