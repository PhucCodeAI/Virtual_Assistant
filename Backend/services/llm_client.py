# Backend/services/llm_client.py
"""Module gateway giao tiếp với API LLM (Data Access Layer).

Cung cấp 3 chế độ gọi mô hình:
    - generate: sinh văn bản thông thường.
    - stream_generate: stream từng chunk qua SSE.
    - structured_generate: ép kiểu output theo Pydantic schema với 3 mode
      (json_schema / json_object / prompt_only) để tương thích mọi model.

Exception sử dụng từ package `exceptions` — không định nghĩa inline.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from typing import Any, TypeVar

import httpx
from config import configs
from exceptions import LLMResponseError, LLMSchemaError, LLMStreamError
from loguru import logger
from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class LLMClient:
    """Gateway giao tiếp với API LLM (OpenRouter-compatible)."""

    def __init__(self, api_key: str) -> None:
        """Khởi tạo LLMClient.

        Args:
            api_key: Khóa xác thực API của nhà cung cấp.

        Raises:
            ValueError: Khi api_key rỗng.
        """
        if not api_key or not api_key.strip():
            raise ValueError("api_key không được rỗng")

        self.cfg = configs.llm
        self.api_key = api_key
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=10.0,
                read=float(self.cfg.timeout_sec),
                write=30.0,
                pool=10.0,
            ),
        )

    async def aclose(self) -> None:
        """Giải phóng tài nguyên HTTP client."""
        await self.client.aclose()

    def _headers(self) -> dict[str, str]:
        """Tạo HTTP headers chuẩn cho OpenRouter.

        Returns:
            Dictionary chứa Authorization và Content-Type.
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Đóng gói payload gửi lên model.

        Args:
            messages: Lịch sử hội thoại.
            **kwargs: Tham số tinh chỉnh bổ sung.

        Returns:
            Payload JSON đã chuẩn hóa (loại bỏ reserved key khỏi kwargs).
        """
        reserved = {"model", "messages", "stream", "stream_options", "response_format"}
        safe_kwargs = {k: v for k, v in kwargs.items() if k not in reserved}
        return {
            "model": self.cfg.model,
            "messages": messages,
            **safe_kwargs,
        }

    # --------------------------------------------------------
    # Retry
    # --------------------------------------------------------
    async def _retry(
        self,
        func: Callable[[], Awaitable[T]],
        max_attempts: int | None = None,
    ) -> T:
        """Thực thi hàm async với retry lũy thừa.

        Args:
            func: Closure async không tham số.
            max_attempts: Số lần thử tối đa. Mặc định lấy từ config.

        Returns:
            Kết quả của func khi thành công.

        Raises:
            httpx.HTTPStatusError: Lỗi HTTP không thể phục hồi.
            httpx.RequestError: Lỗi network sau khi hết lượt retry.
        """
        attempts = max_attempts if max_attempts is not None else self.cfg.max_retries + 1
        last_exc: Exception | None = None

        for attempt in range(1, attempts + 1):
            try:
                return await func()
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in _RETRYABLE_STATUS:
                    raise
                last_exc = e
                wait = self._retry_after(e.response) or float(2 ** (attempt - 1))
                logger.warning(
                    "LLM HTTP {} (attempt {}/{}), retry sau {:.1f}s",
                    e.response.status_code,
                    attempt,
                    attempts,
                    wait,
                )
            except httpx.RequestError as e:
                last_exc = e
                wait = float(2 ** (attempt - 1))
                logger.warning(
                    "LLM network error (attempt {}/{}): {} — retry sau {:.1f}s",
                    attempt,
                    attempts,
                    type(e).__name__,
                    wait,
                )

            if attempt < attempts:
                await asyncio.sleep(wait)

        assert last_exc is not None
        raise last_exc

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        """Đọc header Retry-After nếu có.

        Args:
            response: Phản hồi HTTP.

        Returns:
            Số giây cần chờ, hoặc None nếu không hợp lệ.
        """
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    # --------------------------------------------------------
    # Metadata
    # --------------------------------------------------------
    def _parse_info(self, data: dict[str, Any], elapsed_ms: int) -> dict[str, Any]:
        """Chuẩn hóa metadata từ response OpenRouter.

        Args:
            data: JSON gốc từ API.
            elapsed_ms: Latency đo được (ms).

        Returns:
            Dict metadata đã normalize.
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
            "input_token": int(usage.get("prompt_tokens") or 0),
            "output_token": int(usage.get("completion_tokens") or 0),
            "total_token": int(usage.get("total_tokens") or 0),
            "reasoning_token": int(completion_details.get("reasoning_tokens") or 0),
            "cached_token": int(prompt_details.get("cached_tokens") or 0),
            "cost": float(usage.get("cost") or 0.0),
            "time": elapsed_ms,
            "finish_reason": finish_reason,
        }

    # --------------------------------------------------------
    # Public API
    # --------------------------------------------------------
    async def generate(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Gọi LLM ở chế độ non-stream.

        Args:
            messages: Lịch sử hội thoại.
            **kwargs: Cấu hình bổ sung cho model.

        Returns:
            Dict gồm 'response' (str) và 'info' (dict).
        """
        payload = self._payload(messages, **kwargs)
        start = time.perf_counter()

        async def _post() -> dict[str, Any]:
            resp = await self.client.post(
                url=self.cfg.url,
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

        data = await self._retry(_post)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
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
        """Gọi LLM ở chế độ stream (SSE).

        Chỉ retry nếu chưa yield chunk nào. Nếu đứt giữa chừng, raise
        LLMStreamError để caller quyết định fallback.

        Args:
            messages: Lịch sử hội thoại.
            **kwargs: Cấu hình bổ sung.

        Yields:
            Dict gồm 'response' (str chunk) và 'info' (None hoặc metadata cuối).

        Raises:
            LLMStreamError: Khi stream đứt giữa chừng sau khi đã yield.
        """
        payload = self._payload(
            messages,
            stream=True,
            stream_options={"include_usage": True},
            **kwargs,
        )
        start = time.perf_counter()
        accumulated: dict[str, Any] = {"choices": []}
        has_yielded = False

        try:
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

                    raw = line[len("data: ") :].strip()
                    if raw == "[DONE]":
                        break

                    try:
                        chunk = json.loads(raw)
                    except json.JSONDecodeError:
                        logger.debug("Bỏ qua chunk không parse được: {}", raw[:80])
                        continue

                    for key in ("id", "model", "provider", "usage"):
                        if chunk.get(key):
                            accumulated[key] = chunk[key]

                    choices = chunk.get("choices") or []
                    if choices:
                        delta = choices[0].get("delta") or {}
                        content_chunk = delta.get("content") or ""
                        if choices[0].get("finish_reason"):
                            accumulated["choices"] = choices

                        if content_chunk:
                            has_yielded = True
                            yield {"response": content_chunk, "info": None}

        except httpx.RequestError as e:
            if has_yielded:
                raise LLMStreamError(
                    f"Stream đứt giữa chừng sau khi đã yield: {e}",
                    context={"error_type": type(e).__name__},
                ) from e
            logger.warning("Stream fail trước khi yield, thử lại 1 lần: {}", e)
            async for chunk in self.stream_generate(messages, **kwargs):
                yield chunk
            return

        if "usage" not in accumulated:
            logger.warning("Stream kết thúc mà không có usage chunk — metrics có thể = 0")

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        yield {
            "response": "",
            "info": self._parse_info(accumulated, elapsed_ms),
        }

    async def structured_generate(
        self,
        messages: list[dict[str, str]],
        response_model: type[T],
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Gọi LLM và ép output khớp Pydantic schema.

        Hỗ trợ 3 mode qua configs.llm.structured_mode:
            - json_schema: dùng response_format json_schema (chuẩn nhất).
            - json_object: dùng response_format json_object + prompt schema.
            - prompt_only: chỉ prompt, tự parse JSON từ text trả về.

        Args:
            messages: Lịch sử hội thoại.
            response_model: Pydantic model dùng làm khuôn mẫu.
            **kwargs: Cấu hình bổ sung.

        Returns:
            Dict gồm 'response' (Pydantic instance) và 'info'.

        Raises:
            LLMSchemaError: Khi output không khớp schema sau khi parse.
            LLMResponseError: Khi không parse được JSON từ output.
        """
        mode = self.cfg.structured_mode

        if mode == "json_schema":
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
                include_reasoning=False,
                **kwargs,
            )
        elif mode == "json_object":
            schema_hint = (
                f"\n\nBẮT BUỘC trả về JSON hợp lệ khớp schema sau:\n"
                f"{json.dumps(response_model.model_json_schema(), ensure_ascii=False)}"
            )
            messages = self._append_system_hint(messages, schema_hint)
            payload = self._payload(
                messages,
                response_format={"type": "json_object"},
                include_reasoning=False,
                **kwargs,
            )
        else:  # prompt_only
            schema_hint = (
                f"\n\nBẮT BUỘC trả về DUY NHẤT một object JSON (không markdown fence, "
                f"không giải thích thêm) khớp schema sau:\n"
                f"{json.dumps(response_model.model_json_schema(), ensure_ascii=False)}"
            )
            messages = self._append_system_hint(messages, schema_hint)
            payload = self._payload(messages, include_reasoning=False, **kwargs)

        start = time.perf_counter()

        async def _post() -> dict[str, Any]:
            resp = await self.client.post(
                url=self.cfg.url,
                headers=self._headers(),
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()

        data = await self._retry(_post)
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        content = data["choices"][0]["message"]["content"] or ""

        parsed = self._parse_structured_content(content, response_model)

        return {
            "response": parsed,
            "info": self._parse_info(data, elapsed_ms),
        }

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------
    @staticmethod
    def _append_system_hint(
        messages: list[dict[str, str]],
        hint: str,
    ) -> list[dict[str, str]]:
        """Chèn hint vào system message hoặc tạo mới.

        Args:
            messages: Lịch sử hội thoại gốc.
            hint: Nội dung cần bổ sung.

        Returns:
            List messages mới (không mutate list gốc).
        """
        new_messages = list(messages)
        if new_messages and new_messages[0].get("role") == "system":
            new_messages[0] = {
                "role": "system",
                "content": new_messages[0]["content"] + hint,
            }
        else:
            new_messages.insert(0, {"role": "system", "content": hint.strip()})
        return new_messages

    @staticmethod
    def _parse_structured_content(content: str, response_model: type[T]) -> T:
        """Parse content thô thành Pydantic instance với fallback đa tầng.

        Thử theo thứ tự:
            1. Parse trực tiếp toàn bộ content.
            2. Strip markdown fence (```json ... ```), parse phần bên trong.
            3. Extract JSON object bằng brace-balanced scan từ content đã strip fence.

        Args:
            content: Nội dung text thô từ LLM.
            response_model: Pydantic model đích.

        Returns:
            Instance response_model.

        Raises:
            LLMResponseError: Không extract được JSON.
            LLMSchemaError: JSON không khớp schema.
        """
        candidates: list[str] = []

        stripped = content.strip()
        if stripped:
            candidates.append(stripped)

        cleaned = re.sub(r"```(?:json)?\s*", "", content)
        cleaned = cleaned.replace("```", "").strip()

        if cleaned:
            candidates.append(cleaned)
            extracted = _extract_first_json_object(cleaned)
            if extracted:
                candidates.append(extracted)

        last_error: Exception | None = None
        for candidate in candidates:
            if not candidate:
                continue
            try:
                return response_model.model_validate_json(candidate)
            except (ValidationError, ValueError) as e:
                last_error = e
                continue

        if isinstance(last_error, ValidationError):
            raise LLMSchemaError(
                f"Output không khớp schema {response_model.__name__}: {last_error}",
                context={"model": response_model.__name__, "preview": content[:200]},
            ) from last_error
        raise LLMResponseError(
            f"Không extract được JSON cho {response_model.__name__}: {last_error}",
            context={"model": response_model.__name__, "preview": content[:200]},
        ) from last_error

def _extract_first_json_object(text: str) -> str | None:
    """Extract JSON object đầu tiên bằng brace-balanced scan.

    Handle nested object/array + string escape đúng cách.

    Args:
        text: Chuỗi cần extract.

    Returns:
        Chuỗi JSON hợp lệ hoặc None nếu không tìm thấy.
    """
    start = text.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for i in range(start, len(text)):
        ch = text[i]

        if escape:
            escape = False
            continue

        if ch == "\\":
            escape = True
            continue

        if ch == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    return None


__all__ = ["LLMClient"]


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv
    from pydantic import BaseModel, ConfigDict

    load_dotenv()

    class PersonInfo(BaseModel):
        """Schema test cho structured_generate."""

        model_config = ConfigDict(extra="forbid")
        name: str
        age: int

    async def _test() -> None:
        client = LLMClient(os.environ["OPENROUTER_API_KEY"])
        messages = [{"role": "user", "content": "Say hello in one sentence."}]

        try:
            print("=== generate ===")
            result = await client.generate(messages)
            print(f"Response: {result['response']}")
            print(f"Info: {json.dumps(result['info'], indent=2, ensure_ascii=False)}")

            print("\n=== stream_generate ===")
            async for chunk in client.stream_generate(messages):
                if chunk["response"]:
                    print(chunk["response"], end="", flush=True)
                if chunk["info"]:
                    print(
                        f"\nFinal Stream Info: "
                        f"{json.dumps(chunk['info'], indent=2, ensure_ascii=False)}"
                    )

            print("\n=== structured_generate ===")
            structured = await client.structured_generate(
                [{"role": "user", "content": "Sinh JSON name=John Doe, age=30."}],
                response_model=PersonInfo,
            )
            print(f"Response Model: {structured['response']!r}")
            print(f"Info: {json.dumps(structured['info'], indent=2, ensure_ascii=False)}")

        finally:
            await client.aclose()

    asyncio.run(_test())