from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import demo, repository
from app.alerts import YieldMonitor
from app.config import LOCALHOST_RE, settings
from app.db import create_client
from app.gql.schema import graphql_router
from app.line_client import LineClient
from app.notifier import LineNotifier
from app.routes import dashboard, health, ingest, line_webhook, results


@asynccontextmanager
async def lifespan(app: FastAPI):
    client = create_client()
    app.state.db = client[settings.mongo_db_name]

    await repository.ensure_indexes(app.state.db)

    added = await demo.backfill_if_sparse(app.state.db)
    print(
        f"[demo] backfilled {added} docs at startup"
        if added
        else "[demo] history is already there, nothing to backfill"
    )

    app.state.monitor = YieldMonitor(
        window=settings.alert_window,
        min_samples=settings.alert_min_samples,
        threshold=settings.alert_threshold,
        cooldown_s=settings.alert_cooldown_s,
    )

    app.state.line_client = None
    app.state.notifier = None
    if settings.line_channel_access_token:
        db = app.state.db
        app.state.line_client = LineClient(settings.line_channel_access_token)
        app.state.notifier = LineNotifier(
            app.state.line_client,
            get_recipients=lambda: repository.subscriber_ids(db),
            daily_limit=settings.line_daily_push_limit,
        )
        app.state.notifier.start()
    else:
        print("[line] LINE_CHANNEL_ACCESS_TOKEN not set, LINE push disabled")

    app.state.demo_task = None

    yield

    await demo.stop(app)
    if app.state.notifier:
        await app.state.notifier.stop()
        await app.state.line_client.close()

    await client.close()


app = FastAPI(
    title="Line Monitor",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origin_list,
    allow_origin_regex=LOCALHOST_RE,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.include_router(health.router)
app.include_router(results.router)
app.include_router(ingest.router)
app.include_router(dashboard.router)
app.include_router(graphql_router, prefix="/graphql")
app.include_router(line_webhook.router)
