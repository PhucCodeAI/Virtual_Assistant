import sys
from pathlib import Path

from config import configs
from loguru import logger

IGNORED_MODULES = [
    "httpx",
    "httpcore",
    "uvicorn.access",
    "aiosqlite",
    "opentelemetry",
    "openinference",
]


def _should_log(record) -> bool:
    module_name = record["name"]
    if any(module_name.startswith(ignored) for ignored in IGNORED_MODULES):
        return record["level"].no >= 30
    return True


def setup_logging() -> None:
    logger.remove()

    log_path = Path(configs.logs.log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    console_format = "<level>{level}:</level> [<cyan>{name}</cyan>] {message}"
    logger.add(
        sys.stdout,
        format=console_format,
        level="DEBUG",
        filter=_should_log,
        enqueue=True,
    )

    file_format = "{time:Y-m-d H:mm:ss} - [{level}] - {file}:{line} - {message}"
    logger.add(
        log_path,
        format=file_format,
        level="INFO",
        rotation="5 MB",
        retention=3,
        encoding="utf-8",
        filter=_should_log,
        enqueue=True,
    )
