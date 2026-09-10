"""Yahoo Finance(yfinance)から東証銘柄の日次OHLCVを取得し、
25日/75日移動平均つきで data/prices.db (SQLite) に蓄積する。

GitHub Actions（.github/workflows/update-data.yml）から定期実行される。
ローカル実行も可: `python scripts/fetch_prices.py`(scriptsディレクトリ内で実行)

## なぜJ-Quants APIからyfinanceに切り替えたか
J-Quants API(JPX公式)は正確だが、Freeプランでは直近12週間のデータが取得できず、
「今日の株価」を見たいという用途に向かなかった(有料プランへの契約は費用がかかるため回避)。
yfinanceは非公式(Yahoo Financeのスクレイピング)だが、登録不要・無料・遅延なしで
使えるため、日々の値の鮮度を優先してこちらに切り替えた。

## 銘柄マスタについて
J-Quantsで過去に取得した銘柄一覧(約4,449銘柄・日本語社名つき)を`stocks`テーブルに
そのまま残し、今後はこの一覧を土台として使う(J-Quants APIへは再アクセスしない)。
新規上場銘柄は自動追加されなくなる点は許容している(まれなケースのため)。

## 価格について
yfinanceの`auto_adjust=True`で取得する(株式分割・配当を考慮した調整済み値)。
直近2年分を毎回取得し直して upsert するため、過去の分割等があっても
移動平均が不連続にならず、取得漏れや訂正も自然に自己修復される。

あわせて、Webページ用の軽量なファイルも書き出す:
- data/latest.json        : 銘柄ごとの最新1件(値幅・出来高・移動平均・高値/安値圏の判定)
- data/history/<code>.json: 銘柄ごとの直近 HISTORY_ROWS 営業日分(詳細チャート用。クリック時に個別取得)
"""

from __future__ import annotations

import sqlite3
import time

import yfinance as yf

from db_common import DB_PATH, ensure_schema, export_json, recompute_ma

PERIOD = "2y"
BATCH_SIZE = 200
BATCH_PAUSE_SECONDS = 2.0


def to_yf_symbol(code: str) -> str:
    """J-QuantsのDB内表記(5桁、末尾にパディングの0)をyfinanceのシンボルに変換する。"""
    base = code[:-1] if len(code) == 5 else code
    return f"{base}.T"


def chunked(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def upsert_code_frame(conn: sqlite3.Connection, code: str, df) -> bool:
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if df.empty:
        return False
    rows = [
        (
            code,
            idx.strftime("%Y-%m-%d"),
            float(r.Open),
            float(r.High),
            float(r.Low),
            float(r.Close),
            int(r.Volume),
        )
        for idx, r in zip(df.index, df.itertuples())
    ]
    conn.executemany(
        """
        INSERT OR REPLACE INTO prices (code, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return True


def sync_prices(conn: sqlite3.Connection) -> None:
    codes = [r[0] for r in conn.execute("SELECT code FROM stocks ORDER BY code")]
    if not codes:
        print("銘柄マスタが空のため株価取得をスキップします")
        return

    symbol_by_code = {code: to_yf_symbol(code) for code in codes}
    batches = chunked(codes, BATCH_SIZE)
    print(f"{len(codes)}銘柄を{len(batches)}バッチ(1バッチ{BATCH_SIZE}銘柄)に分けて取得します")

    ok_count = 0
    for batch_index, batch_codes in enumerate(batches, start=1):
        symbols = [symbol_by_code[c] for c in batch_codes]
        try:
            frame = yf.download(
                symbols,
                period=PERIOD,
                interval="1d",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  バッチ{batch_index}/{len(batches)}: 取得失敗 ({exc})")
            continue

        batch_ok = 0
        for code in batch_codes:
            symbol = symbol_by_code[code]
            try:
                df = frame[symbol] if len(symbols) > 1 else frame
            except (KeyError, TypeError):
                continue
            if upsert_code_frame(conn, code, df):
                recompute_ma(conn, code)
                batch_ok += 1
        conn.commit()
        ok_count += batch_ok
        print(f"  バッチ{batch_index}/{len(batches)}: {batch_ok}/{len(batch_codes)}銘柄取得")
        time.sleep(BATCH_PAUSE_SECONDS)

    print(f"株価取得できた銘柄: {ok_count} / {len(codes)}")


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    sync_prices(conn)
    export_json(conn, source="Yahoo Finance (yfinance)")

    conn.close()


if __name__ == "__main__":
    main()
