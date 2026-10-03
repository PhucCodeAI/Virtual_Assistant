import os
from contextlib import asynccontextmanager

import uvicorn
from config import configs
from controller.orchestrator_router import orchestrator_router
from controller.trace_router import trace_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from repositories.storage_repository import StorageRepository
from repositories.trace_repository import TraceRepository

# from repositories.database import DataBase
# from repositories.graphdb import GraphDB
# from repositories.vectordb import VectorDB
from services.embedding_client import EmbeddingClient
from services.git_service import GitService
from services.llm_client import LLMClient
from services.orchestrator import Orchestrator
from services.sandbox_engine import SandboxEngine
from services.trace_service import TraceService
from utils.logger import setup_logging

setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application lifespan.
    This function is called when the application starts and stops.
    """
    logger.info("START...")

    app.state.embedding_client = EmbeddingClient(os.environ["OPENROUTER_API_KEY"])
    app.state.llm_client = LLMClient(os.environ["OPENROUTER_API_KEY"])

    # app.state.db_repo = DataBase()
    # app.state.vector_repo = VectorDB(embedding=app.state.embedding_client)
    # app.state.graph_repo = GraphDB(
    #     llm=app.state.llm_client, embedding=app.state.embedding_client
    # )

    app.state.tracer = TraceService(
        trace_repo=TraceRepository(), storage_repo=StorageRepository()
    )

    app.state.git = GitService()
    app.state.sandbox = SandboxEngine(image="python:3.12-slim", timeout_sec=30)

    app.state.orchestrator = Orchestrator(
        llm_client=app.state.llm_client,
        sandbox=app.state.sandbox,
        git=app.state.git,
        workspace_base=configs.orchestrator.workspace_base,
        trace_service=app.state.tracer,
    )

    yield
    logger.info("SHUT DOWN...")
    del app


app = FastAPI(
    title="Coding Agent", description="API", version="0.0.0", lifespan=lifespan
)

app.include_router(orchestrator_router, tags=["Orchestrator"])
app.include_router(trace_router, tags=["Traces"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=configs.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check() -> dict:
    """
    Docstring: Hàm kiểm tra hệ thống.
    """
    return {"status": "running", "architecture": "Modular APIRouter"}


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host=configs.server.host, port=configs.server.port, reload=False
    )
