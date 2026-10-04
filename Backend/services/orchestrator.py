# Backend/services/orchestrator.py
"""Module điều phối trung tâm của AI Coding Agent (Business Logic Layer).

Vòng lặp tự sửa lỗi:
    1. Gọi LLM sinh AgentPatchResponse (explanation + files + test_command).
    2. Emit plan event công bố kế hoạch cho UI.
    3. Apply từng FileAction, emit file event sau mỗi thao tác.
    4. Chạy test_command trong Docker Sandbox, emit sandbox event.
    5. Nếu test fail → re-prompt LLM (reset messages về base để tránh phình token).
    6. Nếu pass → commit git, emit commit event, kết thúc.

Cleanup khi client disconnect:
    - Cancel lan xuống Orchestrator qua CancelledError.
    - finally block chạy save_session_trace để không mất trace.
    - Không yield thêm event nào trong finally (tránh GeneratorExit RuntimeError).

Exception sử dụng từ package `exceptions`.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncGenerator
from pathlib import Path
from time import perf_counter
from typing import Any

from config import configs
from dtos.agent import AgentPatchResponse, ApplyResult, FileAction
from dtos.orchestrator import (
    CommitEventPayload,
    DoneEventPayload,
    ErrorEventPayload,
    FileEventPayload,
    FilePlanItem,
    InputRequest,
    PlanEventPayload,
    SandboxEventPayload,
    StatusEventPayload,
    StatusStep,
    format_sse,
)
from exceptions import AppError, EditApplyError
from loguru import logger
from services.git_service import GitService
from services.llm_client import LLMClient
from services.sandbox_engine import SandboxEngine
from services.trace_service import ActiveTraceCollector, TraceService
from services.workspace_manager import WorkspaceManager

_MAX_ERROR_LOG_CHARS = 3000

_COMMIT_MSG_MAX_CHARS = 60


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
            llm_client: Client giao tiếp LLM.
            sandbox: Engine thực thi Docker Sandbox.
            git: Dịch vụ quản lý Git.
            trace_service: Dịch vụ ghi trace.
            workspace_base: Thư mục gốc chứa sandbox. None = lấy từ config.
            max_retries: Số lần tự sửa lỗi tối đa. None = lấy từ config.
        """
        cfg = configs.orchestrator
        self.llm_client = llm_client
        self.sandbox = sandbox
        self.git = git
        self.trace_service = trace_service
        self.workspace_base = Path(workspace_base or cfg.workspace_base)
        self.max_retries = max_retries if max_retries is not None else cfg.max_retries
        self.workspace_base.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------
    async def execute_stream(
        self,
        req: InputRequest,
    ) -> AsyncGenerator[str, None]:
        """Thực thi chu trình lập trình tự quyết và stream kết quả qua SSE.

        Args:
            req: Yêu cầu lập trình từ người dùng.

        Yields:
            Chuỗi SSE đã định dạng chuẩn text/event-stream.
        """
        start = perf_counter()
        session_id = req.session_id or "default_workspace"
        workspace_dir = self.workspace_base / session_id
        workspace = WorkspaceManager(workspace_dir)

        collector = self.trace_service.create_collector(
            session_id=session_id,
            prompt=req.prompt,
        )

        metrics: dict[str, float] = {
            "input_tokens": 0,
            "output_tokens": 0,
            "reasoning_tokens": 0,
            "cache_tokens": 0,
            "total_tokens": 0,
            "cost": 0.0,
        }

        final_status = "FAILED"
        err_msg: str | None = None
        cancelled = False

        try:
            await self.git.init_repo_if_needed(workspace_dir)

            base_messages = self._build_initial_messages(req.prompt)
            messages = list(base_messages)
            commit_hash: str | None = None
            changed_files: list[str] = []

            for attempt in range(1, self.max_retries + 1):
                yield self._status_event(
                    "plan",
                    f"Đang sinh mã nguồn & unit test (Lần {attempt}/{self.max_retries})...",
                )

                solution = await self._generate_solution(
                    messages=messages,
                    collector=collector,
                    attempt=attempt,
                    metrics=metrics,
                )

                yield format_sse(
                    "plan",
                    PlanEventPayload(
                        explanation=solution.explanation,
                        files=[
                            FilePlanItem(path=f.path, action=f.action)
                            for f in solution.files
                        ],
                        test_command=solution.test_command,
                    ),
                )

                yield self._status_event(
                    "sandbox",
                    f"Đang nạp {len(solution.files)} file vào workspace...",
                )
                for action in solution.files:
                    apply_result = await workspace.apply_file_action(action)
                    yield self._file_event(apply_result)

                test_command_str = " ".join(solution.test_command)
                yield self._status_event(
                    "test",
                    f"Đang chạy test: {test_command_str}...",
                )

                test_result = await self._run_test(
                    workspace_dir=workspace_dir,
                    command=solution.test_command,
                    collector=collector,
                    attempt=attempt,
                )

                yield format_sse(
                    "sandbox",
                    SandboxEventPayload(
                        command=solution.test_command,
                        exit_code=test_result.exit_code,
                        duration_ms=test_result.duration_ms,
                        is_timeout=test_result.is_timeout,
                        stdout_summary=_tail(test_result.stdout, 500)
                        or _tail(test_result.stderr, 500),
                    ),
                )

                if test_result.exit_code == 0:
                    final_status = "SUCCESS"
                    break

                error_log = _tail(
                    (test_result.stderr or test_result.stdout).strip(),
                    _MAX_ERROR_LOG_CHARS,
                )
                logger.warning(
                    "Lần {} test fail (exit={}):\n{}",
                    attempt,
                    test_result.exit_code,
                    error_log[:500],
                )

                if attempt < self.max_retries:
                    yield self._status_event(
                        "test",
                        f"Test fail lần {attempt}. Đang phân tích lỗi để tự sửa...",
                    )
                    messages = self._build_retry_messages(
                        base=base_messages,
                        previous_solution=solution,
                        error_log=error_log,
                        test_command=test_command_str,
                    )

            if final_status != "SUCCESS":
                err_msg = (
                    f"Đã thử tự sửa lỗi {self.max_retries} lần "
                    f"nhưng không vượt qua được test."
                )
                yield format_sse(
                    "error",
                    ErrorEventPayload(code="TEST_MAX_RETRIES", message=err_msg),
                )
            else:
                yield self._status_event(
                    "git",
                    "Test pass! Tạo Git commit...",
                )
                commit_hash, changed_files = await self._commit(
                    workspace_dir=workspace_dir,
                    prompt=req.prompt,
                    collector=collector,
                )
                if commit_hash:
                    yield format_sse(
                        "commit",
                        CommitEventPayload(
                            hash=commit_hash,
                            message=_build_commit_msg(req.prompt),
                            files=changed_files,
                        ),
                    )
                yield self._status_event("generate", "Hoàn tất.")

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
            yield format_sse(
                "error",
                ErrorEventPayload(code=e.code, message=e.message),
            )
        except AppError as e:
            final_status = "FAILED"
            err_msg = e.message
            logger.error("AppError: {} — {}", e.code, e.message)
            yield format_sse(
                "error",
                ErrorEventPayload(code=e.code, message=e.message),
            )
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
                    metrics=metrics,
                    error_message=err_msg,
                )

        if not cancelled:
            total_ms = int((perf_counter() - start) * 1000)
            yield format_sse(
                "done",
                DoneEventPayload(
                    status=final_status,  # type: ignore[arg-type]
                    duration_ms=total_ms,
                    total_tokens=int(metrics["total_tokens"]),
                    input_tokens=int(metrics["input_tokens"]),
                    output_tokens=int(metrics["output_tokens"]),
                    reasoning_tokens=int(metrics["reasoning_tokens"]),
                    cache_tokens=int(metrics["cache_tokens"]),
                    cost=float(metrics["cost"]),
                    trace_id=collector.trace_id,
                ),
            )

    # --------------------------------------------------------
    # Bước sinh mã
    # --------------------------------------------------------
    async def _generate_solution(
        self,
        messages: list[dict[str, str]],
        collector: ActiveTraceCollector,
        attempt: int,
        metrics: dict[str, float],
    ) -> AgentPatchResponse:
        """Gọi LLM sinh AgentPatchResponse và cập nhật metrics tích lũy.

        Args:
            messages: Lịch sử hội thoại hiện tại.
            collector: Collector để ghi span.
            attempt: Số thứ tự lần thử (1-indexed).

        Returns:
            AgentPatchResponse từ LLM.

        Raises:
            LLMSchemaError: Khi LLM trả output không khớp schema.
            LLMError: Khi gọi LLM thất bại.
        """
        t0 = perf_counter()
        response = await self.llm_client.structured_generate(
            messages=messages,
            response_model=AgentPatchResponse,
        )
        duration_ms = int((perf_counter() - t0) * 1000)

        solution: AgentPatchResponse = response["response"]
        info: dict[str, Any] = response.get("info") or {}

        collector.add_span(
            name=f"LLM Generation (Attempt {attempt})",
            span_type="llm",
            duration_ms=duration_ms,
            input_data={"messages": _truncate_messages(messages)},
            output_data=solution.model_dump(),
            metadata={
                "input_tokens": info.get("input_token", 0),
                "output_tokens": info.get("output_token", 0),
                "reasoning_tokens": info.get("reasoning_token", 0),
                "cached_tokens": info.get("cached_token", 0),
                "cost": info.get("cost", 0.0),
                "finish_reason": info.get("finish_reason"),
            },
        )

        metrics["input_tokens"] += int(info.get("input_token", 0) or 0)
        metrics["output_tokens"] += int(info.get("output_token", 0) or 0)
        metrics["reasoning_tokens"] += int(info.get("reasoning_token", 0) or 0)
        metrics["cache_tokens"] += int(info.get("cached_token", 0) or 0)
        metrics["total_tokens"] += int(info.get("total_token", 0) or 0)
        metrics["cost"] += float(info.get("cost", 0) or 0.0)
        return solution

    # --------------------------------------------------------
    # Bước chạy test
    # --------------------------------------------------------
    async def _run_test(
        self,
        workspace_dir: Path,
        command: list[str],
        collector: ActiveTraceCollector,
        attempt: int,
    ):
        """Chạy test trong sandbox và ghi span tương ứng.

        Args:
            workspace_dir: Thư mục workspace.
            command: Lệnh test.
            collector: Collector để ghi span.
            attempt: Số thứ tự lần thử.

        Returns:
            ExecutionResult từ sandbox.
        """
        t0 = perf_counter()
        result = await self.sandbox.run_command(workspace_dir, command)
        duration_ms = int((perf_counter() - t0) * 1000)

        collector.add_span(
            name=f"Docker Test (Attempt {attempt})",
            span_type="sandbox",
            duration_ms=duration_ms,
            input_data={"command": command},
            output_data={
                "stdout": _tail(result.stdout, _MAX_ERROR_LOG_CHARS),
                "stderr": _tail(result.stderr, _MAX_ERROR_LOG_CHARS),
            },
            metadata={
                "exit_code": result.exit_code,
                "is_timeout": result.is_timeout,
            },
            status="OK" if result.exit_code == 0 else "ERROR",
        )
        return result

    # --------------------------------------------------------
    # Bước commit
    # --------------------------------------------------------
    async def _commit(
        self,
        workspace_dir: Path,
        prompt: str,
        collector: ActiveTraceCollector,
    ) -> tuple[str, list[str]]:
        """Commit thay đổi vào git và ghi span.

        Args:
            workspace_dir: Thư mục workspace.
            prompt: Prompt gốc (dùng cho commit message).
            collector: Collector để ghi span.

        Returns:
            Tuple (commit_hash, changed_files).
        """
        t0 = perf_counter()
        commit_msg = _build_commit_msg(prompt)
        commit_hash, changed_files = await self.git.commit_changes(
            workspace_path=workspace_dir,
            message=commit_msg,
        )
        duration_ms = int((perf_counter() - t0) * 1000)

        collector.add_span(
            name="Git Commit",
            span_type="git",
            duration_ms=duration_ms,
            input_data={"message": commit_msg},
            output_data={
                "commit_hash": commit_hash,
                "changed_files": changed_files,
            },
            status="OK" if commit_hash else "ERROR",
        )
        return commit_hash, changed_files

    # --------------------------------------------------------
    # Build messages
    # --------------------------------------------------------
    def _build_initial_messages(self, prompt: str) -> list[dict[str, str]]:
        """Xây dựng messages ban đầu (system + user).

        Args:
            prompt: Yêu cầu của người dùng.

        Returns:
            Danh sách messages cho LLM lần gọi đầu.
        """
        system = configs.orchestrator.system_prompt
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Yêu cầu: {prompt}"},
        ]

    @staticmethod
    def _build_retry_messages(
        base: list[dict[str, str]],
        previous_solution: AgentPatchResponse,
        error_log: str,
        test_command: str,
    ) -> list[dict[str, str]]:
        """Xây dựng messages cho lần retry, reset về base + error info.

        KHÔNG append tích lũy để tránh phình token qua nhiều lần retry.

        Args:
            base: Messages gốc (system + user ban đầu).
            previous_solution: Solution vừa fail.
            error_log: Log lỗi từ test.
            test_command: Lệnh test đã chạy.

        Returns:
            Danh sách messages mới cho lần thử tiếp theo.
        """
        prev_summary = (
            f"Đã sinh {len(previous_solution.files)} file: "
            f"{[f.path for f in previous_solution.files]}"
        )
        return [
            *base,
            {"role": "assistant", "content": prev_summary},
            {
                "role": "user",
                "content": (
                    f"Lệnh '{test_command}' thất bại với output:\n"
                    f"{error_log}\n\n"
                    "Hãy phân tích nguyên nhân và sinh lại solution đầy đủ. "
                    "Có thể dùng action='update' với edits nếu chỉ cần sửa nhỏ "
                    "trong các file đã tạo, hoặc action='create' để ghi đè."
                ),
            },
        ]

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------
    @staticmethod
    def _status_event(step: StatusStep, message: str) -> str:
        """Tạo SSE event status.

        Args:
            step: Bước trong pipeline.
            message: Mô tả hiển thị UI.

        Returns:
            Chuỗi SSE.
        """
        return format_sse(
            "status",
            StatusEventPayload(step=step, message=message),
        )

    @staticmethod
    def _file_event(result: ApplyResult) -> str:
        """Tạo SSE event file từ ApplyResult.

        Args:
            result: Kết quả apply từ WorkspaceManager.

        Returns:
            Chuỗi SSE.
        """
        return format_sse(
            "file",
            FileEventPayload(
                path=result.path,
                action=result.action,
                lines_added=result.lines_added,
                lines_removed=result.lines_removed,
            ),
        )

    def _accumulate_metrics(self, info: dict[str, Any]) -> None:
        """Cộng dồn metrics từ LLM vào state tích lũy của instance.

        Đây là helper cần mutable state — sẽ refactor sang class-level dict.

        Args:
            info: Dict metadata từ LLMClient.
        """
        _ = info


# ============================================================
# Module-level helpers
# ============================================================
def _build_commit_msg(prompt: str) -> str:
    """Tạo commit message ngắn an toàn từ prompt.

    Args:
        prompt: Prompt gốc.

    Returns:
        Commit message đã cắt gọn tại ranh giới từ.
    """
    one_line = " ".join(prompt.split())
    if len(one_line) <= _COMMIT_MSG_MAX_CHARS:
        short = one_line
    else:
        cut = one_line[:_COMMIT_MSG_MAX_CHARS]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        short = cut + "..."
    return f"feat: vibe solution for '{short}'"


def _tail(text: str, max_chars: int) -> str:
    """Lấy phần cuối của text, thêm marker nếu bị cắt.

    Args:
        text: Chuỗi gốc.
        max_chars: Số ký tự tối đa.

    Returns:
        Chuỗi đã cắt (giữ phần cuối) với prefix '...' nếu bị cắt.
    """
    if len(text) <= max_chars:
        return text
    return "..." + text[-max_chars:]


def _truncate_messages(
    messages: list[dict[str, str]],
    max_chars: int = 4000,
) -> list[dict[str, str]]:
    """Truncate nội dung messages để lưu span không phình quá.

    Args:
        messages: Danh sách messages gốc.
        max_chars: Số ký tự tối đa mỗi message.

    Returns:
        List messages đã truncate.
    """
    result: list[dict[str, str]] = []
    for m in messages:
        content = m.get("content", "")
        if len(content) > max_chars:
            content = content[: max_chars // 2] + "...[truncated]..." + content[-max_chars // 2 :]
        result.append({"role": m.get("role", ""), "content": content})
    return result


__all__ = ["Orchestrator"]


if __name__ == "__main__":
    from unittest.mock import AsyncMock, MagicMock

    from dtos.sandbox import ExecutionResult

    async def _test() -> None:
        mock_llm = AsyncMock(spec=LLMClient)
        mock_llm.structured_generate = AsyncMock(
            return_value={
                "response": AgentPatchResponse(
                    explanation="Tạo module tính toán đơn giản.",
                    files=[
                        FileAction(
                            path="calc.py",
                            action="create",
                            content="def add(a, b):\n    return a + b\n",
                        ),
                        FileAction(
                            path="test_calc.py",
                            action="create",
                            content=(
                                "from calc import add\n"
                                "import unittest\n"
                                "class T(unittest.TestCase):\n"
                                "    def test_add(self):\n"
                                "        self.assertEqual(add(1, 2), 3)\n"
                            ),
                        ),
                    ],
                ),
                "info": {
                    "input_token": 100,
                    "output_token": 200,
                    "reasoning_token": 0,
                    "cached_token": 0,
                    "total_token": 300,
                    "cost": 0.001,
                    "finish_reason": "stop",
                },
            }
        )

        mock_sandbox = AsyncMock(spec=SandboxEngine)
        mock_sandbox.run_command = AsyncMock(
            return_value=ExecutionResult(
                exit_code=0,
                stdout="OK",
                stderr="",
                duration_ms=500,
                is_timeout=False,
            )
        )
        mock_sandbox.cleanup_orphans = AsyncMock(return_value=0)

        mock_git = AsyncMock(spec=GitService)
        mock_git.init_repo_if_needed = AsyncMock(return_value=True)
        mock_git.commit_changes = AsyncMock(
            return_value=("abc1234", ["calc.py", "test_calc.py"])
        )

        mock_trace = MagicMock(spec=TraceService)
        mock_collector = MagicMock()
        mock_collector.trace_id = "tr_mock123"
        mock_collector.add_span = MagicMock()
        mock_trace.create_collector = MagicMock(return_value=mock_collector)
        mock_trace.save_session_trace = AsyncMock(return_value="tr_mock123")

        orch = Orchestrator(
            llm_client=mock_llm,
            sandbox=mock_sandbox,
            git=mock_git,
            trace_service=mock_trace,
            workspace_base="./storage/sandboxes_test",
            max_retries=2,
        )

        req = InputRequest(prompt="Viết hàm add", session_id="test_sess")
        events: list[str] = []

        async for chunk in orch.execute_stream(req):
            events.append(chunk)
            first_line = chunk.split("\n", 1)[0]
            print(f"[SSE] {first_line}")

        event_names = [
            line[len("event: ") :]
            for chunk in events
            for line in chunk.split("\n")
            if line.startswith("event: ")
        ]

        print(f"\nTổng số events: {len(event_names)}")
        print(f"Event types: {event_names}")

        assert "plan" in event_names, "Thiếu plan event"
        assert "file" in event_names, "Thiếu file event"
        assert "sandbox" in event_names, "Thiếu sandbox event"
        assert "commit" in event_names, "Thiếu commit event"
        assert "done" in event_names, "Thiếu done event"
        assert event_names[-1] == "done"

        assert "token" not in event_names, "Token event không nên xuất hiện"

        mock_trace.save_session_trace.assert_called_once()
        call_kwargs = mock_trace.save_session_trace.call_args.kwargs
        assert call_kwargs["status"] == "SUCCESS"
        print(f"\nTrace saved with status={call_kwargs['status']}")
        print(f"Metrics: {call_kwargs['metrics']}")

        print("\nTẤT CẢ TEST PASS")

    asyncio.run(_test())