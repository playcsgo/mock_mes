from fastapi import APIRouter, Query, Request

from app import repository
from app.models import ResultIn

router = APIRouter(prefix="/api/results", tags=["results"])


@router.post("", status_code=201)
async def create_result(item: ResultIn, request: Request):
    return await repository.insert_result(request.app.state.db, item)


@router.get("")
async def list_results(request: Request, limit: int = Query(10, ge=1, le=100)):
    return await repository.latest_results(request.app.state.db, limit)
