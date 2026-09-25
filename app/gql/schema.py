"""define GQL  Query/Mutation behavior."""

from datetime import datetime

import strawberry
from fastapi import Request
from strawberry.fastapi import GraphQLRouter
from strawberry.scalars import JSON
from strawberry.types import Info

from app import repository


# find GraphQL response format
@strawberry.type(description="Result format")
class Result:
    id: strawberry.ID
    station: str
    lot: str
    serial: str
    result: str
    fail_code: str | None  # response reply as camelCase: failCode
    measurements: JSON  # measurements could has different format, so JSON
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


# Query Entry
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


schema = strawberry.Schema(query=Query)


# every request use its own context. avoid Global issue
async def get_context(request: Request) -> dict:
    return {"db": request.app.state.db}


graphal_router = GraphQLRouter(schema, context_getter=get_context)
