import asyncio
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from dtos.request import Request
from services.llm_engine import LLMEngine
from utils.logger import get_logger

log = get_logger(__name__)

# Khởi tạo APIRouter dành riêng cho module Chat
chat_router = APIRouter()
llm = LLMEngine()

@chat_router.post("/chat")
async def process_stream(request: Request):
    """
    Docstring: Endpoint tiếp nhận JSON Body và trả về luồng text stream.
    Đường dẫn thực tế khi gộp vào router tổng sẽ là: /v1/chat
    """
    log.info(f"[Chat] Nhận request: {request.messages}")

    raw_messages = [
        msg.dict() if hasattr(msg, "dict") else msg 
        for msg in request.messages
    ]

    async def process():
        sync_generator = llm.generate_stream(raw_messages)
        while True:
            chunk = await asyncio.to_thread(next, sync_generator, None)
            
            if chunk is None:
                break
                
            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                if token:
                    yield token
                    await asyncio.sleep(0.001)

    return StreamingResponse(
        process(), 
        media_type="text/plain"
    )
