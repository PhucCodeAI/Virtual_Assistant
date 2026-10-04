# Backend/services/sandbox_engine.py
"""Module quản lý và thực thi Sandbox bằng Docker CLI qua Asyncio.

Đặc điểm chính:
    - Cô lập tuyệt đối: network off, memory/cpu limit, drop caps, user 1000:1000.
    - Timeout kép: kill Docker CLI + force kill container qua `docker kill` để
      tránh zombie container chạy nền.
    - Truncate stdout/stderr để không làm phình trace payload.
    - Exception sử dụng từ package `exceptions`.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from dtos.sandbox import ExecutionResult
from exceptions import DockerUnavailableError
from loguru import logger

_MAX_OUTPUT_BYTES = 256 * 1024  # 256 KB


class SandboxEngine:
    """Động cơ thực thi mã nguồn an toàn trong container Docker cô lập.

    Mỗi lần `run_command` tạo một container mới với tên unique (không trùng
    giữa các lần chạy song song), đảm bảo cleanup sạch kể cả khi timeout.
    """

    def __init__(
        self,
        image: str = "python:3.12-slim",
        timeout_sec: int = 30,
        memory_limit: str = "512m",
        cpu_limit: str = "1.0",
    ) -> None:
        """Khởi tạo SandboxEngine.

        Args:
            image: Docker image sử dụng làm môi trường thực thi.
            timeout_sec: Thời gian tối đa cho phép một tiến trình chạy (giây).
            memory_limit: Giới hạn RAM cho container (VD: '512m', '1g').
            cpu_limit: Số CPU ảo được cấp cho container.
        """
        self.image = image
        self.timeout_sec = timeout_sec
        self.memory_limit = memory_limit
        self.cpu_limit = cpu_limit

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------
    async def run_command(
        self,
        workspace_path: Path,
        command: list[str],
    ) -> ExecutionResult:
        """Thực thi một câu lệnh bên trong container Docker mount tới workspace.

        Args:
            workspace_path: Đường dẫn thư mục làm việc trên host cần mount.
            command: Lệnh và tham số cần chạy (VD: ['python', '-m', 'unittest']).

        Returns:
            ExecutionResult chứa mã thoát, stdout, stderr và thời gian chạy.

        Raises:
            DockerUnavailableError: Khi docker CLI không tồn tại hoặc daemon chết.
        """
        container_name = f"sandbox_{uuid.uuid4().hex[:12]}"
        abs_path = str(workspace_path.resolve())
        docker_args = self._build_docker_args(container_name, abs_path, command)

        logger.debug(
            "Sandbox exec | container={} cmd={}",
            container_name,
            " ".join(command),
        )

        process: asyncio.subprocess.Process | None = None
        start = asyncio.get_event_loop().time()

        try:
            process = await asyncio.create_subprocess_exec(
                *docker_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise DockerUnavailableError(
                "Không tìm thấy docker CLI trên hệ thống",
                context={"image": self.image},
            ) from e
        except OSError as e:
            raise DockerUnavailableError(
                f"Không khởi tạo được tiến trình docker: {e}",
                context={"image": self.image},
            ) from e

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout_sec,
            )
            elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)

            return ExecutionResult(
                exit_code=_normalize_returncode(process.returncode),
                stdout=_truncate(stdout_bytes),
                stderr=_truncate(stderr_bytes),
                duration_ms=elapsed_ms,
                is_timeout=False,
            )

        except TimeoutError:
            elapsed_ms = int((asyncio.get_event_loop().time() - start) * 1000)
            logger.warning(
                "Sandbox timeout sau {}s | container={}",
                self.timeout_sec,
                container_name,
            )
            await self._kill_container(container_name, process)
            return ExecutionResult(
                exit_code=-1,
                stdout="",
                stderr=f"Lệnh bị hủy do chạy vượt quá {self.timeout_sec}s.",
                duration_ms=elapsed_ms,
                is_timeout=True,
            )

    async def cleanup_orphans(self, prefix: str = "sandbox_") -> int:
        """Dọn dẹp các container rác còn sót lại từ lần chạy trước.

        Gọi trong lifespan shutdown để đảm bảo không leak container.

        Args:
            prefix: Prefix tên container cần dọn.

        Returns:
            Số container đã kill.
        """
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "ps", "-aq",
                "--filter", f"name={prefix}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()
        except (FileNotFoundError, OSError) as e:
            logger.warning("Không dọn được orphan container: {}", e)
            return 0

        container_ids = [c for c in stdout.decode().split() if c]
        if not container_ids:
            return 0

        logger.info("Dọn {} orphan container", len(container_ids))
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "rm", "-f", *container_ids,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        except (FileNotFoundError, OSError) as e:
            logger.warning("Kill orphan container thất bại: {}", e)
            return 0

        return len(container_ids)

    # --------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------
    def _build_docker_args(
        self,
        container_name: str,
        workspace_abs_path: str,
        command: list[str],
    ) -> list[str]:
        """Đóng gói danh sách tham số docker run với đầy đủ security flags.

        Args:
            container_name: Tên container unique.
            workspace_abs_path: Đường dẫn tuyệt đối tới workspace trên host.
            command: Lệnh cần chạy trong container.

        Returns:
            List tham số để truyền vào `docker run`.
        """
        return [
            "docker", "run", "--rm",
            "--name", container_name,
            "--network", "none",
            "--memory", self.memory_limit,
            "--memory-swap", self.memory_limit,
            "--cpus", self.cpu_limit,
            "--pids-limit", "128",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", "1000:1000",
            "-e", "PYTHONPATH=/workspace",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-e", "PYTHONUNBUFFERED=1",
            "-v", f"{workspace_abs_path}:/workspace",
            "-w", "/workspace",
            self.image,
            *command,
        ]

    async def _kill_container(
        self,
        container_name: str,
        process: asyncio.subprocess.Process | None,
    ) -> None:
        """Kill container và tiến trình docker CLI một cách triệt để.

        Thứ tự:
            1. Gửi `docker kill <name>` để dừng container ngay lập tức.
            2. Terminate docker CLI process.
            3. Nếu CLI không chết trong 2s, kill cứng.

        Args:
            container_name: Tên container cần kill.
            process: Tiến trình docker CLI đang chạy.
        """
        try:
            kill_proc = await asyncio.create_subprocess_exec(
                "docker", "kill", container_name,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(kill_proc.wait(), timeout=5)
        except (TimeoutError, FileNotFoundError, OSError) as e:
            logger.warning(
                "docker kill {} thất bại: {} — fallback kill CLI",
                container_name,
                e,
            )

        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=2)
            except TimeoutError:
                process.kill()
                await process.wait()


# ============================================================
# Module-level helpers
# ============================================================
def _normalize_returncode(returncode: int | None) -> int:
    """Chuẩn hóa returncode None (process chưa exit) thành -1.

    Args:
        returncode: Mã thoát thô từ asyncio.subprocess.

    Returns:
        Mã thoát hợp lệ (-1 nếu None).
    """
    if returncode is None:
        return -1
    return returncode


def _truncate(data: bytes, limit: int = _MAX_OUTPUT_BYTES) -> str:
    """Decode bytes UTF-8 và truncate nếu vượt quá giới hạn.

    Giữ đầu và cuối output (quan trọng cho traceback), bỏ giữa nếu quá dài.

    Args:
        data: Bytes thô từ stdout/stderr.
        limit: Số byte tối đa giữ lại.

    Returns:
        Chuỗi đã decode và truncate (có marker '...[truncated]...' nếu cắt).
    """
    if not data:
        return ""

    truncated = False
    if len(data) > limit:
        half = limit // 2
        data = data[:half] + b"\n...[truncated]...\n" + data[-half:]
        truncated = True

    text = data.decode("utf-8", errors="replace")
    if truncated:
        logger.debug("Output bị truncate xuống {} byte", limit)
    return text


__all__ = ["SandboxEngine"]


if __name__ == "__main__":
    import shutil
    import tempfile

    async def _test() -> None:
        tmp = Path(tempfile.mkdtemp(prefix="sandbox_test_"))
        try:
            (tmp / "hello.py").write_text("print('hello from sandbox')\n")
            engine = SandboxEngine(image="python:3.12-slim", timeout_sec=30)

            print("=== 1. Chạy lệnh thành công ===")
            result = await engine.run_command(tmp, ["python", "hello.py"])
            print(result.model_dump())
            assert result.exit_code == 0
            assert "hello from sandbox" in result.stdout

            print("\n=== 2. Lệnh fail (exit code != 0) ===")
            result = await engine.run_command(tmp, ["python", "-c", "raise ValueError('boom')"])
            print(f"exit_code={result.exit_code}")
            assert result.exit_code != 0
            assert "ValueError" in result.stderr

            print("\n=== 3. Timeout ===")
            fast_engine = SandboxEngine(image="python:3.12-slim", timeout_sec=2)
            result = await fast_engine.run_command(
                tmp, ["python", "-c", "import time; time.sleep(10)"]
            )
            print(result.model_dump())
            assert result.is_timeout is True
            assert result.exit_code == -1

            print("\n=== 4. Không có network ===")
            result = await engine.run_command(
                tmp,
                ["python", "-c", "import urllib.request; urllib.request.urlopen('http://1.1.1.1', timeout=2)"],
            )
            assert result.exit_code != 0
            print("PASS: network bị chặn")

            print("\n=== 5. Cleanup orphans ===")
            killed = await engine.cleanup_orphans()
            print(f"Đã dọn {killed} container rác")

            print("\nTẤT CẢ TEST PASS")

        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    asyncio.run(_test())