import asyncio
import json

import httpx
from config import configs
from pydantic import BaseModel


class LLMClient:
    def __init__(self, api_key: str):
        self.cfg = configs.llm
        self.client = httpx.AsyncClient(timeout=120)
        self.api_key = api_key

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _payload(self, messages: list[dict[str, str]], **kwargs) -> dict:
        payload = {
            "model": self.cfg.model,
            "messages": messages,
        }
        payload.update(kwargs)
        return payload

    async def _retry(self, func, *args, **kwargs):
        last_exc = None
        for attempt in range(self.cfg.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                if e.response.status_code not in (429, 500, 502, 503, 504):
                    raise
                last_exc = e
                if attempt < self.cfg.max_retries:
                    wait = self._retry_after(e.response) or 2**attempt
                    await asyncio.sleep(wait)
        raise last_exc

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        value = response.headers.get("Retry-After")
        if value is None:
            return None
        try:
            return float(value)
        except ValueError:
            return None

    async def generate(self, messages: list[dict[str, str]], **kwargs) -> dict:
        payload = self._payload(messages, **kwargs)

        async def _post():
            response = await self.client.post(
                url=self.cfg.url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            return response.json()

        return await self._retry(_post)

    async def stream_generate(self, messages: list[dict[str, str]], **kwargs):
        payload = self._payload(messages, stream=True, **kwargs)
        async with self.client.stream(
            "POST",
            url=self.cfg.url,
            headers=self._headers(),
            json=payload,
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if not line:
                    continue
                if line.startswith("data: "):
                    data = line[len("data: ") :]
                    if data == "[DONE]":
                        break
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue

    async def structured_generate(
        self,
        messages: list[dict[str, str]],
        response_model: type[BaseModel],
        **kwargs,
    ) -> BaseModel:
        payload = self._payload(
            messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": response_model.__name__,  # Tên của schema
                    "strict": True,  # Ép tuân thủ nghiêm ngặt schema
                    "schema": response_model.model_json_schema(),
                },
            },
            **kwargs,
        )

        async def _post():
            response = await self.client.post(
                url=self.cfg.url,
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            # Parse chuỗi JSON trả về thành Pydantic Model object ban đầu
            return response_model.model_validate_json(content)

        return await self._retry(_post)


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

    async def _test():
        client = LLMClient(os.environ["OPENROUTER_API_KEY"])
        messages = [{"role": "user", "content": "Say hello in one sentence."}]

        print("=== generate ===")
        result = await client.generate(messages)
        print(result)

        # print("=== stream_generate ===")
        # async for chunk in client.stream_generate(messages):
        #     delta = chunk.get("choices", [{}])[0].get("delta", {})
        #     if "content" in delta:
        #         print(delta["content"], end="", flush=True)
        # print()

        # print("=== structured_generate ===")

        # class PersonInfo(BaseModel):
        #     model_config = ConfigDict(extra="forbid")
        #     name: str
        #     age: int

        # structured = await client.structured_generate(
        #     messages, response_model=PersonInfo
        # )
        # print(structured)

    asyncio.run(_test())
