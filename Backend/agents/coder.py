# Backend/agents/coder.py
"""Agent sinh mã + chạy test + retry tự sửa lỗi.

Đây là logic được extract từ `services/orchestrator.py` cũ.
Behavior giữ nguyên 100% — chỉ đổi chỗ ở.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from time import perf_counter
from typing import Any

from config import configs
from dtos.agent import AgentPatchResponse, AgentResult, ApplyResult
from dtos.orchestrator import (
    CommitEventPayload,
    FileEventPayload,
    FilePlanItem,
    PlanEventPayload,
    SandboxEventPayload,
    StatusEventPayload,
    StatusStep,
    format_sse,
)
from exceptions import AppError, EditApplyError
from loguru import logger
from pipeline.context import PipelineContext
from services.git_service import GitService
from services.llm_client import LLMClient
from services.sandbox_engine import SandboxEngine

from agents.base import BaseAgent

_MAX_ERROR_LOG_CHARS = 3000


class CoderAgent(BaseAgent):
    """Agent sinh mã nguồn + test, tự sửa lỗi qua retry."""

    name = "coder"

    def __init__(
        self,
        llm_client: LLMClient,
        sandbox: SandboxEngine,
        git: GitService,
    ) -> None:
        """Khởi tạo CoderAgent.

        Args:
            llm_client: Client gọi LLM.
            sandbox: Engine chạy test trong Docker.
            git: Service commit kết quả.
        """
        self.llm_client = llm_client
        self.sandbox = sandbox
        self.git = git

    async def run(self, context: PipelineContext) -> AsyncGenerator[str, None]:
        """Chạy vòng lặp sinh mã → test → retry.

        Args:
            context: PipelineContext chia sẻ.

        Yields:
            Chuỗi SSE events (status, plan, file, sandbox, commit).
        """
        base_messages = self._build_initial_messages(context.prompt)
        messages = list(base_messages)

        commit_hash: str | None = None
        changed_files: list[str] = []
        success = False

        for attempt in range(1, context.max_retries + 1):
            yield _status_event(
                "plan",
                f"Đang sinh mã nguồn & unit test "
                f"(Lần {attempt}/{context.max_retries})...",
            )

            solution = await self._generate_solution(
                messages=messages,
                context=context,
                attempt=attempt,
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

            yield _status_event(
                "sandbox",
                f"Đang nạp {len(solution.files)} file vào workspace...",
            )
            for action in solution.files:
                apply_result = await context.workspace.apply_file_action(action)
                yield _file_event(apply_result)

            test_command_str = " ".join(solution.test_command)
            yield _status_event("test", f"Đang chạy test: {test_command_str}...")

            test_result = await self._run_test(
                workspace_dir=context.workspace_dir,
                command=solution.test_command,
                context=context,
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
                success = True
                break

            error_log = _tail(
                (test_result.stderr or test_result.stdout).strip(),
                _MAX_ERROR_LOG_CHARS,
            )
            logger.warning(
                "Attempt {} fail (exit={}):\n{}",
                attempt,
                test_result.exit_code,
                error_log[:500],
            )

            if attempt < context.max_retries:
                yield _status_event(
                    "test",
                    f"Test fail lần {attempt}. Đang phân tích lỗi để tự sửa...",
                )
                messages = self._build_retry_messages(
                    base=base_messages,
                    previous_solution=solution,
                    error_log=error_log,
                    test_command=test_command_str,
                )

        if not success:
            context.agent_results[self.name] = AgentResult(
                name=self.name,
                status="FAILED",
                error=f"Đã thử tự sửa lỗi {context.max_retries} lần nhưng thất bại.",
            )
            return

        yield _status_event("git", "Test pass! Tạo Git commit...")
        commit_hash, changed_files = await self._commit(
            workspace_dir=context.workspace_dir,
            prompt=context.prompt,
            context=context,
        )
        if commit_hash:
            yield format_sse(
                "commit",
                CommitEventPayload(
                    hash=commit_hash,
                    message=_build_commit_msg(context.prompt),
                    files=changed_files,
                ),
            )

        yield _status_event("generate", "Hoàn tất.")

        context.agent_results[self.name] = AgentResult(
            name=self.name,
            status="SUCCESS",
            output={"commit_hash": commit_hash, "changed_files": changed_files},
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _generate_solution(
        self,
        messages: list[dict[str, str]],
        context: PipelineContext,
        attempt: int,
    ) -> AgentPatchResponse:
        """Gọi LLM sinh solution và ghi span.

        Args:
            messages: Lịch sử hội thoại.
            context: PipelineContext.
            attempt: Số thứ tự lần thử.

        Returns:
            AgentPatchResponse từ LLM.
        """
        t0 = perf_counter()
        response = await self.llm_client.structured_generate(
            messages=messages,
            response_model=AgentPatchResponse,
        )
        duration_ms = int((perf_counter() - t0) * 1000)

        solution: AgentPatchResponse = response["response"]
        info: dict[str, Any] = response.get("info") or {}

        context.collector.add_span(
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
        context.accumulate_llm_metrics(info)
        return solution

    async def _run_test(
        self,
        workspace_dir: Path,
        command: list[str],
        context: PipelineContext,
        attempt: int,
    ) -> Any:
        """Chạy test trong sandbox + ghi span.

        Args:
            workspace_dir: Thư mục workspace.
            command: Lệnh test.
            context: PipelineContext.
            attempt: Số thứ tự lần thử.

        Returns:
            ExecutionResult.
        """
        t0 = perf_counter()
        result = await self.sandbox.run_command(workspace_dir, command)
        duration_ms = int((perf_counter() - t0) * 1000)

        context.collector.add_span(
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

    async def _commit(
        self,
        workspace_dir: Path,
        prompt: str,
        context: PipelineContext,
    ) -> tuple[str, list[str]]:
        """Commit thay đổi + ghi span.

        Args:
            workspace_dir: Thư mục workspace.
            prompt: Prompt gốc.
            context: PipelineContext.

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

        context.collector.add_span(
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

    def _build_initial_messages(self, prompt: str) -> list[dict[str, str]]:
        """Xây dựng messages ban đầu.

        Args:
            prompt: Prompt gốc.

        Returns:
            List messages cho LLM lần gọi đầu.
        """
        return [
            {"role": "system", "content": configs.orchestrator.system_prompt},
            {"role": "user", "content": f"Yêu cầu: {prompt}"},
        ]

    @staticmethod
    def _build_retry_messages(
        base: list[dict[str, str]],
        previous_solution: AgentPatchResponse,
        error_log: str,
        test_command: str,
    ) -> list[dict[str, str]]:
        """Xây dựng messages retry (không tích lũy).

        Args:
            base: Messages gốc.
            previous_solution: Solution vừa fail.
            error_log: Log lỗi.
            test_command: Lệnh test.

        Returns:
            List messages cho lần retry.
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
                    "Có thể dùng action='update' với edits nếu chỉ cần sửa nhỏ."
                ),
            },
        ]


# ============================================================
# Module-level helpers
# ============================================================


def _status_event(step: StatusStep, message: str) -> str:
    """Tạo SSE event status.

    Args:
        step: Bước pipeline.
        message: Nội dung.

    Returns:
        Chuỗi SSE.
    """
    return format_sse("status", StatusEventPayload(step=step, message=message))


def _file_event(result: ApplyResult) -> str:
    """Tạo SSE event file.

    Args:
        result: Kết quả apply.

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


def _build_commit_msg(prompt: str, max_len: int = 60) -> str:
    """Tạo commit message ngắn gọn.

    Args:
        prompt: Prompt gốc.
        max_len: Độ dài tối đa.

    Returns:
        Commit message.
    """
    one_line = " ".join(prompt.split())
    if len(one_line) <= max_len:
        short = one_line
    else:
        cut = one_line[:max_len]
        if " " in cut:
            cut = cut.rsplit(" ", 1)[0]
        short = cut + "..."
    return f"feat: vibe solution for '{short}'"


def _tail(text: str, max_chars: int) -> str:
    """Lấy phần cuối của text.

    Args:
        text: Chuỗi gốc.
        max_chars: Số ký tự tối đa.

    Returns:
        Chuỗi đã cắt.
    """
    if len(text) <= max_chars:
        return text
    return "..." + text[-max_chars:]


def _truncate_messages(
    messages: list[dict[str, str]],
    max_chars: int = 4000,
) -> list[dict[str, str]]:
    """Truncate messages để span không phình quá.

    Args:
        messages: Danh sách messages.
        max_chars: Số ký tự tối đa mỗi message.

    Returns:
        List messages đã truncate.
    """
    result: list[dict[str, str]] = []
    for m in messages:
        content = m.get("content", "")
        if len(content) > max_chars:
            half = max_chars // 2
            content = content[:half] + "...[truncated]..." + content[-half:]
        result.append({"role": m.get("role", ""), "content": content})
    return result


__all__ = ["CoderAgent"]