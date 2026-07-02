from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from core.models import User
from bot.keyboards.user import main_menu_kb
from bot.config import ADMIN_IDS

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, user: User = None):
    if not user:
        await message.answer("Ошибка. Попробуйте позже.")
        return

    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Я помогу рассчитать налоговый вычет и сформировать декларацию 3-НДФЛ.\n\n"
        f"📌 Ваш тариф: <b>{_access_text(user.access_type)}</b>\n"
        f"📄 Осталось деклараций: <b>{_remaining_text(user)}</b>\n\n"
        f"Загрузите банковскую выписку, а я найду подходящие платежи и запрошу недостающие данные."
    )
    await message.answer(text, reply_markup=main_menu_kb())


@router.callback_query(F.data == "menu_back")
async def back_to_menu(callback: CallbackQuery, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    text = (
        f"👋 Главное меню\n\n"
        f"📌 Тариф: <b>{_access_text(user.access_type)}</b>\n"
        f"📄 Осталось деклараций: <b>{_remaining_text(user)}</b>"
    )
    await callback.message.edit_text(text, reply_markup=main_menu_kb())
    await callback.answer()


def _access_text(access_type: str) -> str:
    match access_type:
        case "demo":
            return "Демо"
        case "monthly":
            return "Месячный"
        case "unlimited":
            return "Безлимит"
        case _:
            return "Неизвестно"


def _remaining_text(user: User) -> str:
    if user.access_type == "unlimited" or user.telegram_id in ADMIN_IDS:
        return "∞"
    if user.access_type == "demo":
        used = user.declarations_used
        return f"{max(0, 1 - used)} из 1"
    if user.access_type == "monthly":
        used = user.declarations_used
        return f"{max(0, 1 - used)} из 1"
    return "0"