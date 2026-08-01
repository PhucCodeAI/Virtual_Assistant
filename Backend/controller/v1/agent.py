from fastapi import APIRouter, Depends, Request
from dtos.orchestrator import AgentRequest
from dtos.response import PlaningResponse
from controller.dependencies import get_orchestrator, get_llm


agent_router = APIRouter()

@agent_router.post("/agent")
def run(req: AgentRequest, orchestrator = Depends(get_orchestrator), llm = Depends(get_llm)):
    return orchestrator.routing(req, llm)