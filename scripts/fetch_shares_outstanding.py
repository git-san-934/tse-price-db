"""発行済株式数(時価総額の算出に必要)を全銘柄について個別取得し、
data/prices.db の stocks テーブルに保存する。

## なぜ日次のfetch_prices.pyと分離しているか
株価(OHLCV)は`yf.download`で複数銘柄をまとめて1リクエストで取得できるが、
発行済株式数はyfinanceの仕様上、銘柄ごとの個別リクエスト(`Ticker.fast_info`)
でしか取得できない。約4,449銘柄すべてを毎日個別取得すると、Yahoo Finance側の
レート制限やブロックのリスクが高く、日次のバッチ取得(fetch_prices.py)の
安定性を損なう。発行済株式数は日々変動するものではないため、本スクリプトは
低頻度(月次目安)の別ワークフロー(.github/workflows/update-shares.yml)から
実行する。

## レート制限対策(ラウンド制のリトライ)
初回実装では並列数10・リクエスト間隔0.2秒で実行したところ、約4,449銘柄中
442銘柄(約1割)しか取得できなかった。実行時間が約2分と極端に短かったことから、
Yahoo Finance側が短時間の大量個別リクエストを検知し、多くのリクエストが
待たされることなく失敗(空応答)を返していたと考えられる。
対策として、(1)並列数を減らしリクエスト間隔を広げて1銘柄あたりの負荷を下げる、
(2)失敗した銘柄だけを対象に、ラウンド間にクールダウン(待機)を挟みながら
複数ラウンド再試行する、という2点を導入した。

GitHub Actionsから定期実行される。
ローカル実行も可: `python scripts/fetch_shares_outstanding.py`(scriptsディレクトリ内で実行)
"""

from __future__ import annotations

import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone

import yfinance as yf

from db_common import DB_PATH, ensure_schema, export_json

MAX_WORKERS = 3
REQUEST_PAUSE_SECONDS = 1.0
COMMIT_EVERY = 200

MAX_ROUNDS = 4
ROUND_COOLDOWN_SECONDS = 90

JST = timezone(timedelta(hours=9))


def to_yf_symbol(code: str) -> str:
    base = code[:-1] if len(code) == 5 else code
    return f"{base}.T"


def fetch_shares(code: str) -> tuple[str, int | None]:
    symbol = to_yf_symbol(code)
    time.sleep(REQUEST_PAUSE_SECONDS)
    try:
        shares = yf.Ticker(symbol).fast_info.get("shares")
        if not shares:
            shares = yf.Ticker(symbol).info.get("sharesOutstanding")
        return code, int(shares) if shares else None
    except Exception:  # noqa: BLE001
        return code, None


def fetch_round(conn: sqlite3.Connection, codes: list[str], today: str) -> list[str]:
    """codesの発行済株式数を取得してDBに反映し、取得できたcodeの一覧を返す。"""
    ok_codes: list[str] = []
    processed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(fetch_shares, code): code for code in codes}
        for future in as_completed(futures):
            code, shares = future.result()
            processed += 1
            if shares:
                conn.execute(
                    "UPDATE stocks SET shares_outstanding = ?, shares_updated_at = ? WHERE code = ?",
                    (shares, today, code),
                )
                ok_codes.append(code)
            if processed % COMMIT_EVERY == 0:
                conn.commit()
                print(f"    進捗: {processed}/{len(codes)}銘柄処理済み({len(ok_codes)}件取得成功)")
    conn.commit()
    return ok_codes


def main() -> None:
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    codes = [r[0] for r in conn.execute("SELECT code FROM stocks ORDER BY code")]
    if not codes:
        print("銘柄マスタが空のため発行済株式数の取得をスキップします")
        conn.close()
        return

    today = datetime.now(JST).strftime("%Y-%m-%d")
    remaining = codes
    total_ok = 0

    for round_index in range(1, MAX_ROUNDS + 1):
        print(
            f"ラウンド{round_index}/{MAX_ROUNDS}: {len(remaining)}銘柄の発行済株式数を取得します"
            f"(並列数{MAX_WORKERS})"
        )
        ok_codes = fetch_round(conn, remaining, today)
        total_ok += len(ok_codes)
        remaining = [c for c in remaining if c not in set(ok_codes)]
        print(f"  ラウンド{round_index}: {len(ok_codes)}銘柄成功、残り{len(remaining)}銘柄")

        if not remaining or round_index == MAX_ROUNDS:
            break
        print(f"  レート制限回避のため{ROUND_COOLDOWN_SECONDS}秒待機します")
        time.sleep(ROUND_COOLDOWN_SECONDS)

    print(f"発行済株式数を取得できた銘柄: {total_ok} / {len(codes)}(未取得: {len(remaining)}銘柄)")

    export_json(conn, source="Yahoo Finance (yfinance)")
    conn.close()


if __name__ == "__main__":
    main()
