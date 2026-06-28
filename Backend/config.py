import tomli
from pathlib import Path
from pydantic import BaseModel

# Đường dẫn tuyệt đối đến file config.toml
CONFIG_PATH = Path(__file__).parent / "config.toml"

# Đọc file TOML bằng thư viện chuẩn của Python (Không cần cài thêm)
with open(CONFIG_PATH, "rb") as f:
    _config_data = tomli.load(f)

class ServerConfig(BaseModel):
    host: str
    port: int
    cors_origins: list[str]

class LLMConfig(BaseModel):
    model_path: str
    n_ctx: int
    n_gpu_layers: int
    temperature: float
    max_tokens: int

class DatabaseConfig(BaseModel):
    sqlite_path: str

class ScraperConfig(BaseModel):
    timeout_seconds: int
    user_agent: str

class AppConfig(BaseModel):
    llm_engine: LLMConfig
    server: ServerConfig

configs = AppConfig(**_config_data)