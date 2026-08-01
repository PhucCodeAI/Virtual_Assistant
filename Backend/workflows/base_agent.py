from typing import Any
from abc import ABC, abstractmethod
from services.llm_engine import LLMEngine
from dtos.response import PlaningResponse
from .general_prompts import GeneralPrompt
from dtos.utils import ChatMessage

class BaseAgent(ABC):
    """
    Base class for all agents.
    """
    prompts: Any
    llm: LLMEngine

    @abstractmethod
    def run(self, *args, **kwargs):
        pass

class PlaningAgent(BaseAgent):
    """
    Agent for planning tasks.
    """
    def __init__(self, llm=None) -> None:
        self.prompts = GeneralPrompt()
        self.llm = llm

    def run(self, content: str) -> PlaningResponse:
        system_message = [
            {
                "role": "system",
                "content": self.prompts.PLANING,
            },
            {
                
            }

        ]

        return self.llm.generate_structured(
            messages=full_messages,
            response_model=PlaningResponse,
            temperature=temperature,
            top_p=top_p
        )