# タスクリスト — PBR・配当利回りの追加

- [x] `scripts/db_common.py`: `stocks.book_value_per_share`/`dividend_rate`カラム追加
      (`ensure_schema`)
- [x] `scripts/db_common.py`: `export_json`でPBR・配当利回りを算出・`latest.json`へ出力
- [x] `scripts/fetch_shares_outstanding.py`: `info`からBPS・配当額も取得するよう拡張
      (`Fundamentals`データクラス導入、COALESCE更新)
- [x] `.github/workflows/update-shares.yml`: 名称・コミットメッセージ更新
- [x] `index.html`: PBR・配当利回り列見出し追加、colspan更新(14→16)、
      アセットバージョン更新
- [x] `assets/app.js`: `dividendYieldFmt`追加、表示列・CSVエクスポート追加、
      colspan更新、`dividend_yield`→`dividendYield`マッピング追加
- [x] `docs/functional-design.md`: データモデル・画面構成の更新
- [x] `docs/architecture.md`: 発行済株式数・EPS・BPS・配当セクションの更新
- [x] Pythonの構文チェック(`python3 -m py_compile`)・JS構文チェック(`node --check`)
- [x] `export_json`のロジックをメモリDBに対してシミュレーションし、
      黒字配当あり/赤字無配/未取得/無配黒字の4パターンでPBR・配当利回り算出を確認
- [ ] `update-shares.yml`の次回実行(月次 or 手動)でBPS・配当額が埋まり、
      PBR・配当利回り列が実際に表示されることを確認(運用後の確認事項)
