# Backend/controller/dependencies.py
"""Module khai báo Dependency Injection cho FastAPI (Presentation Layer).

Nguyên tắc:
    - KHÔNG dùng @lru_cache trên hàm nhận Request (Request object thay đổi mỗi
      HTTP call → cache theo identity là bug).
    - Tất cả singleton (LLMClient, Orchestrator, ...) được khởi tạo MỘT LẦN
      trong lifespan của main.py và lưu vào app.state.
    - Module này chỉ expose getter đọc từ app.state + alias Annotated để router
      dùng gọn gàng, type-safe.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from pipeline.orchestrator import Orchestrator
from repositories.storage_repository import StorageRepository
from repositories.trace_repository import TraceRepository
from services.embedding_client import EmbeddingClient
from services.git_service import GitService
from services.llm_client import LLMClient
from services.sandbox_engine import SandboxEngine
from services.trace_service import TraceService


def get_orchestrator(request: Request) -> Orchestrator:
    """Lấy Orchestrator singleton từ app.state.

    Args:
        request: Đối tượng Request của FastAPI.

    Returns:
        Instance Orchestrator đã được khởi tạo trong lifespan.
    """
    return request.app.state.orchestrator


def get_trace_service(request: Request) -> TraceService:
    """Lấy TraceService singleton từ app.state.

    Args:
        request: Đối tượng Request của FastAPI.

    Returns:
        Instance TraceService đã được khởi tạo trong lifespan.
    """
    return request.app.state.tracer


def get_llm_client(request: Request) -> LLMClient:
    """Lấy LLMClient singleton từ app.state.

    Args:
        request: Đối tượng Request của FastAPI.

    Returns:
        Instance LLMClient đã được khởi tạo trong lifespan.
    """
    return request.app.state.llm_client


def get_embedding_client(request: Request) -> EmbeddingClient:
    """Lấy EmbeddingClient singleton từ app.state.

    Args:
        request: Đối tượng Request của FastAPI.

    Returns:
        Instance EmbeddingClient đã được khởi tạo trong lifespan.
    """
    return request.app.state.embedding_client


def get_sandbox(request: Request) -> SandboxEngine:
    """Lấy SandboxEngine singleton từ app.state.

    Args:
        request: Đối tượng Request của FastAPI.

    Returns:
        Instance SandboxEngine đã được khởi tạo trong lifespan.
    """
    return request.app.state.sandbox


def get_git_service(request: Request) -> GitService:
    """Lấy GitService singleton từ app.state.

    Args:
        request: Đối tượng Request của FastAPI.

    Returns:
        Instance GitService đã được khởi tạo trong lifespan.
    """
    return request.app.state.git


def get_trace_repository(request: Request) -> TraceRepository:
    """Lấy TraceRepository từ app.state.

    Args:
        request: Đối tượng Request của FastAPI.

    Returns:
        Instance TraceRepository đã được khởi tạo trong lifespan.
    """
    return request.app.state.trace_repo


def get_storage_repository(request: Request) -> StorageRepository:
    """Lấy StorageRepository từ app.state.

    Args:
        request: Đối tượng Request của FastAPI.

    Returns:
        Instance StorageRepository đã được khởi tạo trong lifespan.
    """
    return request.app.state.storage_repo


# ============================================================
# Annotated aliases
# ============================================================
OrchestratorDep = Annotated[Orchestrator, Depends(get_orchestrator)]
TraceServiceDep = Annotated[TraceService, Depends(get_trace_service)]
LLMClientDep = Annotated[LLMClient, Depends(get_llm_client)]
EmbeddingClientDep = Annotated[EmbeddingClient, Depends(get_embedding_client)]
SandboxDep = Annotated[SandboxEngine, Depends(get_sandbox)]
GitServiceDep = Annotated[GitService, Depends(get_git_service)]
TraceRepoDep = Annotated[TraceRepository, Depends(get_trace_repository)]
StorageRepoDep = Annotated[StorageRepository, Depends(get_storage_repository)]


__all__ = [
    "EmbeddingClientDep",
    "GitServiceDep",
    "LLMClientDep",
    "OrchestratorDep",
    "SandboxDep",
    "StorageRepoDep",
    "TraceRepoDep",
    "TraceServiceDep",
    "get_embedding_client",
    "get_git_service",
    "get_llm_client",
    "get_orchestrator",
    "get_sandbox",
    "get_storage_repository",
    "get_trace_repository",
    "get_trace_service",
]


if __name__ == "__main__":
    print("=== Kiểm tra import ===")
    from controller import dependencies as deps

    print(f"OrchestratorDep: {deps.OrchestratorDep}")
    print(f"TraceServiceDep: {deps.TraceServiceDep}")
    print(f"Số dependency getters: {len(deps.__all__)}")