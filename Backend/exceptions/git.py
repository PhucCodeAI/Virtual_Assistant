# Backend/exceptions/git.py
"""Nhóm exception liên quan tới GitService."""

from __future__ import annotations

from exceptions.base import AppError


class GitError(AppError):
    """Lỗi gốc cho mọi vấn đề từ GitService."""

    code = "GIT_ERROR"


class GitCommandError(GitError):
    """Lệnh git CLI trả về exit code khác 0.

    Attributes:
        args: Danh sách tham số lệnh git đã chạy.
        exit_code: Mã thoát của tiến trình git.
        stderr: Stderr của git.
    """

    code = "GIT_COMMAND_FAILED"

    def __init__(
        self,
        message: str,
        *,
        args: list[str],
        exit_code: int,
        stderr: str,
    ) -> None:
        """Khởi tạo GitCommandError.

        Args:
            message: Thông báo tóm tắt.
            args: Args lệnh git đã chạy.
            exit_code: Mã thoát.
            stderr: Stderr.
        """
        super().__init__(
            message,
            context={"args": args, "exit_code": exit_code, "stderr": stderr[:500]},
        )
        self.args_list = args
        self.exit_code = exit_code
        self.stderr = stderr


__all__ = [
    "GitCommandError",
    "GitError",
]