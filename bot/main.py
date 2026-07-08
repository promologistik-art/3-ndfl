import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from bot.config import BOT_TOKEN, DATA_TEMP_DIR, ADMIN_IDS
from bot.middlewares.access import AccessMiddleware
from bot.handlers.user.start import router as user_start_router
from bot.handlers.user.upload import router as user_upload_router
from bot.handlers.user.profile import router as user_profile_router
from bot.handlers.admin.panel import router as admin_panel_router
from bot.handlers.admin.access_mgmt import router as admin_access_router
from core.models import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot):
    # Общие команды для всех
    commands = [
        BotCommand(command="start", description="🔄 Перезапуск бота"),
        BotCommand(command="help", description="❓ Помощь и инструкция"),
        BotCommand(command="status", description="📊 Мой тариф и остаток"),
    ]
    await bot.set_my_commands(commands)

    # Добавляем /admin только для админов
    for admin_id in ADMIN_IDS:
        admin_commands = commands + [
            BotCommand(command="admin", description="🔐 Админ-панель"),
        ]
        await bot.set_my_commands(admin_commands, scope={"type": "chat", "chat_id": admin_id})


async def main():
    os.makedirs(DATA_TEMP_DIR, exist_ok=True)
    init_db()
    logger.info("База данных инициализирована")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())

    dp.include_router(user_start_router)
    dp.include_router(user_upload_router)
    dp.include_router(user_profile_router)
    dp.include_router(admin_panel_router)
    dp.include_router(admin_access_router)

    await set_commands(bot)
    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())