"""
File: tests/test_embedding_engine.py
Test suite kiểm thử toàn diện class EmbeddingEngine.
"""

import torch
from services.embedding_engine import EmbeddingEngine


class TestEmbeddingEngineClass:
    def test_model_loading(self, embedding: EmbeddingEngine) -> None:
        """
        Kiểm tra xem model và tokenizer có nạp thành công vào bộ nhớ không.
        """
        assert embedding.model is not None
        assert embedding.tokenizer is not None
        assert embedding.model.training is False

    def test_embedding_output_structure(self, embedding: EmbeddingEngine) -> None:
        """
        Kiểm tra cấu trúc và định dạng của vector đầu ra với 1 văn bản chuẩn.
        """
        test_texts = ["Xin chào trợ lý ảo dữ liệu"]

        vectors = embedding.get_embeddings(test_texts)

        assert isinstance(vectors, list)
        assert isinstance(vectors[0], list)
        assert len(vectors) == len(test_texts)
        assert len(vectors[0]) == 768
        assert isinstance(vectors[0][0], float)

    def test_embedding_batch_processing(self, embedding: EmbeddingEngine) -> None:
        """
        Kiểm tra tính năng chia batch khi truyền vào số lượng văn bản lớn hơn batch_size.
        """
        test_texts = [
            "Văn bản số một",
            "Văn bản số hai",
            "Văn bản số ba",
            "Văn bản số bốn",
        ]
        original_batch_size = embedding.batch_size
        embedding.batch_size = 2

        try:
            vectors = embedding.get_embeddings(test_texts)

            assert isinstance(vectors, list)
            assert len(vectors) == 4
            for vec in vectors:
                assert len(vec) == 768
        finally:
            embedding.batch_size = original_batch_size

    def test_embedding_empty_and_special_strings(
        self, embedding: EmbeddingEngine
    ) -> None:
        """
        Kiểm tra độ ổn định của hàm khi gặp chuỗi trống hoặc ký tự đặc biệt.
        """
        special_texts = ["", "   ", "!@#$%^&*()_+", "\n\t"]
        vectors = embedding.get_embeddings(special_texts)

        assert len(vectors) == len(special_texts)
        assert len(vectors[0]) == 768

    def test_mean_pooling_logic(self) -> None:
        """
        Kiểm tra độc lập hàm tĩnh mean_pooling để đảm bảo tính toán ma trận chính xác.
        """
        mock_output = torch.tensor([[[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]]])
        mock_mask = torch.tensor([[1, 0]])

        pooled = EmbeddingEngine.mean_pooling(mock_output, mock_mask)
        expected = torch.tensor([[1.0, 2.0, 3.0, 4.0]])
        assert torch.allclose(pooled, expected)
