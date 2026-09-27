"""send one pass data and one fail data"""

import asyncio
import json

from websockets.asyncio.client import connect

URL = "ws://localhost:8000/ws/station"

GOOD = {
    "station": "ST-01",
    "lot": "LOT-A",
    "serial": "SN-TEST-1",
    "result": "pass",
    "measurements": {"v_out": 5.01},
}

BAD = {
    "station": "ST-01",
    "lot": "LOT-A",
    "serial": "SN-TEST-1",
    "result": "fail",
    "measurements": {"v_out": 5.01},
}


async def main():
    async with connect(URL) as ws:
        for msg in (GOOD, BAD):
            await ws.send(json.dumps(msg))
            print("sent:", msg)
            print("response:", await ws.recv(), "\n")


if __name__ == "__main__":
    asyncio.run(main())
