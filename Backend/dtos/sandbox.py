"""Module định nghĩa DTOs cho môi trường thực thi cô lập (Sandbox)."""

from pydantic import BaseModel, ConfigDict, Field


class ExecutionResult(BaseModel):
    """Kết quả thực thi lệnh bên trong Docker Sandbox."""

    model_config = ConfigDict(extra="forbid")

    exit_code: int = Field(..., description="Mã thoát của tiến trình (0 là thành công)")
    stdout: str = Field(default="", description="Dữ liệu đầu ra chuẩn")
    stderr: str = Field(default="", description="Thông báo lỗi chuẩn")
    duration_ms: int = Field(..., description="Thời gian thực thi tính bằng mili-giây")
    is_timeout: bool = Field(default=False, description="Đánh dấu tiến trình bị ngắt do quá thời gian")