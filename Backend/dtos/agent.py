"""Module định nghĩa DTOs cho các hành động sinh mã nguồn và kế hoạch của Agent."""

from pydantic import BaseModel, ConfigDict, Field


class FileAction(BaseModel):
    """Mô tả một thao tác tạo hoặc sửa đổi file trong workspace."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Đường dẫn tương đối của file (ví dụ: 'app/calc.py', 'test_calc.py')")
    content: str = Field(..., description="Toàn bộ nội dung mã nguồn của file")


class AgentPatchResponse(BaseModel):
    """Kế hoạch giải quyết và danh sách mã nguồn hoàn chỉnh do LLM sinh ra."""

    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(..., description="Giải thích ngắn gọn hướng giải quyết bằng Tiếng Việt")
    files: list[FileAction] = Field(..., min_length=1, description="Danh sách các file mã nguồn và file test")
    test_command: list[str] = Field(
        default=["python", "-m", "unittest", "discover"],
        description="Lệnh thực thi kiểm thử trong container Docker",
    )