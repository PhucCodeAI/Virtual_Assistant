from fastapi import APIRouter
from services.metrics import HardwareMonitor
from dtos.metrics import MetricsResponse
from .utils import db

metrics_router = APIRouter()

@metrics_router.get("/metrics", response_model=MetricsResponse)
async def get_system_metrics() -> MetricsResponse:
    return HardwareMonitor.get_metrics(db)