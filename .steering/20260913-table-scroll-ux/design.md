# 設計 — 一覧テーブルのスクロールUX改善

## 実装アプローチ

### 1. 上部の横スクロールバー
「ダブルスクロールバー」の定番パターンを採用する。
- `.table-scroll`（実際のテーブルを包むスクロールコンテナ）の**直前**に、
  横スクロールのためだけの薄いダミー要素 `.table-scroll-top` を追加する。
  - 中身は高さ1pxの spacer `div.table-scroll-top-inner` のみ。
  - `.table-scroll-top-inner` の幅をJSでテーブル本体の実幅
    (`table.scrollWidth`)に毎回同期させることで、下側のスクロールバーと
    同じ可動域を持たせる。
- JSで`.table-scroll`と`.table-scroll-top`の`scroll`イベントを相互に監視し、
  どちらかが動いたら他方の`scrollLeft`を同期させる（無限ループ防止のため、
  同期中はイベントを一時的に無視するフラグを持つ）。
- 縦スクロール位置に関わらず常に使えるようにするため、`.table-scroll-top`は
  `position: sticky; top: 0;` とし、既存の`thead th`の`position: sticky`の
  `top`値を`.table-scroll-top`の高さ分だけ下にずらす（重ならないようにする）。
  `z-index`は `.table-scroll-top` > `thead th` の順にする。
- テーブルの行数・列幅は検索絞り込みでは変わらないが、初期データ読み込み完了時
  （`render()`実行後）に幅を再計算する。ウィンドウリサイズ時にも再計算する
  （`resize`イベント、簡易デバウンス）。

### 2. 「先頭へ戻る」ボタン
- 固定位置(`position: fixed; right/bottom`)のボタンをページに1つ追加する。
- `window.scrollY`が一定値(例: 400px)を超えたら表示し、それ以下では非表示にする
  (`scroll`イベント、`{ passive: true }`)。
- クリック時は`window.scrollTo({ top: 0, behavior: "smooth" })`でページ最上部
  （一覧の先頭行）まで戻す。
- 詳細パネル表示中でも独立して機能する(詳細パネルの開閉とは無関係)。

## 変更するコンポーネント
- `index.html`: `.table-scroll-top`要素の追加、「先頭へ戻る」ボタン要素の追加。
- `assets/app.js`: 横スクロール同期処理、スクロール幅の再計算、「先頭へ戻る」
  ボタンの表示制御・クリック処理を追加。
- `assets/style.css`: `.table-scroll-top`のスタイル、`thead th`の`top`値調整、
  「先頭へ戻る」ボタンのスタイル(`.to-top-btn`)を追加。

## データ構造の変更
なし（表示・操作のみの変更）。

## 影響範囲の分析
- 一覧のデータ取得・ソート・検索・判定ロジック・詳細パネルには影響しない。
- 既存の`thead th { position: sticky; top: 0; }`の`top`値を変更するが、
  見た目上はスクロールバー分(たとえば14px)下にずれるだけで、ヘッダー固定の
  挙動自体は維持される。
- 外部ライブラリを追加しないため、`index.html`の`<script>`/`<link>`構成は
  変更しない(既存ファイルの追記のみ)。
- モバイル幅でも横スクロール自体は既存と同じ仕組みのため問題なし。
  「先頭へ戻る」ボタンはモバイルでも指で押しやすい大きさ・位置にする。
