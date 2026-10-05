# Backend/pipeline/__init__.py
"""Package quản lý pipeline orchestration."""

from pipeline.context import PipelineContext
from pipeline.orchestrator import Orchestrator

__all__ = ["Orchestrator", "PipelineContext"]