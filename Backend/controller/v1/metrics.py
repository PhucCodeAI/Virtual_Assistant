from fastapi import APIRouter, Depends
from services.metrics import HardwareMonitor
from dtos.metrics import MetricsResponse
from controller.dependencies import get_db

metrics_router = APIRouter()

@metrics_router.get("/metrics", response_model=MetricsResponse)
async def get_system_metrics() -> MetricsResponse:
    return HardwareMonitor.get_metrics(Depends(get_db))