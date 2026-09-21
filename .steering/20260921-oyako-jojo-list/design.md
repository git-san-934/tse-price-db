# 設計 — 親子上場ウォッチリストの追加

## 実装アプローチ
既存の一覧ページ(`index.html` + `assets/app.js`)と同じ構成、すなわち
「静的HTML + JSONをfetchして描画するJS」を踏襲する。サーバーは不要。

株価データと違い、親子上場の一覧は自動取得できる公開APIがないため、
調査結果を **コミット済みの静的JSON** として持つ。日次のGitHub Actions
(`update-data.yml`)は `data/oyako-jojo.json` に触れないため、株価更新との
競合は起きない。

## 変更・追加するコンポーネント
| ファイル | 内容 |
|---|---|
| `oyako.html` (新規) | 一覧ページ本体。共通CSS(`assets/style.css`)+ 専用CSS |
| `assets/oyako.css` (新規) | 統計カード・区分タグ・解説文のスタイル |
| `assets/oyako.js` (新規) | JSONの読み込み、絞り込み・並べ替え・描画 |
| `data/oyako-jojo.json` (新規) | もとデータ(meta / pairs / excluded) |
| `data/oyako-jojo.csv` (新規) | 表計算ソフト用(UTF-8 BOM付き) |
| `index.html` (変更) | ヘッダーに新ページへのリンクを追加 |
| `assets/style.css` (変更) | 両ページで使う `.backlink` を追加 |
| `README.md` (変更) | ファイル構成とページの説明を追記 |

## データ構造
```json
{
  "meta": { "created": "2026-09-21", "price_date": "2026-09-18", "universe_date": "2026-09-05" },
  "pairs": [
    {
      "code": "8060", "name": "キヤノンマーケティングジャパン", "market": "プライム",
      "mcap": 5000.0, "pbr": 1.2,
      "parent_code": "7751", "parent_name": "キヤノン", "parent_market": "プライム",
      "parent_mcap": 50000.0,
      "ratio": 51.96, "ratio_type": "所有株式数", "as_of": "2025-12-31",
      "source": "https://...", "note": "",
      "category": "連結子会社(50%超)"
    }
  ],
  "excluded": [ { "code": "...", "name": "...", "parent_code": "...", "parent_name": "...", "reason": "..." } ]
}
```

`category` は3種類のみ:
- `連結子会社(50%超)`
- `持分法適用など(20〜50%)`
- `比率未確認`

## 一覧の作成手順(再現方法)
1. 候補の親子ペアを洗い出す(公開情報・Web調査)。
2. `data/prices.db` の `stocks` テーブルに親子とも存在し、`prices` に
   直近の株価があることを確認する。存在しない銘柄は上場廃止として除外する。
3. 各社IR・有価証券報告書・適時開示などで親会社と持株比率を確認し、
   出所URLと基準日を記録する。確認できないものは「比率未確認」とする。
4. 時価総額・PBRは `stocks.shares_outstanding` / `book_value_per_share` と
   最新終値から算出する(既存の一覧と同じ計算)。

## 影響範囲の分析
- `index.html` への変更はヘッダーへのリンク1行と、CSSのキャッシュバスター更新のみ。
  既存のテーブル・ソート・詳細表示のロジックには触れない。
- `assets/style.css` への追加は `.backlink` のみで、既存セレクタと衝突しない。
- Pythonスクリプト(`scripts/`)とGitHub Actionsには変更なし。
- `data/prices.db` のスキーマは変更しない。
- 永続的ドキュメント(`docs/`)は、基本設計(データ取得の仕組み・スキーマ)に
  変更がないため更新しない。一覧ページの追加は既存サイトへのページ追加にとどまる。
