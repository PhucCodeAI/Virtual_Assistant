from pydantic import BaseModel, Field


class DatasetStats(BaseModel):
    """DTO cho thống kê Gamification trên UI"""
    sft: int = Field(default=0, description="Số lượng mẫu SFT")
    dpo: int = Field(default=0, description="Số lượng mẫu DPO")

class MetricsResponse(BaseModel):
    cpu: float
    ram: float
    gpu_vram: float
    throughput: int
    dataset_stats: DatasetStats