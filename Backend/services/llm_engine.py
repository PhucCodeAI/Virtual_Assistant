import asyncio
import json
import os
import time
from collections.abc import AsyncGenerator
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from config import configs
from llama_cpp import ChatCompletionRequestMessage, Llama
from loguru import logger
from pydantic import BaseModel
from utils.utils import _get_optimal_threads

_executor = ThreadPoolExecutor(max_workers=_get_optimal_threads())


class LLMEngine:
    def __init__(
        self,
        model_path: str = f"{configs.setup.model_folder}/{configs.setup.llm_file_name}",
        n_gpu_layers: int = configs.llm_engine.n_gpu_layers,
        n_ctx: int = configs.llm_engine.n_ctx,
    ):
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

        self.lock = asyncio.Lock()

        logger.info(f"Load xong model {model_path.split('/')[-1].split('.')[0]}")

    def _get_input_tokens(self, messages: list[dict[str, str]]) -> int:
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
        token_ids = self.llm.tokenize(chatml_prompt.encode("utf-8"), special=True)
        return len(token_ids)

    def generate(
        self,
        messages: list,
        temperature: float,
        top_p: float,
        stream: bool = False,
        max_tokens: int = configs.llm_engine.max_tokens,
    ):
        return self.llm.create_chat_completion(
            messages,
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stream=stream,
        )

    def generate_structured(
        self,
        messages: list[ChatCompletionRequestMessage],
        response_model: type[BaseModel],
        temperature: float,
        top_p: float,
        max_tokens: int = configs.llm_engine.max_tokens,
        max_retries: int = configs.llm_engine.max_retries,
    ) -> BaseModel:
        def _run(temp) -> BaseModel:
            response_format: Any = {
                "type": "json_object",
                "schema": response_model.model_json_schema(),
            }
            response = self.llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temp,
                top_p=top_p,
                response_format=response_format,
                stream=False,
            )
            json_string = response["choices"][0]["message"]["content"]

            return response_model.model_validate_json(json_string)

        for attempt in range(1, max_retries + 1):
            try:
                future = _executor.submit(_run, temperature)
                return future.result()
            except Exception as e:
                logger.warning(
                    f"⚠️ Lần thử {attempt} thất bại do lỗi định dạng đầu ra: {e!s}"
                )
                temperature = 0.0
                time.sleep(0.5)

        error_msg = f"Thất bại: Đã thử lại tối đa {max_retries} lần nhưng LLM vẫn sinh chuỗi JSON không hợp lệ."
        logger.error(error_msg)
        raise RuntimeError(error_msg)

    async def generate_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.5,
        top_p: float = 0.5,
    ) -> AsyncGenerator[str]:
        """
        Sinh luồng text stream từ LLM.

        -Input: req (ChatRequest, DTO chứa thông tin request từ người dùng)
        -Output: AsyncGenerator[str, None] (Luồng text stream trả về cho Controller)
        """
        logger.info(f"Nhận request: {messages}")

        await self.lock.acquire()
        try:
            start_time = time.perf_counter()
            generated_tokens = 0
            prompt_tokens = self._get_input_tokens(messages)

            if prompt_tokens > configs.llm_engine.n_ctx - configs.llm_engine.max_tokens:
                error_msg = f"Error: Token của request vượt quá giới hạn ({prompt_tokens} > {configs.llm_engine.n_ctx - configs.llm_engine.max_tokens}). Vui lòng giảm độ dài input"
                logger.error(error_msg)
                yield f"data: {json.dumps({'type': 'error', 'content': error_msg}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return

            sync_generator = await asyncio.to_thread(
                self.generate, messages, temperature, top_p, True
            )

            while True:
                chunk = await asyncio.to_thread(lambda: next(sync_generator, None))

                if chunk is None:
                    break

                if chunk.get("usage"):
                    prompt_tokens = chunk["usage"].get("prompt_tokens", 0)

                if "choices" in chunk and len(chunk["choices"]) > 0:
                    delta = chunk["choices"][0].get("delta", {})
                    token = delta.get("content", "")

                    if token:
                        generated_tokens += 1
                        payload = {"type": "text", "content": token}
                        yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

            elapsed_time = time.perf_counter() - start_time
            throughput = (
                round(generated_tokens / elapsed_time, 2) if elapsed_time > 0 else 0
            )

            meta_payload = {
                "type": "metadata",
                "metrics": {
                    "throughput_tps": throughput,
                    "context_length": prompt_tokens + generated_tokens,
                    "generated_tokens": generated_tokens,
                    "elapsed_time_sec": round(elapsed_time, 2),
                },
            }
            yield f"data: {json.dumps(meta_payload, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        finally:
            self.lock.release()

    async def generate_non_stream(
        self,
        messages: list[dict[str, str]],
        temperature=0.5,
        top_p=0.5,
        prompt_tokens=0,
    ) -> dict:
        """
        Sinh text trả về một lần từ LLM.

        -Input: messages (list[dict]), temperature (float), top_p (float), prompt_tokens (int)
        -Output: dict (Kết quả trả về cho Controller)
        """
        await self.lock.acquire()
        try:
            start_time = time.perf_counter()

            response = await asyncio.to_thread(
                self.generate, messages, temperature, top_p, False
            )

            elapsed_time = time.perf_counter() - start_time
            generated_tokens = response["usage"].get("completion_tokens", 0)  # type: ignore
            throughput = (
                round(generated_tokens / elapsed_time, 2) if elapsed_time > 0 else 0
            )

            meta_payload = {
                "type": "metadata",
                "metrics": {
                    "throughput_tps": throughput,
                    "context_length": prompt_tokens + generated_tokens,
                    "generated_tokens": generated_tokens,
                    "elapsed_time_sec": round(elapsed_time, 2),
                },
            }

            return {
                "type": "text",
                "content": response["choices"][0]["message"]["content"],  # type: ignore
                "metadata": meta_payload,
            }

        finally:
            self.lock.release()


if __name__ == "__main__":
    llm_engine = LLMEngine()
    messages = [
        {
            "role": "system",
            "content": 'Bạn là một trợ lí chuyên phân tích văn bản. Hãy trích xuất thông tin từ user và trả về JSON theo định dạng sau: {"entity1": str, "action": str, "entity2": str',
        },
        {
            "role": "user",
            "content": "Tôi đang đi chơi, bạn có muốn đi chơi cùng tôi không?",
        },
    ]

    result = llm_engine.generate(
        messages=messages, temperature=0.7, top_p=0.9, max_tokens=10, stream=False
    )

    print(result["choices"][0]["message"]["content"])
