import asyncio
import json

from websockets.asyncio.client import connect

URL = "ws://localhost:8000/ws/dashboard"


async def main():
    async with connect(URL) as ws:
        print("websocket connected, wait for ingest...")

        async for raw in ws:
            msg = json.loads(raw)
            d = msg["data"]
            if msg["type"] == "result":
                print(f"[result] {d['station']} {d['serial']} {d['result']}")
            else:
                print(f"[{msg['type']}] {d}")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
