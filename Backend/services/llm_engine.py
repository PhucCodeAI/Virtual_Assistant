import os
import time
from typing import Type
from config import configs
from llama_cpp import Llama
from pydantic import BaseModel
from utils.logger import get_logger
from utils.utils import _get_optimal_threads
from concurrent.futures import ThreadPoolExecutor

log = get_logger(__name__)
_executor = ThreadPoolExecutor(max_workers=_get_optimal_threads())

class LLMEngine:
    def __init__(self, model_path: str=configs.llm_engine.model_path, n_gpu_layers: int=configs.llm_engine.n_gpu_layers, n_ctx: int=configs.llm_engine.n_ctx):
        """
        Khởi tạo và cấu hình tối ưu cho LLM
        """
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Không tìm thấy mô hình tại: {model_path}")

        n_threads = _get_optimal_threads()

        self.llm = Llama(
            model_path=model_path,
            n_gpu_layers=n_gpu_layers,
            n_ctx=n_ctx,
            f16_kv=True,
            verbose=False,
            flash_attn=True,
            offload_kqv=True,
            n_threads=n_threads,
            n_threads_batch=n_threads,
        )
        log.info("Đã nạp xong mô hình")

    def _get_input_tokens(self, messages: list) -> int:
        """
        Calculate exact prompt tokens for Qwen 3.5 using the native ChatML format.
        Safely avoids llama-cpp-python internal API breakages.

        -Input: messages (list, List of chat completion message dicts)
        -Output: int (Total exact count of prompt tokens)
        """
        chatml_prompt = ""
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            chatml_prompt += f"<|im_start|>{role}\n{content}<|im_end|>\n"
        
        chatml_prompt += "<|im_start|>assistant\n"
        token_ids = self.llm.tokenize(chatml_prompt.encode('utf-8'), special=True)
        return len(token_ids)
        
    def generate_stream(
        self, messages: list,
        temperature: float,
        top_p: float,
        max_tokens: int=configs.llm_engine.max_tokens,
    ):
        print(self._get_input_tokens(messages))
        return self.llm.create_chat_completion(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=True
        )
    
    def generate(self, messages: list,
        temperature: float,
        top_p: float,
        max_tokens: int=configs.llm_engine.max_tokens
    ):
        
        return self.llm.create_chat_completion(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=False
        )
    
    def generate_structured(
        self, 
        messages: list[dict[str, str]],
        response_model: Type[BaseModel],
        temperature: float,
        top_p: float,
        max_tokens: int = configs.llm_engine.max_tokens,
        max_retries: int = configs.llm_engine.max_retries
    ) -> BaseModel:
        def _run(temp) -> BaseModel:
            response_format = {
                "type": "json_object",
                "schema": response_model.model_json_schema()
            }
            response = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temp,
                top_p=top_p,
                response_format=response_format,
                stream=False
            )
            json_string = response["choices"][0]["message"]["content"]
            
            return response_model.model_validate_json(json_string)
            
        for attempt in range(1, max_retries + 1):
            try:
                future = _executor.submit(_run, temperature)
                return future.result()
            except Exception as e:
                log.warning(f"⚠️ Lần thử {attempt} thất bại do lỗi định dạng đầu ra: {str(e)}")
                temperature = 0.0
                time.sleep(.5)

        error_msg = f"Thất bại: Đã thử lại tối đa {max_retries} lần nhưng LLM vẫn sinh chuỗi JSON không hợp lệ."
        log.error(error_msg)
        raise RuntimeError(error_msg)

class Test(BaseModel):
    name: str
    age: int
    d_m_y_birth: str
    job: str
    education: str

if __name__ == "__main__":
    llm_engine = LLMEngine()
    messages = [
        {"role": "system", "content": "Bạn là một lập trình viên senior xuất sắc và có khả năng phân tích mọi dự án. Dựa vào thông tin mà người dùng cung cấp hãy vẽ ra các bước cần thiết để triển khai công việc"},
        {"role": "user", "content": "Hãy tạo 2 class với 2 thuộc tính ngẫu nhiên name và age"}
    ]
    
    for result in llm_engine.generate_stream(
        messages=messages,
        temperature=0.7,
        top_p=0.9, max_tokens=10
    ):
    
        print(result)