import base64
import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import repository
from app.config import settings
from app.line_client import LineApiError
from app.routes import line_webhook
from tests.fakes import FakeDB

SECRET = "channel-secret"


def sign(body: bytes, secret: str = SECRET) -> str:
    mac = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(mac).decode()


class FakeReplyClient:
    def __init__(self, fail: bool = False) -> None:
        self.replies: list[dict] = []
        self.fail = fail

    async def reply(self, reply_token: str, messages: list[dict]) -> None:
        self.replies.append({"token": reply_token, "messages": messages})
        if self.fail:
            raise LineApiError(400)


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setattr(settings, "line_channel_secret", SECRET)


def make_app(client=None):
    app = FastAPI()
    app.include_router(line_webhook.router)
    app.state.db = FakeDB()
    app.state.line_client = client
    return app


def post(app, events: list[dict], signature: str | None = None):
    body = json.dumps({"destination": "Ubot", "events": events}).encode()
    headers = {"X-Line-Signature": signature if signature is not None else sign(body)}
    return TestClient(app).post("/line/callback", content=body, headers=headers)


def follow(user_id: str) -> dict:
    return {
        "type": "follow",
        "replyToken": "rt-1",
        "source": {"type": "user", "userId": user_id},
    }


def unfollow(user_id: str) -> dict:
    return {"type": "unfollow", "source": {"type": "user", "userId": user_id}}


def test_signature_matches_line_spec():
    body = b'{"events":[]}'
    assert line_webhook.valid_signature(body, sign(body), SECRET) is True


@pytest.mark.parametrize("sig", [None, "", "not-base64!", sign(b"other body")])
def test_bad_signature_is_rejected(sig):
    assert line_webhook.valid_signature(b'{"events":[]}', sig, SECRET) is False


def test_no_secret_configured_rejects_everything():
    body = b'{"events":[]}'
    assert line_webhook.valid_signature(body, sign(body, ""), "") is False


def test_request_with_wrong_signature_gets_400_and_changes_nothing(secret):
    app = make_app()
    r = post(app, [follow("U1")], signature=sign(b"tampered"))

    assert r.status_code == 400
    assert app.state.db[repository.SUBSCRIBERS].docs == []


def test_follow_subscribes_and_says_hello(secret):
    client = FakeReplyClient()
    app = make_app(client)
    r = post(app, [follow("U1")])

    assert r.status_code == 200
    assert [d["user_id"] for d in app.state.db[repository.SUBSCRIBERS].docs] == ["U1"]
    assert client.replies[0]["token"] == "rt-1"


def test_unfollow_unsubscribes(secret):
    app = make_app()
    post(app, [follow("U1"), follow("U2")])
    post(app, [unfollow("U1")])

    assert [d["user_id"] for d in app.state.db[repository.SUBSCRIBERS].docs] == ["U2"]


def test_verify_request_with_no_events_is_ok(secret):
    """LINE console's 'Verify' button sends an empty events list."""
    assert post(make_app(), []).status_code == 200


def test_reply_failure_still_subscribes_and_returns_200(secret):
    app = make_app(FakeReplyClient(fail=True))
    r = post(app, [follow("U1")])

    assert r.status_code == 200
    assert len(app.state.db[repository.SUBSCRIBERS].docs) == 1


def test_group_source_without_user_id_is_ignored(secret):
    app = make_app()
    event = {
        "type": "follow",
        "replyToken": "rt",
        "source": {"type": "group", "groupId": "G1"},
    }
    r = post(app, [event])

    assert r.status_code == 200
    assert app.state.db[repository.SUBSCRIBERS].docs == []


def text_message(text: str, source: dict | None = None) -> dict:
    return {
        "type": "message",
        "replyToken": "rt-msg",
        "source": source or {"type": "user", "userId": "U1"},
        "message": {"type": "text", "text": text},
    }


@pytest.fixture
def fake_answer(monkeypatch):
    asked: list[str] = []

    async def answer(db, text):
        asked.append(text)
        return f"answer to {text}"

    monkeypatch.setattr(line_webhook.line_commands, "answer", answer)
    return asked


def test_text_message_is_answered_with_reply_api(secret, fake_answer):
    client = FakeReplyClient()
    r = post(make_app(client), [text_message("ST-03")])

    assert r.status_code == 200
    assert fake_answer == ["ST-03"]
    assert client.replies == [
        {"token": "rt-msg", "messages": [{"type": "text", "text": "answer to ST-03"}]}
    ]


def test_text_message_in_a_group_is_answered_too(secret, fake_answer):
    client = FakeReplyClient()
    post(make_app(client), [text_message("狀態", {"type": "group", "groupId": "G1"})])

    assert fake_answer == ["狀態"]
    assert len(client.replies) == 1


def test_non_text_message_is_ignored(secret, fake_answer):
    client = FakeReplyClient()
    event = {**text_message("x"), "message": {"type": "sticker"}}
    post(make_app(client), [event])

    assert fake_answer == []
    assert client.replies == []
