import base64
import hashlib
import hmac
from urllib.parse import parse_qs, quote

import segno
from fastapi import APIRouter, HTTPException, Request

from app import line_commands, repository
from app.config import settings
from app.line_client import LineApiError
from app.ws_manager import manager

router = APIRouter()


WELCOME = "已訂閱產線良率告警。任一站良率低於門檻時會通知你。\n\n" + line_commands.HELP
UNKNOWN_NAME = "LINE 使用者"


def valid_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """X-Line-Signature = base64(HMAC-SHA256(channel secret, raw body))"""

    if not secret or not signature:
        return False

    mac = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(mac).decode(), signature)


@router.get("/line/join")
async def join_info():
    """Add-friend link and QR for the dashboard; 404 when no bot ID is set."""
    basic_id = settings.line_bot_basic_id.strip().removeprefix("@")
    if not basic_id:
        raise HTTPException(status_code=404, detail="LINE bot ID not configured")
    url = f"https://line.me/R/ti/p/@{quote(basic_id)}"
    qr = segno.make(url, error="m").svg_data_uri(scale=1, border=2, omitsize=True)
    return {"id": f"@{basic_id}", "url": url, "qr": qr}


@router.post("/line/callback")
async def callback(request: Request):
    body = await request.body()
    if not valid_signature(
        body, request.headers.get("X-Line-Signature"), settings.line_channel_secret
    ):
        raise HTTPException(status_code=400, detail="invalid signature")

    db = request.app.state.db
    client = request.app.state.line_client
    for event in (await request.json()).get("events", []):
        kind = event["type"]
        user_id = event.get("source", {}).get("userId")

        if kind == "message" and event["message"]["type"] == "text":
            text = await line_commands.answer(db, event["message"]["text"])
            await _reply(client, event, text)
        elif kind == "postback" and user_id:
            await _postback(db, client, event, user_id)
        elif kind == "follow" and user_id:
            await repository.add_subscriber(db, user_id)
            await _reply(client, event, WELCOME)
        elif kind == "unfollow" and user_id:
            await repository.remove_subscriber(db, user_id)

    return {}  # LINE only care about status code 200


async def _postback(db, client, event: dict, user_id: str) -> None:
    data = parse_qs(event["postback"]["data"])
    if data.get("action") != ["ack"] or "alert_id" not in data:
        return

    name = await _display_name(client, user_id)
    result = await repository.ack_alert(db, data["alert_id"][0], name)
    if result is None:
        await _reply(client, event, "找不到這則告警，可能已經過期。")
        return

    doc, claimed = result
    if not claimed:
        await _reply(client, event, f"{doc['station']} 已由 {doc['ack_by']} 認領。")
        return

    await manager.broadcast(
        {
            "type": "ack",
            "data": {
                "id": doc["id"],
                "station": doc["station"],
                "ack_by": doc["ack_by"],
                "ack_at": doc["ack_at"],
            },
        }
    )
    await _reply(client, event, f"已認領 {doc['station']}，看板上會顯示由你處理。")


async def _display_name(client, user_id: str) -> str:
    if client is None:
        return UNKNOWN_NAME
    try:
        return await client.display_name(user_id)
    except LineApiError:
        return UNKNOWN_NAME


async def _reply(client, event: dict, text: str) -> None:
    if client is None or "replyToken" not in event:
        return
    try:
        await client.reply(event["replyToken"], [{"type": "text", "text": text}])
    except LineApiError as e:
        print(f"[line] reply failed: {e}")
