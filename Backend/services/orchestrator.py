"""Module điều phối trung tâm của AI Coding Agent (Business Logic Layer)."""

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path
from time import perf_counter

from dtos.agent import AgentPatchResponse
from dtos.orchestrator import (
    CommitEventPayload,
    DoneEventPayload,
    ErrorEventPayload,
    InputRequest,
    StatusEventPayload,
    TokenEventPayload,
    format_sse,
)
from loguru import logger
from services.git_service import GitService
from services.llm_client import LLMClient
from services.sandbox_engine import SandboxEngine
from services.workspace_manager import WorkspaceManager


class Orchestrator:
    """Bộ điều phối vòng lặp thực thi tự quyết của Agent kết hợp Docker Sandbox và Git."""

    def __init__(
        self,
        llm_client: LLMClient,
        sandbox: SandboxEngine,
        git: GitService,
        workspace_base: str = "./storage/sandboxes",
        max_retries: int = 3,
    ) -> None:
        """Khởi tạo Orchestrator.

        Args:
            llm_client (LLMClient): Client giao tiếp mô hình LLM.
            sandbox (SandboxEngine): Engine thực thi Docker Sandbox.
            git (GitService): Dịch vụ quản lý Git.
            workspace_base (str): Thư mục gốc chứa các sandbox làm việc.
            max_retries (int): Số lần tự sửa lỗi tối đa khi kiểm thử thất bại.
        """
        self.llm_client = llm_client
        self.sandbox = sandbox
        self.git = git
        self.workspace_base = Path(workspace_base)
        self.max_retries = max_retries
        self.workspace_base.mkdir(parents=True, exist_ok=True)

    async def execute_stream(self, req: InputRequest) -> AsyncGenerator[str, None]:
        """Thực thi chu trình lập trình tự quyết và stream kết quả về UI qua SSE.

        Args:
            req (InputRequest): Yêu cầu từ người dùng.

        Yields:
            AsyncGenerator[str, None]: Dòng sự kiện SSE dạng văn bản thô.
        """
        start_time = perf_counter()
        session_id = req.session_id or "default_workspace"
        workspace_dir = self.workspace_base / session_id
        workspace = WorkspaceManager(workspace_dir)

        input_token = 0
        reasoning_token = 0
        cache_token = 0
        total_tokens = 0
        total_cost = 0.0

        try:
            await self.git.init_repo_if_needed(workspace_dir)

            system_prompt = (
                "Bạn là Senior AI Coding Agent cấp cao. Bạn phải giải quyết yêu cầu bằng cách viết mã nguồn "
                "và BẮT BUỘC viết file unit test hoàn chỉnh (dùng unittest chuẩn Python).\n"
                "QUY TẮC SỐNG CÒN:\n"
                "1. Tên file test phải bắt đầu bằng 'test_' (ví dụ: 'test_calculator.py').\n"
                "2. File test phải import module trực tiếp (ví dụ: from calculator import Calculator).\n"
                "3. Lệnh test_command nên dùng: ['python', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py']"
            )
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Yêu cầu: {req.prompt}"},
            ]

            success = False
            last_solution: AgentPatchResponse | None = None

            for attempt in range(1, self.max_retries + 1):
                yield format_sse(
                    "status",
                    StatusEventPayload(
                        step="plan",
                        message=f"Đang sinh mã nguồn & unit test (Lần {attempt}/{self.max_retries})...",
                    ),
                )

                llm_res = await self.llm_client.structured_generate(
                    messages=messages,
                    response_model=AgentPatchResponse,
                )
                solution: AgentPatchResponse = llm_res["response"]
                last_solution = solution

                info = llm_res.get("info") or {}
                input_token += info.get("input_token", 0)
                reasoning_token += info.get("reasoning_token", 0)
                cache_token += info.get("cached_token", 0)
                total_tokens += info.get("total_token", 0)
                total_cost += info.get("cost", 0.0)

                yield format_sse(
                    "status",
                    StatusEventPayload(step="sandbox", message="Đang nạp file vào Docker Sandbox..."),
                )
                for f_action in solution.files:
                    workspace.apply_file_action(f_action)

                yield format_sse(
                    "status",
                    StatusEventPayload(step="test", message=f"Đang chạy test: {' '.join(solution.test_command)}..."),
                )
                test_result = await self.sandbox.run_command(workspace_dir, solution.test_command)

                if test_result.exit_code == 0:
                    success = True
                    break

                error_log = (test_result.stderr or test_result.stdout).strip()
                logger.warning(f"Lần {attempt} thất bại. Log:\n{error_log}")

                if attempt < self.max_retries:
                    yield format_sse(
                        "status",
                        StatusEventPayload(
                            step="test",
                            message=f"Kiểm thử thất bại (Lần {attempt})! Đang phân tích lỗi để tự sửa mã...",
                        ),
                    )
                    messages.append({
                        "role": "assistant",
                        "content": f"Tôi đã sinh code nhưng gặp lỗi khi kiểm thử:\n{error_log}",
                    })
                    messages.append({
                        "role": "user",
                        "content": (
                            f"Lệnh kiểm thử '{' '.join(solution.test_command)}' thất bại.\n"
                            f"Chi tiết lỗi:\n{error_log}\n"
                            "Hãy phân tích nguyên nhân lỗi import/logic và sửa lại mã nguồn hoặc file test."
                        ),
                    })

            if not success:
                yield format_sse(
                    "error",
                    ErrorEventPayload(
                        code="TEST_MAX_RETRIES",
                        message=f"Đã thử tự sửa lỗi {self.max_retries} lần nhưng không vượt qua được kiểm thử.",
                    ),
                )
                total_time = int((perf_counter() - start_time) * 1000)
                yield format_sse(
                    "done",
                    DoneEventPayload(
                        input_token=input_token,
                        reasoning_token=reasoning_token,
                        cache_token=cache_token,
                        total_time=total_time,
                        total_token=total_tokens,
                        cost=total_cost,
                    ),
                )
                return

            yield format_sse("status", StatusEventPayload(step="git", message="Kiểm thử thành công! Tạo Git commit..."))
            commit_hash, changed_files = await self.git.commit_changes(
                workspace_dir,
                message=f"feat: vibe solution for '{req.prompt[:35]}'",
            )

            if commit_hash:
                yield format_sse(
                    "commit",
                    CommitEventPayload(
                        hash=commit_hash,
                        message=f"feat: vibe solution for '{req.prompt[:35]}'",
                        files=changed_files,
                    ),
                )

            if last_solution:
                yield format_sse("status", StatusEventPayload(step="generate", message="Hoàn thiện lời giải thích..."))
                explanation_markdown = (
                    f"### Giải pháp hoàn tất\n\n{last_solution.explanation}\n\n"
                    "**Các tệp tin đã tạo và kiểm thử thành công:**\n"
                )
                for f in last_solution.files:
                    explanation_markdown += f"- `{f.path}`\n"

                for word in explanation_markdown.split(" "):
                    yield format_sse("token", TokenEventPayload(delta=word + " "))
                    await asyncio.sleep(0.015)

            total_time = int((perf_counter() - start_time) * 1000)
            yield format_sse(
                "done",
                DoneEventPayload(
                    input_token=input_token,
                    reasoning_token=reasoning_token,
                    cache_token=cache_token,
                    total_time=total_time,
                    total_token=total_tokens,
                    cost=total_cost,
                ),
            )

        except Exception as exc:
            logger.exception("Lỗi không mong muốn trong Orchestrator pipeline")
            yield format_sse("error", ErrorEventPayload(code="SYSTEM_ERROR", message=str(exc)))
            total_time = int((perf_counter() - start_time) * 1000)
            yield format_sse(
                "done",
                DoneEventPayload(
                    input_token=input_token,
                    reasoning_token=reasoning_token,
                    cache_token=cache_token,
                    total_time=total_time,
                    total_token=total_tokens,
                    cost=total_cost,
                ),
            )