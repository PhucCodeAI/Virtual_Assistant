from workflows.base_agent import BaseAgent
from workflows.coding_agent.prompts import CodingPrompt
from services.llm_engine import LLMEngine
from dtos.orchestrator import AgentRequest
from dtos.response import PlaningResponse

class CodingAgent():
    def __init__(self, llm=None) -> None:
        self.prompts = CodingPrompt()
        self.llm = llm

    def planing(self, req: AgentRequest) -> PlaningResponse:
        system_message = [
            {
                "role": "system",
                "content": self.prompts.planing(),
            }
        ]
        
        user_history = req.messages if hasattr(req, 'messages') else req.model_dump().get("messages", [])
        
        full_messages = system_message + user_history

        temperature = getattr(req, 'temperature', 0.1)
        top_p = getattr(req, 'top_p', 0.95)

        return self.llm.generate_structured(
            messages=full_messages,
            response_model=PlaningResponse,
            temperature=temperature,
            top_p=top_p
        )
    
if __name__ == "__main__":
    agent = CodingAgent()
    req = CodingRequets(
        messages=[
            {"role": "user", "content": "Hãy lập kế hoạch chi tiết để xây dựng một ứng dụng web về lĩnh vực thương mại điện tử"}
        ],
        coding_context="Xây dựng ứng dụng web với FastAPI và React.",
        temperature=0.1,
        top_p=0.9
    )
    plan_result = agent.planing(req)
    with open("test.json", 'w', encoding="utf-8") as f:
        f.write(plan_result.model_dump_json(indent=4, ensure_ascii=False))