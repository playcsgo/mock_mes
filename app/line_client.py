import httpx

API = "https://api.line.me/v2/bot"


class LineApiError(Exception):
    def __init__(self, status: int | None, body: str = "") -> None:
        super().__init__(f"LINE API error {status}: {body[:200]}")
        self.status = status
        self.body = body


class LineClient:
    def __init__(self, access_token: str, timeout_s: float = 10) -> None:
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Bearer {access_token}"}, timeout=timeout_s
        )

    async def multicast(
        self, to: list[str], messages: list[dict], retry_key: str
    ) -> None:
        await self._post(
            "/message/multicast",
            {"to": to, "messages": messages},
            headers={"X-Line-Retry-Key": retry_key},
        )

    async def reply(self, reply_token: str, messages: list[dict]) -> None:
        await self._post(
            "/message/reply", {"replyToken": reply_token, "messages": messages}
        )

    async def _post(self, path: str, body: dict, headers: dict | None = None) -> None:
        try:
            r = await self._http.post(API + path, json=body, headers=headers)
        except httpx.HTTPError as e:
            raise LineApiError(None, str(e)) from e
        if r.status_code >= 300:
            raise LineApiError(r.status_code, r.text)

    async def close(self) -> None:
        await self._http.aclose()
