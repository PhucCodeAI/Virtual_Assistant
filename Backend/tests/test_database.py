"""
File: tests/test_database.py
Test suite kiểm thử toàn diện class DataBase.
"""

import sqlite3

import pytest
from config import configs
from repositories.database import DataBase


@pytest.fixture
def test_db(
    tmp_path: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> DataBase:
    """
    Fixture tạo một file SQLite database tạm thời cho mỗi hàm test,
    đảm bảo môi trường kiểm thử hoàn toàn độc lập và không ảnh hưởng DB thật.
    """
    temp_db_file = str(tmp_path / "test_virtual_assistant.db")
    monkeypatch.setattr(configs.database, "db_path", temp_db_file)

    db = DataBase()
    return db


class TestDataBaseClass:
    def test_init_db_creates_table(self, test_db: DataBase) -> None:
        """
        Kiểm tra khởi tạo bảng 'interactions' thành công trong database.
        """
        with test_db._get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='interactions';"
            )
            table = cursor.fetchone()
            assert table is not None
            assert table["name"] == "interactions"

    def test_create_record(self, test_db: DataBase) -> None:
        """
        Kiểm tra [C]reate: Tạo mới bản ghi tương tác và trả về UUID hợp lệ.
        """
        prompt = "Hãy giải thích thuật toán Cosine Similarity."
        ai_res = "Cosine Similarity là độ đo..."
        img_path = "/path/to/image.png"

        record_id = test_db.create(
            prompt_text=prompt, ai_response=ai_res, image_path=img_path
        )

        assert isinstance(record_id, str)
        assert len(record_id) == 36

        record = test_db.read(record_id)
        assert record is not None
        assert record["prompt_text"] == prompt
        assert record["ai_response"] == ai_res
        assert record["image_path"] == img_path
        assert record["status"] == "pending"

    def test_read_record_existing_and_non_existing(self, test_db: DataBase) -> None:
        """
        Kiểm tra [R]ead: Đọc bản ghi tồn tại và trả về None khi ID không tồn tại.
        """
        rec_id = test_db.create("Prompt Test", "Response Test")

        record = test_db.read(rec_id)
        assert record is not None
        assert record["id"] == rec_id

        non_existent = test_db.read("non-existent-uuid-12345")
        assert non_existent is None

    def test_read_all_pagination_and_status_filtering(self, test_db: DataBase) -> None:
        """
        Kiểm tra [R]ead All: Phân trang (limit/offset) và lọc theo status (pending, approved, edited).
        """
        id1 = test_db.create("Prompt 1", "Response 1")
        id2 = test_db.create("Prompt 2", "Response 2")
        id3 = test_db.create("Prompt 3", "Response 3")

        test_db.update(id1, status="approved")
        test_db.update(id2, status="edited")

        all_records = test_db.read_all(limit=10, offset=0)
        assert len(all_records) == 3

        page1 = test_db.read_all(limit=2, offset=0)
        assert len(page1) == 2

        approved_list = test_db.read_all(status="approved")
        assert len(approved_list) == 1
        assert approved_list[0]["id"] == id1

        edited_list = test_db.read_all(status="edited")
        assert len(edited_list) == 1
        assert edited_list[0]["id"] == id2

    def test_update_record_dynamic(self, test_db: DataBase) -> None:
        """
        Kiểm tra [U]pdate: Cập nhật động các trường dữ liệu.
        """
        rec_id = test_db.create("Original Prompt", "Original AI Response")

        assert test_db.update(rec_id) is False
        assert test_db.update("fake-uuid", status="approved") is False

        updated = test_db.update(
            rec_id, status="edited", human_corrected="Human Corrected Response"
        )
        assert updated is True

        record = test_db.read(rec_id)
        assert record["status"] == "edited"
        assert record["human_corrected"] == "Human Corrected Response"

    def test_delete_record(self, test_db: DataBase) -> None:
        """
        Kiểm tra [D]elete: Xóa cứng một bản ghi theo ID.
        """
        rec_id = test_db.create("Prompt to delete", "Response to delete")

        deleted = test_db.delete(rec_id)
        assert deleted is True

        assert test_db.read(rec_id) is None
        assert test_db.delete(rec_id) is False

    def test_get_stats(self, test_db: DataBase) -> None:
        """
        Kiểm tra tính toán số liệu thống kê SFT (approved) và DPO (edited) cho UI realtime.
        """
        stats_initial = test_db.get_stats()
        assert stats_initial == {"sft": 0, "dpo": 0}

        id1 = test_db.create("P1", "R1")
        id2 = test_db.create("P2", "R2")
        id3 = test_db.create("P3", "R3")
        id4 = test_db.create("P4", "R4")

        test_db.update(id1, status="approved")
        test_db.update(id2, status="approved")
        test_db.update(id3, status="edited")

        stats = test_db.get_stats()
        assert stats["sft"] == 2
        assert stats["dpo"] == 1

    def test_connection_context_manager_rollback_on_error(
        self, test_db: DataBase
    ) -> None:
        """
        Kiểm tra cơ chế Transaction Rollback khi có lỗi xảy ra trong Context Manager.
        """
        with pytest.raises(sqlite3.OperationalError), test_db._get_connection() as conn:
            conn.execute(
                "INSERT INTO interactions (id, prompt_text, ai_response) VALUES (?, ?, ?)",
                ("rollback-id", "Test Prompt", "Test Response"),
            )
            conn.execute("INVALID SQL STATEMENT HERE")

        assert test_db.read("rollback-id") is None
