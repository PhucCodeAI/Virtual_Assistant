"""Module điều phối trung tâm của AI Coding Agent kết hợp Trace Engine (Business Logic Layer)."""

import asyncio
import logging
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
from services.git_service import GitService
from services.llm_client import LLMClient
from services.sandbox_engine import SandboxEngine
from services.trace_service import TraceService
from services.workspace_manager import WorkspaceManager

logger = logging.getLogger(__name__)


class Orchestrator:
    """Bộ điều phối vòng lặp thực thi tự quyết của Agent kết hợp Docker, Git và Tracing."""

    def __init__(
        self,
        llm_client: LLMClient,
        sandbox: SandboxEngine,
        git: GitService,
        trace_service: TraceService,
        workspace_base: str = "./storage/sandboxes",
        max_retries: int = 3,
    ) -> None:
        """Khởi tạo Orchestrator.

        Args:
            llm_client: Client giao tiếp mô hình LLM.
            sandbox: Engine thực thi Docker Sandbox an toàn.
            git: Dịch vụ quản lý mã nguồn Git.
            trace_service: Dịch vụ ghi nhận và quản lý Tracing đa tầng.
            workspace_base: Thư mục gốc chứa các sandbox làm việc.
            max_retries: Số lần tự sửa lỗi tối đa khi unit test thất bại.
        """
        self.llm_client = llm_client
        self.sandbox = sandbox
        self.git = git
        self.trace_service = trace_service
        self.workspace_base = Path(workspace_base)
        self.max_retries = max_retries
        self.workspace_base.mkdir(parents=True, exist_ok=True)

    async def execute_stream(self, req: InputRequest) -> AsyncGenerator[str, None]:
        """Thực thi chu trình lập trình tự quyết, ghi nhận trace và stream kết quả về UI qua SSE.

        Args:
            req: Yêu cầu lập trình từ người dùng kèm session_id.

        Yields:
            Các sự kiện SSE dạng chuỗi đã định dạng chuẩn text/event-stream.
        """
        start_time = perf_counter()
        session_id = req.session_id or "default_workspace"
        workspace_dir = self.workspace_base / session_id
        workspace = WorkspaceManager(workspace_dir)

        # 1. Khởi tạo Trace Collector cho phiên hiện tại
        collector = self.trace_service.create_collector(
            session_id=session_id, prompt=req.prompt
        )

        input_token = 0
        output_token = 0
        reasoning_token = 0
        cache_token = 0
        total_tokens = 0
        total_cost = 0.0
        final_status = "FAILED"
        err_msg: str | None = None

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

                # TRACE BƯỚC 1: Gọi LLM
                t_llm = perf_counter()
                llm_res = await self.llm_client.structured_generate(
                    messages=messages,
                    response_model=AgentPatchResponse,
                )
                llm_duration = int((perf_counter() - t_llm) * 1000)

                solution: AgentPatchResponse = llm_res["response"]
                last_solution = solution

                info = llm_res.get("info") or {}
                cur_in = info.get("input_token", 0)
                cur_out = info.get("output_token", 0)
                cur_reason = info.get("reasoning_token", 0)
                cur_cache = info.get("cached_token", 0)
                cur_total = info.get("total_token", 0)
                cur_cost = info.get("cost", 0.0)

                input_token += cur_in
                output_token += cur_out
                reasoning_token += cur_reason
                cache_token += cur_cache
                total_tokens += cur_total
                total_cost += cur_cost

                collector.add_span(
                    name=f"LLM Generation (Attempt {attempt})",
                    span_type="LLM",
                    duration_ms=llm_duration,
                    input_data={"messages": messages},
                    output_data=solution.model_dump(),
                    metadata={"tokens": info, "cost": cur_cost},
                    status="OK",
                )

                # Nạp file vào Sandbox an toàn
                yield format_sse(
                    "status",
                    StatusEventPayload(
                        step="sandbox", message="Đang nạp file vào Docker Sandbox..."
                    ),
                )
                for f_action in solution.files:
                    workspace.apply_file_action(f_action)

                # TRACE BƯỚC 2: Thực thi kiểm thử Docker Sandbox
                yield format_sse(
                    "status",
                    StatusEventPayload(
                        step="test",
                        message=f"Đang chạy test: {' '.join(solution.test_command)}...",
                    ),
                )
                t_test = perf_counter()
                test_result = await self.sandbox.run_command(
                    workspace_dir, solution.test_command
                )
                test_duration = int((perf_counter() - t_test) * 1000)

                collector.add_span(
                    name=f"Docker Test (Attempt {attempt})",
                    span_type="TOOL",
                    duration_ms=test_duration,
                    input_data={"command": solution.test_command},
                    output_data={
                        "stdout": test_result.stdout,
                        "stderr": test_result.stderr,
                    },
                    metadata={"exit_code": test_result.exit_code},
                    status="OK" if test_result.exit_code == 0 else "ERROR",
                )

                if test_result.exit_code == 0:
                    success = True
                    break

                error_log = (test_result.stderr or test_result.stdout).strip()
                logger.warning(
                    "Lần %s kiểm thử thất bại. Chi tiết:\n%s", attempt, error_log
                )

                if attempt < self.max_retries:
                    yield format_sse(
                        "status",
                        StatusEventPayload(
                            step="test",
                            message=f"Kiểm thử thất bại (Lần {attempt})! Đang phân tích lỗi để tự sửa mã...",
                        ),
                    )
                    messages.append(
                        {
                            "role": "assistant",
                            "content": f"Tôi đã sinh code nhưng gặp lỗi khi kiểm thử:\n{error_log}",
                        }
                    )
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Lệnh kiểm thử '{' '.join(solution.test_command)}' thất bại.\n"
                                f"Chi tiết lỗi:\n{error_log}\n"
                                "Hãy phân tích nguyên nhân lỗi import/logic và sửa lại mã nguồn hoặc file test."
                            ),
                        }
                    )

            if not success:
                err_msg = f"Đã thử tự sửa lỗi {self.max_retries} lần nhưng không vượt qua được kiểm thử."
                yield format_sse(
                    "error",
                    ErrorEventPayload(
                        code="TEST_MAX_RETRIES",
                        message=err_msg,
                    ),
                )
                return

            # TRACE BƯỚC 3: Tạo Git Commit
            yield format_sse(
                "status",
                StatusEventPayload(
                    step="git", message="Kiểm thử thành công! Tạo Git commit..."
                ),
            )
            t_git = perf_counter()
            commit_hash, changed_files = await self.git.commit_changes(
                workspace_dir,
                message=f"feat: vibe solution for '{req.prompt[:35]}'",
            )
            git_duration = int((perf_counter() - t_git) * 1000)

            collector.add_span(
                name="Git Commit",
                span_type="TOOL",
                duration_ms=git_duration,
                output_data={"commit_hash": commit_hash, "files": changed_files},
                status="OK",
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

            # Stream lời giải thích về UI
            if last_solution:
                yield format_sse(
                    "status",
                    StatusEventPayload(
                        step="generate", message="Hoàn thiện lời giải thích..."
                    ),
                )
                explanation_markdown = (
                    f"### Giải pháp hoàn tất\n\n{last_solution.explanation}\n\n"
                    "**Các tệp tin đã tạo và kiểm thử thành công:**\n"
                )
                for f in last_solution.files:
                    explanation_markdown += f"- `{f.path}`\n"

                for word in explanation_markdown.split(" "):
                    yield format_sse("token", TokenEventPayload(delta=word + " "))
                    await asyncio.sleep(0.015)

            final_status = "SUCCESS"

        except Exception as exc:
            err_msg = str(exc)
            logger.exception("Lỗi không mong muốn trong Orchestrator pipeline")
            yield format_sse(
                "error", ErrorEventPayload(code="SYSTEM_ERROR", message=err_msg)
            )

        finally:
            # 2. Chốt số liệu và lưu Trace đa tầng (Storage + Database)
            total_time = int((perf_counter() - start_time) * 1000)
            metrics_summary = {
                "total_tokens": total_tokens,
                "input_tokens": input_token,
                "output_tokens": output_token,
                "reasoning_tokens": reasoning_token,
                "cache_tokens": cache_token,
                "cost": total_cost,
            }

            try:
                await self.trace_service.save_session_trace(
                    collector=collector,
                    status=final_status,
                    duration_ms=total_time,
                    metrics=metrics_summary,
                    error_message=err_msg,
                )
            except Exception as trace_err:
                logger.error("Lỗi khi lưu trace đa tầng: %s", trace_err)

            # Đảm bảo event 'done' luôn được gửi kèm trace_id để Frontend mở Waterfall
            yield format_sse(
                "done",
                DoneEventPayload(
                    input_token=input_token,
                    reasoning_token=reasoning_token,
                    cache_token=cache_token,
                    total_time=total_time,
                    total_token=total_tokens,
                    cost=total_cost,
                    trace_id=collector.trace_id,
                ),
            )
