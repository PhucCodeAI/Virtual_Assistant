from contextlib import asynccontextmanager

import uvicorn
from config import configs
from controller.v1.agent import agent_router

# from controller.v1.chat import chat_router
from controller.v1.metrics import metrics_router
from controller.v1.utils import utils_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from repositories.database import DataBase
from repositories.graphdb import GraphDB
from repositories.vectordb import VectorDB
from services.embedding_engine import EmbeddingEngine
from services.llm_engine import LLMEngine
from setup import setup
from utils.logger import get_logger, setup_logging
from workflows.orchestrator import Orchestrator

embedding_dir, llm_path = setup()
setup_logging()
log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application lifespan.
    This function is called when the application starts and stops.
    """
    log.info("START...")

    app.state.embedding_engine = EmbeddingEngine(embedding_dir=embedding_dir)
    app.state.llm_engine = LLMEngine(model_path=llm_path)

    app.state.db_repo = DataBase()
    app.state.vector_repo = VectorDB(embedding=app.state.embedding_engine)
    app.state.graph_repo = GraphDB(
        llm=app.state.llm_engine, embedding=app.state.embedding_engine
    )

    app.state.orchestrator = Orchestrator()

    yield
    log.info("SHUT DOWN...")
    del app


app = FastAPI(
    title="Virtual Assistant API", description="API", version="1.0.0", lifespan=lifespan
)

# app.include_router(chat_router, prefix="/v1", tags=["Chat"])
app.include_router(agent_router, prefix="/v1", tags=["Agent"])
app.include_router(metrics_router, prefix="/v1", tags=["Monitor"])
app.include_router(utils_router, tags=["Utils"])

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
    Docstring: Hàm kiểm tra sức khỏe hệ thống.
    """
    return {"status": "running", "architecture": "Modular APIRouter"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app", host=configs.server.host, port=configs.server.port, reload=True
    )
