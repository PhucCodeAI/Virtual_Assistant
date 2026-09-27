"""Module quản lý thao tác tệp tin trong workspace với cơ chế bảo vệ Path Jail."""

from pathlib import Path

from dtos.agent import FileAction


class WorkspaceManager:
    """Quản lý đọc/ghi tệp tin cô lập, ngăn chặn tấn công Path Traversal."""

    def __init__(self, root_dir: Path) -> None:
        """Khởi tạo WorkspaceManager.

        Args:
            root_dir (Path): Thư mục gốc cô lập của phiên làm việc.
        """
        self.root_dir = root_dir.resolve()
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, relative_path: str) -> Path:
        """Kiểm tra và chuẩn hóa đường dẫn, đảm bảo nằm trong root_dir.

        Args:
            relative_path (str): Đường dẫn tương đối do LLM cung cấp.

        Returns:
            Path: Đường dẫn an toàn tuyệt đối trên máy host.

        Raises:
            PermissionError: Khi phát hiện hành vi ghi đè ra ngoài sandbox hoặc vào .git.
        """
        target_path = (self.root_dir / relative_path).resolve()
        if not target_path.is_relative_to(self.root_dir):
            raise PermissionError(f"Cảnh báo bảo mật: Đường dẫn '{relative_path}' nằm ngoài sandbox!")
        if ".git" in target_path.parts:
            raise PermissionError("Cảnh báo bảo mật: Không được phép sửa đổi trực tiếp thư mục .git!")
        return target_path

    def apply_file_action(self, action: FileAction) -> Path:
        """Ghi nội dung file vào workspace sau khi kiểm tra bảo mật.

        Args:
            action (FileAction): DTO chứa đường dẫn và nội dung file.

        Returns:
            Path: Đường dẫn thực tế của file đã ghi.
        """
        safe_path = self._resolve_safe_path(action.path)
        safe_path.parent.mkdir(parents=True, exist_ok=True)
        safe_path.write_text(action.content, encoding="utf-8")
        return safe_path

    def read_file(self, relative_path: str) -> str:
        """Đọc nội dung một file trong workspace.

        Args:
            relative_path (str): Đường dẫn tương đối cần đọc.

        Returns:
            str: Nội dung của file.
        """
        safe_path = self._resolve_safe_path(relative_path)
        if not safe_path.exists():
            return ""
        return safe_path.read_text(encoding="utf-8")