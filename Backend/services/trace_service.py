"""Module dịch vụ quản lý nghiệp vụ Trace và điều phối lưu trữ đa tầng."""

import logging
import uuid
from typing import Any

from dtos.trace import TraceDetailDTO, TraceSummaryDTO
from repositories.storage_repository import StorageRepository
from repositories.trace_repository import TraceRepository

logger = logging.getLogger(__name__)


class ActiveTraceCollector:
    """Bộ thu thập spans in-memory trong suốt vòng đời của một phiên làm việc."""

    def __init__(self, session_id: str, prompt: str) -> None:
        """Khởi tạo collector cho phiên làm việc.

        Args:
            session_id: Mã định danh phiên làm việc.
            prompt: Câu lệnh yêu cầu ban đầu từ người dùng.
        """
        self.trace_id = f"tr_{uuid.uuid4().hex[:12]}"
        self.session_id = session_id
        self.prompt = prompt
        self.spans: list[dict[str, Any]] = []

    def add_span(
        self,
        name: str,
        span_type: str,
        duration_ms: int,
        input_data: Any = None,
        output_data: Any = None,
        metadata: dict[str, Any] | None = None,
        status: str = "OK",
    ) -> None:
        """Ghi nhận một span thực thi chi tiết vào bộ nhớ tạm.

        Args:
            name: Tên tác vụ (ví dụ: 'call_llm', 'run_pytest').
            span_type: Phân loại span ('llm', 'tool', 'sandbox', 'internal').
            duration_ms: Thời gian thực thi tính bằng mili-giây.
            input_data: Dữ liệu đầu vào của tác vụ.
            output_data: Dữ liệu đầu ra của tác vụ.
            metadata: Siêu dữ liệu bổ sung.
            status: Trạng thái thực thi ('OK', 'ERROR').
        """
        self.spans.append(
            {
                "span_id": f"sp_{uuid.uuid4().hex[:8]}",
                "name": name,
                "span_type": span_type,
                "duration_ms": duration_ms,
                "input_data": input_data,
                "output_data": output_data,
                "metadata": metadata or {},
                "status": status,
            }
        )


class TraceService:
    """Dịch vụ xử lý nghiệp vụ thu thập, phân tích và điều phối lưu trữ Trace."""

    def __init__(
        self,
        trace_repo: TraceRepository,
        storage_repo: StorageRepository,
    ) -> None:
        """Khởi tạo service với các repository độc lập thuộc Data Access Layer.

        Args:
            trace_repo: Repository truy xuất metadata database qua PostgREST.
            storage_repo: Repository lưu trữ heavy payload qua Supabase Storage.
        """
        self.trace_repo = trace_repo
        self.storage_repo = storage_repo

    def create_collector(self, session_id: str, prompt: str) -> ActiveTraceCollector:
        """Khởi tạo một instance collector gom spans cho phiên làm việc.

        Args:
            session_id: Mã phiên làm việc.
            prompt: Nội dung prompt đầu vào.

        Returns:
            Instance của ActiveTraceCollector.
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
        """Đóng gói phiên chạy, đẩy payload lên Storage và lưu metadata vào DB.

        Cơ chế Compensating Transaction: Nếu ghi DB thất bại sau khi đã upload Storage,
        service sẽ tự động xóa file trên Storage để ngăn chặn file rác.

        Args:
            collector: Instance ActiveTraceCollector chứa spans của phiên.
            status: Trạng thái kết thúc ('SUCCESS', 'FAILED').
            duration_ms: Tổng thời gian thực thi (ms).
            metrics: Token tiêu thụ và chi phí tài nguyên.
            error_message: Nội dung lỗi nếu có.

        Returns:
            Mã định danh trace_id vừa lưu.

        Raises:
            Exception: Ném lại ngoại lệ gốc nếu ghi dữ liệu thất bại.
        """
        storage_path = f"{collector.session_id}/{collector.trace_id}.json"

        # 1. Đóng gói Heavy Payload cho Object Storage
        full_payload = {
            "trace_id": collector.trace_id,
            "session_id": collector.session_id,
            "prompt": collector.prompt,
            "status": status,
            "duration_ms": duration_ms,
            "metrics": metrics,
            "spans": collector.spans,
            "error_message": error_message,
        }

        # 2. Upload file lên Supabase Storage
        await self.storage_repo.upload_json(storage_path, full_payload)

        # 3. Đóng gói Metadata tinh gọn để insert Postgres
        record = {
            "trace_id": collector.trace_id,
            "session_id": collector.session_id,
            "prompt": collector.prompt,
            "status": status,
            "duration_ms": duration_ms,
            "total_tokens": metrics.get("total_tokens", 0),
            "input_tokens": metrics.get("input_tokens", 0),
            "output_tokens": metrics.get("output_tokens", 0),
            "reasoning_tokens": metrics.get("reasoning_tokens", 0),
            "cache_tokens": metrics.get("cache_tokens", 0),
            "cost": float(metrics.get("cost", 0.0)),
            "storage_path": storage_path,
            "error_message": error_message,
        }

        # 4. Lưu metadata vào DB kèm rollback nếu lỗi
        try:
            await self.trace_repo.create(record)
        except Exception as exc:
            logger.error(
                "Lỗi ghi Postgres metadata, kích hoạt rollback xóa storage: %s. Chi tiết: %s",
                storage_path,
                exc,
            )
            try:
                await self.storage_repo.delete_file(storage_path)
            except Exception as rollback_exc:
                logger.critical(
                    "Rollback thất bại! Orphan blob tồn tại tại: %s. Chi tiết: %s",
                    storage_path,
                    rollback_exc,
                )
            raise exc

        return collector.trace_id

    async def get_recent_traces(self, limit: int, offset: int) -> list[TraceSummaryDTO]:
        """Lấy danh sách tóm tắt metadata phục vụ UI Dashboard (tải siêu tốc).

        Args:
            limit: Số bản ghi tối đa.
            offset: Vị trí phân trang bắt đầu.

        Returns:
            Danh sách TraceSummaryDTO.
        """
        records = await self.trace_repo.list_summary(limit, offset)
        return [
            TraceSummaryDTO(
                trace_id=r["trace_id"],
                session_id=r["session_id"],
                prompt=r["prompt"],
                status=r["status"],
                duration_ms=r["duration_ms"],
                total_tokens=r.get("total_tokens", 0),
                cost=float(r.get("cost", 0.0)),
                created_at=r.get("created_at", ""),
            )
            for r in records
        ]

    async def get_trace_waterfall(self, trace_id: str) -> TraceDetailDTO | None:
        """Lấy chi tiết toàn bộ Trace và cây Spans từ Storage.

        Args:
            trace_id: Mã định danh của trace.

        Returns:
            TraceDetailDTO nếu tồn tại, ngược lại trả về None.
        """
        raw = await self.trace_repo.get_by_id(trace_id)
        if not raw:
            return None

        storage_path = raw.get("storage_path")
        payload: dict[str, Any] = {}

        if storage_path:
            try:
                downloaded = await self.storage_repo.download_json(storage_path)
                if downloaded:
                    payload = downloaded
            except Exception as exc:
                logger.warning(
                    "Không thể tải payload từ Storage cho trace %s: %s",
                    trace_id,
                    exc,
                )

        return TraceDetailDTO(
            trace_id=raw["trace_id"],
            session_id=raw["session_id"],
            prompt=raw["prompt"],
            status=raw["status"],
            duration_ms=raw["duration_ms"],
            total_tokens=raw.get("total_tokens", 0),
            input_tokens=raw.get("input_tokens", 0),
            output_tokens=raw.get("output_tokens", 0),
            reasoning_tokens=raw.get("reasoning_tokens", 0),
            cache_tokens=raw.get("cache_tokens", 0),
            cost=float(raw.get("cost", 0.0)),
            error_message=raw.get("error_message"),
            created_at=raw.get("created_at", ""),
            spans=payload.get("spans", []),
        )


if __name__ == "__main__":
    import asyncio

    from dotenv import load_dotenv

    load_dotenv()

    trace_repo = TraceRepository()
    storage_repo = StorageRepository()

    tracer = TraceService(trace_repo, storage_repo)

    result = asyncio.run(tracer.get_recent_traces(limit=10, offset=0))
