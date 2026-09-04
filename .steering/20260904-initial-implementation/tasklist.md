# 初回実装 タスクリスト

- [x] 永続的ドキュメント作成(product-requirements / functional-design / architecture)
- [x] 銘柄マスタ `data/universe.csv` の用意
- [x] `scripts/fetch_prices.py`(取得・MA計算・SQLite蓄積・JSON書き出し)
- [x] `.github/workflows/update-data.yml`(定期実行 + 手動実行)
- [x] `index.html` / `assets/style.css` / `assets/app.js`(一覧・ソート・絞り込み・詳細)
- [x] README作成
- [x] `portal` リポジトリへの導線追加
- [ ] GitHub Pages を有効化(リポジトリ設定。Actions APIからは変更不可のため手動)
- [ ] 初回のデータ取得(workflow_dispatchで手動実行、または初回の定期実行を待つ)

## 完了条件
- GitHub Pages公開後、一覧に登録銘柄の最新データが表示される。
- ポータルページから本アプリへ遷移できる。
