"""
File: tests/conftest.py
Chứa các pytest fixture chung được nạp tự động cho toàn bộ tập tin test trong thư mục tests/
"""

import os
import ssl

import pytest
from config import configs
from services.embedding_engine import EmbeddingEngine
from Backend.services.llm_client import LLMEngine

ssl._create_default_https_context = ssl._create_unverified_context


@pytest.fixture(scope="session")
def embedding() -> EmbeddingEngine:
    """Khởi tạo một instance EmbeddingEngine duy nhất cho toàn bộ session test"""
    return EmbeddingEngine()


@pytest.fixture(scope="session")
def llm_engine() -> LLMEngine:
    """Khởi tạo một instance LLMEngine duy nhất cho toàn bộ session test"""
    model_full_path = os.path.join(
        configs.setup.model_folder, configs.setup.llm_file_name
    )
    return LLMEngine(model_path=model_full_path)
