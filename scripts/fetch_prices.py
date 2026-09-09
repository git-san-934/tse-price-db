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

import os
import sqlite3
import time

from jquants_client import JQuantsClient

from db_common import DB_PATH, ensure_schema, export_json, recompute_ma

REQUESTS_PER_MINUTE = float(os.environ.get("JQUANTS_REQUESTS_PER_MINUTE", "5"))
RUN_BUDGET_MINUTES = float(os.environ.get("RUN_BUDGET_MINUTES", "320"))
RESUME_KEY = "last_synced_code"


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
        name = first_present(item, "CoName") or code
        market = first_present(item, "MktNm") or ""
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


def main() -> None:
    api_key = os.environ["JQUANTS_API_KEY"]
    client = JQuantsClient(api_key, requests_per_minute=REQUESTS_PER_MINUTE)

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    sync_universe(conn, client)
    sync_prices(conn, client)
    export_json(conn, source="J-Quants API v2 (JPX)")

    conn.close()


if __name__ == "__main__":
    main()
