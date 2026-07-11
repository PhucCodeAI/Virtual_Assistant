import json
import time
import asyncio
from config import configs
from fastapi import APIRouter
from utils.logger import get_logger
from dtos.chat_request import ChatRequest
from services.llm_engine import LLMEngine
from fastapi.responses import StreamingResponse

log = get_logger(__name__)

chat_router = APIRouter()
llm = LLMEngine()

@chat_router.post("/chat")
async def process_stream(req: ChatRequest) -> StreamingResponse:
    """
    Docstring: Endpoint tiếp nhận JSON Body và trả về luồng text stream.
    Đường dẫn thực tế khi gộp vào router tổng sẽ là: /v1/chat
    """
    log.info(f"Nhận request: {req}")

    raw_messages = [
        msg.model_dump() if hasattr(msg, "dict") else msg 
        for msg in req.messages
    ]

    async def process():
        start_time = time.perf_counter()
        generated_tokens = 0
        prompt_tokens = 0
        
        prompt_tokens = llm._get_input_tokens(raw_messages)

        if prompt_tokens > configs.llm_engine.n_ctx - configs.llm_engine.max_tokens:
            error_msg = f"Error: Token của request vượt quá giới hạn ({prompt_tokens} > {configs.llm_engine.n_ctx - configs.llm_engine.max_tokens}). Vui lòng giảm độ dài input"
            log.error(error_msg)
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
            return

        sync_generator = llm.generate_stream(raw_messages, temperature=req.temperature, top_p=req.top_p)
        
        while True:
            chunk = await asyncio.to_thread(next, sync_generator, None)
            
            if chunk is None:
                break
            
            if "usage" in chunk and chunk["usage"]:
                prompt_tokens = chunk["usage"].get("prompt_tokens", prompt_tokens)

            if "choices" in chunk and len(chunk["choices"]) > 0:
                delta = chunk["choices"][0].get("delta", {})
                token = delta.get("content", "")
                
                if token:
                    generated_tokens += 1
                    payload = {"type": "text", "content": token}
                    yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"

        elapsed_time = time.perf_counter() - start_time
        throughput = round(generated_tokens / elapsed_time, 2) if elapsed_time > 0 else 0

        meta_payload = {
            "type": "metadata",
            "metrics": {
                "throughput_tps": throughput,
                "context_length": prompt_tokens + generated_tokens,
                "generated_tokens": generated_tokens,
                "elapsed_time_sec": round(elapsed_time, 2)
            }
        }
        yield f"data: {json.dumps(meta_payload, ensure_ascii=False)}\n\n"
        
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        process(), 
        media_type="text/event-stream"
    )
