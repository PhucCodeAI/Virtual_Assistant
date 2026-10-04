# Backend/services/trace_service.py
"""Module dịch vụ quản lý nghiệp vụ Trace và điều phối lưu trữ đa tầng.

Kiến trúc 2 tầng:
    - Metadata (Postgres qua TraceRepository): query/filter/sort dashboard.
    - Blob (Supabase Storage qua StorageRepository): full spans + payloads.

Nguyên tắc:
    - Span payload lớn được truncate trước khi lưu để không phình blob.
    - Compensating transaction: nếu ghi DB fail sau khi upload Storage,
      tự động xóa blob để tránh rác.
    - Exception sử dụng từ package `exceptions`.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from dtos.trace import SpanDTO, SpanStatus, SpanType, TraceDetailDTO, TraceSummaryDTO
from exceptions import (
    MetadataWriteError,
    StorageUploadError,
    TraceError,
)
from loguru import logger
from repositories.storage_repository import StorageRepository
from repositories.trace_repository import TraceRepository

_MAX_SPAN_FIELD_BYTES = 32 * 1024

_TRUNCATED_MARKER = "\n...[truncated]...\n"


class ActiveTraceCollector:
    """Bộ thu thập spans in-memory trong suốt vòng đời một phiên làm việc.

    Instance được tạo bởi TraceService.create_collector() và truyền vào
    Orchestrator để thêm span sau mỗi bước.
    """

    def __init__(self, session_id: str, prompt: str) -> None:
        """Khởi tạo collector.

        Args:
            session_id: Mã định danh phiên làm việc.
            prompt: Câu lệnh yêu cầu ban đầu từ người dùng.
        """
        self.trace_id = f"tr_{uuid.uuid4().hex[:12]}"
        self.session_id = session_id
        self.prompt = prompt
        self.started_at = datetime.now(UTC)
        self.spans: list[SpanDTO] = []

    def add_span(
        self,
        name: str,
        span_type: SpanType,
        duration_ms: int,
        input_data: Any = None,
        output_data: Any = None,
        metadata: dict[str, Any] | None = None,
        status: SpanStatus = "OK",
    ) -> SpanDTO:
        """Ghi nhận một span vào bộ đệm.

        Field input/output lớn sẽ được truncate để không phình blob Storage.
        start_offset_ms được tính tự động = (now - started_at) - duration_ms.

        Args:
            name: Tên tác vụ.
            span_type: Loại span ('llm', 'tool', 'sandbox', 'git', 'internal').
            duration_ms: Thời gian thực thi (ms).
            input_data: Dữ liệu đầu vào.
            output_data: Dữ liệu đầu ra.
            metadata: Siêu dữ liệu bổ sung.
            status: 'OK' hoặc 'ERROR'.

        Returns:
            SpanDTO vừa tạo.
        """
        start_offset_ms = self._compute_start_offset(duration_ms)

        span = SpanDTO(
            span_id=f"sp_{uuid.uuid4().hex[:8]}",
            name=name,
            span_type=span_type,
            duration_ms=duration_ms,
            start_offset_ms=start_offset_ms,
            status=status,
            input_data=_truncate_value(input_data),
            output_data=_truncate_value(output_data),
            metadata=metadata or {},
        )
        self.spans.append(span)
        return span

    def _compute_start_offset(self, duration_ms: int) -> int:
        """Tính offset từ lúc trace bắt đầu tới lúc span bắt đầu.

        Args:
            duration_ms: Thời gian thực thi của span.

        Returns:
            Milliseconds, không âm.
        """
        now_ms = int((datetime.now(UTC) - self.started_at).total_seconds() * 1000)
        return max(0, now_ms - duration_ms)


class TraceService:
    """Dịch vụ xử lý nghiệp vụ thu thập, phân tích và điều phối lưu trữ Trace."""

    def __init__(
        self,
        trace_repo: TraceRepository,
        storage_repo: StorageRepository,
    ) -> None:
        """Khởi tạo service.

        Args:
            trace_repo: Repository metadata Postgres.
            storage_repo: Repository blob Supabase Storage.
        """
        self.trace_repo = trace_repo
        self.storage_repo = storage_repo

    # --------------------------------------------------------
    # Collector lifecycle
    # --------------------------------------------------------
    def create_collector(self, session_id: str, prompt: str) -> ActiveTraceCollector:
        """Tạo collector mới cho phiên làm việc.

        Args:
            session_id: Mã phiên.
            prompt: Prompt đầu vào.

        Returns:
            Instance ActiveTraceCollector.
        """
        return ActiveTraceCollector(session_id, prompt)

    async def save_session_trace(
        self,
        collector: ActiveTraceCollector,
        status: str,
        duration_ms: int,
        metrics: dict[str, Any],
        error_message: str | None = None,
    ) -> str:
        """Đóng gói phiên chạy, upload blob và lưu metadata.

        Cơ chế Compensating Transaction: nếu ghi DB thất bại sau khi đã
        upload Storage, tự động xóa blob để tránh file rác.

        Args:
            collector: Collector chứa spans.
            status: 'SUCCESS' hoặc 'FAILED'.
            duration_ms: Tổng thời gian thực thi (ms).
            metrics: Dict token/cost đã normalize.
            error_message: Nội dung lỗi nếu có.

        Returns:
            trace_id vừa lưu.

        Raises:
            MetadataWriteError: Khi insert DB thất bại (đã rollback Storage).
            StorageUploadError: Khi upload blob thất bại.
        """
        finished_at = datetime.now(UTC)
        storage_path = f"{collector.session_id}/{collector.trace_id}.json"

        full_payload = {
            "trace_id": collector.trace_id,
            "session_id": collector.session_id,
            "prompt": collector.prompt,
            "status": status,
            "duration_ms": duration_ms,
            "metrics": metrics,
            "spans": [s.model_dump() for s in collector.spans],
            "error_message": error_message,
            "started_at": collector.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
        }

        try:
            await self.storage_repo.upload_json(storage_path, full_payload)
        except StorageUploadError:
            logger.exception("Upload blob thất bại cho trace {}", collector.trace_id)
            raise

        record = {
            "trace_id": collector.trace_id,
            "session_id": collector.session_id,
            "prompt": collector.prompt,
            "status": status,
            "duration_ms": duration_ms,
            "total_tokens": int(metrics.get("total_tokens") or 0),
            "input_tokens": int(metrics.get("input_tokens") or 0),
            "output_tokens": int(metrics.get("output_tokens") or 0),
            "reasoning_tokens": int(metrics.get("reasoning_tokens") or 0),
            "cache_tokens": int(metrics.get("cache_tokens") or 0),
            "cost": float(metrics.get("cost") or 0.0),
            "storage_path": storage_path,
            "error_message": error_message,
            "finished_at": finished_at.isoformat(),
        }

        try:
            await self.trace_repo.create(record)
        except MetadataWriteError:
            logger.error(
                "Ghi metadata thất bại, kích hoạt rollback blob: {}",
                storage_path,
            )
            try:
                await self.storage_repo.delete_file(storage_path)
            except TraceError as rollback_exc:
                logger.critical(
                    "Rollback thất bại — orphan blob tại {}: {}",
                    storage_path,
                    rollback_exc,
                )
            raise

        logger.info(
            "Đã lưu trace {} | status={} | duration={}ms | tokens={}",
            collector.trace_id,
            status,
            duration_ms,
            record["total_tokens"],
        )
        return collector.trace_id

    # --------------------------------------------------------
    # Query
    # --------------------------------------------------------
    async def get_recent_traces(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[TraceSummaryDTO]:
        """Lấy danh sách tóm tắt cho dashboard.

        Args:
            limit: Số bản ghi tối đa.
            offset: Vị trí bắt đầu (pagination).

        Returns:
            Danh sách TraceSummaryDTO.
        """
        records = await self.trace_repo.list_summary(limit=limit, offset=offset)
        return [_to_summary(r) for r in records]

    async def list_traces_by_session(
        self,
        session_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TraceSummaryDTO]:
        """Lấy danh sách trace thuộc một session.

        Args:
            session_id: Mã phiên làm việc.
            limit: Số bản ghi tối đa.
            offset: Vị trí bắt đầu.

        Returns:
            Danh sách TraceSummaryDTO.
        """
        records = await self.trace_repo.list_by_session(
            session_id, limit=limit, offset=offset
        )
        return [_to_summary(r) for r in records]

    async def search_traces(
        self,
        status: str | None = None,
        session_id: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[TraceSummaryDTO]:
        """Tìm kiếm trace theo filter.

        Args:
            status: Lọc theo trạng thái (SUCCESS/FAILED/RUNNING).
            session_id: Lọc theo session.
            limit: Số bản ghi tối đa.
            offset: Vị trí bắt đầu.

        Returns:
            Danh sách TraceSummaryDTO khớp filter.
        """
        records = await self.trace_repo.search(
            status=status,
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
        return [_to_summary(r) for r in records]

    async def count_traces(
        self,
        status: str | None = None,
        session_id: str | None = None,
    ) -> int:
        """Đếm tổng số trace khớp filter.

        Args:
            status: Lọc theo trạng thái.
            session_id: Lọc theo session.

        Returns:
            Tổng số bản ghi.
        """
        return await self.trace_repo.count(status=status, session_id=session_id)

    async def get_trace_waterfall(self, trace_id: str) -> TraceDetailDTO | None:
        """Lấy chi tiết trace + toàn bộ spans từ Storage.

        Chiến lược hybrid:
            - Metadata query từ Postgres (nhanh, indexed).
            - Spans lazy-load từ Storage (chỉ khi user click xem chi tiết).
            - Nếu Storage fail, vẫn trả về metadata kèm spans rỗng.

        Args:
            trace_id: Mã định danh trace.

        Returns:
            TraceDetailDTO nếu tồn tại, None nếu không.
        """
        raw = await self.trace_repo.get_by_id(trace_id)
        if not raw:
            return None

        spans: list[SpanDTO] = []
        storage_path = raw.get("storage_path")

        if storage_path:
            try:
                payload = await self.storage_repo.download_json(storage_path)
                if payload and isinstance(payload.get("spans"), list):
                    spans = [SpanDTO(**s) for s in payload["spans"]]
            except TraceError as e:
                logger.warning(
                    "Không tải được blob spans cho trace {}: {}",
                    trace_id,
                    e.message,
                )

        return TraceDetailDTO(
            trace_id=raw["trace_id"],
            session_id=raw["session_id"],
            prompt=raw["prompt"],
            status=raw["status"],
            duration_ms=int(raw.get("duration_ms") or 0),
            total_tokens=int(raw.get("total_tokens") or 0),
            input_tokens=int(raw.get("input_tokens") or 0),
            output_tokens=int(raw.get("output_tokens") or 0),
            reasoning_tokens=int(raw.get("reasoning_tokens") or 0),
            cache_tokens=int(raw.get("cache_tokens") or 0),
            cost=float(raw.get("cost") or 0.0),
            error_message=raw.get("error_message"),
            created_at=str(raw.get("created_at") or ""),
            finished_at=raw.get("finished_at"),
            spans=spans,
        )

    # --------------------------------------------------------
    # Delete
    # --------------------------------------------------------
    async def delete_trace(self, trace_id: str) -> bool:
        """Xóa trace cả 2 tầng: DB metadata + Storage blob.

        Thứ tự: xóa DB trước → xóa Storage sau. Nếu Storage fail, log warning
        (blob orphan có thể dọn bằng cleanup job sau), không raise.

        Args:
            trace_id: Mã định danh trace.

        Returns:
            True nếu đã xóa được metadata khỏi DB.
        """
        raw = await self.trace_repo.get_by_id(trace_id)
        if not raw:
            return False

        storage_path = raw.get("storage_path")
        deleted = await self.trace_repo.delete(trace_id)

        if deleted and storage_path:
            try:
                await self.storage_repo.delete_file(storage_path)
            except TraceError as e:
                logger.warning(
                    "Xóa blob thất bại (orphan): {} — {}",
                    storage_path,
                    e.message,
                )

        return deleted


# ============================================================
# Module-level helpers
# ============================================================
def _to_summary(record: dict[str, Any]) -> TraceSummaryDTO:
    """Chuyển dict record từ DB thành TraceSummaryDTO.

    Args:
        record: Dict từ PostgREST.

    Returns:
        TraceSummaryDTO đã validate.
    """
    return TraceSummaryDTO(
        trace_id=record["trace_id"],
        session_id=record["session_id"],
        prompt=record["prompt"],
        status=record["status"],
        duration_ms=int(record.get("duration_ms") or 0),
        total_tokens=int(record.get("total_tokens") or 0),
        cost=float(record.get("cost") or 0.0),
        created_at=str(record.get("created_at") or ""),
    )


def _truncate_value(value: Any, max_bytes: int = _MAX_SPAN_FIELD_BYTES) -> Any:
    """Truncate giá trị lớn để tránh phình blob Storage.

    Chỉ truncate str và dict/list (serialize JSON để đo). Các type khác giữ nguyên.

    Args:
        value: Giá trị cần truncate.
        max_bytes: Số byte tối đa giữ lại.

    Returns:
        Giá trị đã truncate (hoặc nguyên bản nếu không cần).
    """
    if value is None:
        return None

    if isinstance(value, str):
        encoded = value.encode("utf-8")
        if len(encoded) <= max_bytes:
            return value
        half = max_bytes // 2
        head = encoded[:half].decode("utf-8", errors="ignore")
        tail = encoded[-half:].decode("utf-8", errors="ignore")
        return head + _TRUNCATED_MARKER + tail

    if isinstance(value, (dict, list)):
        try:
            serialized = json.dumps(value, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            return str(value)[:max_bytes]
        if len(serialized.encode("utf-8")) <= max_bytes:
            return value
        head = serialized[: max_bytes // 2]
        tail = serialized[-max_bytes // 2 :]
        return head + _TRUNCATED_MARKER + tail

    return value


__all__ = ["ActiveTraceCollector", "TraceService"]


if __name__ == "__main__":
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()

    async def _test() -> None:
        trace_repo = TraceRepository()
        storage_repo = StorageRepository()
        service = TraceService(trace_repo, storage_repo)

        try:
            print("=== 1. Tạo collector + thêm spans ===")
            collector = service.create_collector(
                session_id="sess_smoke",
                prompt="Viết hàm tính giai thừa",
            )
            collector.add_span(
                name="LLM Generation",
                span_type="llm",
                duration_ms=1234,
                input_data={"messages": ["hello"] * 100},  # test truncate
                output_data={"content": "def fact(n): ..."},
                metadata={"tokens": 150, "cost": 0.001},
            )
            collector.add_span(
                name="Docker Test",
                span_type="sandbox",
                duration_ms=890,
                input_data={"command": ["python", "-m", "unittest"]},
                output_data={"stdout": "OK", "stderr": ""},
                metadata={"exit_code": 0},
            )
            print(f"collected {len(collector.spans)} spans, trace_id={collector.trace_id}")

            print("\n=== 2. Save session trace ===")
            saved_id = await service.save_session_trace(
                collector=collector,
                status="SUCCESS",
                duration_ms=2500,
                metrics={
                    "total_tokens": 150,
                    "input_tokens": 100,
                    "output_tokens": 50,
                    "reasoning_tokens": 0,
                    "cache_tokens": 0,
                    "cost": 0.001,
                },
            )
            print(f"saved: {saved_id}")

            print("\n=== 3. Get recent traces ===")
            recent = await service.get_recent_traces(limit=5)
            for r in recent:
                print(f"  - {r.trace_id} | {r.status} | {r.created_at}")

            print("\n=== 4. Get waterfall ===")
            detail = await service.get_trace_waterfall(saved_id)
            assert detail is not None
            print(f"spans loaded: {len(detail.spans)}")
            for s in detail.spans:
                print(f"  - [{s.span_type}] {s.name} ({s.duration_ms}ms)")

            print("\n=== 5. Search by status ===")
            success = await service.search_traces(status="SUCCESS", limit=3)
            print(f"found {len(success)} SUCCESS trace(s)")

            print("\n=== 6. Count ===")
            total = await service.count_traces()
            print(f"total: {total}")

            print("\n=== 7. Delete trace ===")
            deleted = await service.delete_trace(saved_id)
            print(f"deleted={deleted}")
            after = await service.get_trace_waterfall(saved_id)
            assert after is None
            print("PASS: trace đã xóa cả 2 tầng")

            print("\nTẤT CẢ TEST PASS")

        finally:
            await trace_repo.aclose()
            await storage_repo.aclose()

    asyncio.run(_test())