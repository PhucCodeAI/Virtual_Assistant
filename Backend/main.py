# Backend/main.py
"""Entry point FastAPI cho hệ thống AI Coding Agent.

Trách nhiệm:
    - Khởi tạo Loguru và load config ngay khi import.
    - Lifespan: khởi tạo toàn bộ singleton (LLMClient, Orchestrator, repos, ...)
      và wire vào app.state để dependency injection dùng.
    - Shutdown: đóng HTTP client, cleanup orphan container.
    - Đăng ký routers và middleware.
    - Health check 2 mức: liveness (chỉ process còn sống) và readiness
      (dependency sẵn sàng).
"""

from __future__ import annotations

import asyncio
import contextlib
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import uvicorn
from config import configs
from controller.orchestrator_router import orchestrator_router
from controller.trace_router import trace_router
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from pipeline.orchestrator import Orchestrator
from pydantic import BaseModel
from repositories.storage_repository import StorageRepository
from repositories.trace_repository import TraceRepository
from services.embedding_client import EmbeddingClient
from services.git_service import GitService
from services.llm_client import LLMClient
from services.sandbox_engine import SandboxEngine
from services.trace_service import TraceService
from utils.logger import setup_logging

setup_logging()


# ============================================================
# Lifespan
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Vòng đời ứng dụng: khởi tạo và dọn dẹp tài nguyên.

    Args:
        app: Instance FastAPI đang chạy.

    Yields:
        None — FastAPI sẽ chạy các request trong khoảng thời gian này.
    """
    logger.info("=== STARTUP ===")
    secrets = configs.secrets

    # --- HTTP clients ---
    llm_client = LLMClient(secrets.openrouter_api_key)
    embedding_client = EmbeddingClient(secrets.openrouter_api_key)

    # --- Repositories ---
    trace_repo = TraceRepository()
    storage_repo = StorageRepository()

    # --- Services ---
    tracer = TraceService(trace_repo=trace_repo, storage_repo=storage_repo)
    git = GitService()
    sandbox = SandboxEngine(
        image=configs.orchestrator.sandbox_image,
        timeout_sec=configs.orchestrator.sandbox_timeout_sec,
    )

    orchestrator = Orchestrator(
        llm_client=llm_client,
        sandbox=sandbox,
        git=git,
        trace_service=tracer,
        workspace_base=configs.orchestrator.workspace_base,
        max_retries=configs.orchestrator.max_retries,
    )

    app.state.llm_client = llm_client
    app.state.embedding_client = embedding_client
    app.state.trace_repo = trace_repo
    app.state.storage_repo = storage_repo
    app.state.tracer = tracer
    app.state.git = git
    app.state.sandbox = sandbox
    app.state.orchestrator = orchestrator

    try:
        cleaned = await sandbox.cleanup_orphans()
        if cleaned:
            logger.info("Đã dọn {} orphan container khi startup", cleaned)
    except Exception as e:
        logger.warning("Cleanup orphan container khi startup thất bại: {}", e)

    logger.info(
        "Sẵn sàng | workspace_base={} | image={}",
        configs.orchestrator.workspace_base,
        configs.orchestrator.sandbox_image,
    )

    try:
        yield
    finally:
        logger.info("=== SHUTDOWN ===")

        cleanup_tasks: list[tuple[str, object]] = [
            ("llm_client", llm_client.aclose()),
            ("embedding_client", embedding_client.aclose()),
            ("trace_repo", trace_repo.aclose()),
            ("storage_repo", storage_repo.aclose()),
        ]
        results = await asyncio.gather(
            *[coro for _, coro in cleanup_tasks],
            return_exceptions=True,
        )
        for (name, _), result in zip(cleanup_tasks, results, strict=True):
            if isinstance(result, Exception):
                logger.warning("Đóng {} thất bại: {}", name, result)

        with contextlib.suppress(Exception):
            await sandbox.cleanup_orphans()

        logger.info("Đã shutdown sạch")


# ============================================================
# App
# ============================================================
app = FastAPI(
    title="AI Coding Agent",
    description=(
        "Hệ thống Coding Agent tự động: nhận prompt, sinh mã, chạy test trong "
        "Docker Sandbox, commit git, và trace toàn bộ pipeline."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(orchestrator_router)
app.include_router(trace_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=configs.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["content-range"],
)


# ============================================================
# Health endpoints
# ============================================================
class HealthStatus(BaseModel):
    """Schema response cho health check."""

    status: str
    version: str = "0.1.0"


class ReadyStatus(BaseModel):
    """Schema response cho readiness check."""

    status: str
    checks: dict[str, str]


@app.get("/health/live", response_model=HealthStatus, tags=["Health"])
async def liveness() -> HealthStatus:
    """Liveness probe: process còn sống không.

    Returns:
        HealthStatus với status='ok'.
    """
    return HealthStatus(status="ok")


@app.get("/health/ready", response_model=ReadyStatus, tags=["Health"])
async def readiness() -> ReadyStatus:
    """Readiness probe: các dependency sẵn sàng phục vụ chưa.

    Kiểm tra:
        - Docker daemon accessible (thử `docker version` với timeout 3s).
        - Supabase reachable (thử HEAD tới base_url).

    Returns:
        ReadyStatus với map các check.

    Raises:
        HTTPException 503: Khi có dependency chưa sẵn sàng.
    """
    checks: dict[str, str] = {}

    checks["docker"] = await _check_docker()

    checks["supabase"] = await _check_supabase()

    overall = "ok" if all(v == "ok" for v in checks.values()) else "degraded"
    if overall != "ok":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=ReadyStatus(status=overall, checks=checks).model_dump(),
        )
    return ReadyStatus(status=overall, checks=checks)


async def _check_docker() -> str:
    """Kiểm tra Docker daemon accessible.

    Returns:
        'ok' nếu chạy được, ngược lại chuỗi mô tả lỗi.
    """
    try:
        proc = await asyncio.create_subprocess_exec(
            "docker", "version", "--format", "{{.Server.Version}}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=3)
        if proc.returncode == 0 and stdout.strip():
            return "ok"
        return f"exit_{proc.returncode}"
    except (TimeoutError, FileNotFoundError, OSError) as e:
        return f"error:{type(e).__name__}"


async def _check_supabase() -> str:
    """Kiểm tra Supabase reachable bằng cách query count nhẹ.

    Returns:
        'ok' nếu query thành công, ngược lại chuỗi mô tả lỗi.
    """
    from controller.dependencies import get_trace_repository
    repo: TraceRepository | None = getattr(app.state, "trace_repo", None)
    if repo is None:
        return "not_initialized"
    try:
        await asyncio.wait_for(repo.count(), timeout=5)
        return "ok"
    except Exception as e:
        return f"error:{type(e).__name__}"


# ============================================================
# Root
# ============================================================
@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Endpoint gốc giới thiệu API.

    Returns:
        Dict thông tin cơ bản.
    """
    return {
        "name": "AI Coding Agent",
        "version": "0.0.0",
        "docs": "/docs",
        "health": "/health/live",
    }

if __name__ == "__main__":
    host = os.getenv("HOST", configs.server.host)
    port = int(os.getenv("PORT", str(configs.server.port)))
    reload_flag = os.getenv("RELOAD", "false").lower() == "true"

    logger.info("Khởi động server tại {}:{} (reload={})", host, port, reload_flag)
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=reload_flag,
        log_config=None,
    )