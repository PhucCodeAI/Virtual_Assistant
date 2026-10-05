# Backend/agents/base.py
"""Module định nghĩa interface chung cho mọi agent trong pipeline.

Mỗi agent là một async generator yield SSE events, đồng thời ghi kết quả
cuối cùng vào PipelineContext để orchestrator đọc tiếp.

Thiết kế:
    - Agent KHÔNG biết về agent khác — chỉ nhận context + services.
    - Agent KHÔNG save trace — orchestrator lo.
    - Agent emit event qua yield, không qua callback (dễ test, dễ cancel).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any


class BaseAgent(ABC):
    """Interface chung cho mọi agent.

    Subclass phải override `name` và `run`.
    """

    name: str = "base"

    @abstractmethod
    def run(self, context: Any) -> AsyncGenerator[str, None]:
        """Chạy agent, yield SSE events, cập nhật context.

        Args:
            context: PipelineContext chia sẻ giữa các agent.

        Yields:
            Chuỗi SSE đã format.
        """
        ...


__all__ = ["AgentResult", "BaseAgent"]