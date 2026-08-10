from config import configs
from controller.dependencies import get_llm
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from Backend.dtos.response import ChatRequest

chat_router = APIRouter()


@chat_router.post("/chat")
async def process_stream(req: ChatRequest, llm=Depends(get_llm)) -> StreamingResponse:
    """
    Docstring: Endpoint tiếp nhận JSON Body và trả về luồng text stream.
    """
    logger.info(f"Nhận request: {req}")
    raw_messages = [
        msg.model_dump() if hasattr(msg, "dict") else msg for msg in req.messages
    ]

    prompt_tokens = llm._get_input_tokens(raw_messages)

    if prompt_tokens > configs.llm_engine.n_ctx - configs.llm_engine.max_tokens:
        error_msg = f"Error: Token của request vượt quá giới hạn ({prompt_tokens} > {configs.llm_engine.n_ctx - configs.llm_engine.max_tokens}). Vui lòng giảm độ dài input"
        logger.error(error_msg)
        return {"type": "error", "content": error_msg}

    return StreamingResponse(
        llm.generate_stream(raw_messages, req.temperature, req.top_p, prompt_tokens),
        media_type="text/event-stream",
    )
