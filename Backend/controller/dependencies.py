from fastapi import Request
from repositories.database import DataBase
from repositories.graphdb import GraphDB
from repositories.vectordb import VectorDB
from services.embedding_engine import EmbeddingEngine
from Backend.services.llm_client import LLMEngine
from workflows.orchestrator import AgentOrchestrator


def get_vector_db(request: Request) -> VectorDB:
    return request.app.state.vector_repo


def get_graph_db(request: Request) -> GraphDB:
    return request.app.state.graph_repo


def get_db(request: Request) -> DataBase:
    return request.app.state.db_repo


def get_embedding(request: Request) -> EmbeddingEngine:
    return request.app.state.embedding_engine


def get_llm(request: Request) -> LLMEngine:
    return request.app.state.llm_engine


def get_orchestrator(request: Request) -> AgentOrchestrator:
    return request.app.state.orchestrator
