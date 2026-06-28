from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum

# ==========================================
# ENUMS
# ==========================================
class RecordStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EDITED = "edited"
    DISCARDED = "discarded"

# ==========================================
# DTOs REQUEST (Input from UI to Backend)
# ==========================================
class CreateRecord(BaseModel):
    """DTO dùng khi tạo mới một log tương tác"""
    prompt: str = Field(..., description="Câu lệnh của người dùng")
    response: str = Field(..., description="Câu trả lời gốc của AI")
    image_base64: Optional[str] = Field(None, description="Ảnh đính kèm dạng base64 (nếu có)")

class UpdateRecord(BaseModel):
    """DTO dùng khi UI gửi yêu cầu Approve/Edit/Discard"""
    status: RecordStatus = Field(..., description="Trạng thái mới của record")
    human_corrected: Optional[str] = Field(None, description="Nội dung đã được xác thực (Ground Truth)")

# ==========================================
# DTOs RESPONSE (Output from Backend to UI)
# ==========================================
class DBResponse(BaseModel):
    """DTO chuẩn hóa dữ liệu trả về từ Database"""
    id: str
    prompt_text: str
    image_path: Optional[str]
    ai_response: str
    human_corrected: Optional[str]
    status: RecordStatus
    created_at: datetime

class CreateRecordResponse(BaseModel):
    """DTO trả về khi tạo record thành công"""
    id: str
    message: str = "Record created successfully"

class UpdateRecordResponse(BaseModel):
    """DTO trả về khi cập nhật record thành công"""
    result: bool
    message: str = "Record updated successfully"