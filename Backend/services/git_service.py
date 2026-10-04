# Backend/services/git_service.py
"""Module quản lý vòng đời phiên bản mã nguồn bằng Git CLI qua Asyncio.

Đặc điểm chính:
    - Parse `git status --porcelain -z` (null-separated) để xử lý đúng filename
      chứa space và ký tự đặc biệt.
    - Raise GitCommandError khi exit code != 0 (không silent failure).
    - Tự sinh .gitignore chuẩn Python để tránh add rác vào commit.
    - Cấu hình core.autocrlf=false để ổn định line ending giữa host/sandbox.
    - Exception sử dụng từ package `exceptions`.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from exceptions import GitCommandError
from loguru import logger

_DEFAULT_GITIGNORE = """\
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/

# IDE
.vscode/
.idea/
*.swp

# OS
.DS_Store
Thumbs.db

# Project artifacts
*.log
.env
.env.*
"""


class GitService:
    """Dịch vụ thực hiện các thao tác Git tự động trong workspace."""

    def __init__(self, gitignore_content: str | None = None) -> None:
        """Khởi tạo GitService.

        Args:
            gitignore_content: Nội dung .gitignore tùy chỉnh. None = dùng default.
        """
        self.gitignore_content = gitignore_content or _DEFAULT_GITIGNORE

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------
    async def init_repo_if_needed(self, workspace_path: Path) -> bool:
        """Khởi tạo Git repo và cấu hình identity nếu chưa tồn tại.

        Args:
            workspace_path: Thư mục cần kiểm tra hoặc khởi tạo.

        Returns:
            True nếu vừa khởi tạo repo mới, False nếu đã tồn tại.
        """
        if (workspace_path / ".git").exists():
            return False

        logger.info("Khởi tạo git repo tại {}", workspace_path)
        await self._exec_git(workspace_path, ["init"])

        await self._exec_git(workspace_path, ["config", "user.name", "AI Coding Agent"])
        await self._exec_git(
            workspace_path,
            ["config", "user.email", "agent@vibecode.local"],
        )

        await self._exec_git(workspace_path, ["config", "core.autocrlf", "false"])
        await self._write_gitignore(workspace_path)
        return True

    async def commit_changes(
        self,
        workspace_path: Path,
        message: str,
    ) -> tuple[str, list[str]]:
        """Stage toàn bộ thay đổi và tạo commit mới.

        Args:
            workspace_path: Thư mục git repository.
            message: Thông điệp commit.

        Returns:
            Tuple (commit_hash_short, changed_files). Nếu không có gì thay đổi,
            trả về ("", []).

        Raises:
            GitCommandError: Khi git add hoặc git commit thất bại.
        """
        await self.init_repo_if_needed(workspace_path)

        changed_files = await self._get_changed_files(workspace_path)
        if not changed_files:
            logger.debug("Không có file thay đổi để commit")
            return "", []

        await self._exec_git(workspace_path, ["add", "-A"])

        safe_message = _sanitize_commit_message(message)
        await self._exec_git(workspace_path, ["commit", "-m", safe_message])

        commit_hash = await self._get_head_short_hash(workspace_path)
        logger.info(
            "Đã commit {} file(s) | hash={} | message={!r}",
            len(changed_files),
            commit_hash,
            safe_message,
        )
        return commit_hash, changed_files

    async def get_changed_files(self, workspace_path: Path) -> list[str]:
        """Trả về danh sách file đã thay đổi (public wrapper).

        Args:
            workspace_path: Thư mục git repository.

        Returns:
            Danh sách đường dẫn tương đối (dùng '/' làm separator).

        Raises:
            GitCommandError: Khi git status thất bại.
        """
        return await self._get_changed_files(workspace_path)

    # --------------------------------------------------------
    # Internal helpers
    # --------------------------------------------------------
    async def _get_changed_files(self, workspace_path: Path) -> list[str]:
        """Lấy danh sách file thay đổi qua `git status --porcelain -z`.

        Dùng -z để separator là null byte — an toàn với filename chứa space,
        newline, dấu ngoặc kép.

        Args:
            workspace_path: Thư mục git repository.

        Returns:
            Danh sách đường dẫn tương đối.

        Raises:
            GitCommandError: Khi git status thất bại.
        """
        _, raw = await self._exec_git(
            workspace_path,
            ["status", "--porcelain", "-z"],
        )

        if not raw:
            return []

        files: list[str] = []
        for entry in raw.split("\0"):
            if len(entry) < 4:
                continue
            status = entry[:2]
            path = entry[3:]
            if "R" in status or "C" in status:
                logger.debug("Bỏ qua entry rename/copy: {}", entry[:80])
                continue
            files.append(path)

        return files

    async def _get_head_short_hash(self, workspace_path: Path) -> str:
        """Đọc hash ngắn của HEAD.

        Args:
            workspace_path: Thư mục git repository.

        Returns:
            Hash ngắn 7 ký tự.

        Raises:
            GitCommandError: Khi repo không có commit nào.
        """
        _, out = await self._exec_git(
            workspace_path,
            ["rev-parse", "--short", "HEAD"],
        )
        if not out:
            raise GitCommandError(
                "Không đọc được HEAD hash sau khi commit",
                args=["rev-parse", "--short", "HEAD"],
                exit_code=0,
                stderr="empty output",
            )
        return out.strip()

    async def _write_gitignore(self, workspace_path: Path) -> None:
        """Ghi file .gitignore mặc định nếu chưa tồn tại.

        Args:
            workspace_path: Thư mục git repository.
        """
        gitignore = workspace_path / ".gitignore"
        if gitignore.exists():
            return
        await asyncio.to_thread(
            gitignore.write_text,
            self.gitignore_content,
            encoding="utf-8",
        )

    @staticmethod
    async def _exec_git(
        workspace_path: Path,
        args: list[str],
    ) -> tuple[int, str]:
        """Chạy lệnh git trong thư mục chỉ định.

        Args:
            workspace_path: Thư mục chứa repository.
            args: Danh sách tham số lệnh git.

        Returns:
            Tuple (exit_code, stdout). Nếu exit_code != 0, raise GitCommandError.

        Raises:
            GitCommandError: Khi git trả về mã thoát khác 0 hoặc CLI không tồn tại.
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "git",
                *args,
                cwd=workspace_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as e:
            raise GitCommandError(
                "Không tìm thấy git CLI trên hệ thống",
                args=args,
                exit_code=-1,
                stderr=str(e),
            ) from e

        stdout_bytes, stderr_bytes = await process.communicate()
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        code = process.returncode if process.returncode is not None else -1

        if code != 0:
            raise GitCommandError(
                f"git {' '.join(args)} thất bại (exit {code})",
                args=args,
                exit_code=code,
                stderr=stderr,
            )

        return code, stdout.rstrip("\n")


# ============================================================
# Module-level helpers
# ============================================================
def _sanitize_commit_message(message: str, max_len: int = 72) -> str:
    """Chuẩn hóa commit message: bỏ newline, cắt an toàn theo từ.

    Args:
        message: Message gốc.
        max_len: Độ dài tối đa của subject line.

    Returns:
        Message đã chuẩn hóa.
    """
    one_line = " ".join(message.split())
    if len(one_line) <= max_len:
        return one_line
    cut = one_line[:max_len]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut + "..."


__all__ = ["GitService"]


if __name__ == "__main__":
    import shutil
    import tempfile

    async def _test() -> None:
        tmp = Path(tempfile.mkdtemp(prefix="git_test_"))
        try:
            svc = GitService()

            print("=== 1. Init repo ===")
            created = await svc.init_repo_if_needed(tmp)
            print(f"created={created}")
            assert created is True
            assert (tmp / ".git").exists()
            assert (tmp / ".gitignore").exists()

            print("\n=== 2. Init lần 2 → không làm gì ===")
            created = await svc.init_repo_if_needed(tmp)
            assert created is False
            print("PASS")

            print("\n=== 3. Commit khi không có gì thay đổi ===")
            h, files = await svc.commit_changes(tmp, "empty commit")
            print(f"hash={h!r} files={files}")
            assert h == "" and files == []

            print("\n=== 4. Commit file mới ===")
            (tmp / "hello.py").write_text("print('hi')\n")
            (tmp / "test_hello.py").write_text("def test_x(): pass\n")
            h, files = await svc.commit_changes(tmp, "feat: thêm hello world")
            print(f"hash={h} files={files}")
            assert h != ""
            assert "hello.py" in files

            print("\n=== 5. Filename có space ===")
            (tmp / "my file.py").write_text("x = 1\n")
            h, files = await svc.commit_changes(tmp, "feat: file có space")
            print(f"files={files}")
            assert "my file.py" in files

            print("\n=== 6. .gitignore hoạt động ===")
            (tmp / "__pycache__").mkdir()
            (tmp / "__pycache__" / "junk.pyc").write_text("junk")
            h, files = await svc.commit_changes(tmp, "should be empty")
            print(f"files={files}")
            assert files == [], f"__pycache__ bị add nhầm: {files}"

            print("\n=== 7. Commit message dài bị cắt ===")
            long_msg = "feat: " + "very long description " * 10
            (tmp / "a.py").write_text("x = 1\n")
            h, _ = await svc.commit_changes(tmp, long_msg)
            _, show = await svc._exec_git(tmp, ["log", "-1", "--pretty=%s"])
            print(f"subject: {show!r}")
            assert len(show) <= 75

            print("\nTẤT CẢ TEST PASS")

        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    asyncio.run(_test())