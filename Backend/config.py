import tomli
from pathlib import Path
from pydantic import BaseModel


class SetupConfig(BaseModel):
    llm_repo_id: str
    file_name: str
    embedding_repo: str
    model_folder: str

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
    batch_size: int
    max_length: int
    dim: int

class VectorDBConfig(BaseModel):
    vector_db_path: str

class GraphDBConfig(BaseModel):
    graph_db_path: str

class AppConfig(BaseModel):
    setup: SetupConfig
    llm_engine: LLMConfig
    server: ServerConfig
    embedding: EmbeddingConfig
    vectordb: VectorDBConfig
    database: DatabaseConfig
    graphdb: GraphDBConfig

CONFIG_PATH = Path(__file__).parent / "config.toml"

with open(CONFIG_PATH, "rb") as f:
    _config_data = tomli.load(f)
configs = AppConfig(**_config_data)