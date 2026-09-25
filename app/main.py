from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import repository
from app.config import settings
from app.db import create_client
from app.gql.schema import graphal_router
from app.routes import dashboard, health, ingest, results


@asynccontextmanager
async def lifespan(app: FastAPI):
    # init
    client = create_client()
    app.state.db = client[settings.mongo_db_name]

    # should go with DB setting or script. put here just for ez demo
    await repository.ensure_indexes(app.state.db)

    yield

    await client.close()


app = FastAPI(
    title="Line Monitor",
    version="0.8.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(results.router)
app.include_router(ingest.router)
app.include_router(dashboard.router)
app.include_router(graphal_router, prefix="/graphql")
