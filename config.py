import os
from pathlib import Path

import tomli
from dotenv import load_dotenv
from pydantic import BaseModel


class SetupConfig(BaseModel):
    llm_repo_id: str
    llm_file_name: str
    model_folder: str


class LogConfig(BaseModel):
    log_path: str


class PhoenixConfig(BaseModel):
    data_dir: str


class ServerConfig(BaseModel):
    host: str
    port: int
    cors_origins: list[str]


class LLMConfig(BaseModel):
    n_ctx: int
    n_gpu_layers: int
    max_tokens: int
    max_retries: int


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


class BotConfig(BaseModel):
    bot_token: str
    user_id: str


load_dotenv()
bot_token = os.getenv("BOT_TOKEN")
user_id = os.getenv("USER_ID")


class AppConfig(BaseModel):
    setup: SetupConfig
    logs: LogConfig
    phoenix: PhoenixConfig
    llm_engine: LLMConfig
    server: ServerConfig
    embedding: EmbeddingConfig
    vectordb: VectorDBConfig
    database: DatabaseConfig
    graphdb: GraphDBConfig
    bot: BotConfig


CONFIG_PATH = Path(__file__).parent / "config.toml"

with open(CONFIG_PATH, "rb") as f:
    _config_data = tomli.load(f)
    _config_data["bot"] = {}
    _config_data["bot"]["bot_token"] = bot_token
    _config_data["bot"]["user_id"] = user_id
configs = AppConfig(**_config_data)
