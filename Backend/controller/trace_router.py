"""Module REST API cung cấp dữ liệu Trace cho giao diện Frontend."""

from dtos.trace import TraceDetailDTO, TraceSummaryDTO
from fastapi import APIRouter, Depends, HTTPException, Query
from services.trace_service import TraceService

from .dependencies import get_trace_service

trace_router = APIRouter(prefix="/traces", tags=["Traces"])


@trace_router.get("", response_model=list[TraceSummaryDTO])
async def list_traces(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    service: TraceService = Depends(get_trace_service),
) -> list[TraceSummaryDTO]:
    """Lấy danh sách lịch sử các phiên chạy từ Supabase."""
    return await service.get_recent_traces(limit=limit, offset=offset)


@trace_router.get("/{trace_id}", response_model=TraceDetailDTO)
async def get_trace_detail(
    trace_id: str,
    service: TraceService = Depends(get_trace_service),
) -> TraceDetailDTO:
    """Lấy chi tiết Waterfall Spans để UI vẽ cây tiến trình."""
    detail = await service.get_trace_waterfall(trace_id)
    if not detail:
        raise HTTPException(
            status_code=404, detail="Không tìm thấy Trace ID tương ứng."
        )
    return detail
