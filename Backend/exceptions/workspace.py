# Backend/exceptions/workspace.py
"""Nhóm exception liên quan tới thao tác file trong workspace."""

from __future__ import annotations

from exceptions.base import AppError


class WorkspaceError(AppError):
    """Lỗi gốc cho mọi vấn đề trong WorkspaceManager."""

    code = "WORKSPACE_ERROR"


class PathSecurityError(WorkspaceError):
    """Phát hiện path traversal, symlink escape, hoặc truy cập .git.

    Đây là lỗi BẢO MẬT — không bao giờ được retry tự động.
    """

    code = "WORKSPACE_PATH_UNSAFE"


class EditApplyError(WorkspaceError):
    """Không apply được edit (search/replace) lên file.

    Caller (Orchestrator) thường re-prompt LLM yêu cầu dùng action='create'
    để rewrite toàn bộ file.
    """

    code = "WORKSPACE_EDIT_FAILED"


class FileNotFoundInWorkspaceError(WorkspaceError):
    """File cần đọc/update không tồn tại trong workspace."""

    code = "WORKSPACE_FILE_NOT_FOUND"


__all__ = [
    "EditApplyError",
    "FileNotFoundInWorkspaceError",
    "PathSecurityError",
    "WorkspaceError",
]