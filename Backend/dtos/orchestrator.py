# Backend/dtos/orchestrator.py
"""Module định nghĩa DTOs và chuẩn hóa SSE Events cho hệ thống Orchestrator.

Bao gồm:
    - InputRequest: payload đầu vào từ UI.
    - Các *EventPayload: cấu trúc dữ liệu cho 8 loại SSE event (status, plan,
      file, sandbox, token, commit, error, done).
    - format_sse: helper đóng gói payload thành chuỗi chuẩn text/event-stream.
"""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

StatusStep = Literal["plan", "sandbox", "test", "git", "generate", "done"]
FinalStatus = Literal["SUCCESS", "FAILED", "CANCELLED"]
FileActionType = Literal["create", "update", "delete"]


# ============================================================
# Input
# ============================================================
class InputRequest(BaseModel):
    """Schema dữ liệu đầu vào từ người dùng gửi lên API Orchestrator."""

    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(..., min_length=1, description="Yêu cầu lập trình của người dùng")
    session_id: str | None = Field(
        default=None, description="Mã phiên làm việc nếu có; None sẽ dùng workspace mặc định"
    )


# ============================================================
# SSE Event Payloads
# ============================================================
class StatusEventPayload(BaseModel):
    """Payload cho event cập nhật tiến trình ngầm của Agent."""

    model_config = ConfigDict(extra="forbid")

    step: StatusStep = Field(..., description="Bước hiện tại trong pipeline")
    message: str = Field(..., min_length=1, description="Mô tả hành động hiển thị lên UI")


class PlanEventPayload(BaseModel):
    """Payload cho event công bố kế hoạch (sau khi LLM trả về AgentPatchResponse)."""

    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(..., description="Giải thích hướng giải quyết từ LLM")
    files: list[FilePlanItem] = Field(
        default_factory=list, description="Danh sách file sẽ sinh (chỉ path + action)"
    )
    test_command: list[str] = Field(
        default_factory=list, description="Lệnh kiểm thử dự kiến chạy trong sandbox"
    )


class FilePlanItem(BaseModel):
    """Một mục trong kế hoạch file (không chứa nội dung, tiết kiệm băng thông SSE)."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Đường dẫn tương đối của file")
    action: FileActionType = Field(..., description="Hành động: create/update/delete")


class FileEventPayload(BaseModel):
    """Payload cho event thông báo 1 file đã được ghi/cập nhật/xóa."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Đường dẫn tương đối của file")
    action: FileActionType = Field(..., description="Hành động đã thực thi")
    lines_added: int = Field(default=0, ge=0, description="Số dòng thêm vào")
    lines_removed: int = Field(default=0, ge=0, description="Số dòng xóa đi")


class SandboxEventPayload(BaseModel):
    """Payload cho event thông báo kết quả 1 lần chạy lệnh trong sandbox."""

    model_config = ConfigDict(extra="forbid")

    command: list[str] = Field(..., description="Lệnh đã thực thi trong container")
    exit_code: int = Field(..., description="Mã thoát của tiến trình")
    duration_ms: int = Field(..., ge=0, description="Thời gian chạy (ms)")
    is_timeout: bool = Field(default=False, description="Cờ báo tiến trình bị ngắt do timeout")
    stdout_summary: str = Field(
        default="", description="Tóm tắt stdout (tail ~500 ký tự) để UI preview"
    )


class TokenEventPayload(BaseModel):
    """Payload cho event stream từng mẩu text ra màn hình UI."""

    model_config = ConfigDict(extra="forbid")

    delta: str = Field(..., description="Đoạn văn bản/mã nguồn sinh ra theo thời gian thực")


class CommitEventPayload(BaseModel):
    """Payload cho event thông báo Git commit thành công."""

    model_config = ConfigDict(extra="forbid")

    hash: str = Field(..., min_length=1, description="Mã SHA rút gọn của commit")
    message: str = Field(..., min_length=1, description="Thông điệp commit")
    files: list[str] = Field(
        default_factory=list, description="Danh sách file đã thay đổi"
    )


class ErrorEventPayload(BaseModel):
    """Payload cho event báo lỗi trong quá trình thực thi."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., min_length=1, description="Mã định danh lỗi (VD: TEST_MAX_RETRIES)")
    message: str = Field(..., min_length=1, description="Chi tiết thông báo lỗi")


class DoneEventPayload(BaseModel):
    """Payload cho event kết thúc stream kèm thông số đo kiểm chi tiết."""

    model_config = ConfigDict(extra="forbid")

    status: FinalStatus = Field(..., description="Trạng thái cuối cùng của phiên")
    duration_ms: int = Field(..., ge=0, description="Tổng thời gian thực thi (ms)")
    total_tokens: int = Field(default=0, ge=0, description="Tổng lượng token sử dụng")
    input_tokens: int = Field(default=0, ge=0, description="Số lượng prompt token")
    output_tokens: int = Field(default=0, ge=0, description="Số lượng completion token")
    reasoning_tokens: int = Field(
        default=0, ge=0, description="Số lượng thinking/reasoning token"
    )
    cache_tokens: int = Field(default=0, ge=0, description="Số lượng cached token")
    cost: float = Field(default=0.0, ge=0.0, description="Chi phí ước tính (USD)")
    trace_id: str = Field(default="", description="Mã định danh trace để UI mở Waterfall")


# ============================================================
# SSE Formatter
# ============================================================
def format_sse(
    event: str,
    payload: BaseModel | dict[str, Any],
    event_id: str | None = None,
) -> str:
    """Đóng gói dữ liệu thành chuỗi chuẩn Server-Sent Events (SSE).

    Tuân thủ SSE spec: mỗi dòng của data phải có prefix 'data: '. Nếu payload
    chứa ký tự xuống dòng literal, hàm sẽ tách thành nhiều dòng data tương ứng.

    Args:
        event: Tên sự kiện SSE (status, plan, file, sandbox, token, commit,
            error, done).
        payload: Dữ liệu cần chuyển thành chuỗi JSON (BaseModel hoặc dict).
        event_id: ID tùy chọn của event, dùng cho client resume stream.

    Returns:
        Chuỗi định dạng chuẩn 'event: ...\\nid: ...\\ndata: ...\\n\\n'.
    """
    if isinstance(payload, BaseModel):
        raw_json = payload.model_dump_json()
    else:
        raw_json = json.dumps(payload, ensure_ascii=False)

    lines: list[str] = [f"event: {event}"]
    if event_id:
        lines.append(f"id: {event_id}")

    for line in raw_json.splitlines() or [""]:
        lines.append(f"data: {line}")

    return "\n".join(lines) + "\n\n"


def format_sse_ping() -> str:
    """Tạo comment ping chuẩn SSE để giữ kết nối qua proxy.

    Returns:
        Chuỗi comment ':\\n\\n' — SSE client sẽ bỏ qua nhưng proxy vẫn thấy byte.
    """
    return ": ping\n\n"


__all__ = [
    "CommitEventPayload",
    "DoneEventPayload",
    "ErrorEventPayload",
    "FileActionType",
    "FileEventPayload",
    "FilePlanItem",
    "FinalStatus",
    "InputRequest",
    "PlanEventPayload",
    "SandboxEventPayload",
    "StatusEventPayload",
    "StatusStep",
    "TokenEventPayload",
    "format_sse",
    "format_sse_ping",
]


if __name__ == "__main__":
    print("=== Test InputRequest ===")
    req = InputRequest(prompt="Viết hàm tính giai thừa", session_id="sess_001")
    print(req.model_dump_json(indent=2))

    print("\n=== Test StatusEvent ===")
    print(
        format_sse(
            "status",
            StatusEventPayload(step="plan", message="Đang sinh mã nguồn..."),
        )
    )

    print("=== Test PlanEvent ===")
    plan = PlanEventPayload(
        explanation="Dùng đệ quy",
        files=[
            FilePlanItem(path="factorial.py", action="create"),
            FilePlanItem(path="test_factorial.py", action="create"),
        ],
        test_command=["python", "-m", "unittest"],
    )
    print(format_sse("plan", plan))

    print("=== Test DoneEvent ===")
    done = DoneEventPayload(
        status="SUCCESS",
        duration_ms=12345,
        total_tokens=500,
        input_tokens=300,
        output_tokens=200,
        cost=0.0023,
        trace_id="tr_abc123",
    )
    print(format_sse("done", done, event_id="evt_001"))

    print("=== Test Ping ===")
    print(repr(format_sse_ping()))

    print("=== Test multiline payload ===")
    multiline = {"text": "dòng 1\ndòng 2\ndòng 3"}
    print(format_sse("token", multiline))