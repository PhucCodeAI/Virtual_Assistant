from pydantic import BaseModel
from typing import Any

class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]]

class ChatRequest(BaseModel):
    messages: list[ChatMessage]
    temperature: float
    top_p: float