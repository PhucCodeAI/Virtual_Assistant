from typing import Any
from abc import ABC, abstractmethod
from dtos.chat_request import ChatRequest
from services.llm_engine import LLMEngine
from dtos.general_agent import PlaningResponse
from .general_prompts import GeneralPrompt

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
    def __init__(self) -> None:
        self.prompts = GeneralPrompt()
        self.llm = LLMEngine()

    def run(self, req: ChatRequest) -> PlaningResponse:
        system_message = [
            {
                "role": "system",
                "content": self.prompts.planing(),
            }
        ]
        
        user_history = req.messages if hasattr(req, 'messages') else req.model_dump().get("messages", [])
        
        full_messages = system_message + user_history

        temperature = getattr(req, 'temperature', 0.5)
        top_p = getattr(req, 'top_p', 0.95)

        return self.llm.generate_structured(
            messages=full_messages,
            response_model=PlaningResponse,
            temperature=temperature,
            top_p=top_p
        )