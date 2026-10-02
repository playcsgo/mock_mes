import base64
import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request

from app import line_commands, repository
from app.config import settings
from app.line_client import LineApiError

router = APIRouter()

WELCOME = "已訂閱產線良率告警。任一站良率低於門檻時會通知你。\n\n" + line_commands.HELP


def valid_signature(body: bytes, signature: str | None, secret: str) -> bool:
    """X-Line-Signature = base64(HMAC-SHA256(channel secret, raw body))"""

    if not secret or not signature:
        return False

    mac = hmac.new(secret.encode(), body, hashlib.sha256).digest()
    return hmac.compare_digest(base64.b64encode(mac).decode(), signature)


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
        elif kind == "follow" and user_id:
            await repository.add_subscriber(db, user_id)
            await _reply(client, event, WELCOME)
        elif kind == "unfollow" and user_id:
            await repository.remove_subscriber(db, user_id)

    return {}  # LINE only care about status code 200


async def _reply(client, event: dict, text: str) -> None:
    if client is None or "replyToken" not in event:
        return
    try:
        await client.reply(event["replyToken"], [{"type": "text", "text": text}])
    except LineApiError as e:
        print(f"[line] reply failed: {e}")
