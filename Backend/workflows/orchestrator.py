from workflows.coding_agent.agent import CodingAgent
from workflows.base_agent import BaseAgent, PlaningAgent
from dtos.orchestrator import AgentRequest
from workflows.general_prompts import GeneralPrompt
from utils.logger import get_logger
from services.llm_engine import LLMEngine
from dtos.response import RoutingAgentResponse


class Orchestrator:
    def __init__(self) -> None:
        self._registry: dict[str, BaseAgent] = {
            "coding": CodingAgent(),
        }
        self.log = get_logger(__name__)
        self.prompts = GeneralPrompt()

    def routing(self, req: AgentRequest, llm: LLMEngine) -> RoutingAgentResponse:
        """
        Nhận các tin nhắn từ người dùng và xác định Agent phù hợp để xử lý.
        
        -Input: req (AgentRequest, DTO chứa thông tin request từ người dùng)
        -Output: RoutingAgentResponse (Tên của Agent được chọn và reason)
        """
        system_prompt = self.prompts.ROUTING
        content = ""
        for i, message in enumerate(req.messages):
            if message.role == "system":
                content += f"##SYSTEM MESSAGE: {message.content}"
            elif message.role == "user":
                content += f"##USER MESSAGE: {message.content}"
            elif message.role == "assistant":
                content += f"##ASSISTANT MESSAGE: {message.content}"

            if i != len(req.messages) - 1:
                content += "\n---\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]

        result = llm.generate_structured(
            messages=messages,
            response_model=RoutingAgentResponse,
            temperature=req.temperature,
            top_p=req.top_p)

        self.log.info(f"Request: {req}")
        self.log.info(f"Agent Selected: {result.agent_name}")
        self.log.info(f"Agent Selected Reason: {result.reason_for_agent}")
        self.log.info(f"Difficulty: {result.difficulty}")
        self.log.info(f"Difficulty Reason: {result.reason_for_difficulty}")

        self.agent_name = result.agent_name

        if result.difficulty == "hard":
            self.planning = ""

        return result

    def execute(self, agent_name: str, req: AgentRequest):
        """
        Nhận tên Agent được chọn từ UI và thực thi luồng chạy trực tiếp.
        
        -Input: agent_name (str, Tên Agent được người dùng click chọn trên UI)
        -Input: query (str, Nội dung câu hỏi của người dùng)
        -Input: history (list, Lịch sử trò chuyện)
        -Output: AsyncGenerator[str, None] (Luồng text stream trả về cho Controller)
        """
        agent = self._registry.get(agent_name.lower())
        return agent.planing(req)


if __name__ == "__main__":
    orchestrator = Orchestrator()
    llm = LLMEngine()
    req = AgentRequest(
        messages=[
            {"role": "user", "content": "Tôi muốn chết, bạn có cách nào giúp tôi không?"}
        ],
        temperature=0.5,
        top_p=0.9
    )
    result = orchestrator.routing(req, llm)
    print(result)