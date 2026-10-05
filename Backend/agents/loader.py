# Backend/agents/loader.py
"""Module load prompt template của từng agent từ file Markdown.

Cấu trúc thư mục:
    agents/<agent_name>/prompts/<prompt_name>.md

Cache: dùng functools.cache, invalidation thủ công khi cần hot-reload.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path

from exceptions import AppError

_AGENTS_DIR = Path(__file__).parent


class _SafeDict(dict):
    """Dict không raise KeyError, giữ nguyên {key} nếu thiếu.

    Dùng cho str.format_map để không vỡ khi template có placeholder
    không được truyền.
    """

    def __missing__(self, key: str) -> str:
        """Trả về {key} nguyên bản khi không có giá trị.

        Args:
            key: Tên placeholder.

        Returns:
            Chuỗi '{key}'.
        """
        return "{" + key + "}"


@cache
def load_prompt(agent_name: str, prompt_name: str) -> str:
    """Đọc nội dung prompt từ file.

    Args:
        agent_name: Tên agent (VD: 'coder').
        prompt_name: Tên prompt (VD: 'system').

    Returns:
        Nội dung prompt đã strip.

    Raises:
        AppError: Khi file prompt không tồn tại.
    """
    path = _AGENTS_DIR / agent_name / f"{prompt_name}.md"
    if not path.exists():
        raise AppError(
            f"Không tìm thấy prompt: {prompt_name}",
            code="PROMPT_NOT_FOUND",
            context={"path": str(path)},
        )
    return path.read_text(encoding="utf-8").strip()


def render_prompt(agent_name: str, prompt_name: str, **kwargs: str) -> str:
    """Load prompt và thay placeholder {key} bằng giá trị.

    Placeholder không có trong kwargs sẽ giữ nguyên dạng {key}.

    Args:
        agent_name: Tên agent.
        prompt_name: Tên prompt.
        **kwargs: Cặp key-value để thay thế.

    Returns:
        Prompt đã render.
    """
    raw = load_prompt(agent_name, prompt_name)
    return raw.format_map(_SafeDict(kwargs))


def clear_cache() -> None:
    """Xóa cache prompt — dùng khi hot-reload trong dev."""
    load_prompt.cache_clear()


__all__ = ["clear_cache", "load_prompt", "render_prompt"]