# Backend/workflows/coding_agent/agent.py

import ast
import json
import re
from collections.abc import AsyncGenerator

from loguru import logger
from repositories.vectordb import VectorDB
from Backend.services.llm_client import LLMEngine
from workflows.coding_agent.prompts import CODE_GEN, SELF_HEALING


class CodingAgent:
    """
    Agent chuyên trách các tác vụ liên quan đến Lập trình (Coding).
    Tập trung vào 2 nhiệm vụ cốt lõi:
    1. Sinh mã nguồn chất lượng cao (Code Generation via Stream)
    2. Tự kiểm tra cú pháp AST & Tự chữa lành mã lỗi (Static Verification & Self-Healing)
    """

    def __init__(self, llm: LLMEngine, vectordb: VectorDB | None = None) -> None:
        """
        Khởi tạo CodingAgent với LLMEngine và VectorDB (tùy chọn).

        -Input: llm (LLMEngine), vectordb (Optional[VectorDB])
        -Output: None
        """
        self.llm = llm
        self.vectordb = vectordb

    def _verify_python_syntax(self, code_str: str) -> tuple[bool, str | None]:
        """
        Sử dụng Python AST để kiểm tra tính hợp lệ về mặt cú pháp của đoạn code.

        -Input: code_str (str, Đoạn mã nguồn Python)
        -Output: tuple[bool, Optional[str]] ((True, None) nếu hợp lệ, (False, error_message) nếu lỗi)
        """
        try:
            ast.parse(code_str)
            return True, None
        except SyntaxError as e:
            error_msg = f"SyntaxError tại dòng {e.lineno}, cột {e.offset}: {e.msg}"
            return False, error_msg

    def _extract_code_blocks(self, text: str) -> list[str]:
        """
        Trích xuất các đoạn code nằm trong cặp block ```python ... ```.

        -Input: text (str, Chuỗi văn bản phản hồi từ LLM)
        -Output: list[str] (Danh sách các đoạn code Python)
        """
        pattern = r"```python\s*(.*?)\s*```"
        return re.findall(pattern, text, re.DOTALL)

    async def run_stream(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.2,
        top_p: float = 0.95,
    ) -> AsyncGenerator[str, None]:
        """
        Luồng thực thi chính của CodingAgent:
        Inject System Prompt ➔ Stream response ➔ Check Cú pháp AST ➔ Tự sửa lỗi (nếu có).

        -Input: messages (list[dict[str, str]]), temperature (float), top_p (float)
        -Output: AsyncGenerator[str, None] (Luồng SSE Stream cho Orchestrator/Controller)
        """
        # 1. Nạp System Prompt dành riêng cho Coding
        formatted_messages = [{"role": "system", "content": CODE_GEN}] + messages

        # 2. Truy vấn RAG Context (nếu VectorDB khả dụng)
        if self.vectordb:
            user_query = messages[-1].get("content", "") if messages else ""
            rag_results = self.vectordb.search(
                user_query, top_k=2, search_type="hybrid"
            )
            if rag_results:
                context_str = "\n---\n".join([r["text"] for r in rag_results])
                formatted_messages[0]["content"] += (
                    f"\n\nNgữ cảnh mã nguồn tham khảo:\n{context_str}"
                )

        full_response_text = ""

        # 3. Stream câu trả lời từ LLM
        async for chunk in self.llm.generate_stream(
            messages=formatted_messages,
            temperature=temperature,
            top_p=top_p,
        ):
            # Tích lũy nội dung text để phục vụ kiểm tra cú pháp AST sau khi stream xong
            if chunk.startswith("data: "):
                try:
                    data_str = chunk.replace("data: ", "").strip()
                    if data_str != "[DONE]":
                        payload = json.loads(data_str)
                        if payload.get("type") == "text":
                            full_response_text += payload.get("content", "")
                except Exception:
                    pass

            yield chunk

        # 4. Static Verification: Kiểm tra cú pháp AST cho các đoạn code Python sinh ra
        code_blocks = self._extract_code_blocks(full_response_text)
        if code_blocks:
            for code in code_blocks:
                is_valid, error_msg = self._verify_python_syntax(code)
                if not is_valid:
                    logger.warning(
                        f"[CodingAgent] Phát hiện lỗi cú pháp AST: {error_msg}"
                    )

                    # 5. Self-Healing Loop: Tự động yêu cầu LLM sửa lỗi cú pháp (Tối đa 1 lần retry)
                    healing_messages = formatted_messages + [
                        {"role": "assistant", "content": full_response_text},
                        {
                            "role": "user",
                            "content": SELF_HEALING.format(
                                wrong_code=code, error_message=error_msg
                            ),
                        },
                    ]

                    # Bắn thông báo phản hồi cho UI người dùng
                    notice_payload = {
                        "type": "text",
                        "content": f"\n\n⚠️ *[Auto Self-Healing] Phát hiện lỗi cú pháp ({error_msg}). Đang tự động sửa lại...*\n\n",
                    }
                    yield f"data: {json.dumps(notice_payload, ensure_ascii=False)}\n\n"

                    # Stream đoạn code đã được sửa lỗi
                    async for fix_chunk in self.llm.generate_stream(
                        messages=healing_messages,
                        temperature=0.1,  # Nhiệt độ thấp cho tác vụ sửa lỗi
                        top_p=top_p,
                    ):
                        yield fix_chunk
                    break


if __name__ == "__main__":
    import asyncio
    import os

    from config import configs

    model_path = os.path.join(configs.setup.model_folder, configs.setup.llm_file_name)
    llm = LLMEngine(model_path=model_path)
    agent = CodingAgent(llm=llm)

    async def main_test():
        print("=== TEST RUN STREAM CODING AGENT ===")
        test_messages = [
            {"role": "user", "content": "Viết hàm tính chuỗi Fibonacci trong Python"}
        ]
        async for chunk in agent.run_stream(test_messages):
            print(chunk, end="")

    asyncio.run(main_test())
