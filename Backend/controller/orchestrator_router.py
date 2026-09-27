# Backend/controller/orchestrator_router.py

from dtos.orchestrator import InputRequest
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from loguru import logger

from .dependencies import get_orchestrator

orchestrator_router = APIRouter()


@orchestrator_router.post("/orchestrator")
async def run(
    req: InputRequest, orchestrator=Depends(get_orchestrator)
) -> StreamingResponse:
    logger.info(f"Nhận request: {req}")
    return StreamingResponse(
        orchestrator.execute_stream(req),
        media_type="text/event-stream",
    )
