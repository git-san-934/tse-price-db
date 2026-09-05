# J-Quants切り替え・全銘柄・長期履歴対応 タスクリスト

- [x] `scripts/jquants_client.py` の実装(認証・listed_info・daily_quotes・ページネーション)
- [x] `scripts/fetch_prices.py` の全面書き換え(バックフィル/日次更新の自動切り替え)
- [x] `scripts/requirements.txt` 更新(yfinance削除、requests追加)
- [x] `.github/workflows/update-data.yml` 更新(シークレット、working-directory、timeout)
- [x] `assets/app.js` 更新(履歴の遅延読み込み、バックフィル進捗表示、検索デバウンス)
- [x] 旧yfinanceデータ(`data/universe.csv`・旧`prices.db`・`latest.json`・`history.json`)の削除
- [x] `docs/*.md` の更新
- [x] GitHub Actionsシークレット `JQUANTS_API_KEY` の設定(ユーザー作業)
- [x] 初回実行での動作確認(V1→V2切り替え、data/ディレクトリ不備、実行時間予算を修正して成功。4,448銘柄中66銘柄を取得・保存できることを確認)
- [ ] 全銘柄が揃うまでの継続実行(平日の自動実行、または`workflow_dispatch`の`run_budget_minutes`で手動加速)

## 完了条件
- [x] GitHub Actionsが正常終了し、`data/prices.db`・`data/latest.json`・`data/history/*.json` が更新される。
- [ ] 全銘柄(4,448件)分のデータが出揃う(継続実行で徐々に達成)。
