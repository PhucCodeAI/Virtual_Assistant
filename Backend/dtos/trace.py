# Backend/dtos/trace.py
"""Module định nghĩa DTOs cho Trace API.

Bao gồm:
    - SpanDTO: một đơn vị công việc có thời lượng trong trace (LLM call, sandbox
      exec, git commit, ...).
    - TraceSummaryDTO: metadata tinh gọn cho dashboard list.
    - TraceDetailDTO: metadata + toàn bộ spans cho waterfall view.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SpanType = Literal["llm", "tool", "sandbox", "git", "internal"]
SpanStatus = Literal["OK", "ERROR"]


class SpanDTO(BaseModel):
    """Một đơn vị công việc có thời lượng trong trace."""

    model_config = ConfigDict(extra="ignore")

    span_id: str = Field(..., description="ID unique của span")
    name: str = Field(..., description="Tên hiển thị (VD: 'LLM Generation (Attempt 1)')")
    span_type: SpanType = Field(..., description="Loại span để UI phân loại")
    duration_ms: int = Field(..., ge=0, description="Thời gian thực thi (ms)")
    status: SpanStatus = Field(default="OK", description="OK hoặc ERROR")
    input_data: Any = Field(default=None, description="Payload đầu vào (đã truncate)")
    output_data: Any = Field(default=None, description="Payload đầu ra (đã truncate)")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Metadata bổ sung")


class TraceSummaryDTO(BaseModel):
    """Schema tóm tắt hiển thị danh sách Dashboard."""

    model_config = ConfigDict(extra="ignore")

    trace_id: str
    session_id: str
    prompt: str
    status: str
    duration_ms: int
    total_tokens: int
    cost: float
    created_at: str


class TraceDetailDTO(TraceSummaryDTO):
    """Schema chi tiết kèm toàn bộ cây Spans để UI vẽ Waterfall."""

    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    cache_tokens: int = 0
    error_message: str | None = None
    finished_at: str | None = None
    spans: list[SpanDTO] = Field(default_factory=list)


__all__ = [
    "SpanDTO",
    "SpanStatus",
    "SpanType",
    "TraceDetailDTO",
    "TraceSummaryDTO",
]


if __name__ == "__main__":
    print("=== SpanDTO ===")
    span = SpanDTO(
        span_id="sp_abc",
        name="LLM Call",
        span_type="llm",
        duration_ms=1234,
        status="OK",
        input_data={"messages": ["hi"]},
        output_data={"content": "hello"},
        metadata={"tokens": 100},
    )
    print(span.model_dump_json(indent=2))

    print("\n=== TraceDetailDTO ===")
    detail = TraceDetailDTO(
        trace_id="tr_1",
        session_id="sess_1",
        prompt="Viết hàm",
        status="SUCCESS",
        duration_ms=5000,
        total_tokens=300,
        cost=0.001,
        created_at="2026-10-04T00:00:00Z",
        spans=[span],
    )
    print(f"spans={len(detail.spans)}, first={detail.spans[0].name}")