# 初回実装 要求

## 変更・追加する機能
- 東証銘柄の日次OHLCV(始値・高値・安値・終値・出来高)を毎日自動取得する仕組み。
- 取得結果を SQLite データベースに蓄積し続ける仕組み。
- 25日/75日移動平均を算出し、終値との比較で高値圏/中立/安値圏を判定する仕組み。
- 上記を一覧表示し、ソート・絞り込み・銘柄別詳細(チャート+直近20営業日)ができるWeb画面。
- ポータルページ(`git-san-934/portal`)への導線追加。

## ユーザーストーリー
- 利用者として、毎日自動でデータが更新されるWebページを開くだけで、登録銘柄の高値/安値の目安を確認したい。

## 受け入れ条件
- `docs/product-requirements.md` の受け入れ条件を満たすこと。
- GitHub Pages 公開後、`index.html` を開くと一覧が表示されること(初回はActions未実行のため空表示でもよいが、エラーメッセージで初回未更新であることが分かること)。
- `.github/workflows/update-data.yml` を手動実行(workflow_dispatch)すると `data/prices.db` `data/latest.json` `data/history.json` が生成・更新されること。

## 制約事項
- 既存の兄弟プロジェクト(`nikkei-heatmap` 等)と同様、GitHub Pages(静的) + GitHub Actions(Python)の構成とする。
- 銘柄マスタは `stock-investing` リポジトリの `data/tse_universe.csv` を初期値として流用する。
