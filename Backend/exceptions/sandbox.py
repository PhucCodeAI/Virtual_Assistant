# Backend/exceptions/sandbox.py
"""Nhóm exception liên quan tới SandboxEngine."""

from __future__ import annotations

from exceptions.base import AppError


class SandboxError(AppError):
    """Lỗi gốc cho mọi vấn đề từ SandboxEngine."""

    code = "SANDBOX_ERROR"


class DockerUnavailableError(SandboxError):
    """Docker daemon không khả dụng hoặc không có quyền truy cập socket."""

    code = "SANDBOX_DOCKER_UNAVAILABLE"


class SandboxTimeoutError(SandboxError):
    """Tiến trình trong sandbox vượt quá timeout cho phép."""

    code = "SANDBOX_TIMEOUT"


__all__ = [
    "DockerUnavailableError",
    "SandboxError",
    "SandboxTimeoutError",
]