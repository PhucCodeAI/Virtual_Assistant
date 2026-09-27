"""Module quản lý vòng đời phiên bản mã nguồn bằng Git CLI qua Asyncio."""

import asyncio
from pathlib import Path


class GitService:
    """Dịch vụ thực hiện các thao tác Git tự động trong workspace."""

    @staticmethod
    async def _exec_git(workspace_path: Path, args: list[str]) -> tuple[int, str]:
        """Chạy lệnh git trong thư mục chỉ định.

        Args:
            workspace_path (Path): Thư mục chứa repository.
            args (list[str]): Danh sách tham số lệnh git.

        Returns:
            tuple[int, str]: Mã thoát và chuỗi kết quả (stdout/stderr).
        """
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=workspace_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        output = stdout.decode("utf-8", errors="replace") if process.returncode == 0 else stderr.decode("utf-8", errors="replace")
        return process.returncode or 0, output.strip()

    async def init_repo_if_needed(self, workspace_path: Path) -> None:
        """Khởi tạo Git repo và cấu hình identity nếu chưa tồn tại.

        Args:
            workspace_path (Path): Thư mục cần kiểm tra hoặc khởi tạo.
        """
        if not (workspace_path / ".git").exists():
            await self._exec_git(workspace_path, ["init"])
            await self._exec_git(workspace_path, ["config", "user.name", "AI Coding Agent"])
            await self._exec_git(workspace_path, ["config", "user.email", "agent@vibecode.local"])

    async def commit_changes(self, workspace_path: Path, message: str) -> tuple[str, list[str]]:
        """Stage toàn bộ thay đổi và tạo commit mới.

        Args:
            workspace_path (Path): Thư mục git repository.
            message (str): Thông điệp commit.

        Returns:
            tuple[str, list[str]]: Mã SHA ngắn (7 ký tự) và danh sách file đã thay đổi.
        """
        await self.init_repo_if_needed(workspace_path)

        _, status_out = await self._exec_git(workspace_path, ["status", "--porcelain"])
        changed_files = [line[3:].strip() for line in status_out.splitlines() if line.strip()]

        if not changed_files:
            return "", []

        await self._exec_git(workspace_path, ["add", "."])
        await self._exec_git(workspace_path, ["commit", "-m", message])
        _, commit_hash = await self._exec_git(workspace_path, ["rev-parse", "--short", "HEAD"])

        return commit_hash, changed_files