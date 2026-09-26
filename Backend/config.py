from pathlib import Path

import tomli
from pydantic import BaseModel


class LLM(BaseModel):
    model: str
    max_retries: int
    url: str


class LogConfig(BaseModel):
    log_path: str


class PhoenixConfig(BaseModel):
    data_dir: str


class ServerConfig(BaseModel):
    host: str
    port: int
    cors_origins: list[str]


class DatabaseConfig(BaseModel):
    db_path: str


class EmbeddingConfig(BaseModel):
    repo: str
    batch_size: int
    max_length: int
    dim: int


class VectorDBConfig(BaseModel):
    vector_db_path: str


class GraphDBConfig(BaseModel):
    graph_db_path: str


class AppConfig(BaseModel):
    llm: LLM
    logs: LogConfig
    phoenix: PhoenixConfig
    server: ServerConfig
    embedding: EmbeddingConfig
    vectordb: VectorDBConfig
    database: DatabaseConfig
    graphdb: GraphDBConfig


CONFIG_PATH = Path(__file__).parent / "config.toml"

with open(CONFIG_PATH, "rb") as f:
    _config_data = tomli.load(f)
configs = AppConfig(**_config_data)
