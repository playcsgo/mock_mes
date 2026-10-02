import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.routes import line_webhook


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(line_webhook.router)
    return TestClient(app)


def test_join_info_has_link_and_qr(client, monkeypatch):
    monkeypatch.setattr(settings, "line_bot_basic_id", "@abc123")

    body = client.get("/line/join").json()

    assert body["id"] == "@abc123"
    assert body["url"] == "https://line.me/R/ti/p/@abc123"
    assert body["qr"].startswith("data:image/svg+xml")


def test_id_without_at_sign_is_normalised(client, monkeypatch):
    monkeypatch.setattr(settings, "line_bot_basic_id", " abc123 ")

    assert client.get("/line/join").json()["url"] == "https://line.me/R/ti/p/@abc123"


@pytest.mark.parametrize("unset", ["", "  ", "@"])
def test_unset_id_returns_404_so_the_dashboard_hides_the_button(client, monkeypatch, unset):
    monkeypatch.setattr(settings, "line_bot_basic_id", unset)

    assert client.get("/line/join").status_code == 404
