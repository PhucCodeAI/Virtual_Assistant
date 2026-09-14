from pydantic import BaseModel, Field
from dtos.utils import ChatMessage


class AgentRequest(BaseModel):
    messages: list[ChatMessage] = Field(..., description="Danh sách các tin nhắn từ người dùng và AI")
    temperature: float = Field(..., description="Tham số điều chỉnh độ sáng tạo của AI")
    top_p: float = Field(..., description="Tham số điều chỉnh xác suất tích lũy của AI")