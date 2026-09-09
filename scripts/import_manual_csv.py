"""SBI証券の「個別銘柄 株価CSVダウンロード」形式のファイルを取り込み、
data/prices.db(SQLite)に反映する(J-Quantsで自動取得したデータより優先される)。

GitHub Actions(.github/workflows/import-manual-csv.yml)から、
data/manual_csv/ 配下にCSVがpushされるたびに実行される。
ローカル実行も可: `python scripts/import_manual_csv.py`(scriptsディレクトリ内で実行)

## 使い方
1. SBI証券のサイトで個別銘柄の株価CSVをダウンロードする
   (ファイル名は "TimeChart<証券コード><yyyymmdd>.csv" の形式。リネーム不要)
2. data/manual_csv/ フォルダにそのままアップロードする(GitHubのWeb UIでドラッグ&ドロップ可)
3. 自動的にこのスクリプトが実行され、該当銘柄の株価がJ-Quantsより新しい日付まで更新される

## 想定するCSV列(SBI証券の「株価CSVダウンロード」形式)
日付,始値,高値,安値,終値,5日平均,25日平均,75日平均,VWAP,出来高,5日平均,25日平均
このうち 日付・始値・高値・安値・終値・出来高 のみ使用する(移動平均は自前で再計算する。
SBI側の移動平均は算出方法が異なる可能性があり、自前計算と混在させない)。

文字コードはUTF-8(BOM付き)またはShift-JIS(CP932)の両方に対応する。
"""

from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

from db_common import DB_PATH, ROOT, ensure_schema, export_json, recompute_ma

MANUAL_CSV_DIR = ROOT / "data" / "manual_csv"

# SBI証券の株価CSVの列インデックス(0始まり)
COL_DATE, COL_OPEN, COL_HIGH, COL_LOW, COL_CLOSE, COL_VOLUME = 0, 1, 2, 3, 4, 9

FILENAME_CODE_RE = re.compile(r"TimeChart([0-9A-Za-z]{4,5})\d{8}", re.IGNORECASE)


def read_text_any_encoding(path: Path) -> str:
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"{path}: UTF-8/Shift-JISのどちらでも読み込めませんでした")


def parse_number(raw: str) -> float | None:
    raw = raw.strip().replace(",", "")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def parse_sbi_csv(path: Path) -> list[tuple[str, float, float, float, float, int]]:
    text = read_text_any_encoding(path)
    rows = list(csv.reader(text.splitlines()))
    rows = rows[1:]  # ヘッダー行を除く

    parsed = []
    for row in rows:
        if len(row) <= COL_VOLUME or not row[COL_DATE].strip():
            continue
        date = row[COL_DATE].strip().replace("/", "-")
        open_ = parse_number(row[COL_OPEN])
        high = parse_number(row[COL_HIGH])
        low = parse_number(row[COL_LOW])
        close = parse_number(row[COL_CLOSE])
        volume = parse_number(row[COL_VOLUME])
        if close is None:
            continue
        parsed.append((date, open_, high, low, close, int(volume) if volume is not None else None))
    return parsed


def guess_code_from_filename(path: Path) -> str | None:
    m = FILENAME_CODE_RE.search(path.stem)
    return m.group(1) if m else None


def resolve_code(conn: sqlite3.Connection, raw_code: str) -> str | None:
    """4桁の証券コードをJ-Quantsの5桁コード表記に解決する(完全一致→末尾0付与→前方一致の順)。"""
    if conn.execute("SELECT 1 FROM stocks WHERE code = ?", (raw_code,)).fetchone():
        return raw_code
    padded = raw_code + "0"
    if conn.execute("SELECT 1 FROM stocks WHERE code = ?", (padded,)).fetchone():
        return padded
    row = conn.execute(
        "SELECT code FROM stocks WHERE code LIKE ? LIMIT 1", (raw_code + "%",)
    ).fetchone()
    return row[0] if row else None


def main() -> None:
    if not MANUAL_CSV_DIR.exists():
        print(f"{MANUAL_CSV_DIR} が存在しません。何もしません")
        return

    csv_files = sorted(p for p in MANUAL_CSV_DIR.glob("*.csv"))
    if not csv_files:
        print("data/manual_csv/ にCSVファイルが見つかりません")
        return

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    affected_codes: set[str] = set()

    for path in csv_files:
        raw_code = guess_code_from_filename(path)
        if raw_code is None:
            print(f"  {path.name}: ファイル名から証券コードを特定できませんでした。スキップします")
            continue

        code = resolve_code(conn, raw_code)
        if code is None:
            print(f"  {path.name}: 証券コード {raw_code} が銘柄マスタに見つかりません。スキップします")
            continue

        rows = parse_sbi_csv(path)
        if not rows:
            print(f"  {path.name}: 取り込める行がありませんでした")
            continue

        conn.executemany(
            """
            INSERT OR REPLACE INTO prices (code, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [(code, date, o, h, low, c, v) for date, o, h, low, c, v in rows],
        )
        affected_codes.add(code)
        dates = sorted(r[0] for r in rows)
        print(f"  {path.name} -> {code}: {len(rows)}件取り込み({dates[0]} 〜 {dates[-1]})")

    for code in affected_codes:
        recompute_ma(conn, code)
    conn.commit()

    if affected_codes:
        export_json(conn, source="J-Quants API v2 (JPX) + 手動CSV(SBI証券等)")

    conn.close()
    print(f"手動CSV取り込み完了: {len(affected_codes)}銘柄を更新しました")


if __name__ == "__main__":
    main()
