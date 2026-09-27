import asyncio
import time
from typing import Any

import httpx
from config import configs


class EmbeddingClient:
    """Client xử lý Vector Embedding thông qua API.

    Chuyển đổi danh sách văn bản thành vector biểu diễn ngữ nghĩa bằng giao thức HTTP bất đồng bộ.
    Hỗ trợ chia lô tự động (batching), xử lý song song có kiểm soát luồng (semaphore) và thu thập metadata giám sát chi phí/token.
    """

    def __init__(self, api_key: str):
        """Khởi tạo EmbeddingClient.

        Args:
            api_key (str): Khóa xác thực API của OpenRouter.
        """
        self.cfg = configs.embedding
        self.client = httpx.AsyncClient(timeout=60)
        self.api_key = api_key
        self._semaphore = asyncio.Semaphore(getattr(self.cfg, "concurrency", 5))

    async def aclose(self) -> None:
        """Đóng kết nối HTTP Client an toàn."""
        await self.client.aclose()

    def _headers(self) -> dict[str, str]:
        """Tạo HTTP Headers chuẩn cho OpenRouter API.

        Returns:
            dict[str, str]: Dictionary chứa thông tin Authorization và Content-Type.
        """
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _retry(self, func: Any, *args: Any, **kwargs: Any) -> Any:
        """Cơ chế retry lũy thừa xử lý lỗi.

        Args:
            func (Any): Hàm bất đồng bộ cần bọc cơ chế retry.
            *args (Any): Tham số vị trí.
            **kwargs (Any): Tham số định danh.

        Returns:
            Any: Kết quả từ phản hồi hợp lệ.

        Raises:
            httpx.HTTPStatusError: Lỗi HTTP nếu vượt quá số lần retry tối đa.
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
                    retry_after = e.response.headers.get("Retry-After")
                    try:
                        wait = float(retry_after) if retry_after else 2**attempt
                    except ValueError:
                        wait = 2**attempt
                    await asyncio.sleep(wait)
        if last_exc:
            raise last_exc

    async def _embed_batch(self, batch_texts: list[str]) -> dict[str, Any]:
        """Gửi 1 batch văn bản lên API OpenRouter để lấy vector embeddings.

        Args:
            batch_texts (list[str]): Danh sách văn bản trong một batch.

        Returns:
            dict[str, Any]: Phản hồi JSON gốc từ server.
        """
        payload = {
            "model": self.cfg.model,
            "input": batch_texts,
        }

        async def _post() -> dict[str, Any]:
            async with self._semaphore:
                response = await self.client.post(
                    url=self.cfg.url,
                    headers=self._headers(),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()

        return await self._retry(_post)

    async def get_embeddings(self, texts: list[str]) -> dict[str, Any]:
        """Tạo vector embeddings cho danh sách văn bản và tổng hợp metadata.

        Tự động phân mảnh danh sách thành nhiều batch và thực thi đồng thời, sau đó sắp xếp lại theo đúng thứ tự ban đầu của đầu vào.

        Args:
            texts (list[str]): Danh sách các đoạn văn bản cần tạo vector.

        Returns:
            dict[str, Any]: Dữ liệu trả về chuẩn hóa:
                - response (list[list[float]]): Array 2 chiều chứa các vector nhúng.
                - info (dict): Metadata phục vụ giám sát Agent.
        """
        if not texts:
            return {
                "response": [],
                "info": {
                    "model": self.cfg.model,
                    "input_token": 0,
                    "output_token": 0,
                    "total_token": 0,
                    "cost": 0.0,
                    "time": 0,
                    "batch_count": 0,
                },
            }

        start_time = time.perf_counter()
        batch_size = self.cfg.batch_size
        batches = [
            texts[i : i + batch_size] for i in range(0, len(texts), batch_size)
        ]

        batch_tasks = [self._embed_batch(batch) for batch in batches]
        results = await asyncio.gather(*batch_tasks)

        all_embeddings: list[list[float]] = []
        total_tokens = 0
        total_cost = 0.0
        provider = "unknown"

        for result in results:
            usage = result.get("usage") or {}
            total_tokens += usage.get("prompt_tokens") or usage.get("total_tokens", 0)
            total_cost += float(usage.get("cost", 0.0))
            if "provider" in result:
                provider = result["provider"]

            sorted_data = sorted(result["data"], key=lambda item: item["index"])
            all_embeddings.extend([item["embedding"] for item in sorted_data])

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        info = {
            "model": self.cfg.model,
            "provider": provider,
            "input_token": total_tokens,
            "output_token": 0,
            "total_token": total_tokens,
            "cost": total_cost,
            "time": elapsed_ms,
            "batch_count": len(batches),
        }

        return {
            "response": all_embeddings,
            "info": info,
        }

    async def get_embedding(self, text: str) -> dict[str, Any]:
        """Tiện ích tạo vector embedding cho một chuỗi văn bản đơn lẻ.

        Args:
            text (str): Đoạn văn bản cần nhúng vector.

        Returns:
            dict[str, Any]: Gồm 'response' (list[float] 1 chiều) và 'info' (dict metadata).
        """
        result = await self.get_embeddings([text])
        return {
            "response": result["response"][0] if result["response"] else [],
            "info": result["info"],
        }


if __name__ == "__main__":
    import os

    from dotenv import load_dotenv

    load_dotenv()

    async def _test() -> None:
        client = EmbeddingClient(os.environ["OPENROUTER_API_KEY"])
        test_corpus = [
            "Khởi tạo hệ thống autonomous coding agent.",
            "Tối ưu hóa pipeline với AsyncIO và Pydantic.",
            "Kiến trúc 3 lớp: Presentation, Business Logic, Data Access.",
        ]

        try:
            print("=== get_embeddings ===")
            result = await client.get_embeddings(test_corpus)
            vectors = result["response"]
            print(f"Số lượng vector nhận được: {len(vectors)}")
            if vectors:
                print(f"Kích thước vector chiều không gian: {len(vectors[0])}")
            print(f"Info đo kiểm: {result['info']}")

            print("\n=== get_embedding (Single text) ===")
            single_result = await client.get_embedding(test_corpus[0])
            print(f"Vector size: {len(single_result['response'])}")
            print(f"Single Info: {single_result['info']}")

        finally:
            await client.aclose()

    asyncio.run(_test())