from app.alerts import YieldMonitor


def feed(m: YieldMonitor, station: str, results: list[bool], now: float = 0.0):
    alert = None
    for r in results:
        alert = m.add(station, r, now=now)
    return alert


def test_no_alert_when_samples_too_few():
    m = YieldMonitor(min_samples=20)

    assert feed(m, "ST-01", [False] * 10) is None


def test_no_alert_when_yield_is_good():
    m = YieldMonitor(min_samples=20)

    assert feed(m, "ST-01", [True] * 19 + [False] * 1) is None


def test_alert_when_yield_is_drops():
    m = YieldMonitor(min_samples=20, threshold=0.9)
    alert = feed(m, "ST-03", [True] * 15 + [False] * 5)

    assert alert is not None
    assert alert["station"] == "ST-03"
    assert alert["yield_rate"] == 0.75


def test_cooldown_blocks_repeated_alerts():
    m = YieldMonitor(min_samples=20, threshold=0.9, cooldown_s=60)

    assert feed(m, "ST-03", [False] * 20, now=0) is not None
    assert m.add("ST-03", False, now=30) is None
    assert m.add("ST-03", False, now=61) is not None


def test_window_drop_old_results():
    m = YieldMonitor(window=20, min_samples=20, threshold=0.9)
    feed(m, "ST-01", [False] * 20)

    assert feed(m, "ST-01", [True] * 20, now=100) is None


def test_stations_are_independent():
    m = YieldMonitor(min_samples=20, threshold=0.9)
    feed(m, "ST-01", [False] * 20)

    assert feed(m, "ST-02", [True] * 20) is None


def test_first_alert_is_a_new_incident():
    m = YieldMonitor(min_samples=20, threshold=0.9)

    assert feed(m, 'ST-03', [False] * 20)['new_incident'] is True

def test_alert_after_cooldown_is_not_a_new_incident_while_still_bad():
    m = YieldMonitor(min_samples=20, threshold=0.9, cooldown_s=60)
    feed(m, "ST-03", [False] * 20, now=0)

    assert m.add("ST-03", False, now=61)["new_incident"] is False


def test_alert_after_recovery_is_a_new_incident_again():
    m = YieldMonitor(window=20, min_samples=20, threshold=0.9, cooldown_s=60)
    feed(m, "ST-03", [False] * 20, now=0)
    feed(m, "ST-03", [True] * 20, now=100)

    assert feed(m, "ST-03", [False] * 3, now=200)["new_incident"] is True


def test_incident_older_than_ttl_counts_as_new_again():
    m = YieldMonitor(min_samples=20, threshold=0.9, cooldown_s=60, incident_ttl_s=180)
    feed(m, "ST-03", [False] * 20, now=0)

    assert m.add("ST-03", False, now=61)["new_incident"] is False
    assert m.add("ST-03", False, now=122)["new_incident"] is False
    assert m.add("ST-03", False, now=183)["new_incident"] is True
    # the TTL restarts with the new incident
    assert m.add("ST-03", False, now=244)["new_incident"] is False


def test_ttl_equal_to_cooldown_makes_every_alert_a_new_incident():
    m = YieldMonitor(min_samples=20, threshold=0.9, cooldown_s=60, incident_ttl_s=60)
    feed(m, "ST-03", [False] * 20, now=0)

    assert m.add("ST-03", False, now=61)["new_incident"] is True
    assert m.add("ST-03", False, now=122)["new_incident"] is True
