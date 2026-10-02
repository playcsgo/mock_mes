import base64
import hashlib
import hmac
import json
from types import SimpleNamespace

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
    return {"type": "follow", "replyToken": "rt-1",
            "source": {"type": "user", "userId": user_id}}


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
    event = {"type": "follow", "replyToken": "rt", "source": {"type": "group", "groupId": "G1"}}
    r = post(app, [event])

    assert r.status_code == 200
    assert app.state.db[repository.SUBSCRIBERS].docs == []


def text_message(text: str, source: dict | None = None) -> dict:
    return {"type": "message", "replyToken": "rt-msg",
            "source": source or {"type": "user", "userId": "U1"},
            "message": {"type": "text", "text": text}}


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
    assert client.replies == [{"token": "rt-msg", "messages": [
        {"type": "text", "text": "answer to ST-03"}]}]


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


class FakeProfileClient(FakeReplyClient):
    def __init__(self, name: str | None = "Amy", **kw) -> None:
        super().__init__(**kw)
        self.name = name

    async def display_name(self, user_id: str) -> str:
        if self.name is None:
            raise LineApiError(404)
        return self.name


@pytest.fixture
def broadcasts(monkeypatch):
    sent: list[dict] = []

    async def fake_broadcast(message):
        sent.append(message)

    monkeypatch.setattr(line_webhook.manager, "broadcast", fake_broadcast)
    return sent


def claim(alert_id: str, user_id: str = "U1") -> dict:
    return {"type": "postback", "replyToken": "rt-pb",
            "source": {"type": "user", "userId": user_id},
            "postback": {"data": f"action=ack&alert_id={alert_id}"}}


def app_with_alert(client):
    import asyncio

    app = make_app(client)
    alert = {"station": "ST-03", "yield_rate": 0.7, "window": 50, "threshold": 0.9}
    doc = asyncio.run(repository.insert_alert(app.state.db, alert))
    return app, doc["id"]


def reply_text(client) -> str:
    return client.replies[-1]["messages"][0]["text"]


def test_claim_records_name_tells_user_and_updates_dashboard(secret, broadcasts):
    client = FakeProfileClient("Amy")
    app, alert_id = app_with_alert(client)
    r = post(app, [claim(alert_id)])

    assert r.status_code == 200
    assert app.state.db[repository.ALERTS].docs[0]["ack_by"] == "Amy"
    assert "已認領" in reply_text(client)
    assert broadcasts[0]["type"] == "ack"
    assert broadcasts[0]["data"]["id"] == alert_id
    assert broadcasts[0]["data"]["ack_by"] == "Amy"


def test_second_claim_is_told_who_already_has_it(secret, broadcasts):
    client = FakeProfileClient("Amy")
    app, alert_id = app_with_alert(client)
    post(app, [claim(alert_id, "U1")])
    client.name = "Bob"
    post(app, [claim(alert_id, "U2")])

    assert app.state.db[repository.ALERTS].docs[0]["ack_by"] == "Amy"
    assert "Amy" in reply_text(client)
    assert len(broadcasts) == 1  # dashboard only hears about the winner


def test_claim_of_missing_alert_is_answered_politely(secret, broadcasts):
    client = FakeProfileClient()
    app, _ = app_with_alert(client)
    post(app, [claim("does-not-exist")])

    assert "找不到" in reply_text(client)
    assert broadcasts == []


def test_profile_lookup_failure_falls_back_to_a_generic_name(secret, broadcasts):
    client = FakeProfileClient(name=None)
    app, alert_id = app_with_alert(client)
    post(app, [claim(alert_id)])

    assert app.state.db[repository.ALERTS].docs[0]["ack_by"] == line_webhook.UNKNOWN_NAME


def test_unknown_postback_is_ignored(secret, broadcasts):
    client = FakeProfileClient()
    app, _ = app_with_alert(client)
    event = {**claim("x"), "postback": {"data": "action=something-else"}}
    r = post(app, [event])

    assert r.status_code == 200
    assert client.replies == []
