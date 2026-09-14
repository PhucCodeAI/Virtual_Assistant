import os
from contextlib import asynccontextmanager

# import phoenix as px
import uvicorn
from config import configs
from controller.v1.agent import agent_router
from controller.v1.metrics import metrics_router
from controller.v1.utils import utils_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# from openinference.instrumentation.openai import OpenAIInstrumentor
# from opentelemetry import trace
# from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
# from opentelemetry.sdk.trace import TracerProvider
# from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from services.llm_engine import LLMEngine
from services.report_manager import start_bot_service, stop_bot_service
from utils.logger import setup_logging
from utils.setup import setup
from workflows.orchestrator import AgentOrchestrator

llm_path = setup()
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

    # 1. Tracing setup
    # px.launch_app()

    # tracer_provider = TracerProvider()
    # processor = SimpleSpanProcessor(
    #     OTLPSpanExporter(endpoint="http://localhost:6006/v1/traces")
    # )
    # tracer_provider.add_span_processor(processor)
    # trace.set_tracer_provider(tracer_provider)

    # OpenAIInstrumentor().instrument()

    # 2. Khởi tạo các engines & repositories
    # app.state.embedding_engine = EmbeddingEngine()
    app.state.llm_engine = LLMEngine(model_path=llm_path)

    # app.state.db_repo = DataBase()
    # app.state.vector_repo = VectorDB(embedding=app.state.embedding_engine)
    # app.state.graph_repo = GraphDB(
    #     llm=app.state.llm_engine, embedding=app.state.embedding_engine
    # )

    app.state.orchestrator = AgentOrchestrator(llm=app.state.llm_engine)

    # 3. Khởi tạo & Đăng ký Telegram Service
    await start_bot_service(app)

    yield

    logger.info("SHUT DOWN...")

    await stop_bot_service(app)

    # # 6. Close Phoenix
    # try:
    #     px.close_app()
    # except Exception:
    #     pass
    # del app


app = FastAPI(
    title="Virtual Assistant API", description="API", version="1.0.0", lifespan=lifespan
)

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
    uvicorn.run(
        "main:app", host=configs.server.host, port=configs.server.port, reload=False
    )
