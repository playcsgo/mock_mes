from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import create_client
from app.routes import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # init
    client = create_client()
    app.state.db = client[settings.mongo_db_name]

    yield

    await client.close()


app = FastAPI(
    title="Line Monitor",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(health.router)
