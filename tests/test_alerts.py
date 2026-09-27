from app.alerts import YeildMonitor


def feed(m: YeildMonitor, station: str, results: list[bool], now: float = 0.0):
    alert = None
    for r in results:
        alert = m.add(station, r, now=now)
    return alert


def test_no_alert_when_samples_too_few():
    m = YeildMonitor(min_samples=20)

    assert feed(m, "ST-01", [False] * 10) is None


def test_no_alert_when_yeild_is_good():
    m = YeildMonitor(min_samples=20)

    assert feed(m, "ST-01", [True] * 19 + [False] * 1) is None


def test_alert_when_yield_is_drops():
    m = YeildMonitor(min_samples=20, threshold=0.9)
    alert = feed(m, "ST-03", [True] * 15 + [False] * 5)

    assert alert is not None
    assert alert["station"] == "ST-03"
    assert alert["yield_rate"] == 0.75


def test_cooldown_blocks_repeated_alerts():
    m = YeildMonitor(min_samples=20, threshold=0.9, cooldown_s=60)

    assert feed(m, "ST-03", [False] * 20, now=0) is not None
    assert m.add("ST-03", False, now=30) is None
    assert m.add("ST-03", False, now=61) is not None


def test_window_drop_old_results():
    m = YeildMonitor(window=20, min_samples=20, threshold=0.9)
    feed(m, "ST-01", [False] * 20)

    assert feed(m, "ST-01", [True] * 20, now=100) is None


def test_stations_are_independent():
    m = YeildMonitor(min_samples=20, threshold=0.9)
    feed(m, "ST-01", [False] * 20)

    assert feed(m, "ST-02", [True] * 20) is None
