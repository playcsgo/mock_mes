import asyncio
import uuid

from dotenv import dotenv_values

from app.line_client import LineClient


async def main() -> None:
    env = dotenv_values(".env")
    client = LineClient(env["LINE_CHANNEL_ACCESS_TOKEN"])
    try:
        await client.multicast(
            to=[env["LINE_TEST_USER_ID"]],
            messages=[{"type": "text", "text": "hi"}],
            retry_key=str(uuid.uuid4()),
        )
        print("sent")
    finally:
        await client.close()


asyncio.run(main())
