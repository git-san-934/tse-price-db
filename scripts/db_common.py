"""data/prices.db(SQLite)の共通スキーマ・移動平均計算・JSON書き出しロジック。

scripts/fetch_prices.py(yfinanceからの自動取得)と
scripts/import_manual_csv.py(SBI証券などの手動CSV取り込み)の両方から使われる。
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "prices.db"
LATEST_JSON = ROOT / "data" / "latest.json"
HISTORY_DIR = ROOT / "data" / "history"

# 5年分チャート用の週次データ(別ファイル。日次DBとファイルサイズ予算を分離するため)。
WEEKLY_DB_PATH = ROOT / "data" / "prices_weekly.db"
HISTORY_WEEKLY_DIR = ROOT / "data" / "history_weekly"

JST = timezone(timedelta(hours=9))

MA_SHORT_WINDOW = 25
MA_LONG_WINDOW = 75
HISTORY_ROWS = 120
WEEKLY_HISTORY_ROWS = 260  # 約5年分(52週 × 5年)

# data/prices.db をGitHubの1ファイル100MB上限に収めるための保持期間。
# 全銘柄(約4,449)×保持日数がそのままファイルサイズに比例するため、上限に
# 対して十分な余裕を持たせている(実測: 全銘柄×2年分で約227MB → 100MB超過)。
PRUNE_RETENTION_DAYS = 200

# data/prices_weekly.db の保持期間(約5年)。週次×終値のみなので日次DBよりずっと軽い。
WEEKLY_RETENTION_DAYS = 1825


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
def ensure_weekly_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prices_weekly (
            code TEXT NOT NULL,
            date TEXT NOT NULL,
            close REAL,
            volume INTEGER,
            PRIMARY KEY (code, date)
        )
        """
    )


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


def prune_old_prices(conn: sqlite3.Connection) -> None:
    """PRUNE_RETENTION_DAYSより古い行を削除し、VACUUMでファイルサイズを実際に縮小する。

    SQLiteはDELETEしただけではファイルサイズが減らないため、VACUUMが必須。
    """
    cutoff = (datetime.now(JST) - timedelta(days=PRUNE_RETENTION_DAYS)).strftime("%Y-%m-%d")
    deleted = conn.execute("DELETE FROM prices WHERE date < ?", (cutoff,)).rowcount
    conn.commit()
    conn.execute("VACUUM")
    print(f"古いデータを削除しました: {deleted}行({cutoff}より前)")


def prune_old_weekly_prices(conn: sqlite3.Connection) -> None:
    """WEEKLY_RETENTION_DAYSより古い行を削除し、VACUUMでファイルサイズを実際に縮小する。"""
    cutoff = (datetime.now(JST) - timedelta(days=WEEKLY_RETENTION_DAYS)).strftime("%Y-%m-%d")
    deleted = conn.execute("DELETE FROM prices_weekly WHERE date < ?", (cutoff,)).rowcount
    conn.commit()
    conn.execute("VACUUM")
    print(f"[週次] 古いデータを削除しました: {deleted}行({cutoff}より前)")


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


def export_json(conn: sqlite3.Connection, source: str) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    stocks = conn.execute("SELECT code, name, market FROM stocks ORDER BY code").fetchall()

    latest_items = []
    codes_with_data = 0
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
                    "reasons": ["この銘柄はまだデータを取得できていません"],
                }
            )
            continue

        codes_with_data += 1
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

    LATEST_JSON.write_text(
        json.dumps(
            {
                "updated_at": updated_at,
                "source": source,
                "codes_with_data": codes_with_data,
                "codes_total": len(stocks),
                "items": latest_items,
            },
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    print(f"書き出し完了: {LATEST_JSON}, {HISTORY_DIR}/*.json ({len(stocks)}銘柄)")


def export_weekly_json(conn: sqlite3.Connection, codes: list[str]) -> None:
    """5年分チャート用の週次データを銘柄ごとにJSON書き出しする({date, close, volume}の配列)。

    日次のdata/history/<code>.jsonとは別ディレクトリに書き出す(MA25/MA75は含まない。
    週次のMAは意味合いが異なるため、5年チャートでは終値の折れ線のみ表示する設計)。
    """
    HISTORY_WEEKLY_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for code in codes:
        df = pd.read_sql_query(
            "SELECT date, close, volume FROM prices_weekly WHERE code = ? ORDER BY date",
            conn,
            params=(code,),
        )
        if df.empty:
            continue
        tail = df.tail(WEEKLY_HISTORY_ROWS)
        rows = [
            {
                "date": r.date,
                "close": round(float(r.close), 1),
                "volume": None if pd.isna(r.volume) else int(r.volume),
            }
            for r in tail.itertuples()
        ]
        (HISTORY_WEEKLY_DIR / f"{code}.json").write_text(
            json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        count += 1
    print(f"[週次] 書き出し完了: {HISTORY_WEEKLY_DIR}/*.json ({count}銘柄)")
