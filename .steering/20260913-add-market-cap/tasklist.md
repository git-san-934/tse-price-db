# タスクリスト — 時価総額・売買代金の追加

- [x] 1. `scripts/db_common.py`: `stocks`テーブルに`shares_outstanding` / `shares_updated_at`
      列を追加（`ensure_schema`をALTER TABLE対応に拡張、既存列チェック付き）
- [x] 2. `scripts/db_common.py`: `export_json`で`market_cap`(=close×shares_outstanding)・
      `turnover`(=close×volume)を算出し`latest.json`の各itemに追加
- [x] 3. `scripts/fetch_shares_outstanding.py` 新規作成
      （全銘柄の発行済株式数を並列個別取得し`stocks`テーブルを更新）
- [x] 4. `.github/workflows/update-shares.yml` 新規作成（月次cron + workflow_dispatch、
      `update-data`と同じconcurrency group）
- [x] 5. `index.html`: 列見出し「時価総額(億円)」「売買代金」追加、colspan 11→13
- [x] 6. `assets/app.js`: `market_cap`/`turnover`のキー→表示用マッピング、
      億円フォーマット関数追加、`render()`にセル追加、キャッシュバスティング用
      クエリ文字列の更新
- [x] 7. `docs/functional-design.md` 更新（データモデル・画面構成への追記）
- [x] 8. `docs/architecture.md` 更新（発行済株式数取得を日次から分離した設計判断を追記）
- [x] 9. 品質チェック（ローカルでのスキーマ移行確認・`export_json`出力値の検算・
      列数とcolspanの整合性確認。ブラウザでの実機確認はChrome連携ツールが
      本セッションで利用できず未実施 — マージ前に`python -m http.server`での
      目視確認を推奨）

## 完了条件
- 一覧に時価総額・売買代金の列が表示され、ソート可能。
- 発行済株式数未取得銘柄は時価総額「―」表示。
- 日次`fetch_prices.py`のロジック・実行時間に変更がない。
- 関連ドキュメント(`docs/functional-design.md`, `docs/architecture.md`)が更新されている。
