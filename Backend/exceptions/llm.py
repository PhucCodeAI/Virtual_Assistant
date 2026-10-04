# Backend/exceptions/llm.py
"""Nhóm exception liên quan tới LLMClient.

Phân biệt 4 loại lỗi để caller xử lý khác nhau:
    - LLMError: base cho mọi lỗi LLM.
    - LLMResponseError: không parse được response thành JSON.
    - LLMSchemaError: JSON hợp lệ nhưng không khớp Pydantic schema.
    - LLMStreamError: stream đứt giữa chừng sau khi đã yield chunk.
"""

from __future__ import annotations

from exceptions.base import AppError


class LLMError(AppError):
    """Lỗi gốc cho mọi vấn đề phát sinh từ LLMClient."""

    code = "LLM_ERROR"


class LLMResponseError(LLMError):
    """Response không đúng cấu trúc JSON mong đợi."""

    code = "LLM_RESPONSE_INVALID"


class LLMSchemaError(LLMError):
    """Response parse được JSON nhưng không khớp Pydantic schema.

    Caller (Orchestrator) thường sẽ re-prompt LLM để sửa format.
    """

    code = "LLM_SCHEMA_MISMATCH"


class LLMStreamError(LLMError):
    """Stream bị đứt giữa chừng sau khi đã yield ít nhất 1 chunk.

    Không thể retry an toàn vì nội dung đã gửi xuống UI.
    """

    code = "LLM_STREAM_BROKEN"


__all__ = [
    "LLMError",
    "LLMResponseError",
    "LLMSchemaError",
    "LLMStreamError",
]