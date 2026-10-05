# Backend/pipeline/context.py
"""Module định nghĩa PipelineContext — state chia sẻ giữa các agent.

Context được tạo MỘT LẦN ở đầu mỗi lần chạy pipeline, truyền qua mọi agent.
Agent có thể đọc + ghi vào context (metrics, agent_results, ...).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from services.trace_service import ActiveTraceCollector
from services.workspace_manager import WorkspaceManager


@dataclass
class PipelineContext:
    """State chia sẻ giữa các agent trong một lần chạy pipeline.

    Attributes:
        session_id: Mã phiên.
        prompt: Prompt gốc của user.
        workspace_dir: Thư mục workspace trên host.
        workspace: Manager thao tác file.
        collector: Trace collector để ghi span.
        metrics: Dict tích lũy tokens/cost — agent cộng dồn.
        agent_results: Kết quả của từng agent, key = agent.name.
        max_retries: Số lần tự sửa lỗi tối đa (từ config).
        metadata: Metadata tự do cho agent truyền thông tin phụ.
    """

    session_id: str
    prompt: str
    workspace_dir: Path
    workspace: WorkspaceManager
    collector: ActiveTraceCollector
    max_retries: int
    metrics: dict[str, float] = field(
        default_factory=lambda: {
            "input_tokens": 0.0,
            "output_tokens": 0.0,
            "reasoning_tokens": 0.0,
            "cache_tokens": 0.0,
            "total_tokens": 0.0,
            "cost": 0.0,
        }
    )
    agent_results: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def accumulate_llm_metrics(self, info: dict[str, Any]) -> None:
        """Cộng dồn metrics từ một lần gọi LLM vào context.

        Args:
            info: Dict metadata từ LLMClient._parse_info.
        """
        self.metrics["input_tokens"] += int(info.get("input_token") or 0)
        self.metrics["output_tokens"] += int(info.get("output_token") or 0)
        self.metrics["reasoning_tokens"] += int(info.get("reasoning_token") or 0)
        self.metrics["cache_tokens"] += int(info.get("cached_token") or 0)
        self.metrics["total_tokens"] += int(info.get("total_token") or 0)
        self.metrics["cost"] += float(info.get("cost") or 0.0)


def new_trace_id() -> str:
    """Sinh trace_id mới.

    Returns:
        Chuỗi trace_id format tr_{12 hex}.
    """
    return f"tr_{uuid.uuid4().hex[:12]}"


__all__ = ["PipelineContext", "new_trace_id"]