# Backend/controller/v1/telegram.py
from collections import defaultdict

from loguru import logger

CHAT_HISTORIES = defaultdict(list)
MAX_HISTORY_MESSAGES = 10


async def handle_message(chat_id: int, user_text: str, orchestrator) -> str:
    """
    Hàm xử lý tin nhắn đa lượt (Multi-turn Conversation) cho Telegram.
    """

    # Reset lịch sử
    clean_text = user_text.strip().lower()
    if clean_text in ["/reset", "/clear", "reset", "clear"]:
        CHAT_HISTORIES[chat_id] = []
        logger.info(f"[Telegram] Đã xóa lịch sử trò chuyện của ChatID: {chat_id}")
        return "🧹 Đã xóa sạch lịch sử trò chuyện! Bạn có thể bắt đầu chủ đề mới."

    try:
        system_prompt = "You are a helpful and concise local AI assistant."
        history = CHAT_HISTORIES[chat_id]

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        # ⚡ Gọi trực tiếp Orchestrator qua await (Vì hàm giờ là async def thuần túy)
        response = await orchestrator.execute_non_stream(messages)

        # Xử lý an toàn nếu kết quả trả về dạng dict
        if isinstance(response, dict):
            response = response.get("content", str(response))
        else:
            response = str(response)

        response = response.strip()
        if not response:
            return "⚠️ AI không trả về nội dung văn bản nào."

        # Lưu vào bộ nhớ lịch sử
        history.append({"role": "user", "content": user_text})
        history.append({"role": "assistant", "content": response})

        # Cắt tỉa Sliding Window
        if len(history) > MAX_HISTORY_MESSAGES:
            CHAT_HISTORIES[chat_id] = history[-MAX_HISTORY_MESSAGES:]

        return response

    except Exception as e:
        logger.error(f"[Telegram Handler Error]: {e}")
        return f"❌ Đã xảy ra lỗi khi xử lý: {e!s}"
