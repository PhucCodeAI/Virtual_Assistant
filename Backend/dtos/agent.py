from pydantic import BaseModel, Field

class LineRange(BaseModel):
    start_line: int = Field(..., description="Dòng bắt đầu")
    end_line: int = Field(..., description="Dòng kết thúc")

class RefactorCode(BaseModel):
    file: str = Field(..., description="Đường dẫn file cần sửa")
    line: int | None = Field(None, description="Số dòng (nếu biết chính xác)")
    old_code: str = Field(..., description="Đoạn code cũ cần tìm kiếm (Bắt buộc để thay thế chính xác)")
    new_code: str = Field(..., description="Đoạn code mới để thay thế")
    desc: str | None = Field(None, description="Giải thích lý do sửa")

class NewCode(BaseModel):
    file: str = Field(..., description="Đường dẫn file cần thêm code")
    position: str | None = Field(None, description="Vị trí thêm: 'trên cùng', 'dưới cùng', 'sau function_X'")
    line: int | None = Field(None, description="Dòng muốn chèn vào")
    code: str = Field(..., description="Đoạn code mới cần chèn")
    desc: str | None = Field(None, description="Giải thích")

class DeleteCode(BaseModel):
    file: str = Field(..., description="Đường dẫn file cần xóa code")
    line_range: LineRange | None = Field(None, description="Khoảng dòng cần xóa")
    old_code: str | None = Field(None, description="Đoạn code cần xóa (Ưu tiên dùng cái này hơn số dòng)")
    desc: str | None = Field(None, description="Giải thích lý do xóa")

class CreateFile(BaseModel):
    file: str = Field(..., description="Đường dẫn file mới cần tạo")
    code: str = Field(..., description="Toàn bộ nội dung code của file mới")
    desc: str | None = Field(None, description="Giải thích chức năng file")

class ShellCommand(BaseModel):
    command: str = Field(..., description="Lệnh terminal cần chạy")
    desc: str | None = Field(None, description="Giải thích lệnh này làm gì")

# --- 3. CLASS GOM NHÓM LỖI ---
class Problems(BaseModel):
    summary: str = Field(..., description="Tóm tắt lỗi") # Đã fix lỗi chính tả summery
    file: str | None = Field(None, description="File gây lỗi")
    error: str | None = Field(None, description="Chi tiết mã lỗi")
    type_error: str | None = Field(None, description="Loại lỗi (Syntax, Logic, Runtime)")
    pro_lang: str | None = Field(None, description="Ngôn ngữ lập trình")
    refactor_code: list[RefactorCode] = Field(default_factory=list, description="Các bước sửa lỗi")
    desc: str | None = Field(None, description="Phân tích nguyên nhân")

# --- 4. PAYLOAD TRẢ VỀ CUỐI CÙNG ---
class CodingResponse(BaseModel):
    response: str = Field(..., description="Câu trả lời giao tiếp với User")
    problem: list[Problems] | None = Field(None, description="Danh sách lỗi phát hiện được")
    new_code: list[NewCode] | None = Field(None, description="Các đoạn code cần chèn thêm")
    delete_code: list[DeleteCode] | None = Field(None, description="Các đoạn code cần xóa")
    create_file: list[CreateFile] | None = Field(None, description="Các file mới cần tạo")
    shell_command: list[ShellCommand] | None = Field(None, description="Các lệnh terminal cần chạy")
    desc: str | None = Field(None, description="Tổng kết chung")