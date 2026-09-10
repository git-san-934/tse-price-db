# yfinanceへの切り替え(J-Quants撤去) 設計

## 実装アプローチ
`scripts/fetch_prices.py`を全面書き換え:
1. `stocks`テーブル(既存の約4,449銘柄)から証券コード一覧を読む(J-Quants APIは呼ばない)。
2. 証券コード(5桁、例 "13010")をyfinanceシンボル(例 "1301.T")に変換する
   (`to_yf_symbol`: 5桁なら末尾1文字を除去、それ以外はそのまま)。
3. 200銘柄ずつのバッチに分け、`yf.download(symbols, period="2y", auto_adjust=True,
   threads=True)`で並列取得する。
4. バッチごとに`prices`テーブルへupsertし、`db_common.recompute_ma`で移動平均を再計算する。
5. 全バッチ処理後、`db_common.export_json(conn, source="Yahoo Finance (yfinance)")`で
   JSONを書き出す。

`scripts/jquants_client.py`は削除。`scripts/db_common.py`(共通スキーマ・MA計算・
JSON書き出し)と`scripts/import_manual_csv.py`(SBI証券等の手動CSV取り込み)は
変更せずそのまま使う。

`.github/workflows/update-data.yml`からJQUANTS_API_KEY等の環境変数、
run_budget_minutes入力、ローテーション関連の説明を削除し、シンプルな
チェックアウト→インストール→実行→コミットの4ステップに戻す。

## 変更するコンポーネント
- 変更: `scripts/fetch_prices.py`(全面書き換え、yfinance版)
- 削除: `scripts/jquants_client.py`
- 変更: `scripts/db_common.py`(未使用になった`sync_state`テーブル作成を削除)
- 変更: `scripts/requirements.txt`(requests削除、yfinance追加)
- 変更: `.github/workflows/update-data.yml`(J-Quants関連の設定を削除、timeout見直し)
- 変更: `README.md` / `docs/*.md`(J-Quants関連の説明をyfinanceベースに置き換え)

## データ構造の変更
スキーマ変更なし。`stocks`テーブルは今後静的に扱う(INSERT/UPDATEするコードパスがなくなる)。

## 影響範囲の分析
- `data/manual_csv/`によるSBI証券CSV取り込み機能には影響しない(db_common経由で共存)。
- 既存の`prices.db`に蓄積済みのJ-Quants由来データはそのまま残る
  (yfinanceが直近2年分を上書きし、それより古い行は保持される)。
- `portal`リポジトリへの導線・URLは変更なし。
