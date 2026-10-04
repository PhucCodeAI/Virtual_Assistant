# Backend/repositories/_supabase.py
"""Base class cho các repository giao tiếp Supabase (Data Access Layer).

Đặc điểm:
    - Quản lý vòng đời `httpx.AsyncClient` tập trung, tránh leak.
    - Retry lũy thừa cho status 429/5xx + network error.
    - Header auth dùng chung (apikey + Authorization).
    - Exception sử dụng từ package `exceptions`.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypeVar

import httpx
from config import configs
from exceptions import TraceError
from loguru import logger

T = TypeVar("T")

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class SupabaseBaseRepository:
    """Base class quản lý HTTP client và retry cho Supabase API.

    Không được khởi tạo trực tiếp — kế thừa và dùng `_request()`.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Khởi tạo base repository.

        Args:
            client: HTTP client dùng chung. Nếu None, tự tạo mới.

        Raises:
            RuntimeError: Khi thiếu SUPABASE_URL hoặc SUPABASE_KEY trong env.
        """
        secrets = configs.secrets
        self.base_url = secrets.supabase_url.rstrip("/")
        self.api_key = secrets.supabase_key

        if not self.base_url.startswith(("https://", "http://")):
            raise RuntimeError(
                f"SUPABASE_URL không hợp lệ: {self.base_url[:30]}..."
            )

        self._client_owned = client is None
        self.client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=60.0,
                write=60.0,
                pool=10.0,
            ),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
            ),
        )

    async def aclose(self) -> None:
        """Đóng client nếu base class tự sở hữu (không phải injected)."""
        if self._client_owned:
            await self.client.aclose()

    async def __aenter__(self) -> SupabaseBaseRepository:
        """Hỗ trợ async context manager."""
        return self

    async def __aexit__(self, *_args: Any) -> None:
        """Đóng client khi thoát context."""
        await self.aclose()

    # --------------------------------------------------------
    # Headers
    # --------------------------------------------------------
    def _auth_headers(
        self,
        content_type: str | None = "application/json",
    ) -> dict[str, str]:
        """Header xác thực Supabase chuẩn.

        Args:
            content_type: Content-Type header. None = bỏ qua (dùng cho GET).

        Returns:
            Dict headers đầy đủ.
        """
        headers: dict[str, str] = {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
        }
        if content_type is not None:
            headers["Content-Type"] = content_type
        return headers

    # --------------------------------------------------------
    # Request with retry
    # --------------------------------------------------------
    async def _request(
        self,
        method: str,
        url: str,
        *,
        max_attempts: int | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        """Thực thi HTTP request với retry lũy thừa.

        Args:
            method: HTTP method (GET, POST, DELETE, ...).
            url: URL tuyệt đối.
            max_attempts: Số lần thử tối đa. Mặc định 3.
            **kwargs: Tham số truyền cho httpx (headers, json, content, ...).

        Returns:
            httpx.Response đã raise_for_status.

        Raises:
            httpx.HTTPStatusError: Lỗi HTTP không thể phục hồi.
            httpx.RequestError: Lỗi network sau khi hết lượt retry.
        """
        attempts = max_attempts if max_attempts is not None else 3
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                response = await self.client.request(method, url, **kwargs)
                if response.status_code in _RETRYABLE_STATUS and attempt < attempts:
                    wait = self._retry_after(response) or float(2 ** (attempt - 1))
                    logger.warning(
                        "Supabase HTTP {} (attempt {}/{}), retry sau {:.1f}s",
                        response.status_code,
                        attempt,
                        attempts,
                        wait,
                    )
                    await asyncio.sleep(wait)
                    continue

                response.raise_for_status()
                return response

            except httpx.RequestError as e:
                last_exc = e
                if attempt < attempts:
                    wait = float(2 ** (attempt - 1))
                    logger.warning(
                        "Supabase network error (attempt {}/{}): {} — retry sau {:.1f}s",
                        attempt,
                        attempts,
                        type(e).__name__,
                        wait,
                    )
                    await asyncio.sleep(wait)

        if last_exc is not None:
            raise last_exc
        raise TraceError("Supabase request thất bại không xác định")

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        """Đọc header Retry-After nếu có.

        Args:
            response: Phản hồi HTTP.

        Returns:
            Số giây cần chờ, hoặc None.
        """
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None


__all__ = ["SupabaseBaseRepository"]