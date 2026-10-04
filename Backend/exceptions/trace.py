# Backend/exceptions/trace.py
"""Nhóm exception liên quan tới TraceService và repositories."""

from __future__ import annotations

from exceptions.base import AppError


class TraceError(AppError):
    """Lỗi gốc cho mọi vấn đề từ tầng Trace."""

    code = "TRACE_ERROR"


class StorageUploadError(TraceError):
    """Upload blob lên Supabase Storage thất bại."""

    code = "TRACE_STORAGE_UPLOAD_FAILED"


class StorageDownloadError(TraceError):
    """Tải blob từ Supabase Storage thất bại."""

    code = "TRACE_STORAGE_DOWNLOAD_FAILED"


class MetadataWriteError(TraceError):
    """Ghi metadata vào Postgres thất bại."""

    code = "TRACE_METADATA_WRITE_FAILED"


class TraceNotFoundError(TraceError):
    """Không tìm thấy trace theo trace_id."""

    code = "TRACE_NOT_FOUND"


__all__ = [
    "MetadataWriteError",
    "StorageDownloadError",
    "StorageUploadError",
    "TraceError",
    "TraceNotFoundError",
]