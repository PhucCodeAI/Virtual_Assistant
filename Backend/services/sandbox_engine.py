"""Module quản lý và thực thi Sandbox bằng Docker CLI qua Asyncio."""

import asyncio
import time
from pathlib import Path

from dtos.sandbox import ExecutionResult


class SandboxEngine:
    """Động cơ thực thi mã nguồn an toàn trong container Docker cô lập."""

    def __init__(self, image: str = "python:3.11-slim", timeout_sec: int = 30) -> None:
        """Khởi tạo SandboxEngine.

        Args:
            image (str): Docker image sử dụng làm môi trường thực thi.
            timeout_sec (int): Thời gian tối đa cho phép một tiến trình chạy (giây).
        """
        self.image = image
        self.timeout_sec = timeout_sec

    async def run_command(self, workspace_path: Path, command: list[str]) -> ExecutionResult:
        """Thực thi một câu lệnh bên trong container Docker mount tới workspace.

        Args:
            workspace_path (Path): Đường dẫn thư mục làm việc trên máy host cần mount.
            command (list[str]): Lệnh và các tham số cần chạy (ví dụ: ["pytest"]).

        Returns:
            ExecutionResult: DTO chứa mã thoát, stdout, stderr và thời gian chạy.
        """
        abs_path = str(workspace_path.resolve())
        docker_args = [
            "docker", "run", "--rm",
            "--network", "none",
            "--memory", "512m",
            "--cpus", "1.0",
            "-e", "PYTHONPATH=/workspace",
            "-v", f"{abs_path}:/workspace",
            "-w", "/workspace",
            self.image,
            *command,
        ]

        start_time = time.perf_counter()
        process = None

        try:
            process = await asyncio.create_subprocess_exec(
                *docker_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_sec,
            )
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)

            return ExecutionResult(
                exit_code=process.returncode or 0,
                stdout=stdout_bytes.decode("utf-8", errors="replace"),
                stderr=stderr_bytes.decode("utf-8", errors="replace"),
                duration_ms=elapsed_ms,
                is_timeout=False,
            )

        except asyncio.TimeoutError:
            if process:
                process.kill()
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Lệnh bị hủy do chạy vượt quá {self.timeout_sec}s.",
                duration_ms=elapsed_ms,
                is_timeout=True,
            )
        except Exception as exc:
            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Lỗi khởi tạo Docker CLI: {exc}",
                duration_ms=elapsed_ms,
                is_timeout=False,
            )