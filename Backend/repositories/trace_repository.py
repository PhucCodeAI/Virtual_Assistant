"""Module Repository đảm nhận CRUD metadata trace với Supabase qua PostgREST API."""

import os
from typing import Any

import httpx


class TraceRepository:
    """Lớp truy xuất bảng traces trong Supabase bằng giao thức HTTP tiêu chuẩn."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Khởi tạo cấu hình kết nối Supabase PostgREST API.

        Args:
            client: HTTP client bất đồng bộ dùng chung pipeline.
        """
        self.base_url = os.environ["SUPABASE_URL"].rstrip("/")
        self.api_key = os.environ["SUPABASE_KEY"]
        self.endpoint = f"{self.base_url}/rest/v1/traces"
        self.client = client or httpx.AsyncClient(timeout=10.0)

    def _headers(self) -> dict[str, str]:
        """Header xác thực chuẩn cho Supabase PostgREST."""
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }

    async def create(self, metadata: dict[str, Any]) -> None:
        """Thêm mới một bản ghi metadata trace vào PostgREST.

        Args:
            metadata: Bản ghi thông tin trace (phải bao gồm storage_path).

        Raises:
            httpx.HTTPStatusError: Khi request insert database thất bại.
        """
        response = await self.client.post(
            self.endpoint,
            headers=self._headers(),
            json=metadata,
        )
        response.raise_for_status()

    async def list_summary(self, limit: int, offset: int) -> list[dict[str, Any]]:
        """Lấy danh sách tóm tắt trace cho table view hoặc metrics.

        Args:
            limit: Số lượng bản ghi tối đa.
            offset: Điểm bắt đầu phân trang.

        Returns:
            Danh sách metadata của các trace.
        """
        headers = self._headers()
        params = {
            "select": "trace_id,session_id,prompt,status,duration_ms,total_tokens,cost,storage_path,created_at",
            "order": "created_at.desc",
            "limit": str(limit),
            "offset": str(offset),
        }
        response = await self.client.get(self.endpoint, headers=headers, params=params)
        response.raise_for_status()
        return response.json()

    async def get_by_id(self, trace_id: str) -> dict[str, Any] | None:
        """Lấy bản ghi metadata theo ID để lấy storage_path.

        Args:
            trace_id: Mã định danh duy nhất của trace.

        Returns:
            Bản ghi metadata hoặc None nếu không tồn tại.
        """
        headers = self._headers()
        params = {
            "trace_id": f"eq.{trace_id}",
            "select": "*",
        }
        response = await self.client.get(self.endpoint, headers=headers, params=params)
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None

    async def delete(self, trace_id: str) -> None:
        """Xóa metadata trace khỏi database.

        Args:
            trace_id: Mã định danh của trace cần xóa.
        """
        headers = self._headers()
        params = {"trace_id": f"eq.{trace_id}"}
        response = await self.client.delete(
            self.endpoint, headers=headers, params=params
        )
        response.raise_for_status()
