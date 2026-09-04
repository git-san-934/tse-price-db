"""東証銘柄の日次OHLCVを取得し、25日/75日移動平均つきで data/prices.db (SQLite) に蓄積する。

GitHub Actions（.github/workflows/update-data.yml）から定期実行される。
ローカル実行も可: `python scripts/fetch_prices.py`

実行するたびに、直近1年分のデータを再取得して data/prices.db に upsert する。
過去に取得済みで今回の取得期間(1年)より古い日付の行はそのまま残るため、
リポジトリを更新し続ける限りデータベースは日々蓄積されていく。

あわせて、Webページがそのまま読み込める軽量な JSON も書き出す:
- data/latest.json  : 銘柄ごとの最新1件(値幅・出来高・移動平均・高値/安値圏の判定)
- data/history.json : 銘柄ごとの直近120営業日分(チャート・データテーブル用)
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent.parent
UNIVERSE_CSV = ROOT / "data" / "universe.csv"
DB_PATH = ROOT / "data" / "prices.db"
LATEST_JSON = ROOT / "data" / "latest.json"
HISTORY_JSON = ROOT / "data" / "history.json"

JST = timezone(timedelta(hours=9))

MA_SHORT_WINDOW = 25
MA_LONG_WINDOW = 75
HISTORY_ROWS = 120


def load_universe() -> list[dict]:
    with UNIVERSE_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def to_symbol(code: str) -> str:
    return f"{code}.T"


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS stocks (
            code TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            market TEXT
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


def judge(close: float, ma25: float | None, ma75: float | None) -> tuple[str, list[str]]:
    if ma25 is None or ma75 is None or pd.isna(ma25) or pd.isna(ma75):
        return "判定不可", ["25日/75日移動平均を計算するためのデータがまだ足りません"]

    above_short = close > ma25
    above_long = close > ma75
    reasons = []
    reasons.append(
        f"終値が25日移動平均({ma25:,.1f}円)を{'上回っています' if above_short else '下回っています'}"
    )
    reasons.append(
        f"終値が75日移動平均({ma75:,.1f}円)を{'上回っています' if above_long else '下回っています'}"
    )

    if above_short and above_long:
        return "高値圏", reasons
    if not above_short and not above_long:
        return "安値圏", reasons
    return "中立", reasons


def main() -> None:
    universe = load_universe()
    symbols = [to_symbol(row["code"]) for row in universe]

    print(f"{len(symbols)} 銘柄の株価を取得します...")
    frame = yf.download(
        symbols,
        period="1y",
        interval="1d",
        group_by="ticker",
        auto_adjust=False,
        threads=True,
        progress=False,
    )

    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    conn.executemany(
        "INSERT OR REPLACE INTO stocks (code, name, market) VALUES (?, ?, ?)",
        [(row["code"], row["name"], row.get("market", "")) for row in universe],
    )

    ok_count = 0
    latest_items = []
    history = {}

    for row in universe:
        code = row["code"]
        symbol = to_symbol(code)
        try:
            df = frame[symbol][["Open", "High", "Low", "Close", "Volume"]].dropna()
        except (KeyError, TypeError):
            df = pd.DataFrame()

        if df.empty:
            latest_items.append(
                {
                    "code": code,
                    "name": row["name"],
                    "market": row.get("market", ""),
                    "date": None,
                    "open": None,
                    "high": None,
                    "low": None,
                    "close": None,
                    "volume": None,
                    "ma25": None,
                    "ma75": None,
                    "judgment": "取得失敗",
                    "reasons": ["この銘柄の株価データを取得できませんでした"],
                }
            )
            continue

        ok_count += 1
        df["ma25"] = df["Close"].rolling(MA_SHORT_WINDOW).mean()
        df["ma75"] = df["Close"].rolling(MA_LONG_WINDOW).mean()

        db_rows = [
            (
                code,
                idx.strftime("%Y-%m-%d"),
                float(r.Open),
                float(r.High),
                float(r.Low),
                float(r.Close),
                int(r.Volume),
                None if pd.isna(r.ma25) else float(r.ma25),
                None if pd.isna(r.ma75) else float(r.ma75),
            )
            for idx, r in zip(df.index, df.itertuples())
        ]
        conn.executemany(
            """
            INSERT OR REPLACE INTO prices
                (code, date, open, high, low, close, volume, ma25, ma75)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            db_rows,
        )

        last = df.iloc[-1]
        last_ma25 = None if pd.isna(last["ma25"]) else float(last["ma25"])
        last_ma75 = None if pd.isna(last["ma75"]) else float(last["ma75"])
        judgment, reasons = judge(float(last["Close"]), last_ma25, last_ma75)

        latest_items.append(
            {
                "code": code,
                "name": row["name"],
                "market": row.get("market", ""),
                "date": df.index[-1].strftime("%Y-%m-%d"),
                "open": round(float(last["Open"]), 1),
                "high": round(float(last["High"]), 1),
                "low": round(float(last["Low"]), 1),
                "close": round(float(last["Close"]), 1),
                "volume": int(last["Volume"]),
                "ma25": None if last_ma25 is None else round(last_ma25, 1),
                "ma75": None if last_ma75 is None else round(last_ma75, 1),
                "judgment": judgment,
                "reasons": reasons,
            }
        )

        tail = df.tail(HISTORY_ROWS)
        history[code] = [
            {
                "date": idx.strftime("%Y-%m-%d"),
                "open": round(float(r.Open), 1),
                "high": round(float(r.High), 1),
                "low": round(float(r.Low), 1),
                "close": round(float(r.Close), 1),
                "volume": int(r.Volume),
                "ma25": None if pd.isna(r.ma25) else round(float(r.ma25), 1),
                "ma75": None if pd.isna(r.ma75) else round(float(r.ma75), 1),
            }
            for idx, r in zip(tail.index, tail.itertuples())
        ]

    conn.commit()
    conn.close()

    print(f"株価取得できた銘柄: {ok_count} / {len(universe)}")

    updated_at = datetime.now(JST).isoformat(timespec="seconds")

    LATEST_JSON.write_text(
        json.dumps(
            {"updated_at": updated_at, "source": "Yahoo Finance (yfinance)", "items": latest_items},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    HISTORY_JSON.write_text(
        json.dumps(
            {"updated_at": updated_at, "history": history},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"書き出し完了: {LATEST_JSON}, {HISTORY_JSON}, {DB_PATH}")


if __name__ == "__main__":
    main()
