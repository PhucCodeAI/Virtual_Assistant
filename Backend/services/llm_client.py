import asyncio
import json
import time
from collections.abc import AsyncGenerator
from typing import Any, TypeVar

import httpx
from config import configs
from pydantic import BaseModel, ConfigDict

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Gateway giao tiếp với API LLM (Data Access Layer).

    Cung cấp các phương thức gọi mô hình ngôn ngữ (thường, stream và ép kiểu dữ liệu)
    với cơ chế retry lũy thừa và chuẩn hóa phản hồi phục vụ giám sát hệ thống Agent.
    """

    def __init__(self, api_key: str):
        """Khởi tạo LLMClient.

        Args:
            api_key (str): Khóa xác thực API của nhà cung cấp (OpenRouter).
        """
        self.cfg = configs.llm
        self.client = httpx.AsyncClient(timeout=120)
        self.api_key = api_key

    async def aclose(self) -> None:
        """Giải phóng tài nguyên và đóng HTTP client kết nối ngầm."""
        await self.client.aclose()

    def _headers(self) -> dict[str, str]:
        """Tạo HTTP Headers chuẩn cho yêu cầu.

        Returns:
            dict[str, str]: Dictionary chứa thông tin Authorization và Content-Type.
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        """Đóng gói dữ liệu yêu cầu gửi lên mô hình.

        Args:
            messages (list[dict[str, str]]): Lịch sử ngữ cảnh tin nhắn.
            **kwargs (Any): Các tham số tinh chỉnh bổ sung (temperature, top_p,...).

        Returns:
            dict[str, Any]: Payload JSON chuẩn bị gửi đi.
        """
        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
        }
        payload.update(kwargs)
        return payload

    async def _retry(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Thực thi hàm bất đồng bộ với cơ chế retry khi gặp lỗi tạm thời.

        Args:
            func (Any): Hàm bất đồng bộ cần thực thi.
            *args (Any): Tham số vị trí của hàm.
            **kwargs (Any): Tham số định danh của hàm.

        Returns:
            Any: Kết quả trả về của hàm được gọi.

        Raises:
            httpx.HTTPStatusError: Lỗi HTTP nếu vượt quá số lần retry hoặc lỗi không thể phục hồi.
        """
        last_exc: httpx.HTTPStatusError | None = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in (429, 500, 502, 503, 504):
                    raise
                last_exc = e
                if attempt < self.cfg.max_retries:
                    wait = self._retry_after(e.response) or (2**attempt)
                    await asyncio.sleep(wait)
        if last_exc:
            raise last_exc

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        """Đọc thời gian chờ được khuyến nghị từ HTTP Header Retry-After.

        Args:
            response (httpx.Response): Đối tượng phản hồi từ server.

        Returns:
            float | None: Số giây cần chờ, hoặc None nếu không tồn tại hoặc sai định dạng.
        """
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    def _parse_info(self, data: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
        """Trích xuất và chuẩn hóa metadata đo kiểm từ dữ liệu thô của OpenRouter.

        Args:
            data (dict[str, Any]): Dữ liệu JSON gốc trả về từ API.
            elapsed_ms (int): Tổng thời gian phản hồi (latency) tính bằng ms.

        Returns:
            dict[str, Any]: Metadata chuẩn hóa cho logging và đánh giá hiệu năng Agent.
        """
        usage = data.get("usage") or {}
        prompt_details = usage.get("prompt_tokens_details") or {}
        completion_details = usage.get("completion_tokens_details") or {}
        choices = data.get("choices") or []
        finish_reason = choices[0].get("finish_reason") if choices else None

        return {
            "request_id": data.get("id"),
            "model": data.get("model", self.cfg.model),
            "provider": data.get("provider", "unknown"),
            "input_token": usage.get("prompt_tokens", 0),
            "output_token": usage.get("completion_tokens", 0),
            "total_token": usage.get("total_tokens", 0),
            "reasoning_token": completion_details.get("reasoning_tokens", 0),
            "cached_token": prompt_details.get("cached_tokens", 0),
            "cost": float(usage.get("cost", 0.0)),
            "time": elapsed_ms,
            "finish_reason": finish_reason,
        }

    async def generate(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        """Gửi yêu cầu sinh văn bản thông thường từ LLM.

        Args:
            messages (list[dict[str, str]]): Lịch sử hội thoại.
            **kwargs (Any): Cấu hình bổ sung cho model.

        Returns:
            dict[str, Any]: Dạng chuẩn gồm 'response' (str) và 'info' (dict).
        """
        payload = self._payload(messages, **kwargs)
        start_time = time.perf_counter()

        async def _post() -> dict[str, Any]:
            response = await self.client.post(
                url=self.cfg.url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

        data = await self._retry(_post)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        content = data["choices"][0]["message"]["content"] or ""

        return {
            "response": content,
            "info": self._parse_info(data, elapsed_ms),
        }

    async def stream_generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Gửi yêu cầu stream văn bản từng đoạn về Presentation Layer.

        Tự động cấu hình kèm stream_options để thu thập usage metrics ở chunk cuối cùng.

        Args:
            messages (list[dict[str, str]]): Lịch sử hội thoại.
            **kwargs (Any): Cấu hình bổ sung.

        Yields:
            dict[str, Any]: Định dạng chuẩn gồm 'response' (str chunk) và 'info' (None hoặc dict ở chunk cuối).
        """
        payload = self._payload(
            messages,
            stream=True,
            stream_options={"include_usage": True},
            **kwargs,
        )
        start_time = time.perf_counter()
        accumulated_meta: dict[str, Any] = {"choices": []}

        async with self.client.stream(
            "POST",
            url=self.cfg.url,
            headers=self._headers(),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue

                raw_data = line[len("data: ") :].strip()
                if raw_data == "[DONE]":
                    break

                try:
                    chunk = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue

                for key in ("id", "model", "provider", "usage"):
                    if key in chunk and chunk[key]:
                        accumulated_meta[key] = chunk[key]

                choices = chunk.get("choices", [])
                if choices:
                    delta = choices[0].get("delta", {})
                    content_chunk = delta.get("content", "")
                    if choices[0].get("finish_reason"):
                        accumulated_meta["choices"] = choices

                    if content_chunk:
                        yield {"response": content_chunk, "info": None}

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            yield {
                "response": "",
                "info": self._parse_info(accumulated_meta, elapsed_ms),
            }

    async def structured_generate(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Gửi yêu cầu ép kiểu cấu trúc dữ liệu trả về theo Schema của Pydantic Model.

        Args:
            messages (list[dict[str, str]]): Lịch sử hội thoại.
            response_model (type[T]): Lớp Pydantic Model dùng làm khuôn mẫu xác thực dữ liệu.
            **kwargs (Any): Cấu hình bổ sung.

        Returns:
            dict[str, Any]: Dạng chuẩn gồm 'response' (Pydantic Model) và 'info' (dict).
        """
        payload = self._payload(
            messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,
                    "strict": True,
                    "schema": response_model.model_json_schema(),
                },
            },
            **kwargs,
        )
        start_time = time.perf_counter()

        async def _post() -> dict[str, Any]:
            response = await self.client.post(
                url=self.cfg.url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

        data = await self._retry(_post)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        content = data["choices"][0]["message"]["content"]
        parsed_response = response_model.model_validate_json(content)

        return {
            "response": parsed_response,
            "info": self._parse_info(data, elapsed_ms),
        }


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()

    async def _test() -> None:
        client = LLMClient(os.environ["OPENROUTER_API_KEY"])
        messages = [{"role": "user", "content": "Say hello in one sentence."}]

        try:
            print("=== generate ===")
            result = await client.generate(messages)
            print(f"Response: {result['response']}")
            print(f"Info: {json.dumps(result['info'], indent=2)}")

            print("\n=== stream_generate ===")
            async for chunk in client.stream_generate(messages):
                if chunk["response"]:
                    print(chunk["response"], end="", flush=True)
                if chunk["info"]:
                    print(f"\nFinal Stream Info: {json.dumps(chunk['info'], indent=2)}")

            print("\n=== structured_generate ===")

            class PersonInfo(BaseModel):
                model_config = ConfigDict(extra="forbid")
                name: str
                age: int

            test_messages = [
                {
                    "role": "user",
                    "content": "Generate a JSON with name John Doe and age 30.",
                }
            ]
            structured = await client.structured_generate(
                test_messages, response_model=PersonInfo
            )
            print(f"Response Model: {repr(structured['response'])}")
            print(f"Info: {json.dumps(structured['info'], indent=2)}")

        finally:
            await client.aclose()

    asyncio.run(_test())