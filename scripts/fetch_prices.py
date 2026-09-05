"""J-Quants API(JPX公式)から東証全銘柄の日次OHLCVを取得し、
25日/75日移動平均つきで data/prices.db (SQLite) に蓄積する。

GitHub Actions（.github/workflows/update-data.yml）から定期実行される。
ローカル実行も可(環境変数 JQUANTS_MAIL / JQUANTS_PASSWORD が必要):
    export JQUANTS_MAIL=... JQUANTS_PASSWORD=...
    python scripts/fetch_prices.py

## 実行モード
- 銘柄マスタ(data/prices.db の stocks テーブル)は毎回 /listed/info で同期する。
  新規上場・廃止銘柄が自動的に反映される。
- stocks.backfilled = 0 の銘柄が残っている間は「初回バックフィルモード」:
  1回の実行につき最大 BACKFILL_BATCH_SIZE 銘柄だけ、取得可能な全期間(最大10年強)の
  日次データを /prices/daily_quotes?code=... で取得して蓄積する。
  銘柄数が多い場合は複数回の実行(手動再実行 or 次回の定期実行)にまたがって進む。
- 全銘柄のバックフィルが完了すると「日次更新モード」に自動的に切り替わり、
  直近数日分を /prices/daily_quotes?date=... でまとめて取得する軽い処理になる。

## 価格について
J-Quants が提供する「調整済み株価」(AdjustmentOpen/High/Low/Close/Volume)を使用する。
株式分割・併合を考慮済みのため、10年分の長期データでも移動平均が分割によって
不連続にならない。

あわせて、Webページ用の軽量なファイルも書き出す:
- data/latest.json        : 銘柄ごとの最新1件(値幅・出来高・移動平均・高値/安値圏の判定)
- data/history/<code>.json: 銘柄ごとの直近 HISTORY_ROWS 営業日分(詳細チャート用。クリック時に個別取得)
"""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from jquants_client import JQuantsClient

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "prices.db"
LATEST_JSON = ROOT / "data" / "latest.json"
HISTORY_DIR = ROOT / "data" / "history"

JST = timezone(timedelta(hours=9))

MA_SHORT_WINDOW = 25
MA_LONG_WINDOW = 75
HISTORY_ROWS = 300
BACKFILL_BATCH_SIZE = int(os.environ.get("BACKFILL_BATCH_SIZE", "500"))
INCREMENTAL_LOOKBACK_DAYS = 6


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            market TEXT,
            backfilled INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prices (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            ma25 REAL,
            ma75 REAL,
            PRIMARY KEY (code, date)
        )
        """
    )


def sync_universe(conn: sqlite3.Connection, client: JQuantsClient) -> None:
    """上場銘柄一覧を同期する。既存銘柄の backfilled フラグは維持する。"""
    info = client.listed_info()
    print(f"上場銘柄一覧: {len(info)} 件")
    rows = [
        (item["Code"], item.get("CompanyName") or item["Code"], item.get("MarketCodeName") or "")
        for item in info
        if item.get("Code")
    ]
    conn.executemany(
        """
        INSERT INTO stocks (code, name, market) VALUES (?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET name = excluded.name, market = excluded.market
        """,
        rows,
    )
    conn.commit()


def quote_row(q: dict) -> tuple | None:
    """J-Quantsの1レコードをprices用のタプルに変換する(調整済み値を使用)。"""
    close = q.get("AdjustmentClose")
    if close is None:
        return None
    return (
        q["Code"],
        q["Date"],
        q.get("AdjustmentOpen"),
        q.get("AdjustmentHigh"),
        q.get("AdjustmentLow"),
        close,
        q.get("AdjustmentVolume"),
    )


def upsert_quotes(conn: sqlite3.Connection, quotes: list[dict]) -> set[str]:
    rows = [r for r in (quote_row(q) for q in quotes) if r is not None]
    conn.executemany(
        """
        INSERT OR REPLACE INTO prices (code, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    return {r[0] for r in rows}


def recompute_ma(conn: sqlite3.Connection, code: str) -> None:
    df = pd.read_sql_query(
        "SELECT date, close FROM prices WHERE code = ? ORDER BY date", conn, params=(code,)
    )
    if df.empty:
        return
    df["ma25"] = df["close"].rolling(MA_SHORT_WINDOW).mean()
    df["ma75"] = df["close"].rolling(MA_LONG_WINDOW).mean()
    conn.executemany(
        "UPDATE prices SET ma25 = ?, ma75 = ? WHERE code = ? AND date = ?",
        [
            (
                None if pd.isna(r.ma25) else float(r.ma25),
                None if pd.isna(r.ma75) else float(r.ma75),
                code,
                r.date,
            )
            for r in df.itertuples()
        ],
    )


def run_backfill(conn: sqlite3.Connection, client: JQuantsClient) -> bool:
    """未取得銘柄のバックフィルを最大 BACKFILL_BATCH_SIZE 件だけ進める。
    まだ未取得の銘柄が残っている場合は True を返す(=今回はバックフィルモード)。"""
    pending = [
        r[0]
        for r in conn.execute(
            "SELECT code FROM stocks WHERE backfilled = 0 ORDER BY code LIMIT ?",
            (BACKFILL_BATCH_SIZE,),
        )
    ]
    if not pending:
        return False

    total_pending = conn.execute(
        "SELECT COUNT(*) FROM stocks WHERE backfilled = 0"
    ).fetchone()[0]
    print(f"バックフィルモード: 残り{total_pending}銘柄のうち{len(pending)}銘柄を処理します")

    for i, code in enumerate(pending, start=1):
        try:
            quotes = client.daily_quotes_by_code(code)
            upsert_quotes(conn, quotes)
            recompute_ma(conn, code)
            conn.execute("UPDATE stocks SET backfilled = 1 WHERE code = ?", (code,))
            conn.commit()
        except Exception as exc:  # noqa: BLE001
            print(f"  [{i}/{len(pending)}] {code}: 取得失敗 ({exc})")
            continue
        if i % 50 == 0:
            print(f"  [{i}/{len(pending)}] 完了")

    return True


def run_incremental(conn: sqlite3.Connection, client: JQuantsClient) -> None:
    print("日次更新モード: 直近数日分をまとめて取得します")
    today = datetime.now(JST).date()
    affected_codes: set[str] = set()
    for offset in range(INCREMENTAL_LOOKBACK_DAYS):
        date = (today - timedelta(days=offset)).strftime("%Y-%m-%d")
        try:
            quotes = client.daily_quotes_by_date(date)
        except Exception as exc:  # noqa: BLE001
            print(f"  {date}: 取得失敗 ({exc})")
            continue
        if not quotes:
            continue
        affected_codes |= upsert_quotes(conn, quotes)
        conn.commit()
        print(f"  {date}: {len(quotes)}件")

    print(f"移動平均を再計算します({len(affected_codes)}銘柄)")
    for code in affected_codes:
        recompute_ma(conn, code)
    conn.commit()


def judge(close: float, ma25: float | None, ma75: float | None) -> tuple[str, list[str]]:
    if ma25 is None or ma75 is None:
        return "判定不可", ["25日/75日移動平均を計算するためのデータがまだ足りません"]

    above_short = close > ma25
    above_long = close > ma75
    reasons = [
        f"終値が25日移動平均({ma25:,.1f}円)を{'上回っています' if above_short else '下回っています'}",
        f"終値が75日移動平均({ma75:,.1f}円)を{'上回っています' if above_long else '下回っています'}",
    ]
    if above_short and above_long:
        return "高値圏", reasons
    if not above_short and not above_long:
        return "安値圏", reasons
    return "中立", reasons


def export_json(conn: sqlite3.Connection) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stocks = conn.execute("SELECT code, name, market FROM stocks ORDER BY code").fetchall()

    latest_items = []
    for code, name, market in stocks:
        df = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume, ma25, ma75 "
            "FROM prices WHERE code = ? ORDER BY date",
            conn,
            params=(code,),
        )
        if df.empty:
            latest_items.append(
                {
                    "code": code,
                    "name": name,
                    "market": market,
                    "date": None,
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": None,
                    "volume": None,
                    "ma25": None,
                    "ma75": None,
                    "judgment": "未取得",
                    "reasons": ["この銘柄はまだデータを取得できていません(バックフィル待ち)"],
                }
            )
            continue

        last = df.iloc[-1]
        ma25 = None if pd.isna(last["ma25"]) else float(last["ma25"])
        ma75 = None if pd.isna(last["ma75"]) else float(last["ma75"])
        judgment, reasons = judge(float(last["close"]), ma25, ma75)

        latest_items.append(
            {
                "code": code,
                "name": name,
                "market": market,
                "date": last["date"],
                "open": round(float(last["open"]), 1),
                "high": round(float(last["high"]), 1),
                "low": round(float(last["low"]), 1),
                "close": round(float(last["close"]), 1),
                "volume": None if pd.isna(last["volume"]) else int(last["volume"]),
                "ma25": None if ma25 is None else round(ma25, 1),
                "ma75": None if ma75 is None else round(ma75, 1),
                "judgment": judgment,
                "reasons": reasons,
            }
        )

        tail = df.tail(HISTORY_ROWS)
        history_rows = [
            {
                "date": r.date,
                "open": round(float(r.open), 1),
                "high": round(float(r.high), 1),
                "low": round(float(r.low), 1),
                "close": round(float(r.close), 1),
                "volume": None if pd.isna(r.volume) else int(r.volume),
                "ma25": None if pd.isna(r.ma25) else round(float(r.ma25), 1),
                "ma75": None if pd.isna(r.ma75) else round(float(r.ma75), 1),
            }
            for r in tail.itertuples()
        ]
        (HISTORY_DIR / f"{code}.json").write_text(
            json.dumps(history_rows, ensure_ascii=False, indent=1), encoding="utf-8"
        )

    updated_at = datetime.now(JST).isoformat(timespec="seconds")
    backfill_total = len(stocks)
    backfill_done = conn.execute(
        "SELECT COUNT(*) FROM stocks WHERE backfilled = 1"
    ).fetchone()[0]

    LATEST_JSON.write_text(
        json.dumps(
            {
                "updated_at": updated_at,
                "source": "J-Quants API (JPX)",
                "backfill_done": backfill_done,
                "backfill_total": backfill_total,
                "items": latest_items,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"書き出し完了: {LATEST_JSON}, {HISTORY_DIR}/*.json ({len(stocks)}銘柄)")


def main() -> None:
    mail = os.environ["JQUANTS_MAIL"]
    password = os.environ["JQUANTS_PASSWORD"]

    client = JQuantsClient(mail, password)
    client.login()

    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    sync_universe(conn, client)

    still_backfilling = run_backfill(conn, client)
    if not still_backfilling:
        run_incremental(conn, client)

    export_json(conn)
    conn.close()


if __name__ == "__main__":
    main()
