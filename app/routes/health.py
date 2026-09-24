from fastapi import APIRouter, Request
from pymongo.errors import PyMongoError

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    db = request.app.state.db

    try:
        await db.command("ping")
        mongo = "ok"
    except PyMongoError as e:
        mongo = f"error: {type(e).__name__}"

    return {"status": "ok", "mongoDB": mongo}
