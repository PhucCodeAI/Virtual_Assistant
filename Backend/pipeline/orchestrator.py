# Backend/pipeline/orchestrator.py
"""Orchestrator top-level — điều phối các agent và quản lý SSE stream.

Trách nhiệm:
    - Tạo PipelineContext cho mỗi request.
    - Route qua các agent theo thứ tự.
    - Save trace bất chấp cancel.
    - Emit done event ở cuối (không nằm trong finally).

Hiện tại chỉ có 1 agent (CoderAgent). Khi thêm agent mới, sửa `_run_agents`.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from pathlib import Path
from time import perf_counter

from agents.coder import CoderAgent
from config import configs
from dtos.orchestrator import (
    DoneEventPayload,
    ErrorEventPayload,
    InputRequest,
    format_sse,
)
from exceptions import AppError, EditApplyError
from loguru import logger
from services.git_service import GitService
from services.llm_client import LLMClient
from services.sandbox_engine import SandboxEngine
from services.trace_service import TraceService
from services.workspace_manager import WorkspaceManager

from pipeline.context import PipelineContext


class Orchestrator:
    """Bộ điều phối vòng lặp thực thi tự quyết của Agent."""

    def __init__(
        self,
        llm_client: LLMClient,
        sandbox: SandboxEngine,
        git: GitService,
        trace_service: TraceService,
        workspace_base: str | None = None,
        max_retries: int | None = None,
    ) -> None:
        """Khởi tạo Orchestrator.

        Args:
            llm_client: Client gọi LLM.
            sandbox: Engine sandbox.
            git: Service Git.
            trace_service: Service trace.
            workspace_base: Thư mục gốc chứa workspace. None = từ config.
            max_retries: Số lần tự sửa lỗi. None = từ config.
        """
        cfg = configs.orchestrator
        self.workspace_base = Path(workspace_base or cfg.workspace_base)
        self.max_retries = max_retries if max_retries is not None else cfg.max_retries
        self.workspace_base.mkdir(parents=True, exist_ok=True)

        self.trace_service = trace_service
        self.agents: list[CoderAgent] = [
            CoderAgent(llm_client=llm_client, sandbox=sandbox, git=git),
        ]

    async def execute_stream(
        self,
        req: InputRequest,
    ) -> AsyncGenerator[str, None]:
        """Thực thi pipeline và stream SSE events.

        Args:
            req: Yêu cầu từ user.

        Yields:
            Chuỗi SSE.
        """
        start = perf_counter()
        session_id = req.session_id or "default_workspace"
        workspace_dir = self.workspace_base / session_id
        workspace = WorkspaceManager(workspace_dir)

        collector = self.trace_service.create_collector(
            session_id=session_id,
            prompt=req.prompt,
        )

        context = PipelineContext(
            session_id=session_id,
            prompt=req.prompt,
            workspace_dir=workspace_dir,
            workspace=workspace,
            collector=collector,
            max_retries=self.max_retries,
        )

        final_status = "FAILED"
        err_msg: str | None = None
        cancelled = False

        try:
            async for event in self._run_agents(context):
                yield event

            coder_result = context.agent_results.get("coder")
            if coder_result and coder_result.status == "SUCCESS":
                final_status = "SUCCESS"
            else:
                err_msg = (
                    coder_result.error
                    if coder_result
                    else "Pipeline kết thúc không rõ trạng thái."
                )
                yield format_sse(
                    "error",
                    ErrorEventPayload(code="TEST_MAX_RETRIES", message=err_msg),
                )

        except asyncio.CancelledError:
            cancelled = True
            final_status = "CANCELLED"
            err_msg = "Client ngắt kết nối"
            logger.info("Orchestrator bị cancel (client disconnect)")
            raise
        except EditApplyError as e:
            final_status = "FAILED"
            err_msg = e.message
            logger.error("Edit apply fail: {}", e)
            yield format_sse("error", ErrorEventPayload(code=e.code, message=e.message))
        except AppError as e:
            final_status = "FAILED"
            err_msg = e.message
            logger.error("AppError: {} — {}", e.code, e.message)
            yield format_sse("error", ErrorEventPayload(code=e.code, message=e.message))
        except Exception as e:
            final_status = "FAILED"
            err_msg = f"Lỗi hệ thống không mong đợi: {e}"
            logger.exception("Lỗi không mong đợi trong Orchestrator")
            yield format_sse(
                "error",
                ErrorEventPayload(code="SYSTEM_ERROR", message=str(e)),
            )

        finally:
            total_ms = int((perf_counter() - start) * 1000)
            with contextlib.suppress(Exception):
                await self.trace_service.save_session_trace(
                    collector=collector,
                    status=final_status,
                    duration_ms=total_ms,
                    metrics=context.metrics,
                    error_message=err_msg,
                )

        if not cancelled:
            total_ms = int((perf_counter() - start) * 1000)
            yield format_sse(
                "done",
                DoneEventPayload(
                    status=final_status,
                    duration_ms=total_ms,
                    total_tokens=int(context.metrics["total_tokens"]),
                    input_tokens=int(context.metrics["input_tokens"]),
                    output_tokens=int(context.metrics["output_tokens"]),
                    reasoning_tokens=int(context.metrics["reasoning_tokens"]),
                    cache_tokens=int(context.metrics["cache_tokens"]),
                    cost=float(context.metrics["cost"]),
                    trace_id=collector.trace_id,
                ),
            )

    async def _run_agents(self, context: PipelineContext) -> AsyncGenerator[str, None]:
        """Route qua các agent theo thứ tự.

        Hiện tại chỉ chạy CoderAgent. Khi thêm agent:
            - PlannerAgent chạy trước CoderAgent.
            - ReviewerAgent chạy xen giữa hoặc sau.
        Nhưng logic route cụ thể nên để đến khi có agent thứ 2.

        Args:
            context: PipelineContext.
        """
        for agent in self.agents:
            logger.debug("Running agent: {}", agent.name)
            async for event in agent.run(context):
                yield event


__all__ = ["Orchestrator"]