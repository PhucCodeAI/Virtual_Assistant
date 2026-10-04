# Backend/repositories/storage_repository.py
"""Module Repository đọc/ghi Object Storage qua Supabase Storage REST API.

Đặc điểm:
    - Kế thừa SupabaseBaseRepository → dùng chung client + retry.
    - Hỗ trợ upload/download/list/delete JSON và binary.
    - Đường dẫn blob được sanitize (chặn path traversal ở bucket level).
    - Exception sử dụng từ package `exceptions`.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import quote

import httpx
from config import configs
from exceptions import (
    StorageDownloadError,
    StorageUploadError,
    TraceError,
)
from loguru import logger
from repositories._supabase import SupabaseBaseRepository


class StorageRepository(SupabaseBaseRepository):
    """Repository giao tiếp Supabase Storage API.

    Convention đường dẫn blob: `<bucket>/<session_id>/<trace_id>.json`.
    """

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Khởi tạo StorageRepository.

        Args:
            client: HTTP client dùng chung. Nếu None, tự tạo.
        """
        super().__init__(client)
        self.bucket = configs.storage.bucket

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------
    async def upload_json(
        self,
        path: str,
        payload: dict[str, Any],
    ) -> str:
        """Upload payload JSON lên bucket.

        Args:
            path: Đường dẫn tương đối trong bucket (VD: 'sess_1/tr_abc.json').
            payload: Dữ liệu JSON cần upload.

        Returns:
            Đường dẫn tương đối đã chuẩn hóa.

        Raises:
            StorageUploadError: Khi request thất bại.
            TraceError: Khi path không hợp lệ.
        """
        safe_path = _sanitize_blob_path(path)
        endpoint = self._object_url(safe_path)
        headers = self._auth_headers()
        headers["x-upsert"] = "true"
        headers["cache-control"] = "max-age=3600"

        data_bytes = json.dumps(
            payload, ensure_ascii=False, separators=(",", ":")
        ).encode("utf-8")

        try:
            await self._request(
                "POST",
                endpoint,
                headers=headers,
                content=data_bytes,
            )
        except httpx.HTTPStatusError as e:
            raise StorageUploadError(
                f"Upload Storage thất bại: {safe_path}",
                context={
                    "path": safe_path,
                    "size_bytes": len(data_bytes),
                    "status": e.response.status_code,
                    "body": e.response.text[:500],
                },
            ) from e
        except httpx.RequestError as e:
            raise StorageUploadError(
                f"Upload Storage lỗi network: {safe_path}",
                context={"path": safe_path, "error": type(e).__name__},
            ) from e

        logger.debug("Uploaded {} ({} bytes)", safe_path, len(data_bytes))
        return safe_path

    async def download_json(self, path: str) -> dict[str, Any] | None:
        """Tải và parse JSON từ bucket.

        Args:
            path: Đường dẫn blob.

        Returns:
            Dict dữ liệu, hoặc None nếu không tồn tại (404).

        Raises:
            StorageDownloadError: Khi request thất bại (trừ 404).
            TraceError: Khi path không hợp lệ.
        """
        safe_path = _sanitize_blob_path(path)
        endpoint = self._authenticated_object_url(safe_path)

        try:
            response = await self._request(
                "GET",
                endpoint,
                headers=self._auth_headers(content_type=None),
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.debug("Blob không tồn tại: {}", safe_path)
                return None
            raise StorageDownloadError(
                f"Download Storage thất bại: {safe_path}",
                context={"path": safe_path, "status": e.response.status_code},
            ) from e
        except httpx.RequestError as e:
            raise StorageDownloadError(
                f"Download Storage lỗi network: {safe_path}",
                context={"path": safe_path, "error": type(e).__name__},
            ) from e

        try:
            return response.json()
        except json.JSONDecodeError as e:
            raise StorageDownloadError(
                f"Blob không phải JSON hợp lệ: {safe_path}",
                context={"path": safe_path},
            ) from e

    async def delete_file(self, path: str) -> None:
        """Xóa một blob khỏi bucket.

        Args:
            path: Đường dẫn blob cần xóa.

        Raises:
            TraceError: Khi request thất bại.
        """
        await self.delete_files([path])

    async def delete_files(self, paths: list[str]) -> None:
        """Xóa nhiều blob cùng lúc (dùng bulk API).

        Args:
            paths: Danh sách đường dẫn blob.

        Raises:
            TraceError: Khi request thất bại.
        """
        if not paths:
            return

        safe_paths = [_sanitize_blob_path(p) for p in paths]
        endpoint = f"{self.base_url}/storage/v1/object/{self.bucket}"

        try:
            await self._request(
                "DELETE",
                endpoint,
                headers=self._auth_headers(),
                json={"prefixes": safe_paths},
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise TraceError(
                f"Xóa {len(safe_paths)} blob thất bại",
                code="TRACE_STORAGE_DELETE_FAILED",
                context={"paths": safe_paths[:5]},
            ) from e

        logger.debug("Đã xóa {} blob", len(safe_paths))

    async def list_objects(
        self,
        prefix: str = "",
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Liệt kê các object trong bucket (dùng cho cleanup job).

        CẢNH BÁO: Supabase Storage list là O(n) — không dùng cho hot path
        (dashboard). Chỉ dùng cho maintenance.

        Args:
            prefix: Prefix lọc (VD: 'sess_1/').
            limit: Số object tối đa trả về.
            offset: Vị trí bắt đầu (dùng cho pagination).

        Returns:
            Danh sách dict metadata của object (name, id, updated_at, ...).

        Raises:
            TraceError: Khi request thất bại.
        """
        endpoint = f"{self.base_url}/storage/v1/object/list/{self.bucket}"

        try:
            response = await self._request(
                "POST",
                endpoint,
                headers=self._auth_headers(),
                json={
                    "prefix": prefix,
                    "limit": limit,
                    "offset": offset,
                    "sortBy": {"column": "name", "order": "asc"},
                },
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise TraceError(
                "List Storage thất bại",
                code="TRACE_STORAGE_LIST_FAILED",
                context={"prefix": prefix, "limit": limit},
            ) from e

        data = response.json()
        return data if isinstance(data, list) else []

    # --------------------------------------------------------
    # URL builders
    # --------------------------------------------------------
    def _object_url(self, blob_path: str) -> str:
        """URL cho upload/delete object (không cần auth đọc).

        Args:
            blob_path: Đường dẫn blob đã sanitize.

        Returns:
            URL đầy đủ.
        """
        return (
            f"{self.base_url}/storage/v1/object/{self.bucket}/"
            f"{quote(blob_path, safe='/')}"
        )

    def _authenticated_object_url(self, blob_path: str) -> str:
        """URL cho download object (cần auth đọc private bucket).

        Args:
            blob_path: Đường dẫn blob đã sanitize.

        Returns:
            URL đầy đủ.
        """
        return (
            f"{self.base_url}/storage/v1/object/authenticated/{self.bucket}/"
            f"{quote(blob_path, safe='/')}"
        )


# ============================================================
# Module-level helpers
# ============================================================
def _sanitize_blob_path(path: str) -> str:
    """Chuẩn hóa và kiểm tra đường dẫn blob an toàn.

    Args:
        path: Đường dẫn thô.

    Returns:
        Đường dẫn đã chuẩn hóa (không có leading slash, không có '..').

    Raises:
        TraceError: Khi path chứa '..', tuyệt đối, hoặc rỗng.
    """
    cleaned = path.replace("\\", "/").strip().lstrip("/")
    if not cleaned:
        raise TraceError("Đường dẫn blob rỗng", code="TRACE_BLOB_PATH_INVALID")

    parts = cleaned.split("/")
    if any(p in ("", ".", "..") for p in parts):
        raise TraceError(
            f"Đường dẫn blob không hợp lệ: {path!r}",
            code="TRACE_BLOB_PATH_INVALID",
            context={"path": path},
        )

    return cleaned


__all__ = ["StorageRepository"]


if __name__ == "__main__":
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()

    async def _test() -> None:
        repo = StorageRepository()
        try:
            test_path = "test_suite/sample.json"
            payload = {"msg": "xin chào", "value": 42, "unicode": "→ ★"}

            print("=== 1. Upload ===")
            returned = await repo.upload_json(test_path, payload)
            print(f"uploaded: {returned}")
            assert returned == test_path

            print("\n=== 2. Download ===")
            downloaded = await repo.download_json(test_path)
            print(f"downloaded: {downloaded}")
            assert downloaded == payload

            print("\n=== 3. Download blob không tồn tại → None ===")
            missing = await repo.download_json("test_suite/not_exist_xyz.json")
            print(f"missing: {missing}")
            assert missing is None

            print("\n=== 4. List objects ===")
            objects = await repo.list_objects(prefix="test_suite/", limit=10)
            print(f"found {len(objects)} object(s)")
            for o in objects:
                print(f"  - {o.get('name')}")

            print("\n=== 5. Path traversal bị chặn ===")
            try:
                await repo.upload_json("../etc/passwd", {"x": 1})
            except TraceError as e:
                print(f"PASS: {e.code}")

            print("\n=== 6. Delete ===")
            await repo.delete_file(test_path)
            missing = await repo.download_json(test_path)
            assert missing is None
            print("PASS: blob đã xóa")

            print("\n=== 7. Cleanup test artifacts ===")
            await repo.delete_files(["test_suite/sample.json"])
            print("PASS")

            print("\nTẤT CẢ TEST PASS")

        finally:
            await repo.aclose()

    asyncio.run(_test())