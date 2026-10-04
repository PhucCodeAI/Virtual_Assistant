# Backend/exceptions/__init__.py
"""Package gom nhóm toàn bộ exception tùy chỉnh của hệ thống.

Import tập trung tại đây để các module khác chỉ cần:
    from exceptions import LLMSchemaError, EditApplyError, SandboxTimeoutError
"""

from __future__ import annotations

from exceptions.base import AppError
from exceptions.git import GitCommandError, GitError
from exceptions.llm import (
    LLMError,
    LLMResponseError,
    LLMSchemaError,
    LLMStreamError,
)
from exceptions.sandbox import (
    DockerUnavailableError,
    SandboxError,
    SandboxTimeoutError,
)
from exceptions.trace import (
    MetadataWriteError,
    StorageDownloadError,
    StorageUploadError,
    TraceError,
    TraceNotFoundError,
)
from exceptions.workspace import (
    EditApplyError,
    FileNotFoundInWorkspaceError,
    PathSecurityError,
    WorkspaceError,
)

__all__ = [
    "AppError",
    "DockerUnavailableError",
    "EditApplyError",
    "FileNotFoundInWorkspaceError",
    "GitCommandError",
    "GitError",
    "LLMError",
    "LLMResponseError",
    "LLMSchemaError",
    "LLMStreamError",
    "MetadataWriteError",
    "PathSecurityError",
    "SandboxError",
    "SandboxTimeoutError",
    "StorageDownloadError",
    "StorageUploadError",
    "TraceError",
    "TraceNotFoundError",
    "WorkspaceError",
]


if __name__ == "__main__":
    # Test nhanh: chạy `python -m exceptions` từ Backend/
    err = LLMSchemaError("Không khớp schema", context={"field": "files"})
    print(f"Type: {type(err).__name__}")
    print(f"Code: {err.code}")
    print(f"Dict: {err.to_dict()}")
    print(f"Repr: {err!r}")

    assert isinstance(err, AppError)
    assert isinstance(err, LLMError)
    print("PASS: kế thừa đúng chuỗi AppError → LLMError → LLMSchemaError")