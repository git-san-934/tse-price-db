# SBI証券等の手動CSV取り込み 設計

## 実装アプローチ
共通のDBロジック(スキーマ・移動平均計算・JSON書き出し)を `scripts/db_common.py` に切り出し、
`scripts/fetch_prices.py`(J-Quants自動取得)と `scripts/import_manual_csv.py`(手動CSV取り込み)
の両方から使う。

`scripts/import_manual_csv.py`:
1. `data/manual_csv/*.csv` を走査する。
2. ファイル名(`TimeChart<コード><yyyymmdd>.csv`)から証券コードを正規表現で抽出する。
3. `stocks`テーブルに対して、完全一致→末尾"0"付与→前方一致、の順でJ-Quants表記の
   5桁コードに解決する(SBI証券は4桁、J-Quantsは5桁表記のため)。
4. CSVを解析し(UTF-8-sig / CP932の順で試す)、日付・OHLCV列のみ`prices`にupsertする
   (移動平均列は使わず、`db_common.recompute_ma`で自前計算する)。
5. 影響を受けた銘柄の移動平均を再計算し、`db_common.export_json`でJSONを書き出す。

`.github/workflows/import-manual-csv.yml` が `data/manual_csv/*.csv` へのpushをトリガーに実行する。
`update-data.yml`と同じconcurrencyグループ(`update-data`)を使い、同時実行によるDB競合を避ける。

## 変更するコンポーネント
- 新規: `scripts/db_common.py`(共通ロジックの切り出し)
- 新規: `scripts/import_manual_csv.py`
- 新規: `.github/workflows/import-manual-csv.yml`
- 新規: `data/manual_csv/README.md`(利用者向け手順)
- 変更: `scripts/fetch_prices.py`(db_common.pyを使うようリファクタ、重複コード削除)

## データ構造の変更
スキーマ変更なし。`prices`テーブルへの書き込み元がJ-Quantsだけでなく手動CSVにも
広がるが、テーブル構造・主キー(`code`,`date`)は変わらない。

## 影響範囲の分析
- 既存のJ-Quants自動取得フローには影響しない(共通化はリファクタのみで、動作は変えていない)。
- `data/latest.json`の`source`フィールドは、手動CSV取り込み実行時のみ
  「J-Quants API v2 (JPX) + 手動CSV(SBI証券等)」に変わる(次のJ-Quants自動実行で元に戻る)。
