# Backend/exceptions/base.py
"""Module định nghĩa lớp Exception gốc cho toàn hệ thống.

Mọi exception tùy chỉnh trong dự án PHẢI kế thừa từ AppError để:
    - Đảm bảo có thuộc tính `code` (map thẳng sang ErrorEventPayload.code).
    - Cho phép catch tổng quát ở tầng Presentation khi cần fallback.
    - Tách biệt lỗi nghiệp vụ với lỗi hệ thống (RuntimeError, ValueError).
"""

from __future__ import annotations


class AppError(Exception):
    """Exception gốc cho mọi lỗi nghiệp vụ trong hệ thống.

    Attributes:
        code: Mã định danh lỗi, dùng để map sang SSE error event.
        message: Mô tả chi tiết lỗi cho người dùng.
        context: Dict metadata bổ sung (VD: file path, attempt number).
    """

    code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        context: dict[str, object] | None = None,
    ) -> None:
        """Khởi tạo AppError.

        Args:
            message: Thông báo lỗi.
            code: Override mã lỗi mặc định của class.
            context: Metadata bổ sung.
        """
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.context: dict[str, object] = context or {}

    def to_dict(self) -> dict[str, object]:
        """Chuyển lỗi thành dict để serialize vào SSE event.

        Returns:
            Dict gồm code, message và context (nếu có).
        """
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.context:
            payload["context"] = self.context
        return payload

    def __repr__(self) -> str:
        """Biểu diễn string để debug."""
        return f"{type(self).__name__}(code={self.code!r}, message={self.message!r})"


__all__ = ["AppError"]