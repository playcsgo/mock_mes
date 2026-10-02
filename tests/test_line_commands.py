import asyncio

import pytest

from app import line_commands, repository

YIELDS = [
    {"station": "ST-01", "total": 480, "passed": 476, "yield_rate": 476 / 480},
    {"station": "ST-03", "total": 120, "passed": 86, "yield_rate": 86 / 120},
]
FAILS = [
    {"station": "ST-03", "fail_code": "V_OUT_LOW", "count": 14},
    {"station": "ST-03", "fail_code": "TEMP_HIGH", "count": 11},
]


@pytest.fixture
def calls(monkeypatch):
    """Replace the two aggregations; record the filters they were called with."""
    seen: list[tuple] = []

    async def fake_yield(db, lot=None, since=None):
        seen.append(("yield", since))
        return YIELDS

    async def fake_fails(db, station=None, lot=None, since=None, limit=5):
        seen.append(("fails", station, limit))
        return [f for f in FAILS if station in (None, f["station"])]

    monkeypatch.setattr(repository, "yield_by_station", fake_yield)
    monkeypatch.setattr(repository, "top_failures", fake_fails)
    return seen


def ask(text: str) -> str:
    return asyncio.run(line_commands.answer(None, text))


@pytest.mark.parametrize("text", ["ST-03", "st-03", "ST03", "st3", " ST-3 "])
def test_station_query_accepts_loose_spelling(calls, text):
    reply = ask(text)

    assert "ST-03" in reply
    assert "71.7%" in reply
    assert "V_OUT_LOW" in reply


def test_station_query_asks_failures_of_that_station_only(calls):
    ask("ST-03")

    assert ("fails", "ST-03", 3) in calls


def test_station_below_threshold_is_marked(calls):
    assert "低於門檻" in ask("ST-03")
    assert "低於門檻" not in ask("ST-01")


def test_unknown_station_says_no_data(calls):
    assert "ST-09" in ask("ST-09")
    assert "沒有資料" in ask("ST-09")


@pytest.mark.parametrize("text", ["狀態", "status", "Status"])
def test_status_lists_every_station_and_top_failures(calls, text):
    reply = ask(text)

    assert "ST-01" in reply and "99.2%" in reply
    assert "ST-03" in reply and "71.7%" in reply
    assert "V_OUT_LOW" in reply


def test_queries_only_look_at_the_last_hour(calls):
    from datetime import timedelta

    from app.models import utc_now

    ask("狀態")
    since = next(c[1] for c in calls if c[0] == "yield")

    assert timedelta(minutes=59) < utc_now() - since < timedelta(minutes=61)


def test_status_with_no_data(monkeypatch):
    async def empty(*a, **k):
        return []

    monkeypatch.setattr(repository, "yield_by_station", empty)
    monkeypatch.setattr(repository, "top_failures", empty)

    assert "沒有資料" in ask("狀態")


@pytest.mark.parametrize("text", ["hi", "說明", "?", "ST-ABC"])
def test_anything_else_gets_help(calls, text):
    reply = ask(text)

    assert "狀態" in reply and "ST-03" in reply
    assert calls == []  # help never touches the database
