"""Module Repository đảm nhận đọc/ghi Object Storage thô qua Supabase Storage API."""

import json
import os
from typing import Any

import httpx


class StorageRepository:
    """Lớp truy xuất Supabase Storage REST API bằng HTTP thuần."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Khởi tạo cấu hình kết nối Supabase Storage API.

        Args:
            client: HTTP client bất đồng bộ dùng chung pipeline.
        """
        self.base_url = os.environ["SUPABASE_URL"].rstrip("/")
        self.api_key = os.environ["SUPABASE_KEY"]
        self.bucket = os.getenv("SUPABASE_STORAGE_BUCKET", "trace-logs")
        self.client = client or httpx.AsyncClient(timeout=30.0)

    def _headers(self, content_type: str = "application/json") -> dict[str, str]:
        """Header xác thực chuẩn cho Supabase Storage.

        Args:
            content_type: Kiểu nội dung của file tải lên.

        Returns:
            Dictionary chứa các HTTP header cần thiết.
        """
        return {
            "apikey": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": content_type,
        }

    async def upload_json(self, path: str, payload: dict[str, Any]) -> str:
        """Upload payload định dạng JSON lên Storage bucket.

        Args:
            path: Đường dẫn lưu file trên bucket (ví dụ: 'session_123/trace_abc.json').
            payload: Toàn bộ dữ liệu chi tiết cần lưu trữ.

        Returns:
            Đường dẫn tương đối của file vừa upload.

        Raises:
            httpx.HTTPStatusError: Khi request tới Storage thất bại.
        """
        endpoint = f"{self.base_url}/storage/v1/object/{self.bucket}/{path.lstrip('/')}"
        headers = self._headers()
        headers["x-upsert"] = "true"

        data_bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        response = await self.client.post(endpoint, headers=headers, content=data_bytes)
        response.raise_for_status()
        return path

    async def download_json(self, path: str) -> dict[str, Any] | None:
        """Tải và parse file JSON từ Storage bucket.

        Args:
            path: Đường dẫn file cần tải.

        Returns:
            Dictionary dữ liệu tải về, hoặc None nếu không tìm thấy file.

        Raises:
            httpx.HTTPStatusError: Khi gặp lỗi server khác 404.
        """
        endpoint = f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/{path.lstrip('/')}"
        response = await self.client.get(endpoint, headers=self._headers())

        if response.status_code == 404:
            return None

        response.raise_for_status()
        return response.json()

    async def delete_file(self, path: str) -> None:
        """Xóa file khỏi Storage (dùng cho cơ chế rollback khi insert DB lỗi).

        Args:
            path: Đường dẫn file cần xóa.

        Raises:
            httpx.HTTPStatusError: Khi yêu cầu xóa gặp lỗi.
        """
        endpoint = f"{self.base_url}/storage/v1/object/{self.bucket}"
        response = await self.client.request(
            method="DELETE",
            url=endpoint,
            headers=self._headers(),
            json={"prefixes": [path.lstrip("/")]},
        )
        response.raise_for_status()
