import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.v1.chat import chat_router
from api.v1.metrics import metrics_router
from api.v1.database import db_router
from config import configs
from utils.logger import setup_logging, get_logger

setup_logging()
log = get_logger(__name__)

app = FastAPI(
    title="Virtual Assistant API",
    description="API",
    version="1.0.0"
)

app.include_router(chat_router, prefix="/v1", tags=["Chat"])
app.include_router(metrics_router, prefix="/v1", tags=["Monitor"])
app.include_router(db_router, tags=["Database"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    """
    Docstring: Hàm kiểm tra sức khỏe hệ thống.
    """
    return {"status": "running", "architecture": "Modular APIRouter"}


if __name__ == "__main__":
    import uvicorn
    log.info("Khởi động server...")
    uvicorn.run("main:app",
                host=configs.server.host,
                port=configs.server.port,
                reload=True)