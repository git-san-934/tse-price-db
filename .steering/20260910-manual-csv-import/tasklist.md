# SBI証券等の手動CSV取り込み タスクリスト

- [x] `scripts/db_common.py` に共通ロジックを切り出し(`fetch_prices.py`をリファクタ)
- [x] `scripts/import_manual_csv.py` の実装(ファイル名からのコード抽出、コード解決、CSV解析、upsert)
- [x] 実際にユーザー提供のSBI証券CSV(銘柄コード6525)でローカル動作確認(126件取り込み、MA計算、判定まで正常)
- [x] `.github/workflows/import-manual-csv.yml` の追加
- [x] `data/manual_csv/README.md` の追加
- [x] `README.md` / `docs/architecture.md` の更新
- [ ] 実際にGitHubのWeb UIからCSVをアップロードして、Actions経由の動作を確認(ユーザー作業)

## 完了条件
- ユーザーがSBI証券のCSVを `data/manual_csv/` にアップロードすると、
  数分以内にその銘柄の最新株価がサイトに反映される。
