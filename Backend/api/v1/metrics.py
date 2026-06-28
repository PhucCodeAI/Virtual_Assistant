from fastapi import APIRouter
from services.metrics import HardwareMonitor
from dtos.metrics import MetricsResponse
from api.v1.database import db

metrics_router = APIRouter()

@metrics_router.get("/metrics", response_model=MetricsResponse)
async def get_system_metrics():
    return HardwareMonitor.get_metrics(db)