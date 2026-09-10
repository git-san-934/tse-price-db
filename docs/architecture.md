# 技術仕様書 — 東証株価データベース

## テクノロジースタック
| 層 | 技術 | 備考 |
|---|---|---|
| ホスティング | GitHub Pages(main / root を配信) | 静的のみ。ビルド工程なし |
| フロントエンド | 素の HTML / CSS / JavaScript(ES2020) | フレームワーク・外部チャートライブラリ不使用(SVGを直接生成) |
| 定期バッチ | GitHub Actions + Python 3.12 | `.github/workflows/update-data.yml` |
| 株価取得 | Yahoo Finance(yfinance) | 登録・費用不要。非公式ラッパーのため仕様変更リスクは許容している |
| 手動データ補完 | SBI証券等の株価CSV | `scripts/import_manual_csv.py`。`data/manual_csv/`へのpushで`.github/workflows/import-manual-csv.yml`が実行 |
| 蓄積用データベース | SQLite(`data/prices.db`) | Pythonの標準ライブラリ `sqlite3` で読み書き |
| フロントエンド用データ | JSON(`data/latest.json` + `data/history/<code>.json`) | Actionsが `prices.db` から生成。一覧は`latest.json`のみ、詳細は銘柄クリック時に個別取得 |
| 銘柄マスタ | `stocks`テーブル(静的、約4,449件) | J-Quants APIから開発時に一度取得したものを土台として使用。以後の自動同期はなし |

## なぜJ-Quants APIからyfinanceに切り替えたか
当初はJ-Quants API(JPX公式)を使用していたが、Freeプランでは直近12週間のデータが
取得できず、「今日の株価を見たい」という要求を満たせなかった。有料プランへの
契約(月額費用)は避けたいという意向のため、無料・登録不要で遅延の少ないyfinanceに
切り替えた。トレードオフとして、yfinanceは非公式(Yahoo Financeのスクレイピング)
であり、Yahoo側の仕様変更で予告なく壊れるリスクがある。個人利用の範囲では
広く使われている実績があり、そのリスクは許容した上で採用している。

## 銘柄マスタが静的である理由
yfinance自体には「東証の全上場銘柄一覧」を取得する機能がない。そのため、開発時に
J-Quants API(無料プランでも`/v2/equities/master`は利用可能)で一度取得した
約4,449銘柄の一覧(証券コード・日本語社名・市場区分)を`stocks`テーブルに保存し、
以後はJ-Quants APIへ再アクセスせず、この一覧を土台として使い続ける設計にした。
新規上場・上場廃止は自動反映されないが、個人利用でその都度の反映が必須ではないため
許容している。追加したい場合は`stocks`テーブルに手動で行を追加すればよい
(次回の`fetch_prices.py`実行で価格データが自動的に埋まる)。

## 「直近6か月分を毎回取り直す」設計
- `scripts/fetch_prices.py`は、実行のたびに全銘柄の直近6か月分の日次OHLCVを
  yfinanceから取得し直し、`prices`テーブルにupsertする。
- yfinanceにはJ-Quantsのようなプラン別レート制限がないため、200銘柄ずつの
  バッチに分けて`yf.download(threads=True)`で並列取得し、1回の実行で全銘柄
  (約4,449銘柄・23バッチ)を処理できる。
- `auto_adjust=True`を指定し、株式分割・配当を考慮した調整済み値を使用する。
  これにより長期の移動平均が分割によって不連続にならない。
- 「直近6か月分を毎回取り直す」ことで、取得漏れやYahoo側のデータ訂正も
  自動的に自己修復される。

## データベースのサイズ管理(GitHubの100MB制限への対応)
- 実際に全銘柄×2年分を蓄積したところ`data/prices.db`が約227MBに達し、
  GitHubの1ファイル100MB上限を超えてpushが拒否される不具合が発生した。
- 対策として、`scripts/fetch_prices.py`の株価取得後に`db_common.prune_old_prices()`
  を呼び、`PRUNE_RETENTION_DAYS`(既定200日)より古い行を毎回削除している。
  SQLiteは`DELETE`だけではファイルサイズが縮小しないため、`VACUUM`も実行する。
- 200日という保持期間は、MA75(75営業日)の計算に十分な余裕を持たせつつ、
  全銘柄分でも100MBに対して安全な余裕(目安60〜70MB程度)を残せる値として選んだ。
- この設計により、`data/prices.db`は「無限に蓄積される長期データベース」ではなく
  「直近約200日分のローリングウィンドウ」になる。より長期のデータが必要な場合は、
  保持期間を延ばす代わりにGit LFSの利用や、蓄積用DBをリポジトリの外に置く設計への
  変更を検討する必要がある(現時点では未実装)。

## 手動CSV取り込み(SBI証券等)によるさらなる鮮度向上
- yfinanceは通常翌営業日には反映されるが、それでも特定の銘柄をより新しい
  情報で上書きしたい場合に備え、証券会社が提供する個別銘柄CSVを取り込める
  補助的な仕組みを用意している。
- `data/manual_csv/` フォルダにCSVがpushされると `scripts/import_manual_csv.py` が実行され、
  該当銘柄の `prices` テーブルを upsert する(yfinance由来の行と同じテーブルに混在させ、
  日付が重複する場合は手動CSV側の値で上書きする)。
- SBI証券の「株価CSVダウンロード」形式(日付,始値,高値,安値,終値,...,出来高,...)を前提とし、
  ファイル名(`TimeChart<証券コード><yyyymmdd>.csv`)から証券コードを自動判定する。
  移動平均はCSV記載の値を使わず、`db_common.recompute_ma`で自前計算し直すことで、
  yfinance由来のMA25/75と算出方法を統一する。
- 文字コードはUTF-8(BOM付き)・Shift-JIS(CP932)の両方を試す(証券会社のCSVはShift-JISが多いため)。

## なぜ SQLite + JSON の二段構成か
- GitHub Pages は静的配信のみでサーバーサイド実行環境を持てないため、ブラウザから直接SQLiteファイルへSQLを発行する仕組み(sql.js等)を使うことも可能だが、追加の依存(wasm配信)が増える。
- 一方で「日々蓄積するデータベースが欲しい」という要求には応えたいため、Actions側(Pythonが動く場所)では標準の `sqlite3` で実データベース(`data/prices.db`)を作り、リポジトリに蓄積し続ける。
- ブラウザ表示用には、そのDBから軽量な JSON を書き出して配信することで、フロントエンドをシンプルに保つ。全銘柄(約4,449)分の全期間データを1つのJSONにまとめると数百MB級になり読み込めないため、一覧用の最新値(`latest.json`)と、銘柄クリック時だけ読み込む詳細履歴(`data/history/<code>.json`、直近300営業日)に分割している。
- 将来、蓄積したデータをより高度に分析したくなった場合は、ローカルにリポジトリを clone して `data/prices.db` をそのまま SQLite クライアントや pandas で読める。

## 開発ツールと手法
- ドキュメント先行(`docs/` と `.steering/`)。CLAUDE.md のワークフローに従う。
- ビルド/バンドラなし。ファイルをそのまま配置。
- ローカル確認は `python -m http.server`。
- ローカルでのデータ更新確認: `pip install -r scripts/requirements.txt && python scripts/fetch_prices.py`(scriptsディレクトリ内で実行)

## 技術的制約
- サーバーサイドの実行環境を持てない(GitHub Pages は静的配信のみ)。
  → 動的データは Actions が生成した JSON を介してのみ供給する。
- Actions のスケジュール実行は数分〜十数分遅延しうる。分単位の精度は保証しない。
- yfinanceは非公式ラッパーであり、Yahoo Finance側の仕様変更で予告なく動かなくなる
  可能性がある。取得失敗・未取得銘柄は該当銘柄のみ表示に反映し、他銘柄には影響させない。
- ブラウザから外部APIを直接叩かない(CORS・レート制限・認証情報の露出を避けるため)。

## パフォーマンス要件
- 初回表示: `latest.json`(全銘柄の最新値、数MB程度)の取得・描画を数秒以内に完了することを目標とする。
- 銘柄詳細表示: `data/history/<code>.json`(1銘柄分、数十KB)をクリック時に取得するため、一覧表示自体は軽量なまま。
- 列ソート・検索絞り込み: クライアント側の配列操作のみ。数千行規模でも体感できる遅延を抑えるため、検索欄の入力は120ms程度デバウンスする。

## セキュリティ / プライバシー
- 個人情報・認証情報を一切扱わない。Cookie・localStorage も未使用。
- Actions は `contents: write` 権限のみ。`GITHUB_TOKEN` で自リポジトリへ push。
