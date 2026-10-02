import asyncio
import uuid
from collections.abc import Awaitable, Callable

from app.line_client import LineApiError
from app.models import utc_now


def alert_card(alert: dict) -> dict:
    station = alert["station"]
    rate = f"{alert['yield_rate']:.1%}"
    threshold = f"{alert['threshold']:.0%}"

    def row(label: str, value: str, color: str = "#111111") -> dict:
        return {
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": label, "size": "sm", "color": "#888888"},
                {
                    "type": "text",
                    "text": value,
                    "size": "sm",
                    "color": color,
                    "align": "end",
                    "weight": "bold",
                },
            ],
        }

    return {
        "type": "flex",
        "altText": f"[良率告警] {station} 良率 {rate}，低於 {threshold}",
        "contents": {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#D93025",
                "contents": [
                    {
                        "type": "text",
                        "text": "良率告警",
                        "color": "#FFFFFF",
                        "weight": "bold",
                        "size": "lg",
                    },
                ],
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {"type": "text", "text": station, "weight": "bold", "size": "xxl"},
                    row("目前良率", rate, "#D93025"),
                    row("門檻", threshold),
                    row("樣本數", f"最近 {alert['window']} 筆"),
                ],
            },
        },
    }


def _retryable(e: LineApiError) -> bool:
    return e.status is None or e.status == 429 or e.status >= 500


class LineNotifier:
    def __init__(
        self,
        client,
        get_recipients: Callable[[], Awaitable[list[str]]],
        daily_limit: int = 10,
        max_retries: int = 3,
        base_delay_s: float = 1.0,
        queue_size: int = 100,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    ) -> None:
        self.client = client
        self.get_recipients = get_recipients
        self.daily_limit = daily_limit
        self.max_retries = max_retries
        self.base_delay_s = base_delay_s
        self.queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=queue_size)
        self.sleep = sleep
        self.today: Callable[[], object] = lambda: utc_now().date()
        self._day = None
        self._sent = 0
        self._task: asyncio.Task | None = None

    @property
    def sent_today(self) -> int:
        return self._sent if self._day == self.today() else 0

    def enqueue(self, alert: dict) -> bool:
        if not alert.get("new_incident"):
            return False

        try:
            self.queue.put_nowait(alert)
        except asyncio.QueueFull:
            print(f"[line] queue full, dropped alert for {alert['station']}")
            return False
        return True

    async def send(self, alert: dict) -> None:
        to = await self.get_recipients()
        if not to:
            return
        if self.sent_today + len(to) > self.daily_limit:
            print(
                f"[line] daily limit {self.daily_limit} reached, skip {alert['station']}"
            )
            return

        messages = [alert_card(alert)]
        retry_key = str(uuid.uuid4())

        for attempt in range(self.max_retries + 1):
            try:
                await self.client.multicast(to, messages, retry_key)
                break
            except LineApiError as e:
                if e.status == 409:
                    break
                if not _retryable(e) or attempt == self.max_retries:
                    print(f"[line] push failed, giving up: {e}")
                    return
            await self.sleep(self.base_delay_s * 2**attempt)

        self._count(len(to))

    def _count(self, n: int) -> None:
        if self._day != self.today():
            self._day, self._sent = self.today(), 0
        self._sent += n

    async def _worker(self) -> None:
        while True:
            alert = await self.queue.get()
            try:
                await self.send(alert)
            except Exception as e:  # one bad push must not kill the worker
                print(f"[line] unexpected error: {e!r}")
            finally:
                self.queue.task_done()

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._worker())

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
