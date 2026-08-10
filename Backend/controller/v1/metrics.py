from controller.dependencies import get_db
from dtos.metrics import MetricsResponse
from fastapi import APIRouter, Depends
from services.metrics import HardwareMonitor

metrics_router = APIRouter()


@metrics_router.get("/metrics", response_model=MetricsResponse)
async def get_system_metrics(db_instance=Depends(get_db)) -> MetricsResponse:
    return HardwareMonitor.get_metrics(db_instance=db_instance)
