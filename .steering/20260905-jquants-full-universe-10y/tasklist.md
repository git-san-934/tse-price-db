# J-Quants切り替え・全銘柄・長期履歴対応 タスクリスト

- [x] `scripts/jquants_client.py` の実装(認証・listed_info・daily_quotes・ページネーション)
- [x] `scripts/fetch_prices.py` の全面書き換え(バックフィル/日次更新の自動切り替え)
- [x] `scripts/requirements.txt` 更新(yfinance削除、requests追加)
- [x] `.github/workflows/update-data.yml` 更新(シークレット、working-directory、timeout)
- [x] `assets/app.js` 更新(履歴の遅延読み込み、バックフィル進捗表示、検索デバウンス)
- [x] 旧yfinanceデータ(`data/universe.csv`・旧`prices.db`・`latest.json`・`history.json`)の削除
- [x] `docs/*.md` の更新
- [ ] GitHub Actionsシークレット `JQUANTS_MAIL` / `JQUANTS_PASSWORD` の設定(ユーザー作業)
- [ ] 初回実行での動作確認(実APIレスポンスに合わせた微調整が必要になる可能性あり)
- [ ] バックフィル完了までの手動再実行(必要な場合)

## 完了条件
- GitHub Actionsが正常終了し、`data/prices.db`・`data/latest.json`・`data/history/*.json` が更新される。
- トップページで全銘柄が一覧表示され、バックフィル進捗または完了状態が確認できる。
