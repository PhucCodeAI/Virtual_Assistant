from functools import lru_cache

from fastapi import Request
from repositories.graphdb import GraphDB
from repositories.vectordb import VectorDB
from services.embedding_client import EmbeddingClient
from services.llm_client import LLMClient
from services.orchestrator import Orchestrator
from services.trace_service import TraceService


@lru_cache
def get_vector_db(request: Request) -> VectorDB:
    return request.app.state.vector_repo


@lru_cache
def get_graph_db(request: Request) -> GraphDB:
    return request.app.state.graph_repo


@lru_cache
def get_trace_service(request: Request) -> TraceService:
    return request.app.state.tracer


@lru_cache
def get_embedding(request: Request) -> EmbeddingClient:
    return request.app.state.embedding_client


@lru_cache
def get_llm(request: Request) -> LLMClient:
    return request.app.state.llm_client


@lru_cache
def get_orchestrator(request: Request) -> Orchestrator:
    return request.app.state.orchestrator
