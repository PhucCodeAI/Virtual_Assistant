import tomli
from pathlib import Path
from pydantic import BaseModel


class ServerConfig(BaseModel):
    host: str
    port: int
    cors_origins: list[str]

class LLMConfig(BaseModel):
    model_path: str
    n_ctx: int
    n_gpu_layers: int
    max_tokens: int
    max_retries: int

class DatabaseConfig(BaseModel):
    db_path: str

class EmbeddingConfig(BaseModel):
    model_name: str
    cache_path: str
    max_length: int
    dim: int

class VectorDBConfig(BaseModel):
    vdb_path: str

class AppConfig(BaseModel):
    llm_engine: LLMConfig
    server: ServerConfig
    embedding: EmbeddingConfig
    vectordb: VectorDBConfig
    database: DatabaseConfig

CONFIG_PATH = Path(__file__).parent / "config.toml"

with open(CONFIG_PATH, "rb") as f:
    _config_data = tomli.load(f)
configs = AppConfig(**_config_data)