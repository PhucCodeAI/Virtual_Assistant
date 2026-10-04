# Backend/controller/trace_router.py
"""Router FastAPI cho Trace API (Presentation Layer).

Endpoints:
    - GET    /traces                  → list trace gần nhất (paginated).
    - GET    /traces/{trace_id}       → chi tiết trace + spans.
    - GET    /traces/stats/count      → đếm tổng số trace (filter-able).
    - GET    /traces/session/{sid}    → filter theo session.
    - DELETE /traces/{trace_id}       → xóa cả metadata + blob.
"""

from __future__ import annotations

from typing import Annotated

from controller.dependencies import TraceServiceDep
from dtos.trace import TraceDetailDTO, TraceSummaryDTO
from exceptions import AppError
from fastapi import APIRouter, HTTPException, Query, status
from loguru import logger

trace_router = APIRouter(prefix="/traces", tags=["Traces"])


# ============================================================
# List & filter
# ============================================================
@trace_router.get("", response_model=list[TraceSummaryDTO])
async def list_traces(
    trace_service: TraceServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    session_id: Annotated[str | None, Query()] = None,
) -> list[TraceSummaryDTO]:
    """Liệt kê trace gần nhất với filter tùy chọn.

    Args:
        trace_service: TraceService được inject từ DI.
        limit: Số bản ghi tối đa (1-100).
        offset: Vị trí bắt đầu (pagination).
        status_filter: Lọc theo trạng thái (SUCCESS/FAILED/RUNNING).
        session_id: Lọc theo session.

    Returns:
        Danh sách TraceSummaryDTO sắp xếp theo created_at giảm dần.
    """
    try:
        if status_filter or session_id:
            return await trace_service.search_traces(
                status=status_filter,
                session_id=session_id,
                limit=limit,
                offset=offset,
            )
        return await trace_service.get_recent_traces(limit=limit, offset=offset)
    except AppError as e:
        logger.error("List traces thất bại: {}", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": e.code, "message": e.message},
        ) from e


@trace_router.get(
    "/session/{session_id}",
    response_model=list[TraceSummaryDTO],
)
async def list_traces_by_session(
    session_id: str,
    trace_service: TraceServiceDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[TraceSummaryDTO]:
    """Liệt kê trace thuộc một session cụ thể.

    Args:
        session_id: Mã phiên làm việc.
        trace_service: TraceService được inject từ DI.
        limit: Số bản ghi tối đa.
        offset: Vị trí bắt đầu.

    Returns:
        Danh sách TraceSummaryDTO.
    """
    try:
        return await trace_service.list_traces_by_session(
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
    except AppError as e:
        logger.error("List by session thất bại: {}", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": e.code, "message": e.message},
        ) from e


@trace_router.get("/stats/count")
async def count_traces(
    trace_service: TraceServiceDep,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    session_id: Annotated[str | None, Query()] = None,
) -> dict:
    """Đếm tổng số trace khớp filter (cho dashboard pagination).

    Args:
        trace_service: TraceService được inject từ DI.
        status_filter: Lọc theo trạng thái.
        session_id: Lọc theo session.

    Returns:
        Dict gồm `count` (tổng số bản ghi).
    """
    try:
        total = await trace_service.count_traces(
            status=status_filter,
            session_id=session_id,
        )
        return {"count": total}
    except AppError as e:
        logger.error("Count traces thất bại: {}", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": e.code, "message": e.message},
        ) from e


# ============================================================
# Detail
# ============================================================
@trace_router.get("/{trace_id}", response_model=TraceDetailDTO)
async def get_trace_detail(
    trace_id: str,
    trace_service: TraceServiceDep,
) -> TraceDetailDTO:
    """Lấy chi tiết trace kèm toàn bộ spans để UI vẽ waterfall.

    Args:
        trace_id: Mã định danh trace.
        trace_service: TraceService được inject từ DI.

    Returns:
        TraceDetailDTO với đầy đủ spans.

    Raises:
        HTTPException 404: Khi không tìm thấy trace.
        HTTPException 502: Khi tầng dữ liệu lỗi.
    """
    try:
        detail = await trace_service.get_trace_waterfall(trace_id)
    except AppError as e:
        logger.error("Get trace detail thất bại: {}", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": e.code, "message": e.message},
        ) from e

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TRACE_NOT_FOUND", "message": f"Không tìm thấy trace: {trace_id}"},
        )
    return detail


# ============================================================
# Delete
# ============================================================
@trace_router.delete("/{trace_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trace(
    trace_id: str,
    trace_service: TraceServiceDep,
) -> None:
    """Xóa trace cả 2 tầng: metadata DB và blob Storage.

    Args:
        trace_id: Mã định danh trace.
        trace_service: TraceService được inject từ DI.

    Raises:
        HTTPException 404: Khi không tìm thấy trace.
        HTTPException 502: Khi tầng dữ liệu lỗi.
    """
    try:
        deleted = await trace_service.delete_trace(trace_id)
    except AppError as e:
        logger.error("Delete trace thất bại: {}", e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": e.code, "message": e.message},
        ) from e

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TRACE_NOT_FOUND", "message": f"Không tìm thấy trace: {trace_id}"},
        )


__all__ = ["trace_router"]


if __name__ == "__main__":
    print("=== Kiểm tra router khởi tạo ===")
    from controller.trace_router import trace_router as tr

    routes = [(r.path, sorted(r.methods)) for r in tr.routes]
    for path, methods in routes:
        print(f"  {methods} {path}")
    print("PASS: module import thành công, các endpoint đã đăng ký.")