# Backend/config.py
"""Module cấu hình trung tâm cho hệ thống AI Coding Agent.

Đọc cấu hình từ file TOML, hợp nhất với biến môi trường (dotenv), cung cấp
singleton AppConfig đã được validate bằng Pydantic. Hỗ trợ override đường dẫn
config qua biến môi trường APP_CONFIG_PATH phục vụ đa môi trường.

Nguyên tắc bảo mật: mọi credentials (Supabase URL/KEY, OpenRouter KEY) chỉ được
nạp từ biến môi trường (.env), KHÔNG BAO GIỜ lưu trong config.toml.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import tomli
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator

_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(_ENV_PATH, override=False)


def _require_env(key: str) -> str:
    """Đọc biến môi trường bắt buộc, fail-fast nếu thiếu.

    Args:
        key: Tên biến môi trường.

    Returns:
        Giá trị của biến môi trường (đã strip).

    Raises:
        RuntimeError: Khi biến môi trường không tồn tại hoặc rỗng.
    """
    value = os.getenv(key, "").strip()
    if not value:
        raise RuntimeError(
            f"Thiếu biến môi trường bắt buộc '{key}'. "
            f"Kiểm tra file .env hoặc export thủ công."
        )
    return value


def _validate_url(v: str) -> str:
    """Chuẩn hóa và kiểm tra URL hợp lệ.

    Args:
        v: URL thô.

    Returns:
        URL đã strip trailing slash.

    Raises:
        ValueError: Khi URL không bắt đầu bằng http(s).
    """
    if not v.startswith(("https://", "http://")):
        raise ValueError("URL phải bắt đầu bằng http:// hoặc https://")
    return v.rstrip("/")


# ============================================================
# Schema các section trong config.toml
# ============================================================
class LLMConfig(BaseModel):
    """Cấu hình cho LLMClient."""

    model: str
    url: str
    provider: str
    max_retries: int = Field(default=3, ge=0, le=10)
    timeout_sec: int = Field(default=600, ge=10, le=3600)
    structured_mode: str = Field(
        default="json_schema",
        description="Chế độ structured output: json_schema | json_object | prompt_only",
    )

    @field_validator("structured_mode")
    @classmethod
    def _validate_structured_mode(cls, v: str) -> str:
        allowed = {"json_schema", "json_object", "prompt_only"}
        if v not in allowed:
            raise ValueError(f"structured_mode phải thuộc {allowed}, nhận được '{v}'")
        return v


class LogConfig(BaseModel):
    """Cấu hình logging."""

    log_path: str = "./logs"
    level: str = "INFO"
    rotation: str = "10 MB"
    retention: str = "7 days"


class ServerConfig(BaseModel):
    """Cấu hình HTTP server."""

    host: str = "0.0.0.0"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: list[str] = Field(default_factory=list)


class DatabaseConfig(BaseModel):
    """Cấu hình Postgres.

    Credentials được nạp động từ biến môi trường, không lưu trong TOML.
    """

    table_name: str = "traces"

    @property
    def supabase_url(self) -> str:
        """URL Supabase (đọc từ env SUPABASE_URL)."""
        return _validate_url(_require_env("SUPABASE_URL"))

    @property
    def supabase_key(self) -> str:
        """API key Supabase (đọc từ env SUPABASE_KEY)."""
        return _require_env("SUPABASE_KEY")


class StorageConfig(BaseModel):
    """Cấu hình Storage.

    Credentials được nạp động từ biến môi trường, không lưu trong TOML.
    """

    bucket: str = "trace-logs"

    @property
    def supabase_url(self) -> str:
        """URL Supabase (đọc từ env SUPABASE_URL)."""
        return _validate_url(_require_env("SUPABASE_URL"))

    @property
    def supabase_key(self) -> str:
        """API key Supabase (đọc từ env SUPABASE_KEY)."""
        return _require_env("SUPABASE_KEY")


class EmbeddingConfig(BaseModel):
    """Cấu hình EmbeddingClient."""

    url: str
    model: str
    batch_size: int = Field(default=32, ge=1, le=512)
    max_retries: int = Field(default=3, ge=0, le=10)
    concurrency: int = Field(default=5, ge=1, le=50)
    timeout_sec: int = Field(default=60, ge=5, le=300)


class OrchestratorConfig(BaseModel):
    """Cấu hình Orchestrator."""

    workspace_base: str = "./storage/sandboxes"
    max_retries: int = Field(default=3, ge=1, le=10)
    sandbox_image: str = "python:3.12-slim"
    sandbox_timeout_sec: int = Field(default=30, ge=5, le=600)
    system_prompt: str = Field(
        default=(
            "Bạn là Senior AI Coding Agent cấp cao. Bạn phải giải quyết yêu cầu "
            "bằng cách viết mã nguồn và BẮT BUỘC viết file unit test hoàn chỉnh "
            "(dùng unittest chuẩn Python).\n"
            "QUY TẮC SỐNG CÒN:\n"
            "1. Tên file test phải bắt đầu bằng 'test_' (ví dụ: 'test_calculator.py').\n"
            "2. File test phải import module trực tiếp "
            "(ví dụ: from calculator import Calculator).\n"
            "3. Lệnh test_command nên dùng: "
            "['python', '-m', 'unittest', 'discover', '-s', '.', '-p', 'test_*.py']"
        ),
        description="System prompt nạp vào LLM đầu mỗi phiên.",
    )


class SecretsConfig(BaseModel):
    """Credentials nạp từ biến môi trường (không có trong TOML)."""

    openrouter_api_key: str = Field(default_factory=lambda: _require_env("OPENROUTER_API_KEY"))
    supabase_url: str = Field(default_factory=lambda: _require_env("SUPABASE_URL"))
    supabase_key: str = Field(default_factory=lambda: _require_env("SUPABASE_KEY"))


class AppConfig(BaseModel):
    """Root config gộp tất cả section."""

    llm: LLMConfig
    logs: LogConfig
    server: ServerConfig
    database: DatabaseConfig
    storage: StorageConfig
    embedding: EmbeddingConfig
    orchestrator: OrchestratorConfig
    secrets: SecretsConfig = Field(default_factory=SecretsConfig)


# ============================================================
# Loader + singleton
# ============================================================
def _resolve_config_path(path: Path | None = None) -> Path:
    """Xác định đường dẫn file config.toml cần đọc.

    Ưu tiên: tham số truyền vào > biến môi trường APP_CONFIG_PATH > mặc định
    cạnh file config.py.

    Args:
        path: Đường dẫn tường minh do caller chỉ định.

    Returns:
        Đường dẫn tuyệt đối tới file config.toml.

    Raises:
        FileNotFoundError: Khi file config không tồn tại.
    """
    if path is None:
        env_path = os.getenv("APP_CONFIG_PATH")
        path = Path(env_path) if env_path else Path(__file__).parent / "config.toml"
    path = path.resolve()
    if not path.exists():
        raise FileNotFoundError(f"Không tìm thấy file config tại: {path}")
    return path


def load_config(path: Path | None = None) -> AppConfig:
    """Đọc và validate cấu hình từ file TOML, hợp nhất với secrets từ env.

    Args:
        path: Đường dẫn tùy chọn tới file config.toml.

    Returns:
        AppConfig đã được validate.

    Raises:
        FileNotFoundError: Khi file config không tồn tại.
        RuntimeError: Khi thiếu biến môi trường bắt buộc.
        ValidationError: Khi cấu trúc TOML không khớp schema.
    """
    resolved = _resolve_config_path(path)
    with resolved.open("rb") as f:
        data = tomli.load(f)
    return AppConfig(**data)


@lru_cache(maxsize=1)
def get_configs() -> AppConfig:
    """Trả về singleton AppConfig đã được cache.

    Returns:
        AppConfig instance.
    """
    return load_config()

configs = get_configs()

if __name__ == "__main__":
    import json

    cfg = get_configs()
    dumped = cfg.model_dump()
    dumped["secrets"] = {k: "***REDACTED***" for k in dumped.get("secrets", {})}
    print("=== CONFIG LOADED ===")
    print(json.dumps(dumped, indent=2, ensure_ascii=False, default=str))