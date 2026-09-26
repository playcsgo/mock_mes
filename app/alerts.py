import time
from collections import deque


class YeildMonitor:
    def __init__(
        self,
        window: int = 50,
        min_samples: int = 20,
        threshold: float = 0.90,
        cooldown_s: float = 60,
    ) -> None:
        self.window = window
        self.min_samples = min_samples
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self._history: dict[str, deque[bool]] = {}
        self._last_alert: dict[str, float] = {}

    def add(self, station: str, passed: bool, now: float | None = None) -> dict | None:
        now = time.monotonic() if now is None else now
        history = self._history.setdefault(station, deque(maxlen=self.window))
        history.append(passed)

        if len(history) < self.min_samples:
            return None

        rate = sum(history) / len(history)
        if rate >= self.threshold:
            return None

        last = self._last_alert.get(station)
        if last is not None and now - last < self.cooldown_s:
            return None

        self._last_alert[station] = now
        return {
            "station": station,
            "yield_rate": round(rate, 3),
            "window": len(history),
            "threshold": self.threshold,
        }
