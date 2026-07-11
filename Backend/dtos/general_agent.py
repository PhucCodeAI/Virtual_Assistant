from pydantic import BaseModel, Field

class Steps(BaseModel):
    step: int
    action: str = Field(..., description="Hành động cần thực hiện")
    target: str | None = Field(description="Kết quả mục tiêu của hành động")

class PlaningResponse(BaseModel):
    desc: str = Field(..., description="Giải thích sơ bộ kế hoạch mà bạn sẽ thực hiện")
    steps: list[Steps] = Field(..., description="Các bước thực hiện chi tiết")