# Backend/workflows/orchestrator.py

import inspect
import json
from collections.abc import AsyncGenerator

from dtos.orchestrator import AgentRequest
from dtos.response import PlaningResponse, RoutingAgentResponse
from loguru import logger
from services.llm_engine import LLMEngine

from .base_agent import PlanningAgent, RoutingAgent
from .coding_agent.agent import CodingAgent


class AgentOrchestrator:
    """
    Đầu não điều phối toàn bộ hệ thống Multi-Agent.
    Chịu trách nhiệm: Routing ➔ Planning (nếu hard) ➔ Executing Agent ➔ Stream SSE Events & Text.
    """

    def __init__(self, llm: LLMEngine) -> None:
        """
        Khởi tạo Orchestrator và các Agent thành phần.

        -Input: llm (LLMEngine, Engine thực thi LLM chính)
        -Output: None
        """
        self.llm = llm
        self.router = RoutingAgent(llm)
        self.planner = PlanningAgent(llm)

        self.agents = {
            "coding": CodingAgent(self.llm),
            # "analyst": AnalystAgent(llm),
        }

    def _emit_event(
        self, node_name: str, status: str, detail: dict | None = None
    ) -> str:
        """
        Đóng gói sự kiện Workflow dạng SSE JSON gửi lên Svelte UI.

        -Input: node_name (str), status (str), detail (dict | None)
        -Output: str (Chuỗi SSE formatted 'data: {...}\n\n')
        """
        payload = {
            "type": "workflow_event",
            "node": node_name,
            "status": status,  # "running", "success", "error"
            "detail": detail or {},
        }
        return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

    def _build_planned_prompt(self, original_query: str, plan: PlaningResponse) -> str:
        """Format lại prompt câu hỏi kèm theo kế hoạch đã lập từ Planner."""
        steps_text = "\n".join(
            [
                f"{i + 1}. {step.action} (Mục tiêu: {step.target or 'Hoàn thành bước này'})"
                for i, step in enumerate(plan.steps)
            ]
        )
        return (
            f"Yêu cầu gốc từ người dùng: {original_query}\n\n"
            f"Kế hoạch thực thi khuyến nghị:\n"
            f"Lời dẫn: {plan.intro}\n"
            f"Lý do: {plan.reason}\n"
            f"Các bước thực hiện:\n{steps_text}\n\n"
            f"Hãy dựa trên kế hoạch trên để trả lời đầy đủ, chính xác và chi tiết cho người dùng."
        )

    async def execute_stream(self, req: AgentRequest) -> AsyncGenerator[str, None]:
        """
        Luồng điều phối chính: Routing ➔ Planning (nếu cần) ➔ Execution Stream.

        -Input: req (AgentRequest, DTO chứa lịch sử chat và cấu hình)
        -Output: AsyncGenerator[str, None] (Luồng SSE Stream gửi cho Controller)
        """
        try:
            # Lấy câu hỏi mới nhất từ người dùng
            user_query = req.messages[-1].content if req.messages else ""
            logger.info(f"Orchestrator: {user_query}")

            # ==========================================
            # BƯỚC 1: ROUTING (Điều hướng & Đánh giá độ khó)
            # ==========================================
            yield self._emit_event("Router", "running")

            routing_res: RoutingAgentResponse = await self.router.run(req)

            yield self._emit_event(
                "Router",
                "success",
                {
                    "selected_agent": routing_res.agent_name,
                    "difficulty": routing_res.difficulty,
                    "reason": routing_res.reason_for_agent,
                },
            )

            # ==========================================
            # BƯỚC 2: PLANNING (Chỉ chạy khi difficulty == 'hard')
            # ==========================================
            plan_res: PlaningResponse | None = None
            if routing_res.difficulty == "hard":
                yield self._emit_event("Planner", "running")

                plan_res = await self.planner.run(user_query)

                yield self._emit_event(
                    "Planner",
                    "success",
                    {
                        "intro": plan_res.intro,
                        "reason": plan_res.reason,
                        "total_steps": len(plan_res.steps),
                    },
                )

            # ==========================================
            # BƯỚC 3: EXECUTION (Chuyển giao cho Agent thực thi)
            # ==========================================
            target_agent_name = routing_res.agent_name
            yield self._emit_event(f"{target_agent_name.capitalize()}Agent", "running")

            user_system_messages = [
                m.model_dump() for m in req.messages if m.role == "system"
            ]
            clean_history = [m.model_dump() for m in req.messages if m.role != "system"]

            if plan_res and clean_history:
                planned_content = self._build_planned_prompt(user_query, plan_res)
                clean_history[-1]["content"] = planned_content

            # ==========================================
            # BƯỚC 4: EXECUTION STREAM
            # ==========================================
            if target_agent_name in self.agents:
                # Trường hợp 1: Chạy Agent chuyên biệt -> Agent tự đè System Prompt riêng của nó
                target_agent = self.agents[target_agent_name]
                async for chunk in target_agent.run_stream(
                    clean_history, req.temperature, req.top_p
                ):
                    yield chunk
            else:
                # Trường hợp 2: Fallback (Tôn trọng và BẢO TỒN System Prompt gốc của Người dùng/Controller)
                if not user_system_messages:
                    user_system_messages = [
                        {
                            "role": "system",
                            "content": "Bạn là Trợ lý AI cá nhân chuyên nghiệp.",
                        }
                    ]

                # Gộp tất cả System Prompt gốc của user thành 1 duy nhất ở Index 0
                merged_user_system = "\n\n".join(
                    [m["content"] for m in user_system_messages if m.get("content")]
                )
                fallback_messages = [
                    {"role": "system", "content": merged_user_system}
                ] + clean_history

                async for chunk in self.llm.generate_stream(
                    messages=fallback_messages,
                    temperature=req.temperature,
                    top_p=req.top_p,
                ):
                    yield chunk

            yield self._emit_event(f"{target_agent_name.capitalize()}Agent", "success")

        except Exception as e:
            logger.error(f"[Orchestrator] Lỗi trong quá trình điều phối: {e!s}")
            yield self._emit_event("System", "error", {"error_message": str(e)})
            yield "data: [DONE]\n\n"

    async def execute_non_stream(self, messages: list[dict[str, str]]) -> str:
        """
        Luồng điều phối chính (Non-stream): Routing ➔ Planning ➔ Execution.
        Dùng logger.info theo dõi các bước và return trực tiếp kết quả.
        """
        try:
            user_query = messages[-1]["content"]
            logger.info(f"[Orchestrator] Processing query: {user_query}")

            # 1. Routing Step
            routing_res: RoutingAgentResponse = await self.router.run(messages)

            # 2. Planning Step (nếu câu hỏi khó)
            plan_res: PlaningResponse | None = None
            if routing_res.difficulty == "hard":
                plan_res = await self.planner.run(user_query)

            target_agent_name = routing_res.agent_name
            user_system_messages = [m for m in messages if m["role"] == "system"]
            clean_history = [m for m in messages if m["role"] != "system"]

            if plan_res and clean_history:
                planned_content = self._build_planned_prompt(user_query, plan_res)
                clean_history[-1]["content"] = planned_content

            # 3. Execution Step
            if target_agent_name in self.agents:
                target_agent = self.agents[target_agent_name]
                return await target_agent.run(clean_history)

            else:
                # Fallback: Tôn trọng System Prompt gốc
                logger.info("[Orchestrator] Executing fallback LLM...")
                if not user_system_messages:
                    user_system_messages = [
                        {
                            "role": "system",
                            "content": "Bạn là Trợ lý AI cá nhân chuyên nghiệp. Hãy trả dữ liệu về với người dùng dưới dạng Markdown",
                        }
                    ]

                merged_user_system = "\n\n".join(
                    [m["content"] for m in user_system_messages if m.get("content")]
                )
                fallback_messages = [
                    {"role": "system", "content": merged_user_system}
                ] + clean_history

                return await self.llm.generate_non_stream(messages=fallback_messages)

        except Exception as e:
            logger.error(f"[Orchestrator] Lỗi trong quá trình điều phối: {e!s}")
            return f"❌ Lỗi Orchestrator: {e!s}"
