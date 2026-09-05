"""J-Quants API v2(JPX公式)から東証の日次OHLCVを取得し、
25日/75日移動平均つきで data/prices.db (SQLite) に蓄積する。

GitHub Actions（.github/workflows/update-data.yml）から定期実行される。
ローカル実行も可(環境変数 JQUANTS_API_KEY が必要):
    export JQUANTS_API_KEY=...
    python scripts/fetch_prices.py

## レートリミットと巡回方式
J-Quants v2 はプランごとに1分あたりのリクエスト数に上限がある
(Free:5, Light:60, Standard:120, Premium:500)。Freeプランだと全銘柄(約4,000)を
1銘柄1リクエストで処理するには10時間以上かかり、1回のGitHub Actions実行では終わらない。

そのため、全銘柄を「順番に少しずつ」処理するラウンドロビン方式にした。
- 前回どこまで処理したかを `sync_state` テーブルに記録しておく。
- 今回の実行は、その続きの銘柄から開始し、実行時間の上限(RUN_BUDGET_MINUTES)に
  達するか、全銘柄を一周したら終了する。
- 上位プラン(Standard/Premium)であれば1回の実行で全銘柄を一周できるため、
  実質的に毎回全銘柄が更新される。Freeプランでは一周に複数回の実行(=複数日)が
  かかるが、時間が経てば全銘柄に行き渡る。

## なぜ日付ベースの差分取得ではないのか
J-Quantsはプランによって「直近データの遅延日数」が異なる(例: Freeは直近12週間が
見えない)。日付を指定して差分だけ取ろうとすると、この遅延日数をプランごとに
実装へ埋め込む必要があり壊れやすい。銘柄ごとに「今取得できる範囲を全部」
問い合わせる方式なら、プランの違いを一切気にせず常に正しいデータになる。

## 価格について
J-Quants が提供する「調整済み株価」(AdjO/AdjH/AdjL/AdjC/AdjVo)を使用する。
株式分割・併合を考慮済みのため、長期データでも移動平均が分割によって不連続にならない。

あわせて、Webページ用の軽量なファイルも書き出す:
- data/latest.json        : 銘柄ごとの最新1件(値幅・出来高・移動平均・高値/安値圏の判定)
- data/history/<code>.json: 銘柄ごとの直近 HISTORY_ROWS 営業日分(詳細チャート用。クリック時に個別取得)
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
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
REQUESTS_PER_MINUTE = float(os.environ.get("JQUANTS_REQUESTS_PER_MINUTE", "5"))
RUN_BUDGET_MINUTES = float(os.environ.get("RUN_BUDGET_MINUTES", "320"))
RESUME_KEY = "last_synced_code"


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
    conn.execute(
        "CREATE TABLE IF NOT EXISTS sync_state (key TEXT PRIMARY KEY, value TEXT)"
    )


def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM sync_state WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO sync_state (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def first_present(item: dict, *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if value not in (None, ""):
            return value
    return None


def sync_universe(conn: sqlite3.Connection, client: JQuantsClient) -> None:
    info = client.listed_master()
    print(f"上場銘柄一覧: {len(info)} 件")
    rows = []
    for item in info:
        code = first_present(item, "Code")
        if not code:
            continue
        name = first_present(item, "CompanyName", "Name") or code
        market = first_present(item, "MarketCodeName", "Market") or ""
        rows.append((code, name, market))
    conn.executemany(
        """
        INSERT INTO stocks (code, name, market) VALUES (?, ?, ?)
        ON CONFLICT(code) DO UPDATE SET name = excluded.name, market = excluded.market
        """,
        rows,
    )
    conn.commit()


def bar_row(q: dict) -> tuple | None:
    """J-Quants v2の1レコードをprices用のタプルに変換する(調整済み値を優先)。"""
    code = q.get("Code")
    date = q.get("Date")
    close = first_present(q, "AdjC", "C")
    if not code or not date or close is None:
        return None
    return (
        code,
        date,
        first_present(q, "AdjO", "O"),
        first_present(q, "AdjH", "H"),
        first_present(q, "AdjL", "L"),
        close,
        first_present(q, "AdjVo", "Vo"),
    )


def upsert_bars(conn: sqlite3.Connection, bars: list[dict]) -> None:
    rows = [r for r in (bar_row(b) for b in bars) if r is not None]
    conn.executemany(
        """
        INSERT OR REPLACE INTO prices (code, date, open, high, low, close, volume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
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


def sync_prices(conn: sqlite3.Connection, client: JQuantsClient) -> None:
    all_codes = [r[0] for r in conn.execute("SELECT code FROM stocks ORDER BY code")]
    if not all_codes:
        print("銘柄マスタが空のため株価取得をスキップします")
        return

    resume_after = get_state(conn, RESUME_KEY)
    if resume_after and resume_after in all_codes:
        start_index = all_codes.index(resume_after) + 1
    else:
        start_index = 0
    order = all_codes[start_index:] + all_codes[:start_index]

    deadline = time.monotonic() + RUN_BUDGET_MINUTES * 60
    print(
        f"{len(order)}銘柄を巡回します(前回の続き: {resume_after or '(最初から)'}、"
        f"レート上限 {REQUESTS_PER_MINUTE}req/分、時間予算 {RUN_BUDGET_MINUTES}分)"
    )

    ok_count = 0
    processed = 0
    last_code = resume_after
    for code in order:
        if time.monotonic() >= deadline:
            print(f"時間予算に達したため中断します({processed}銘柄処理)")
            break
        try:
            bars = client.daily_bars_by_code(code)
            upsert_bars(conn, bars)
            recompute_ma(conn, code)
            conn.commit()
            if bars:
                ok_count += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  {code}: 取得失敗 ({exc})")

        processed += 1
        last_code = code
        set_state(conn, RESUME_KEY, last_code)
        if processed % 100 == 0:
            print(f"  {processed}/{len(order)} 完了(成功 {ok_count})")

    print(f"今回処理した銘柄: {processed}件(成功 {ok_count}件)。次回は {last_code} の続きから再開します")


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
                "source": "J-Quants API v2 (JPX)",
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


def main() -> None:
    api_key = os.environ["JQUANTS_API_KEY"]
    client = JQuantsClient(api_key, requests_per_minute=REQUESTS_PER_MINUTE)

    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    sync_universe(conn, client)
    sync_prices(conn, client)
    export_json(conn)

    conn.close()


if __name__ == "__main__":
    main()
