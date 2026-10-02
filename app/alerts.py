import time
from collections import deque


class YieldMonitor:
    def __init__(
        self,
        window: int = 50,
        min_samples: int = 20,
        threshold: float = 0.90,
        cooldown_s: float = 60,
        incident_ttl_s: float | None = None,
    ) -> None:
        self.window = window
        self.min_samples = min_samples
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self.incident_ttl_s = incident_ttl_s
        self._history: dict[str, deque[bool]] = {}
        self._last_alert: dict[str, float] = {}
        # station -> when its current incident started; leaving = recovered
        self._in_alarm: dict[str, float] = {}

    def add(self, station: str, passed: bool, now: float | None = None) -> dict | None:
        now = time.monotonic() if now is None else now
        history = self._history.setdefault(station, deque(maxlen=self.window))
        history.append(passed)

        if len(history) < self.min_samples:
            return None

        rate = sum(history) / len(history)
        if rate >= self.threshold:
            self._in_alarm.pop(station, None)
            return None

        last = self._last_alert.get(station)
        if last is not None and now - last < self.cooldown_s:
            return None

        self._last_alert[station] = now
        # new_incident: normal -> abnormal. Re-alerts after cooldown are False,
        # so LINE can push once per incident instead of once per cooldown.
        # With incident_ttl_s, an incident that has lasted that long counts as a
        # new one, so a station stuck below threshold gets pushed again.
        started = self._in_alarm.get(station)
        new_incident = started is None or (
            self.incident_ttl_s is not None and now - started >= self.incident_ttl_s
        )
        if new_incident:
            self._in_alarm[station] = now
        return {
            "station": station,
            "yield_rate": round(rate, 3),
            "window": len(history),
            "threshold": self.threshold,
            "new_incident": new_incident,
        }
