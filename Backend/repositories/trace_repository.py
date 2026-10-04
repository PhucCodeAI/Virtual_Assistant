# Backend/repositories/trace_repository.py
"""Module Repository đọc/ghi metadata Trace qua Supabase PostgREST (Data Access Layer).

Đặc điểm:
    - Kế thừa SupabaseBaseRepository → dùng chung client + retry + headers.
    - Giao tiếp PostgREST: insert, get_by_id, list_summary, list_by_session, delete.
    - Hỗ trợ filter + phân trang + sort theo chuẩn PostgREST.
    - Exception sử dụng từ package `exceptions`.

Schema Postgres tối thiểu (chạy migration trước khi dùng):
    traces(trace_id PK, session_id, prompt, status, duration_ms,
           total_tokens, input_tokens, output_tokens, reasoning_tokens,
           cache_tokens, cost, storage_path, error_message,
           created_at, finished_at)
"""

from __future__ import annotations

from typing import Any

import httpx
from config import configs
from exceptions import (
    MetadataWriteError,
    TraceError,
    TraceNotFoundError,
)
from loguru import logger
from repositories._supabase import SupabaseBaseRepository


class TraceRepository(SupabaseBaseRepository):
    """Repository giao tiếp Supabase PostgREST cho bảng `traces`."""

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        """Khởi tạo TraceRepository.

        Args:
            client: HTTP client dùng chung. Nếu None, tự tạo.
        """
        super().__init__(client)
        self.table = configs.database.table_name
        self.rest_url = f"{self.base_url}/rest/v1/{self.table}"

    # --------------------------------------------------------
    # Write
    # --------------------------------------------------------
    async def create(self, record: dict[str, Any]) -> dict[str, Any]:
        """Insert một trace record mới vào Postgres.

        Args:
            record: Dict các field khớp schema bảng `traces`.

        Returns:
            Record đã insert (đọc lại từ server qua Prefer=representation).

        Raises:
            MetadataWriteError: Khi insert thất bại.
            TraceError: Khi record rỗng.
        """
        if not record:
            raise TraceError("Record rỗng", code="TRACE_RECORD_EMPTY")

        headers = self._auth_headers()
        headers["Prefer"] = "return=representation"

        try:
            response = await self._request(
                "POST",
                self.rest_url,
                headers=headers,
                json=record,
            )
        except httpx.HTTPStatusError as e:
            logger.error("PostgREST insert body: {}", e.response.text[:500])
            raise MetadataWriteError(
                f"Insert trace thất bại (HTTP {e.response.status_code})",
                context={
                    "trace_id": record.get("trace_id"),
                    "status": e.response.status_code,
                    "body": e.response.text[:500],
                },
            ) from e
        except httpx.RequestError as e:
            raise MetadataWriteError(
                "Insert trace lỗi network",
                context={
                    "trace_id": record.get("trace_id"),
                    "error": type(e).__name__,
                },
            ) from e

        data = response.json()
        if isinstance(data, list) and data:
            return data[0]
        return record

    # --------------------------------------------------------
    # Read
    # --------------------------------------------------------
    async def get_by_id(self, trace_id: str) -> dict[str, Any] | None:
        """Lấy một trace theo trace_id.

        Args:
            trace_id: Mã định danh trace.

        Returns:
            Dict record hoặc None nếu không tìm thấy.

        Raises:
            TraceError: Khi request thất bại (khác 200/404).
        """
        endpoint = f"{self.rest_url}?trace_id=eq.{_escape(trace_id)}&limit=1"
        records = await self._fetch(endpoint)
        return records[0] if records else None

    async def get_by_id_or_raise(self, trace_id: str) -> dict[str, Any]:
        """Lấy một trace hoặc raise nếu không tồn tại.

        Args:
            trace_id: Mã định danh trace.

        Returns:
            Dict record.

        Raises:
            TraceNotFoundError: Khi không tìm thấy.
        """
        record = await self.get_by_id(trace_id)
        if record is None:
            raise TraceNotFoundError(
                f"Không tìm thấy trace: {trace_id}",
                context={"trace_id": trace_id},
            )
        return record

    async def list_summary(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Lấy danh sách trace gần nhất, sắp xếp theo created_at giảm dần.

        Chỉ select các field cần thiết cho dashboard (không kéo blob).

        Args:
            limit: Số bản ghi tối đa.
            offset: Vị trí bắt đầu (pagination).

        Returns:
            Danh sách record đã sort.

        Raises:
            TraceError: Khi request thất bại.
        """
        fields = (
            "trace_id,session_id,prompt,status,duration_ms,"
            "total_tokens,input_tokens,output_tokens,reasoning_tokens,"
            "cache_tokens,cost,error_message,created_at,finished_at"
        )
        endpoint = (
            f"{self.rest_url}"
            f"?select={fields}"
            f"&order=created_at.desc"
            f"&limit={limit}"
            f"&offset={offset}"
        )
        return await self._fetch(endpoint)

    async def list_by_session(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Lấy danh sách trace thuộc một session.

        Args:
            session_id: Mã phiên làm việc.
            limit: Số bản ghi tối đa.
            offset: Vị trí bắt đầu.

        Returns:
            Danh sách record đã sort.

        Raises:
            TraceError: Khi request thất bại.
        """
        endpoint = (
            f"{self.rest_url}"
            f"?session_id=eq.{_escape(session_id)}"
            f"&order=created_at.desc"
            f"&limit={limit}"
            f"&offset={offset}"
        )
        return await self._fetch(endpoint)

    async def search(
        self,
        status: str | None = None,
        session_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """Tìm kiếm trace theo filter.

        Args:
            status: Lọc theo trạng thái (SUCCESS/FAILED/RUNNING).
            session_id: Lọc theo session.
            limit: Số bản ghi tối đa.
            offset: Vị trí bắt đầu.

        Returns:
            Danh sách record khớp filter.

        Raises:
            TraceError: Khi request thất bại.
        """
        filters: list[str] = []
        if status:
            filters.append(f"status=eq.{_escape(status)}")
        if session_id:
            filters.append(f"session_id=eq.{_escape(session_id)}")

        query = "&".join(filters) if filters else ""
        endpoint = (
            f"{self.rest_url}"
            f"?{query + '&' if query else ''}"
            f"order=created_at.desc"
            f"&limit={limit}"
            f"&offset={offset}"
        )
        return await self._fetch(endpoint)

    async def count(
        self,
        status: str | None = None,
        session_id: str | None = None,
    ) -> int:
        """Đếm số trace khớp filter (dùng cho dashboard pagination).

        Args:
            status: Lọc theo trạng thái.
            session_id: Lọc theo session.

        Returns:
            Tổng số bản ghi.

        Raises:
            TraceError: Khi request thất bại.
        """
        filters: list[str] = []
        if status:
            filters.append(f"status=eq.{_escape(status)}")
        if session_id:
            filters.append(f"session_id=eq.{_escape(session_id)}")

        query = "&".join(filters) if filters else ""
        endpoint = f"{self.rest_url}?select=trace_id&{query}"

        headers = self._auth_headers(content_type=None)
        headers["Prefer"] = "count=exact"
        headers["Range-Unit"] = "items"
        headers["Range"] = "0-0"

        try:
            response = await self._request(
                "GET",
                endpoint,
                headers=headers,
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise TraceError(
                "Đếm trace thất bại",
                code="TRACE_COUNT_FAILED",
                context={"status": status, "session_id": session_id},
            ) from e

        content_range = response.headers.get("content-range", "")
        # Format: "0-0/1234"
        if "/" in content_range:
            try:
                return int(content_range.rsplit("/", 1)[1])
            except ValueError:
                pass
        return 0

    # --------------------------------------------------------
    # Delete
    # --------------------------------------------------------
    async def delete(self, trace_id: str) -> bool:
        """Xóa một trace theo trace_id.

        Args:
            trace_id: Mã định danh trace.

        Returns:
            True nếu có ít nhất 1 row bị xóa, False nếu không tìm thấy.

        Raises:
            TraceError: Khi request thất bại.
        """
        endpoint = f"{self.rest_url}?trace_id=eq.{_escape(trace_id)}"
        headers = self._auth_headers()
        headers["Prefer"] = "return=representation"

        try:
            response = await self._request(
                "DELETE",
                endpoint,
                headers=headers,
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise TraceError(
                f"Xóa trace thất bại: {trace_id}",
                code="TRACE_DELETE_FAILED",
                context={"trace_id": trace_id},
            ) from e

        data = response.json()
        deleted = isinstance(data, list) and len(data) > 0
        if deleted:
            logger.info("Đã xóa trace metadata: {}", trace_id)
        return deleted

    # --------------------------------------------------------
    # Internal
    # --------------------------------------------------------
    async def _fetch(self, endpoint: str) -> list[dict[str, Any]]:
        """Helper GET PostgREST trả về list record.

        Args:
            endpoint: URL đầy đủ (đã có query string).

        Returns:
            Danh sách dict record.

        Raises:
            TraceError: Khi request thất bại hoặc response không phải list.
        """
        try:
            response = await self._request(
                "GET",
                endpoint,
                headers=self._auth_headers(content_type=None),
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            raise TraceError(
                "Query trace thất bại",
                code="TRACE_QUERY_FAILED",
                context={"endpoint": endpoint[:200]},
            ) from e

        data = response.json()
        if not isinstance(data, list):
            raise TraceError(
                "Response PostgREST không phải list",
                code="TRACE_RESPONSE_INVALID",
                context={"type": type(data).__name__},
            )
        return data


# ============================================================
# Module-level helpers
# ============================================================
def _escape(value: str) -> str:
    """Escape giá trị filter cho PostgREST query string.

    PostgREST dùng cú pháp `field=eq.value`. Các ký tự đặc biệt như `,`,
    `(`, `)`, `.` có thể phá vỡ cú pháp. Hàm này URL-encode để an toàn.

    Args:
        value: Giá trị thô cần escape.

    Returns:
        Chuỗi đã URL-encode an toàn cho PostgREST filter.
    """
    from urllib.parse import quote

    return quote(str(value), safe="")


__all__ = ["TraceRepository"]


if __name__ == "__main__":
    import asyncio
    from datetime import UTC, datetime

    from dotenv import load_dotenv

    load_dotenv()

    async def _test() -> None:
        repo = TraceRepository()
        test_id = f"tr_test_{int(datetime.now(UTC).timestamp())}"

        try:
            print("=== 1. Insert ===")
            record = {
                "trace_id": test_id,
                "session_id": "sess_test",
                "prompt": "Viết hàm tính tổng",
                "status": "SUCCESS",
                "duration_ms": 1234,
                "total_tokens": 100,
                "input_tokens": 60,
                "output_tokens": 40,
                "reasoning_tokens": 0,
                "cache_tokens": 0,
                "cost": 0.0012,
                "storage_path": f"sess_test/{test_id}.json",
                "error_message": None,
                "created_at": datetime.now(UTC).isoformat(),
            }
            inserted = await repo.create(record)
            print(f"inserted trace_id={inserted.get('trace_id')}")

            print("\n=== 2. Get by id ===")
            fetched = await repo.get_by_id(test_id)
            assert fetched is not None
            print(f"fetched status={fetched['status']} tokens={fetched['total_tokens']}")

            print("\n=== 3. List summary ===")
            rows = await repo.list_summary(limit=5)
            print(f"found {len(rows)} record(s)")
            for r in rows[:3]:
                print(f"  - {r['trace_id']} | {r['status']} | {r['created_at']}")

            print("\n=== 4. Count ===")
            n = await repo.count()
            print(f"total traces: {n}")

            print("\n=== 5. Search by session ===")
            rows = await repo.list_by_session("sess_test", limit=10)
            print(f"session sess_test có {len(rows)} record(s)")

            print("\n=== 6. Delete ===")
            deleted = await repo.delete(test_id)
            print(f"deleted={deleted}")
            assert deleted is True

            after = await repo.get_by_id(test_id)
            assert after is None
            print("PASS: record đã xóa")

            print("\nTẤT CẢ TEST PASS")

        finally:
            await repo.delete(test_id)
            await repo.aclose()

    asyncio.run(_test())