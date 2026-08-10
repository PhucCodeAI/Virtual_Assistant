from controller.dependencies import get_orchestrator
from dtos.orchestrator import AgentRequest
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from loguru import logger

agent_router = APIRouter()


@agent_router.post("/agent")
async def run(
    req: AgentRequest, orchestrator=Depends(get_orchestrator)
) -> StreamingResponse:
    logger.info(f"Nhận request: {req}")
    return StreamingResponse(
        orchestrator.execute_stream(req),
        media_type="text/event-stream",
    )
