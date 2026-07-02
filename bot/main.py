import sys
import os

# Добавляем корень проекта в sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from bot.config import BOT_TOKEN, DATA_TEMP_DIR
from bot.middlewares.access import AccessMiddleware
from bot.handlers.user.start import router as user_start_router
from bot.handlers.user.upload import router as user_upload_router
from bot.handlers.user.profile import router as user_profile_router
from bot.handlers.admin.panel import router as admin_panel_router
from bot.handlers.admin.access_mgmt import router as admin_access_router
from core.models import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    # Создаём временную папку
    os.makedirs(DATA_TEMP_DIR, exist_ok=True)

    # Инициализация БД
    await init_db()
    logger.info("База данных инициализирована")

    # Бот и диспетчер
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    # Подключаем middleware
    dp.message.middleware(AccessMiddleware())
    dp.callback_query.middleware(AccessMiddleware())

    # Подключаем роутеры
    dp.include_router(user_start_router)
    dp.include_router(user_upload_router)
    dp.include_router(user_profile_router)
    dp.include_router(admin_panel_router)
    dp.include_router(admin_access_router)

    logger.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())