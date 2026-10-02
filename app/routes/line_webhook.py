import base64
import hashlib
import hmac

from fastapi import APIRouter, HTTPException, Request

from app import repository
from app.config import settings
from app.line_client import LineApiError

router = APIRouter()

WELCOME = "Success Subscribed !"


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
        user_id = event.get("source", {}).get("userId")

        if not user_id:
            continue
        if event["type"] == "follow":
            await repository.add_subscriber(db, user_id)
            await _reply(client, event, WELCOME)
        elif event["type"] == "unfollow":
            await repository.remove_subscriber(db, user_id)

    return {}  # LINE only care about status code 200


async def _reply(client, event: dict, text: str) -> None:
    if client is None or "replyToken" not in event:
        return
    try:
        await client.reply(event["replyToken"], [{"type": "text", "text": text}])
    except LineApiError as e:
        print(f"[line] reply failed: {e}")
