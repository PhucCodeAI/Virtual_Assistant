import os
from contextlib import asynccontextmanager

import phoenix as px
import uvicorn
from config import configs
from controller.v1.metrics import metrics_router
from controller.v1.pipeline import pipeline_router
from controller.v1.utils import utils_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from openinference.instrumentation.openai import OpenAIInstrumentor
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from repositories.database import DataBase
from repositories.graphdb import GraphDB
from repositories.vectordb import VectorDB
from services.embedding_engine import EmbeddingEngine
from Backend.services.llm_client import LLMEngine
from utils.logger import setup_logging
from workflows.orchestrator import AgentOrchestrator

setup_logging()

os.makedirs(configs.phoenix.data_dir, exist_ok=True)
os.environ["PHOENIX_WORKING_DIRECTORY"] = configs.phoenix.data_dir
os.environ["PHOENIX_MAX_TRACES"] = "5000"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application lifespan.
    This function is called when the application starts and stops.
    """
    logger.info("START...")

    # 1. Chuyển việc khởi chạy Phoenix và Tracing vào trong lifespan.
    # Việc này giúp Phoenix chỉ khởi chạy đúng 1 lần khi app FastAPI thực sự start,
    # và tắt sạch sẽ khi Uvicorn reload, tránh bị treo daemon thread trên macOS.
    px.launch_app()

    tracer_provider = TracerProvider()
    processor = SimpleSpanProcessor(
        OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces")
    )
    tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(tracer_provider)

    OpenAIInstrumentor().instrument()

    # Kế tiếp khởi tạo các engine
    app.state.embedding_engine = EmbeddingEngine()
    app.state.llm_engine = LLMEngine(model_path=llm_path)

    app.state.db_repo = DataBase()
    app.state.vector_repo = VectorDB(embedding=app.state.embedding_engine)
    app.state.graph_repo = GraphDB(
        llm=app.state.llm_engine, embedding=app.state.embedding_engine
    )

    app.state.orchestrator = AgentOrchestrator(llm=app.state.llm_engine)

    yield
    logger.info("SHUT DOWN...")

    # 2. Chủ động close Phoenix khi tắt/reload app để giải phóng hoàn toàn lock terminal
    try:
        px.close_app()
    except Exception:
        pass
    del app


app = FastAPI(
    title="Virtual Assistant API", description="API", version="1.0.0", lifespan=lifespan
)

app.include_router(pipeline_router, prefix="/v1", tags=["Pipeline"])
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
    uvicorn.run(
        "main:app", host=configs.server.host, port=configs.server.port, reload=False
    )
