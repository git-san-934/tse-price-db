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
直近6か月分を毎回取得し直して upsert するため、過去の分割等があっても
移動平均が不連続にならず、取得漏れや訂正も自然に自己修復される。

## データベースのサイズについて
全銘柄(約4,449)×保持期間がそのまま`data/prices.db`のファイルサイズに比例する。
GitHubは1ファイル100MBを超えるとpushを拒否するため、`db_common.PRUNE_RETENTION_DAYS`
より古い行を毎回削除している(実測: 全銘柄×2年分で約227MBとなり上限超過した)。

あわせて、Webページ用の軽量なファイルも書き出す:
- data/latest.json        : 銘柄ごとの最新1件(値幅・出来高・移動平均・高値/安値圏の判定)
- data/history/<code>.json: 銘柄ごとの直近 HISTORY_ROWS 営業日分(詳細チャート用。クリック時に個別取得)

## 5年分チャート(週次データ)について
日次DB(data/prices.db)は直近約200日しか保持しないため、5年分をそのまま表示すると
GitHubの100MB制限を超える。そこで週次(終値・出来高のみ)の別データベース
(data/prices_weekly.db)を用意し、5年分の値動きを軽量に保持する。
"""

from __future__ import annotations

import sqlite3
import time

import pandas as pd
import yfinance as yf

from db_common import (
    DB_PATH,
    WEEKLY_DB_PATH,
    ensure_schema,
    ensure_weekly_schema,
    export_json,
    export_weekly_json,
    prune_old_prices,
    prune_old_weekly_prices,
    recompute_ma,
)

PERIOD = "6mo"
WEEKLY_PERIOD = "5y"
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


def upsert_code_frame_weekly(conn: sqlite3.Connection, code: str, df) -> bool:
    df = df[["Close", "Volume"]].dropna(subset=["Close"])
    if df.empty:
        return False
    rows = [
        (
            code,
            idx.strftime("%Y-%m-%d"),
            float(r.Close),
            None if pd.isna(r.Volume) else int(r.Volume),
        )
        for idx, r in zip(df.index, df.itertuples())
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO prices_weekly (code, date, close, volume) VALUES (?, ?, ?, ?)",
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


def sync_weekly_prices(conn: sqlite3.Connection, codes: list[str]) -> None:
    if not codes:
        print("[週次] 銘柄マスタが空のため取得をスキップします")
        return

    symbol_by_code = {code: to_yf_symbol(code) for code in codes}
    batches = chunked(codes, BATCH_SIZE)
    print(f"[週次] {len(codes)}銘柄を{len(batches)}バッチに分けて5年分の週足を取得します")

    ok_count = 0
    for batch_index, batch_codes in enumerate(batches, start=1):
        symbols = [symbol_by_code[c] for c in batch_codes]
        try:
            frame = yf.download(
                symbols,
                period=WEEKLY_PERIOD,
                interval="1wk",
                group_by="ticker",
                auto_adjust=True,
                threads=True,
                progress=False,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  [週次] バッチ{batch_index}/{len(batches)}: 取得失敗 ({exc})")
            continue

        batch_ok = 0
        for code in batch_codes:
            symbol = symbol_by_code[code]
            try:
                df = frame[symbol] if len(symbols) > 1 else frame
            except (KeyError, TypeError):
                continue
            if upsert_code_frame_weekly(conn, code, df):
                batch_ok += 1
        conn.commit()
        ok_count += batch_ok
        print(f"  [週次] バッチ{batch_index}/{len(batches)}: {batch_ok}/{len(batch_codes)}銘柄取得")
        time.sleep(BATCH_PAUSE_SECONDS)

    print(f"[週次] 株価取得できた銘柄: {ok_count} / {len(codes)}")


def main() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    sync_prices(conn)
    prune_old_prices(conn)
    export_json(conn, source="Yahoo Finance (yfinance)")

    codes = [r[0] for r in conn.execute("SELECT code FROM stocks ORDER BY code")]
    conn.close()

    weekly_conn = sqlite3.connect(WEEKLY_DB_PATH)
    ensure_weekly_schema(weekly_conn)
    sync_weekly_prices(weekly_conn, codes)
    prune_old_weekly_prices(weekly_conn)
    export_weekly_json(weekly_conn, codes)
    weekly_conn.close()


if __name__ == "__main__":
    main()
