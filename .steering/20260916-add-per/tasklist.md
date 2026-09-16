# タスクリスト — PER(株価収益率)の追加

- [x] `scripts/db_common.py`: `stocks.trailing_eps`カラム追加(`ensure_schema`)
- [x] `scripts/db_common.py`: `export_json`でPER算出・`latest.json`へ出力
- [x] `scripts/fetch_shares_outstanding.py`: `info`からEPSも取得するよう拡張
      (`fetch_fundamentals`にリネーム、COALESCE更新)
- [x] `.github/workflows/update-shares.yml`: 名称・コミットメッセージ更新
- [x] `index.html`: PER列見出し追加、colspan更新(13→14)
- [x] `assets/app.js`: PERフォーマット関数・表示列・CSVエクスポート追加、colspan更新
- [x] `docs/functional-design.md`: データモデル・画面構成の更新
- [x] `docs/architecture.md`: 発行済株式数・EPS・時価総額・PERセクションの更新
- [x] Pythonの構文チェック(`python3 -m py_compile`)
- [ ] `update-shares.yml`の次回実行(月次 or 手動)でEPSが埋まり、PER列が
      実際に表示されることを確認(運用後の確認事項)
