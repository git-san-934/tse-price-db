"""J-Quants API v2(JPXが提供する公式の株価データAPI)の薄いクライアント。

v2 では認証がAPIキー方式になった(v1のメール+パスワード→トークン発行は廃止)。
J-Quantsのダッシュボードで発行したAPIキーを `x-api-key` ヘッダーに載せるだけでよく、
有効期限もない。

レスポンスは原則 `{"data": [...], "pagination_key": "..."}` の形。

参考: https://jpx.gitbook.io/j-quants-ja/(V1からV2への変更点)
"""

from __future__ import annotations

import time
from typing import Any

import requests

BASE_URL = "https://api.jquants.com/v2"
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5


class JQuantsError(RuntimeError):
    pass


class JQuantsClient:
    def __init__(self, api_key: str, requests_per_minute: float = 5.0) -> None:
        self._api_key = api_key
        self._min_interval = 60.0 / requests_per_minute
        self._last_request_at: float | None = None

    def _headers(self) -> dict:
        return {"x-api-key": self._api_key}

    def _throttle(self) -> None:
        if self._last_request_at is not None:
            elapsed = time.monotonic() - self._last_request_at
            wait = self._min_interval - elapsed
            if wait > 0:
                time.sleep(wait)
        self._last_request_at = time.monotonic()

    def _request_json(self, method: str, url: str, **kwargs: Any) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            self._throttle()
            try:
                resp = requests.request(method, url, timeout=30, **kwargs)
                if resp.status_code == 200:
                    return resp.json()
                if resp.status_code == 429:
                    # レートリミット超過。少し長めに待ってリトライする。
                    time.sleep(self._min_interval * 3)
                last_error = JQuantsError(
                    f"{method} {url} -> HTTP {resp.status_code}: {resp.text[:500]}"
                )
            except requests.RequestException as exc:
                last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS * attempt)
        assert last_error is not None
        raise last_error

    def _get_paginated(self, path: str, params: dict) -> list[dict]:
        results: list[dict] = []
        query = dict(params)
        while True:
            data = self._request_json(
                "GET", f"{BASE_URL}{path}", headers=self._headers(), params=query
            )
            results.extend(data.get("data", []))
            pagination_key = data.get("pagination_key")
            if not pagination_key:
                break
            query = dict(params, pagination_key=pagination_key)
        return results

    def listed_master(self) -> list[dict]:
        """上場銘柄一覧(全市場)を取得する。"""
        return self._get_paginated("/equities/master", {})

    def daily_bars_by_code(self, code: str) -> list[dict]:
        """指定銘柄について、契約プランで取得可能な範囲の日次四本値を全て取得する。"""
        return self._get_paginated("/equities/bars/daily", {"code": code})
