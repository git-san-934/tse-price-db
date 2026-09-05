"""J-Quants API(JPXが提供する公式の株価データAPI)の薄いクライアント。

認証の流れ:
1. メールアドレス・パスワードで /token/auth_user を呼び、リフレッシュトークンを取得
2. リフレッシュトークンで /token/auth_refresh を呼び、IDトークン(有効期限24時間)を取得
3. 以降のAPI呼び出しは IDトークンを Authorization: Bearer ヘッダーに載せる

このスクリプトは毎回の実行で 1〜2 を行うため、リフレッシュトークン自体の期限切れを
気にする必要がない(メールアドレス・パスワードだけ有効であれば動く)。

参考: https://jpx.gitbook.io/j-quants-ja/api-reference
"""

from __future__ import annotations

import time
from typing import Any

import requests

BASE_URL = "https://api.jquants.com/v1"
MAX_RETRIES = 3
RETRY_WAIT_SECONDS = 5


class JQuantsError(RuntimeError):
    pass


class JQuantsClient:
    def __init__(self, mail: str, password: str) -> None:
        self._mail = mail
        self._password = password
        self._id_token: str | None = None

    def login(self) -> None:
        refresh_token = self._request_json(
            "POST",
            f"{BASE_URL}/token/auth_user",
            json={"mailaddress": self._mail, "password": self._password},
        )["refreshToken"]

        self._id_token = self._request_json(
            "POST",
            f"{BASE_URL}/token/auth_refresh",
            params={"refreshtoken": refresh_token},
        )["idToken"]

    def _headers(self) -> dict:
        if self._id_token is None:
            raise JQuantsError("login()が呼ばれていません")
        return {"Authorization": f"Bearer {self._id_token}"}

    def _request_json(self, method: str, url: str, **kwargs: Any) -> dict:
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                resp = requests.request(method, url, timeout=30, **kwargs)
                if resp.status_code == 200:
                    return resp.json()
                last_error = JQuantsError(
                    f"{method} {url} -> HTTP {resp.status_code}: {resp.text[:500]}"
                )
            except requests.RequestException as exc:
                last_error = exc
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT_SECONDS * attempt)
        assert last_error is not None
        raise last_error

    def listed_info(self) -> list[dict]:
        """上場銘柄一覧(全市場)を取得する。"""
        data = self._request_json("GET", f"{BASE_URL}/listed/info", headers=self._headers())
        return data.get("info", [])

    def daily_quotes_by_code(self, code: str) -> list[dict]:
        """指定銘柄の取得可能な全期間の日次四本値を取得する(ページネーション対応)。"""
        return self._paginated_daily_quotes({"code": code})

    def daily_quotes_by_date(self, date: str) -> list[dict]:
        """指定日の全銘柄の日次四本値を取得する(ページネーション対応)。"""
        return self._paginated_daily_quotes({"date": date})

    def _paginated_daily_quotes(self, params: dict) -> list[dict]:
        results: list[dict] = []
        query = dict(params)
        while True:
            data = self._request_json(
                "GET",
                f"{BASE_URL}/prices/daily_quotes",
                headers=self._headers(),
                params=query,
            )
            results.extend(data.get("daily_quotes", []))
            pagination_key = data.get("pagination_key")
            if not pagination_key:
                break
            query = dict(params, pagination_key=pagination_key)
        return results
