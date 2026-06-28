import os
import sys
from config import configs
from llama_cpp import Llama
from utils.logger import get_logger
from utils.utils import _get_optimal_threads

log = get_logger(__name__)

class LLMEngine:
    def __init__(self, model_path: str=configs.llm_engine.model_path, n_gpu_layers: int=configs.llm_engine.n_gpu_layers, n_ctx: int=configs.llm_engine.n_ctx):
        """
        Khởi tạo và cấu hình tối ưu VRAM cho card đồ họa GTX 1660 SUPER.
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Không tìm thấy mô hình tại: {model_path}")

        n_threads = _get_optimal_threads()

        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,      # Đẩy 100% các lớp mô hình vào VRAM của 1660S
            n_ctx=n_ctx,           # Khóa ngữ cảnh 2K để giữ an toàn cache, tránh tràn VRAM
            f16_kv=True,          # Tiết kiệm bộ nhớ đệm KV Cache
            verbose=False,         # Tắt log C++ chi tiết sau khi đã xác thực cấu hình thành công
            flash_attn=True,      # Tăng tốc tính toán, tiết kiệm 15% VRAM
            offload_kqv=True,     # Đẩy ma trận chú ý vào GPU
            n_threads=n_threads,          # Tận dụng 6 nhân của i5-12400F
            n_threads_batch=n_threads,    # Tối ưu đa luồng đa nhiệm 
        )
        log.info("Đã nạp xong trên GPU CUDA!")
        
    def generate_stream(self, messages: list, max_tokens: int=configs.llm_engine.max_tokens, temperature: float=configs.llm_engine.temperature):
        return self.llm.create_chat_completion(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        )