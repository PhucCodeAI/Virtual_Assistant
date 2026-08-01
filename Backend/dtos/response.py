from pydantic import BaseModel, Field
from typing import Literal

class RoutingAgentResponse(BaseModel):
    agent_name: Literal["coding", "analyst", "general"] = Field(..., description="Tên của Agent được chọn để xử lý yêu cầu")
    reason_for_agent: str = Field(..., description="Lý do tại sao Agent này được chọn")
    difficulty: Literal["easy", "hard"] = Field(..., description="Độ khó của yêu cầu từ người dùng")
    reason_for_difficulty: str = Field(..., description="Lý do tại sao yêu cầu này được đánh giá là dễ hay khó")

class Steps(BaseModel):
    action: str = Field(..., description="Mô tả hành động cần thực hiện")
    target: str | None = Field(description="Mô tả kết quả cần đạt được của hành động")

class PlaningResponse(BaseModel):
    reason: str = Field(..., description="Giải thích tại sao bạn lại lên kế hoạch như vậy")
    steps: list[Steps] = Field(..., description="Các bước thực hiện chi tiết")