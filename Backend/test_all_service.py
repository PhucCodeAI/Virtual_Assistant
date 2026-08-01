"""
File: test_all_service.py
Test suite tập trung kiểm tra toàn diện các class.
"""

import asyncio
import json
import ssl

import pytest
import torch
from fastapi.testclient import TestClient
from main import app
from services.embedding_engine import EmbeddingEngine
from setup import setup

ssl._create_default_https_context = ssl._create_unverified_context

client = TestClient(app)
embedding_dir, llm_path = setup()


@pytest.fixture(scope="module")
def embedding() -> EmbeddingEngine:
    """Khởi tạo một instance EmbeddingEngine cho toàn bộ file test"""
    return EmbeddingEngine(embedding_dir=embedding_dir)


# =====================================================================
# PHẦN 1: TEST TỪNG CLASS LOGIC (EmbeddingEngine)
# =====================================================================
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


# =====================================================================
# PHẦN 2: TEST TỪNG CLASS LOGIC (LLMEngine)
# =====================================================================
from pydantic import BaseModel
from services.llm_engine import LLMEngine


@pytest.fixture(scope="module")
def llm_engine() -> LLMEngine:
    """Khởi tạo một instance LLMEngine cho toàn bộ phần test LLM"""
    return LLMEngine(model_path=llm_path)


class TestLLMEngineClass:
    def test_model_not_found_exception(self) -> None:
        """
        Kiểm tra ngoại lệ FileNotFoundError khi truyền đường dẫn mô hình không tồn tại.
        """
        invalid_path = "./static/models/non_existent_model.gguf"
        with pytest.raises(FileNotFoundError) as exc_info:
            LLMEngine(model_path=invalid_path)
        assert "Không tìm thấy mô hình tại" in str(exc_info.value)

    def test_llm_initialization(self, llm_engine: LLMEngine) -> None:
        """
        Kiểm tra việc khởi tạo đối tượng LLM và các thuộc tính quản lý concurrency.
        """
        assert llm_engine.llm is not None
        assert isinstance(llm_engine.lock, asyncio.Lock)

    def test_get_input_tokens_chatml(self, llm_engine: LLMEngine) -> None:
        """
        Kiểm tra đếm chính xác số lượng Prompt Token dựa trên định dạng ChatML của Qwen.
        """
        messages = [
            {"role": "system", "content": "Bạn là trợ lý AI."},
            {"role": "user", "content": "Xin chào!"},
        ]
        tokens_count = llm_engine._get_input_tokens(messages)

        assert isinstance(tokens_count, int)
        assert tokens_count > 0

    def test_sync_generate(self, llm_engine: LLMEngine) -> None:
        """
        Kiểm tra hàm sinh text đồng bộ cơ bản (generate).
        """
        messages = [{"role": "user", "content": "Trả lời ngắn: 1 + 1 bằng mấy?"}]
        response = llm_engine.generate(
            messages=messages, temperature=0.1, top_p=0.9, stream=False
        )

        assert isinstance(response, dict)
        assert "choices" in response
        assert len(response["choices"]) > 0
        content = response["choices"][0]["message"]["content"]
        assert isinstance(content, str)
        assert len(content.strip()) > 0

    def test_generate_structured_success(self, llm_engine: LLMEngine) -> None:
        """
        Kiểm tra tính năng sinh dữ liệu chuẩn cấu trúc JSON tuân thủ Pydantic Schema.
        """

        class PersonInfo(BaseModel):
            name: str
            age: int

        messages = [
            {
                "role": "user",
                "content": "Hãy trích xuất thông tin: Anh Nam năm nay 30 tuổi.",
            }
        ]

        result = llm_engine.generate_structured(
            messages=messages,
            response_model=PersonInfo,
            temperature=0.1,
            top_p=0.9,
            max_retries=2,
        )

        assert isinstance(result, PersonInfo)
        assert isinstance(result.name, str)
        assert isinstance(result.age, int)
        assert "Nam" in result.name
        assert result.age == 30

    @pytest.mark.asyncio
    async def test_generate_non_stream(self, llm_engine: LLMEngine) -> None:
        """
        Kiểm tra hàm sinh text bất đồng bộ một lần (generate_non_stream) kèm metadata metrics.
        """
        messages = [{"role": "user", "content": "Nói từ 'Chào' ngắn gọn."}]
        result = await llm_engine.generate_non_stream(
            messages=messages, temperature=0.1, top_p=0.9
        )

        assert isinstance(result, dict)
        assert result["type"] == "text"
        assert isinstance(result["content"], str)
        assert "metadata" in result

        metrics = result["metadata"]["metrics"]
        assert "throughput_tps" in metrics
        assert "context_length" in metrics
        assert "generated_tokens" in metrics
        assert "elapsed_time_sec" in metrics

    @pytest.mark.asyncio
    async def test_generate_stream_success(self, llm_engine: LLMEngine) -> None:
        """
        Kiểm tra luồng Streaming bất đồng bộ (generate_stream) theo chuẩn định dạng SSE.
        """
        messages = [{"role": "user", "content": "Đếm từ 1 đến 3."}]
        chunks = []

        async for chunk in llm_engine.generate_stream(
            messages=messages, temperature=0.1, top_p=0.9
        ):
            chunks.append(chunk)

        assert len(chunks) > 0

        assert chunks[-1] == "data: [DONE]\n\n"

        has_metadata = False
        has_text_data = False

        for chunk in chunks:
            if chunk.startswith("data: ") and chunk != "data: [DONE]\n\n":
                json_str = chunk.replace("data: ", "").strip()
                payload = json.loads(json_str)

                if payload.get("type") == "text":
                    has_text_data = True
                elif payload.get("type") == "metadata":
                    has_metadata = True

        assert has_text_data is True
        assert has_metadata is True

    @pytest.mark.asyncio
    async def test_generate_stream_context_overflow_guardrail(
        self, llm_engine: LLMEngine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Kiểm tra cơ chế phòng thủ (Guardrail) khi prompt token vượt quá giới hạn Context Window.
        """
        import config

        monkeypatch.setattr(config.configs.llm_engine, "n_ctx", 10)
        monkeypatch.setattr(config.configs.llm_engine, "max_tokens", 5)

        messages = [
            {
                "role": "user",
                "content": "Đây là một câu văn dài nhằm cố tình làm tràn bộ nhớ context.",
            }
        ]

        chunks = []
        async for chunk in llm_engine.generate_stream(messages=messages):
            chunks.append(chunk)

        assert len(chunks) == 2

        error_payload = json.loads(chunks[0].replace("data: ", "").strip())
        assert error_payload["type"] == "error"
        assert "vượt quá giới hạn" in error_payload["content"]
        assert chunks[1] == "data: [DONE]\n\n"
