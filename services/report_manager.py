# Backend/services/report_manager.py
import asyncio

from config import configs
from controller.v1.telegram import handle_message
from fastapi import FastAPI
from loguru import logger

# Nếu sau này đổi sang Discord, bạn chỉ cần sửa duy nhất dòng import này!
from services.telegram_service import TelegramService as ActiveBotService


async def start_bot_service(app: FastAPI):
    """
    Khởi tạo và chạy ngầm Bot Service.
    """
    logger.info("[BotManager] Đang khởi tạo Bot Service...")

    # 1. Khởi tạo Service
    app.state.bot_service = ActiveBotService(
        bot_token=configs.bot.bot_token, allowed_chat_ids=[configs.bot.user_id]
    )

    # 2. Handler Adapter
    async def message_dispatcher(chat_id: int, user_text: str) -> str:
        return await handle_message(
            chat_id=chat_id, user_text=user_text, orchestrator=app.state.orchestrator
        )

    # 3. Chạy Task ngầm
    app.state.telegram_task = asyncio.create_task(
        app.state.bot_service.start_polling(message_handler=message_dispatcher)
    )
    logger.info("[BotManager] Bot Service đã kích hoạt thành công!")


async def stop_bot_service(app: FastAPI):
    """
    Tắt Bot Service sạch sẽ khi ứng dụng shutdown.
    """
    if hasattr(app.state, "bot_service") and hasattr(app.state, "telegram_task"):
        logger.info("[BotManager] Đang dừng Bot Service...")
        app.state.bot_service.stop()
        app.state.telegram_task.cancel()
        try:
            await app.state.telegram_task
        except asyncio.CancelledError:
            pass
        logger.info("[BotManager] Bot Service đã dừng hẳn.")
