from typing import Literal

from pydantic import BaseModel, Field


class RoutingAgentResponse(BaseModel):
    agent_name: Literal["coding", "analyst", "general"] = Field(
        ...,
        description="Chọn 'coding' cho lập trình, 'analyst' cho tài chính/data, 'general' cho câu hỏi thông thường",
    )
    reason_for_agent: str
    difficulty: Literal["easy", "hard"]
    reason_for_difficulty: str


class Steps(BaseModel):
    action: str = Field(..., description="Hành động cụ thể cần thực hiện")
    target: str = Field(
        ..., description="Mục tiêu hoặc output cụ thể mong muốn của hành động"
    )


class PlaningResponse(BaseModel):
    intro: str
    reason: str = Field(
        ..., description="Lý do ngắn gọn tại sao chọn luồng kế hoạch này"
    )
    steps: list[Steps]
