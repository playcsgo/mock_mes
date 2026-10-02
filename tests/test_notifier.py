import asyncio

from app.line_client import LineApiError
from app.notifier import LineNotifier

ALERT = {
    "id": "a1",
    "station": "ST-03",
    "yield_rate": 0.72,
    "window": 50,
    "threshold": 0.9,
    "new_incident": True,
}


class FakeLineClient:
    """Records multicast calls; fails with the queued errors first."""

    def __init__(self, errors: list[LineApiError] | None = None) -> None:
        self.calls: list[dict] = []
        self.errors = list(errors or [])

    async def multicast(self, to: list[str], messages: list[dict], retry_key: str):
        self.calls.append({"to": to, "messages": messages, "retry_key": retry_key})
        if self.errors:
            raise self.errors.pop(0)


def make_notifier(client, recipients=("U1",), daily_limit=10, sleeps=None):
    async def get_recipients():
        return list(recipients)

    async def fake_sleep(s):
        if sleeps is not None:
            sleeps.append(s)

    return LineNotifier(
        client, get_recipients, daily_limit=daily_limit, sleep=fake_sleep
    )


def test_enqueue_accepts_new_incident_only():
    n = make_notifier(FakeLineClient())

    assert n.enqueue(ALERT) is True
    assert n.enqueue({**ALERT, "new_incident": False}) is False
    assert n.queue.qsize() == 1


def test_enqueue_never_blocks_when_queue_is_full():
    n = make_notifier(FakeLineClient())
    for _ in range(n.queue.maxsize):
        n.enqueue(ALERT)

    assert n.enqueue(ALERT) is False


def test_send_multicasts_a_card_to_all_subscribers():
    client = FakeLineClient()
    n = make_notifier(client, recipients=["U1", "U2"])
    asyncio.run(n.send(ALERT))

    assert len(client.calls) == 1
    call = client.calls[0]
    assert call["to"] == ["U1", "U2"]
    assert call["messages"][0]["type"] == "flex"
    assert "ST-03" in call["messages"][0]["altText"]
    assert n.sent_today == 2


def test_send_skips_when_nobody_subscribed():
    client = FakeLineClient()
    n = make_notifier(client, recipients=[])
    asyncio.run(n.send(ALERT))

    assert client.calls == []


def test_retries_rate_limit_and_server_errors_with_backoff_and_same_key():
    sleeps: list[float] = []
    client = FakeLineClient([LineApiError(429), LineApiError(500)])
    n = make_notifier(client, sleeps=sleeps)
    asyncio.run(n.send(ALERT))

    assert len(client.calls) == 3
    assert len({c["retry_key"] for c in client.calls}) == 1
    assert sleeps == [1.0, 2.0]
    assert n.sent_today == 1


def test_network_error_is_retried():
    client = FakeLineClient([LineApiError(None)])
    n = make_notifier(client)
    asyncio.run(n.send(ALERT))

    assert len(client.calls) == 2
    assert n.sent_today == 1


def test_client_error_is_not_retried():
    client = FakeLineClient([LineApiError(400)])
    n = make_notifier(client)
    asyncio.run(n.send(ALERT))

    assert len(client.calls) == 1
    assert n.sent_today == 0


def test_conflict_means_line_already_accepted_this_retry_key():
    client = FakeLineClient([LineApiError(500), LineApiError(409)])
    n = make_notifier(client)
    asyncio.run(n.send(ALERT))

    assert len(client.calls) == 2
    assert n.sent_today == 1


def test_gives_up_after_max_retries():
    client = FakeLineClient([LineApiError(500)] * 10)
    n = make_notifier(client)
    asyncio.run(n.send(ALERT))

    assert len(client.calls) == n.max_retries + 1
    assert n.sent_today == 0


def test_daily_limit_counts_recipients_not_alerts():
    client = FakeLineClient()
    n = make_notifier(client, recipients=["U1", "U2", "U3"], daily_limit=5)

    async def run():
        await n.send(ALERT)
        await n.send(ALERT)

    asyncio.run(run())

    assert len(client.calls) == 1
    assert n.sent_today == 3


def test_daily_limit_resets_on_a_new_day():
    client = FakeLineClient()
    n = make_notifier(client, recipients=["U1"], daily_limit=1)
    day = {"d": "2026-09-29"}
    n.today = lambda: day["d"]

    async def run():
        await n.send(ALERT)
        await n.send(ALERT)
        day["d"] = "2026-09-30"
        await n.send(ALERT)

    asyncio.run(run())

    assert len(client.calls) == 2


def test_worker_sends_enqueued_alerts_and_stops_cleanly():
    client = FakeLineClient()
    n = make_notifier(client)

    async def run():
        n.start()
        n.enqueue(ALERT)
        await asyncio.wait_for(n.queue.join(), timeout=1)
        await n.stop()

    asyncio.run(run())

    assert len(client.calls) == 1


def test_worker_survives_an_unexpected_error():
    class Boom(FakeLineClient):
        async def multicast(self, to, messages, retry_key):
            await super().multicast(to, messages, retry_key)
            if len(self.calls) == 1:
                raise RuntimeError("boom")

    client = Boom()
    n = make_notifier(client)

    async def run():
        n.start()
        n.enqueue(ALERT)
        n.enqueue(ALERT)
        await asyncio.wait_for(n.queue.join(), timeout=1)
        await n.stop()

    asyncio.run(run())

    assert len(client.calls) == 2
