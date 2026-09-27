"""Module định nghĩa DTOs và chuẩn hóa SSE Events cho hệ thống Orchestrator."""

import json
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class InputRequest(BaseModel):
    """Schema dữ liệu đầu vào từ người dùng gửi lên API Orchestrator."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, description="Yêu cầu lập trình của người dùng")
    session_id: str | None = Field(default=None, description="Mã phiên làm việc nếu có")


class StatusEventPayload(BaseModel):
    """Payload cho event cập nhật tiến trình ngầm của Agent."""

    step: str = Field(..., description="Tên bước hiện tại: plan, sandbox, test, git")
    message: str = Field(..., description="Mô tả hành động hiển thị lên UI")


class TokenEventPayload(BaseModel):
    """Payload cho event stream từng mẩu text ra màn hình UI."""

    delta: str = Field(..., description="Đoạn văn bản/mã nguồn sinh ra theo thời gian thực")


class CommitEventPayload(BaseModel):
    """Payload cho event thông báo Git commit thành công."""

    hash: str = Field(..., description="Mã SHA của commit")
    message: str = Field(..., description="Thông điệp của commit")
    files: list[str] = Field(default_factory=list, description="Danh sách các file đã thay đổi")


class ErrorEventPayload(BaseModel):
    """Payload cho event báo lỗi trong quá trình thực thi."""

    code: str = Field(..., description="Mã định danh lỗi")
    message: str = Field(..., description="Chi tiết thông báo lỗi")


class DoneEventPayload(BaseModel):
    """Payload cho event kết thúc stream kèm thông số đo kiểm chi tiết."""

    model_config = ConfigDict(extra="forbid")

    total_time: int = Field(..., description="Tổng thời gian thực thi (ms)")
    total_token: int = Field(..., description="Tổng lượng token sử dụng")
    input_token: int = Field(default=0, description="Số lượng prompt token")
    reasoning_token: int = Field(default=0, description="Số lượng thinking/reasoning token")
    cache_token: int = Field(default=0, description="Số lượng cached token")
    cost: float = Field(default=0.0, description="Chi phí ước tính")


def format_sse(event_name: str, payload: BaseModel | dict[str, Any]) -> str:
    """Đóng gói dữ liệu thành chuỗi chuẩn Server-Sent Events (SSE).

    Args:
        event_name (str): Tên của sự kiện SSE (status, token, commit, error, done).
        payload (BaseModel | dict[str, Any]): Dữ liệu cần chuyển thành chuỗi JSON.

    Returns:
        str: Chuỗi định dạng chuẩn 'event: ...\\ndata: ...\\n\\n'.
    """
    if isinstance(payload, BaseModel):
        raw_json = payload.model_dump_json()
    else:
        raw_json = json.dumps(payload, ensure_ascii=False)
    return f"event: {event_name}\ndata: {raw_json}\n\n"