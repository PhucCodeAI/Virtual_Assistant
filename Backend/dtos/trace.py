"""Module định nghĩa DTOs cho Trace API."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
    spans: list[dict[str, Any]] = Field(default_factory=list)
