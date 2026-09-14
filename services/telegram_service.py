"""
Telegram Background Service (Business Logic Layer).
Đã bổ sung Debug Logging bằng Loguru để theo dõi luồng tin nhắn.
"""

import asyncio
from collections.abc import Awaitable, Callable

import httpx
from loguru import logger  # Đồng bộ với Logger toàn project của bạn


class TelegramService:
    """Service xử lý kết nối ngầm với Telegram."""

    def __init__(self, bot_token: str, allowed_chat_ids: list[int]):
        """
        Khởi tạo Telegram Service.
        """
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        # Ép kiểu int cho tất cả Chat ID để tránh lỗi so sánh string vs int
        self.allowed_chat_ids = [int(cid) for cid in allowed_chat_ids if cid]
        self.offset = 0
        self.is_running = False

    async def send_message(self, chat_id: int, text: str) -> bool:
        """
        Gửi tin nhắn phản hồi tới Telegram.
        Tự động fallback về Plain Text nếu câu trả lời từ LLM chứa Markdown lỗi.
        """
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                res = await client.post(url, json=payload)

                # Nếu Telegram từ chối do lỗi cú pháp Markdown (HTTP status 400)
                if res.status_code == 400 and "can't parse entities" in res.text:
                    logger.warning(
                        "[TelegramService] LLM trả về Markdown sai cú pháp. Đang retry gửi lại dạng Plain Text..."
                    )
                    payload.pop(
                        "parse_mode", None
                    )  # Xóa parse_mode để gửi dạng Text thuần
                    res = await client.post(url, json=payload)

                if res.status_code != 200:
                    logger.error(
                        f"[TelegramService] Gửi tin thất bại status={res.status_code}: {res.text}"
                    )
                return res.status_code == 200

            except Exception as e:
                logger.error(f"[TelegramService] Lỗi gửi tin nhắn: {e}")
                return False

    async def start_polling(
        self, message_handler: Callable[[int, str], Awaitable[str]]
    ):
        """
        Khởi chạy Long Polling lắng nghe tin nhắn mới.
        """
        self.is_running = True
        logger.info(
            f"[TelegramService] Bắt đầu Polling... Allowed Chat IDs danh sách: {self.allowed_chat_ids}"
        )

        async with httpx.AsyncClient(timeout=35.0) as client:
            while self.is_running:
                try:
                    url = f"{self.api_url}/getUpdates"
                    params = {"offset": self.offset, "timeout": 30}

                    response = await client.get(url, params=params)

                    # Nếu Telegram trả lỗi (Ví dụ 401 Unauthorized do sai Token)
                    if response.status_code != 200:
                        logger.warning(
                            f"[TelegramService] getUpdates thất bại Status={response.status_code}: {response.text}"
                        )
                        await asyncio.sleep(5)
                        continue

                    data = response.json()
                    results = data.get("result", [])

                    for result in results:
                        self.offset = result["update_id"] + 1
                        message = result.get("message", {})
                        chat_id = message.get("chat", {}).get("id")
                        text = message.get("text", "")

                        if not chat_id:
                            continue

                        # IN LOG MỌI TIN NHẮN BẮT ĐƯỢC
                        logger.info(
                            f"[Nhận yêu cầu từ Telegram] Chat ID: {chat_id} | Text: '{text}'"
                        )

                        if not text:
                            continue

                        # Gọi Handler xử lý logic
                        bot_reply = await message_handler(chat_id, text)

                        # Trả lời lại người dùng
                        if bot_reply:
                            await self.send_message(chat_id, bot_reply)

                except asyncio.CancelledError:
                    self.is_running = False
                    break
                except Exception as e:
                    logger.error(
                        f"[TelegramService] Lỗi ngoại lệ trong vòng lặp Polling: {e}"
                    )
                    await asyncio.sleep(3)

    def stop(self):
        """Dừng service."""
        self.is_running = False
