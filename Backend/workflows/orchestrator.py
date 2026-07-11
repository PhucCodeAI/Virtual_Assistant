from .coding_agent.agent import CodingAgent
from .base_agent import BaseAgent

class AgentOrchestrator:
    def __init__(self) -> None:
        # Khởi tạo các Agent và đăng ký vào Registry
        # Toàn bộ Agent chia sẻ chung một LLM Engine để tiết kiệm VRAM
        self._registry: dict[str, BaseAgent] = {
            "coding": CodingAgent()
        }

    async def execute(self, agent_name: str, query: str, history: list) -> AsyncGenerator[str, None]:
        """
        Nhận tên Agent được chọn từ UI và thực thi luồng chạy trực tiếp.
        
        -Input: agent_name (str, Tên Agent được người dùng click chọn trên UI)
        -Input: query (str, Nội dung câu hỏi của người dùng)
        -Input: history (list, Lịch sử trò chuyện)
        -Output: AsyncGenerator[str, None] (Luồng text stream trả về cho Controller)
        """
        agent = self._registry.get(agent_name.lower())