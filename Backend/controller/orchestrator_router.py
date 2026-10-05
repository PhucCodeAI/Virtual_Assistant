# Backend/controller/orchestrator_router.py
"""Router FastAPI cho Orchestrator API (Presentation Layer).

Endpoints:
    - POST /orchestrator/run: chạy pipeline và stream kết quả qua SSE.
    - POST /orchestrator/run/sync: chạy pipeline và trả JSON (không stream).

Đặc điểm:
    - SSE headers đầy đủ để tránh buffer qua Nginx/proxy.
    - Heartbeat ping định kỳ để giữ kết nối qua firewall idle timeout.
    - Client disconnect được xử lý sạch (không leak LLM tokens).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections.abc import AsyncGenerator

from controller.dependencies import OrchestratorDep
from dtos.orchestrator import InputRequest, format_sse_ping
from exceptions import AppError
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from loguru import logger

orchestrator_router = APIRouter(prefix="/orchestrator", tags=["Orchestrator"])

_HEARTBEAT_INTERVAL_SEC = 15.0

_SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
    "Content-Type": "text/event-stream; charset=utf-8",
}


# ============================================================
# SSE streaming endpoint
# ============================================================
@orchestrator_router.post("/run")
async def run_stream(
    req: InputRequest,
    orchestrator: OrchestratorDep,
) -> StreamingResponse:
    """Chạy pipeline AI Coding Agent và stream kết quả qua SSE.

    Args:
        req: Yêu cầu lập trình từ người dùng.
        orchestrator: Orchestrator được inject từ DI.

    Returns:
        StreamingResponse với media type text/event-stream.
    """
    logger.info(
        "Nhận SSE request | session={} | prompt_len={}",
        req.session_id,
        len(req.prompt),
    )

    stream = _wrap_heartbeat(orchestrator.execute_stream(req))
    return StreamingResponse(
        stream,
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


# ============================================================
# Sync endpoint — chạy đầy đủ rồi trả JSON
# ============================================================
@orchestrator_router.post("/run/sync")
async def run_sync(
    req: InputRequest,
    orchestrator: OrchestratorDep,
) -> dict:
    """Chạy pipeline và trả kết quả cuối cùng dạng JSON (không stream).

    Dùng cho client chỉ cần kết quả cuối (VD: batch job, integration test).
    Toàn bộ token events bị discard; chỉ giữ các event quan trọng.

    Args:
        req: Yêu cầu lập trình từ người dùng.
        orchestrator: Orchestrator được inject từ DI.

    Returns:
        Dict gồm plan, file_events, sandbox_events, commit, done, errors.

    Raises:
        HTTPException: Khi pipeline fail không thể phục hồi.
    """
    logger.info(
        "Nhận SYNC request | session={} | prompt_len={}",
        req.session_id,
        len(req.prompt),
    )

    collected = await _collect_stream(orchestrator.execute_stream(req))

    if collected.get("done") is None and not collected["errors"]:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Pipeline kết thúc mà không có sự kiện 'done'.",
        )

    return collected


# ============================================================
# Internal helpers
# ============================================================
async def _wrap_heartbeat(
    source: AsyncGenerator[str, None],
    interval: float = _HEARTBEAT_INTERVAL_SEC,
) -> AsyncGenerator[str, None]:
    """Bọc generator SSE để chèn ping khi không có event trong khoảng interval.

    Dùng asyncio.wait thay vì wait_for để KHÔNG cancel task đang chờ
    __anext__() khi timeout — nếu cancel, CancelledError sẽ lan xuống
    orchestrator và bị nhầm thành client disconnect.

    Args:
        source: Generator SSE gốc từ Orchestrator.
        interval: Số giây tối đa giữa 2 event trước khi phát ping.

    Yields:
        Chuỗi SSE đã được chèn ping.
    """
    iterator = source.__aiter__()
    next_task: asyncio.Task[str] | None = None

    try:
        while True:
            if next_task is None:
                next_task = asyncio.create_task(iterator.__anext__())

            done, _ = await asyncio.wait({next_task}, timeout=interval)

            if next_task in done:
                try:
                    chunk = next_task.result()
                except StopAsyncIteration:
                    return
                next_task = None
                yield chunk
            else:
                yield format_sse_ping()

    except asyncio.CancelledError:
        logger.info("SSE client disconnect — dừng stream")
        await _cancel_task(next_task)
        await source.aclose()
        raise
    finally:
        await _cancel_task(next_task)
        if source.ag_frame is not None:
            with contextlib.suppress(Exception):
                await source.aclose()


async def _cancel_task(task: asyncio.Task | None) -> None:
    """Cancel task an toàn, chờ nó thoát hẳn.

    Args:
        task: Task cần cancel. Bỏ qua nếu None hoặc đã done.
    """
    if task is None or task.done():
        return
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError, StopAsyncIteration):
        await task


async def _collect_stream(
    source: AsyncGenerator[str, None],
) -> dict:
    """Chạy hết stream SSE và gom các event quan trọng thành dict.

    Parse chuỗi SSE theo format: "event: <name>\\ndata: <json>\\n\\n".
    Token events bị bỏ qua để tiết kiệm bộ nhớ.

    Args:
        source: Generator SSE từ Orchestrator.

    Returns:
        Dict gồm: trace_id, status, plan, file_events, sandbox_events,
        commit, done, errors.
    """
    result: dict = {
        "trace_id": None,
        "status": None,
        "plan": None,
        "file_events": [],
        "sandbox_events": [],
        "commit": None,
        "done": None,
        "errors": [],
    }

    async for sse_chunk in source:
        event_name, payload = _parse_sse(sse_chunk)
        if event_name is None:
            continue

        if event_name == "plan":
            result["plan"] = payload
        elif event_name == "file":
            result["file_events"].append(payload)
        elif event_name == "sandbox":
            result["sandbox_events"].append(payload)
        elif event_name == "commit":
            result["commit"] = payload
        elif event_name == "error":
            result["errors"].append(payload)
        elif event_name == "done":
            result["done"] = payload
            result["trace_id"] = payload.get("trace_id")
            result["status"] = payload.get("status")
    return result


def _parse_sse(chunk: str) -> tuple[str | None, dict | None]:
    """Parse một chuỗi SSE thành (event_name, data_dict).

    Args:
        chunk: Chuỗi SSE đầy đủ (có thể gồm nhiều dòng).

    Returns:
        Tuple (event_name, payload_dict). Trả về (None, None) nếu là ping
        hoặc không parse được.
    """
    if not chunk or chunk.startswith(":"):
        return None, None

    event_name: str | None = None
    data_parts: list[str] = []

    for line in chunk.split("\n"):
        if line.startswith("event: "):
            event_name = line[len("event: ") :].strip()
        elif line.startswith("data: "):
            data_parts.append(line[len("data: ") :])

    if event_name is None or not data_parts:
        return None, None

    raw = "\n".join(data_parts)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("Không parse được SSE data: {}", raw[:120])
        return None, None

    return event_name, payload


__all__ = ["orchestrator_router"]


if __name__ == "__main__":
    print("=== Test _parse_sse ===")
    sample = (
        "event: plan\n"
        'data: {"explanation":"x","files":[]}\n\n'
    )
    name, payload = _parse_sse(sample)
    print(f"event={name}, payload={payload}")
    assert name == "plan"
    assert payload == {"explanation": "x", "files": []}

    print("\n=== Test ping bị bỏ qua ===")
    name, payload = _parse_sse(": ping\n\n")
    assert name is None and payload is None
    print("PASS")

    print("\n=== Test JSON không hợp lệ bị bỏ qua ===")
    name, payload = _parse_sse("event: x\ndata: not-json\n\n")
    assert name is None
    print("PASS")