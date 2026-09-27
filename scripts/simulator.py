"""mock line MES"""

import argparse
import asyncio
import json
import random
import sys
from datetime import date
from pathlib import Path

from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.demo import make_record


async def run_stations(station: str, args) -> None:
    """connect -> send data -> wait for ack -> idel a while -> repeat"""

    fail_rate = args.bad_rate if station == args.bad_station else args.fail_rate
    n = 0

    while True:
        try:
            async with connect(args.url) as ws:
                print(f"[{station}] connected (fail_rate={fail_rate})")
                while True:
                    n += 1
                    record = make_record(station, args.lot, n, fail_rate)

                    await ws.send(json.dumps(record))
                    ack = json.loads(await ws.recv())
                    mark = "✓" if ack.get("ok") else f"✗ {ack.get('error')}"

                    print(
                        f"[{station}] #{n:<5} {record['result']:<4}"
                        f"{record.get('fail_code') or '':<12} {mark}"
                    )

                    # add interval to avoid all mock data come at once
                    await asyncio.sleep(args.interval * random.uniform(0.7, 1.3))
        except (OSError, ConnectionClosed):
            print(f"[{station}] disconnect, retry after 2 seconds")
            await asyncio.sleep(2)


async def main() -> None:
    p = argparse.ArgumentParser(description=" mock MES")
    p.add_argument("--url", default="ws://localhost:8000/ws/station")
    p.add_argument("--stations", type=int, default=3, help="amount of mock stations")
    p.add_argument(
        "--interval", type=float, default=1.0, help="data frequency of each station"
    )
    p.add_argument(
        "--fail-rate", type=float, default=0.03, help="expected failure rate"
    )
    p.add_argument("--bad-station", default=None, help="set target station not working")
    p.add_argument(
        "--bad-rate", type=float, default=0.3, help="failure rate of the bad station"
    )
    p.add_argument("--lot", default=f"LOT-{date.today():%Y%m%d}")

    args = p.parse_args()

    stations = [f"ST-{i:02d}" for i in range(1, args.stations + 1)]

    await asyncio.gather(*(run_stations(s, args) for s in stations))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nsimulation stopped!")
