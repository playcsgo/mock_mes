"""define GQL  Query/Mutation behavior."""

from datetime import datetime, timedelta, timezone

import strawberry
from fastapi import Request
from strawberry.fastapi import GraphQLRouter
from strawberry.scalars import JSON
from strawberry.types import Info

from app import repository


@strawberry.type(description="Result format")
class Result:
    id: strawberry.ID
    station: str
    lot: str
    serial: str
    result: str
    fail_code: str | None
    measurements: JSON
    ts: datetime

    @classmethod
    def from_doc(cls, d: dict) -> "Result":
        return cls(
            id=d["id"],
            station=d["station"],
            lot=d["lot"],
            serial=d["serial"],
            result=d["result"],
            fail_code=d.get("fail_code"),
            measurements=d.get("measurements", {}),
            ts=d["ts"],
        )


@strawberry.type(description="yield_rate of station")
class StationYield:
    station: str
    total: int
    passed: int
    yield_rate: float


@strawberry.type(description="pass/fail of the latest results of one station")
class RecentResults:
    station: str
    passed: list[bool]  # oldest first


@strawberry.type(description="fail stastic")
class FailureCount:
    station: str
    fail_code: str
    count: int


@strawberry.type(description="alert for low yield rate")
class Alert:
    id: strawberry.ID
    station: str
    yield_rate: float
    window: int
    threshold: float
    ts: datetime
    ack_by: str | None = None
    ack_at: datetime | None = None

    @classmethod
    def from_doc(cls, d: dict) -> "Alert":
        return cls(
            id=d["id"],
            station=d["station"],
            yield_rate=d["yield_rate"],
            window=d["window"],
            threshold=d["threshold"],
            ts=d["ts"],
            ack_by=d.get("ack_by"),
            ack_at=d.get("ack_at"),
        )


def minutes_ago(minutes: int | None) -> datetime | None:
    if minutes is None:
        return None

    return datetime.now(timezone.utc) - timedelta(minutes=minutes)


@strawberry.type
class Query:
    @strawberry.field(description="query format")
    async def results(
        self,
        info: Info,
        station: str | None = None,
        lot: str | None = None,
        result: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 20,
    ) -> list[Result]:
        db = info.context["db"]
        docs = await repository.find_results(
            db,
            limit=limit,
            station=station,
            lot=lot,
            result=result,
            since=since,
            until=until,
        )
        return [Result.from_doc(d) for d in docs]

    @strawberry.field(
        description="yield rate of station, return all time when input without a minute"
    )
    async def yield_by_station(
        self, info: Info, lot: str | None = None, since_minutes: int | None = None
    ) -> list[StationYield]:
        rows = await repository.yield_by_station(
            info.context["db"], lot=lot, since=minutes_ago(since_minutes)
        )
        return [StationYield(**r) for r in rows]

    @strawberry.field(description="latest results per station, for the rolling yield")
    async def recent_results(self, info: Info, limit: int = 100) -> list[RecentResults]:
        rows = await repository.recent_results_by_station(
            info.context["db"], limit=max(1, min(limit, 500))
        )
        return [RecentResults(**r) for r in rows]

    @strawberry.field(description="top failure cause")
    async def top_failures(
        self,
        info: Info,
        station: str | None = None,
        lot: str | None = None,
        since_minutes: int | None = None,
        limit: int = 5,
    ) -> list[FailureCount]:
        rows = await repository.top_failures(
            info.context["db"],
            station=station,
            lot=lot,
            since=minutes_ago(since_minutes),
            limit=limit,
        )

        return [FailureCount(**r) for r in rows]

    @strawberry.field(description="latest alerts, newest first")
    async def alerts(self, info: Info, limit: int = 10) -> list[Alert]:
        rows = await repository.latest_alerts(info.context["db"], limit)
        return [Alert.from_doc(r) for r in rows]


schema = strawberry.Schema(query=Query)


async def get_context(request: Request) -> dict:
    return {"db": request.app.state.db}


graphql_router = GraphQLRouter(schema, context_getter=get_context)
