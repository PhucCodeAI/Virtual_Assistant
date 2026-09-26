# Backend / workflows / base_agent.py

import asyncio

from dtos.orchestrator import AgentRequest
from dtos.response import PlaningResponse, RoutingAgentResponse
from loguru import logger
from Backend.services.llm_client import LLMEngine
from utils.utils import format_message

from .general_prompts import PLANNING, ROUTING


class PlanningAgent:
    """Agent chịu trách nhiệm phân rã yêu cầu phức tạp thành các bước xử lý (Planning)."""

    def __init__(self, llm: LLMEngine) -> None:
        """
        Khởi tạo PlanningAgent với LLMEngine được tiêm vào.

        -Input: llm (LLMEngine, Engine thực thi sinh text/structured output)
        -Output: None
        """
        self.llm = llm

    async def run(self, prompt: str) -> PlaningResponse:
        """
        Nhận yêu cầu và lập kế hoạch thực thi từng bước (Step-by-Step).

        -Input: prompt (str, Ngữ cảnh câu hỏi hoặc yêu cầu từ Router)
        -Output: PlaningResponse (DTO chứa intro, reason và danh sách steps)
        """
        messages = format_message(system_prompt=PLANNING, prompt=prompt)

        result = await asyncio.to_thread(
            self.llm.generate_structured,
            messages=messages,
            response_model=PlaningResponse,
            temperature=0.3,
            top_p=0.9,
        )

        logger.info(
            f"[PlanningAgent] Lập kế hoạch thành công với {len(result.steps)} bước."
        )
        return result


class RoutingAgent:
    """Agent chịu trách nhiệm phân loại ý định người dùng và đánh giá độ khó của yêu cầu."""

    def __init__(self, llm: LLMEngine) -> None:
        """
        Khởi tạo RoutingAgent với LLMEngine được tiêm vào.

        -Input: llm (LLMEngine, Engine thực thi sinh text/structured output)
        -Output: None
        """
        self.llm = llm

    def _format_history_to_prompt(self, messages: list) -> str:
        """Format danh sách tin nhắn lịch sử thành chuỗi văn bản phân định rõ vai trò."""
        formatted_parts = []
        for msg in messages:
            role_tag = f"##{msg.role.upper()} MESSAGE"
            formatted_parts.append(f"{role_tag}: {msg.content}")
        return "\n---\n".join(formatted_parts)

    async def run(self, req: AgentRequest) -> RoutingAgentResponse:
        """
        Phân tích tin nhắn người dùng để xác định Agent xử lý và đánh giá độ khó (easy/hard).

        -Input: req (AgentRequest, DTO chứa lịch sử tin nhắn và tham số nhiệt độ)
        -Output: RoutingAgentResponse (DTO chứa agent_name, reason, difficulty)
        """
        formatted_prompt = self._format_history_to_prompt(req.messages)

        messages = format_message(system_prompt=ROUTING, prompt=formatted_prompt)

        result = await asyncio.to_thread(
            self.llm.generate_structured,
            messages=messages,
            response_model=RoutingAgentResponse,
            temperature=req.temperature,
            top_p=req.top_p,
        )

        logger.info(
            f"[RoutingAgent] Đã điều hướng -> Agent: '{result.agent_name}' | Độ khó: '{result.difficulty}'"
        )
        return result
