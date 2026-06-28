# Backend/logger.py
import sys
import logging
from pathlib import Path
from logging.handlers import RotatingFileHandler

class ColorConsoleFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: "\033[94m",
        logging.INFO: "\033[92m",
        logging.WARNING: "\033[93m",
        logging.ERROR: "\033[91m",
        logging.CRITICAL: "\033[1;91m"
    }
    RESET = "\033[0m"

    def format(self, record):
        log_color = self.COLORS.get(record.levelno, self.RESET)
        record.levelname = f"{log_color}{record.levelname}{self.RESET}"
        record.name = f"\033[36m{record.name}{self.RESET}"
        return super().format(record)

def setup_logging() -> None:
    log_dir = Path("./logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG) 
    root_logger.handlers = []

    file_handler = RotatingFileHandler(
        log_dir / "app.log", 
        maxBytes=5_000_000, # 5MB
        backupCount=3, 
        encoding="utf-8"
    )
    file_formatter = logging.Formatter(
        "%(asctime)s - [%(levelname)s] - %(filename)s:%(lineno)d - %(message)s", 
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.INFO)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_formatter = ColorConsoleFormatter("%(levelname)s: [%(name)s] %(message)s")
    stream_handler.setFormatter(stream_formatter)
    stream_handler.setLevel(logging.DEBUG)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING) 

def get_logger(module_name: str) -> logging.Logger:
    return logging.getLogger(module_name)