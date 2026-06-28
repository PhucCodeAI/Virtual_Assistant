from pydantic import BaseModel
from typing import List, Dict, Any, Union

class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]

class Request(BaseModel):
    messages: List[ChatMessage]