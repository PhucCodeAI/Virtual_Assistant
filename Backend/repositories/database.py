import sqlite3
import uuid
import os
from typing import Optional, Dict, List, Any

class DataBase:
    """
    Lớp quản lý Database SQLite theo chuẩn CRUD (Data Access Object).
    Tối ưu cho việc thu thập dữ liệu SFT và DPO.
    Không sử dụng ORM để đảm bảo tốc độ truy vấn (Latency < 5ms).
    """
    
    def __init__(self, db_path: str = "database/virtual_assistant.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Tạo kết nối DB và cấu hình trả về dạng dict (sqlite3.Row)."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Khởi tạo schema nếu chưa tồn tại."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id TEXT PRIMARY KEY,
                    prompt_text TEXT NOT NULL,
                    image_path TEXT,
                    ai_response TEXT NOT NULL,
                    human_corrected TEXT,
                    status TEXT DEFAULT 'pending', -- pending, approved, edited, discarded
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    # ==========================================
    # CHUẨN CRUD (CREATE - READ - UPDATE - DELETE)
    # ==========================================

    def create(self, prompt_text: str, ai_response: str, image_path: Optional[str] = None) -> str:
        """[C] Tạo mới một bản ghi tương tác."""
        record_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO interactions (id, prompt_text, image_path, ai_response, status)
                VALUES (?, ?, ?, ?, 'pending')
            """, (record_id, prompt_text, image_path, ai_response))
            conn.commit()
        return record_id

    def read(self, record_id: str) -> Optional[Dict[str, Any]]:
        """[R] Đọc một bản ghi theo ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT * FROM interactions WHERE id = ?", (record_id,))
            row = cursor.fetchone()
            return dict(row) if row else None   

    def read_all(self, limit: int = 10, offset: int = 0, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """[R] Đọc danh sách bản ghi (Hỗ trợ phân trang và lọc theo status)."""
        query = "SELECT * FROM interactions"
        params = []
        
        if status:
            query += " WHERE status = ?"
            params.append(status)
            
        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def update(self, record_id: str, **kwargs) -> bool:
        """
        [U] Cập nhật bản ghi động (Dynamic Update).
        Ví dụ: db.update(id, status='approved', human_corrected='...')
        """
        print(f"\n--- [DỮ LIỆU CẬP NHẬT TỪ UI BẮN LÊN] ---")
        print(f"ID mục tiêu: {record_id}")
        print(f"Body nhận được: {kwargs}")
        print("----------------------------------------\n")
        if not kwargs:
            return False
            
        # Tạo câu lệnh SET động dựa trên kwargs
        set_clause = ", ".join([f"{key} = ?" for key in kwargs.keys()])
        values = list(kwargs.values())
        values.append(record_id)
        
        query = f"UPDATE interactions SET {set_clause} WHERE id = ?"
        
        with self._get_connection() as conn:
            cursor = conn.execute(query, values)
            conn.commit()
            return cursor.rowcount > 0

    def delete(self, record_id: str) -> bool:
        """[D] Xóa cứng một bản ghi."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM interactions WHERE id = ?", (record_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ==========================================
    # NGHIỆP VỤ MỞ RỘNG (BUSINESS LOGIC)
    # ==========================================

    def get_stats(self) -> Dict[str, int]:
        """Lấy thống kê realtime để hiển thị lên UI (Gamification)."""
        with self._get_connection() as conn:
            cursor = conn.execute("""
                SELECT 
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as sft_count,
                    SUM(CASE WHEN status = 'edited' THEN 1 ELSE 0 END) as dpo_count
                FROM interactions
            """)
            row = cursor.fetchone()
            return {
                "sft": row["sft_count"] or 0,
                "dpo": row["dpo_count"] or 0
            }
        
if __name__ == "__main__":
    db = DataBase()
    print(db.read_all())