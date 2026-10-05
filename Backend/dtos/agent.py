# Backend/dtos/agent.py
"""Module định nghĩa DTOs cho hành động sinh mã nguồn và kế hoạch của Agent.

Bao gồm:
    - FileEdit: một cặp search/replace để chỉnh sửa file đã tồn tại.
    - FileAction: thao tác create/update/delete trên một file trong workspace.
    - AgentPatchResponse: kế hoạch đầy đủ do LLM sinh ra (explanation + files +
      test_command).

Ràng buộc an toàn: đường dẫn file được validate ngay tại DTO boundary để chặn
path traversal trước khi chạm tới WorkspaceManager.
"""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FileActionType = Literal["create", "update", "delete"]


class FileEdit(BaseModel):
    """Một cặp search/replace để chỉnh sửa cục bộ file đã tồn tại.

    Thuật toán apply (thực thi tại WorkspaceManager):
        1. Thử khớp exact `old_text` trong file.
        2. Nếu fail, thử khớp không phân biệt trailing whitespace mỗi dòng.
        3. Nếu vẫn fail → raise EditApplyError để Orchestrator re-prompt LLM.
    """

    model_config = ConfigDict(extra="forbid")

    old_text: str = Field(
        ...,
        min_length=1,
        description="Đoạn text gốc cần tìm. Phải unique trong file để tránh sửa nhầm.",
    )
    new_text: str = Field(
        ...,
        description="Đoạn text thay thế. Cho phép rỗng để biểu diễn hành vi xóa.",
    )


class FileAction(BaseModel):
    """Mô tả một thao tác tạo, sửa đổi hoặc xóa file trong workspace.

    Quy tắc sử dụng theo `action`:
        - create: bắt buộc có `content` (toàn bộ nội dung file mới).
        - update: bắt buộc có `edits` (danh sách search/replace). Nếu LLM muốn
          rewrite toàn bộ file cũ, dùng action="create" để ghi đè.
        - delete: chỉ cần `path`, bỏ trống `content` và `edits`.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(
        ...,
        min_length=1,
        max_length=512,
        description="Đường dẫn tương đối của file (VD: 'app/calc.py', 'test_calc.py')",
    )
    action: FileActionType = Field(
        default="create",
        description="Hành động: create | update | delete",
    )
    content: str | None = Field(
        default=None,
        description="Toàn bộ nội dung file. Bắt buộc khi action='create'.",
    )
    edits: list[FileEdit] | None = Field(
        default=None,
        description="Danh sách search/replace. Bắt buộc khi action='update'.",
    )
    language: str | None = Field(
        default=None,
        description="Ngôn ngữ để UI syntax highlight (VD: 'python'). None = tự đoán.",
    )

    @field_validator("path")
    @classmethod
    def _validate_path(cls, v: str) -> str:
        """Chuẩn hóa và kiểm tra đường dẫn an toàn.

        Args:
            v: Đường dẫn thô do LLM sinh ra.

        Returns:
            Đường dẫn đã chuẩn hóa (dùng '/' làm separator).

        Raises:
            ValueError: Khi path tuyệt đối, chứa '..', hoặc trỏ vào .git.
        """
        normalized = v.replace("\\", "/").strip()
        if not normalized:
            raise ValueError("Đường dẫn không được rỗng")

        pure = PurePosixPath(normalized)
        if pure.is_absolute():
            raise ValueError(f"Đường dẫn tuyệt đối không được phép: '{v}'")
        if ".." in pure.parts:
            raise ValueError(f"Đường dẫn chứa '..' không được phép: '{v}'")
        if ".git" in pure.parts:
            raise ValueError(f"Không được thao tác trong .git: '{v}'")

        return str(pure)

    @model_validator(mode="after")
    def _validate_action_fields(self) -> FileAction:
        """Kiểm tra tính nhất quán giữa `action` và các field đi kèm.

        Returns:
            Instance đã validate.

        Raises:
            ValueError: Khi field không khớp với action.
        """
        if self.action == "create":
            if not self.content:
                raise ValueError("action='create' bắt buộc phải có 'content'")
            if self.edits:
                raise ValueError("action='create' không được có 'edits'")
        elif self.action == "update":
            if not self.edits:
                raise ValueError("action='update' bắt buộc phải có 'edits'")
            if self.content is not None:
                raise ValueError(
                    "action='update' không nhận 'content'. "
                    "Muốn rewrite toàn bộ file, dùng action='create'."
                )
        elif self.action == "delete":
            if self.content or self.edits:
                raise ValueError("action='delete' chỉ nhận 'path'")
        return self


class AgentPatchResponse(BaseModel):
    """Kế hoạch giải quyết và danh sách thao tác file do LLM sinh ra."""

    model_config = ConfigDict(extra="forbid")

    explanation: str = Field(
        ...,
        min_length=1,
        description="Giải thích ngắn gọn hướng giải quyết bằng Tiếng Việt",
    )
    files: list[FileAction] = Field(
        ...,
        min_length=1,
        description="Danh sách thao tác file (bao gồm file mã nguồn và file test)",
    )
    test_command: list[str] = Field(
        default_factory=lambda: [
            "python",
            "-m",
            "unittest",
            "discover",
            "-s",
            ".",
            "-p",
            "test_*.py",
        ],
        description="Lệnh thực thi kiểm thử trong container Docker",
    )

    @field_validator("test_command")
    @classmethod
    def _validate_test_command(cls, v: list[str]) -> list[str]:
        """Đảm bảo test_command là list không rỗng các string không rỗng.

        Args:
            v: Danh sách tham số lệnh.

        Returns:
            Danh sách đã strip.

        Raises:
            ValueError: Khi list rỗng hoặc chứa phần tử rỗng.
        """
        if not v:
            raise ValueError("test_command không được rỗng")
        cleaned = [part.strip() for part in v]
        if any(not part for part in cleaned):
            raise ValueError("test_command không được chứa phần tử rỗng")
        return cleaned

class ApplyResult(BaseModel):
    """Kết quả của một thao tác FileAction đã được thực thi lên workspace.

    Dùng để emit FileEventPayload và ghi trace span.
    """

    model_config = ConfigDict(extra="forbid")

    path: str = Field(..., description="Đường dẫn tương đối của file")
    action: FileActionType = Field(..., description="Hành động đã thực thi")
    lines_added: int = Field(default=0, ge=0, description="Số dòng thêm vào")
    lines_removed: int = Field(default=0, ge=0, description="Số dòng xóa đi")
    bytes_written: int = Field(default=0, ge=0, description="Số byte ghi vào đĩa")

__all__ = [
    "AgentPatchResponse",
    "ApplyResult",
    "FileAction",
    "FileActionType",
    "FileEdit",
]


if __name__ == "__main__":
    from pydantic import ValidationError

    print("=== Test FileAction create ===")
    create = FileAction(
        path="app/calculator.py",
        action="create",
        content="def add(a, b):\n    return a + b\n",
        language="python",
    )
    print(create.model_dump_json(indent=2))

    print("\n=== Test FileAction update với edits ===")
    update = FileAction(
        path="app/calculator.py",
        action="update",
        edits=[
            FileEdit(
                old_text="return a + b",
                new_text="return a + b  # cộng hai số",
            )
        ],
        language="python",
    )
    print(update.model_dump_json(indent=2))

    print("\n=== Test FileAction delete ===")
    delete = FileAction(path="old.py", action="delete")
    print(delete.model_dump_json())

    print("\n=== Test chặn path traversal ===")
    try:
        FileAction(path="../../../etc/passwd", action="delete")
    except ValidationError as e:
        print(f"PASS: {e.errors()[0]['msg']}")

    print("\n=== Test chặn .git ===")
    try:
        FileAction(path=".git/config", action="delete")
    except ValidationError as e:
        print(f"PASS: {e.errors()[0]['msg']}")

    print("\n=== Test chặn create thiếu content ===")
    try:
        FileAction(path="a.py", action="create")
    except ValidationError as e:
        print(f"PASS: {e.errors()[0]['msg']}")

    print("\n=== Test chặn update có content ===")
    try:
        FileAction(path="a.py", action="update", content="x", edits=[])
    except ValidationError as e:
        print(f"PASS: {e.errors()[0]['msg']}")

    print("\n=== Test AgentPatchResponse ===")
    patch = AgentPatchResponse(
        explanation="Tạo module tính toán và test tương ứng.",
        files=[
            FileAction(
                path="calc.py",
                action="create",
                content="def add(a, b): return a + b\n",
            ),
            FileAction(
                path="test_calc.py",
                action="create",
                content="from calc import add\n",
            ),
        ],
    )
    print(patch.model_dump_json(indent=2))

    print("\n=== Test AgentPatchResponse thiếu files ===")
    try:
        AgentPatchResponse(explanation="x", files=[])
    except ValidationError as e:
        print(f"PASS: {e.errors()[0]['msg']}")

class AgentResult(BaseModel):
    """Kết quả sau khi agent chạy xong."""

    model_config = ConfigDict(extra="forbid")

    name: str
    status: str = "SUCCESS"
    output: dict[str, Any] = {}
    error: str | None = None