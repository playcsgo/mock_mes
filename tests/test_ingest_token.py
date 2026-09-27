import asyncio

import pytest

from app.config import ingest_allowed, settings
from app.routes.ingest import station_ws


@pytest.fixture
def token(monkeypatch):
    monkeypatch.setattr(settings, "ingest_token", "s3cret-token")
    return "s3cret-token"


def test_correct_token_is_allowed(token):
    assert ingest_allowed(token) is True


@pytest.mark.parametrize("bad", [None, "", "wrong", "s3cret-toke", "s3cret-tokenX"])
def test_wrong_token_is_rejected(token, bad):
    assert ingest_allowed(bad) is False


def test_unset_token_rejects_everything(monkeypatch):
    monkeypatch.setattr(settings, "ingest_token", "")

    assert ingest_allowed("anything") is False
    assert ingest_allowed("") is False
    assert ingest_allowed(None) is False


class MockWs:
    def __init__(self, token: str | None) -> None:
        self.query_params = {} if token is None else {"token": token}
        self.closed_with = None
        self.accepted = False

    async def close(self, code: int) -> None:
        self.closed_with = code

    async def accept(self) -> None:
        self.accepted = True


def test_handler_closes_before_accepting_when_token_is_wrong(token):
    ws = MockWs("wrong")
    asyncio.run(station_ws(ws))  # type: ignore[arg-type]

    assert ws.closed_with == 1008
    assert ws.accepted is False


def test_handler_closes_when_no_token_given(token):
    ws = MockWs(None)
    asyncio.run(station_ws(ws))  # type: ignore[arg-type]

    assert ws.closed_with == 1008
    assert ws.accepted is False
