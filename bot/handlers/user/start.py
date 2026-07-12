from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from datetime import datetime, timezone
from core.models import User, Declaration, get_session
from bot.keyboards.user import main_menu_kb
from bot.keyboards.admin import admin_panel_kb
from bot.config import ADMIN_IDS
from sqlalchemy import select, func

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext, user: User = None):
    await state.clear()

    if not user:
        await message.answer("Ошибка. Попробуйте позже.")
        return

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Я помогу рассчитать налоговый вычет и сформировать декларацию 3-НДФЛ.\n\n"
        f"📌 Ваш тариф: <b>{_access_text(user.access_type)}</b>\n"
        f"📄 Осталось деклараций: <b>{_remaining_text(user)}</b>",
        reply_markup=main_menu_kb()
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "❓ <b>Помощь</b>\n\n"
        "Я бот для расчёта налоговых вычетов и заполнения декларации 3-НДФЛ.\n\n"
        "<b>Какие вычеты поддерживаются:</b>\n"
        "🏥 Медицинские услуги\n🎓 Обучение\n🏠 Имущественный вычет\n📈 Инвестиционный вычет (в разработке)\n\n"
        "<b>Как пользоваться:</b>\n"
        "1. Нажмите «Заполнить декларацию»\n"
        "2. Выберите способ: загрузить выписку или ответить на вопросы\n"
        "3. Выберите типы вычетов\n"
        "4. Введите необходимые данные\n"
        "5. Проверьте расчёт и получите декларацию\n\n"
        "<b>Тарифы:</b>\n"
        "🆓 Демо — 1 декларация, только расчёт\n"
        "📅 Месячный — 1 декларация в месяц, 100₽\n"
        "♾️ Безлимит — неограниченно, 500₽\n\n"
        "📩 По вопросам доступа: <b>@silverzen</b>"
    )
    await message.answer(text)


@router.message(Command("status"))
async def cmd_status(message: Message, user: User = None):
    if not user:
        await message.answer("Ошибка. Попробуйте позже.")
        return

    session = next(get_session())
    try:
        total_decls = session.scalar(
            select(func.count(Declaration.id)).where(Declaration.user_id == user.id)
        )
    finally:
        session.close()

    expires_text = ""
    if user.access_type == "monthly" and user.access_expires:
        now = datetime.now(timezone.utc)
        expires = user.access_expires.replace(tzinfo=timezone.utc)
        days_left = (expires - now).days
        expires_text = f"\n⏳ Дней до конца подписки: <b>{max(0, days_left)}</b>"

    text = (
        f"📊 <b>Ваш статус</b>\n\n"
        f"📌 Тариф: <b>{_access_text(user.access_type)}</b>{expires_text}\n"
        f"📄 Всего деклараций: <b>{total_decls}</b>\n"
        f"📝 Осталось: <b>{_remaining_text(user)}</b>\n\n"
        f"📩 По вопросам доступа: <b>@silverzen</b>"
    )
    await message.answer(text)


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Доступ запрещён.")
        return
    await message.answer("🔐 <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=admin_panel_kb())


@router.callback_query(F.data == "menu_back")
async def back_to_menu(callback: CallbackQuery, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return
    await callback.message.answer(
        f"👋 Главное меню\n\n📌 Тариф: <b>{_access_text(user.access_type)}</b>\n📄 Осталось деклараций: <b>{_remaining_text(user)}</b>",
        reply_markup=main_menu_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "menu_status")
async def menu_status(callback: CallbackQuery, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return
    session = next(get_session())
    try:
        total_decls = session.scalar(select(func.count(Declaration.id)).where(Declaration.user_id == user.id))
    finally:
        session.close()
    await callback.message.answer(
        f"📊 <b>Ваш статус</b>\n\n📌 Тариф: <b>{_access_text(user.access_type)}</b>\n"
        f"📄 Всего деклараций: <b>{total_decls}</b>\n📝 Осталось: <b>{_remaining_text(user)}</b>"
    )
    await callback.answer()


@router.callback_query(F.data == "menu_history")
async def menu_history(callback: CallbackQuery, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return
    from bot.handlers.user.profile import show_history
    await show_history(callback, user)
    await callback.answer()


@router.callback_query(F.data == "menu_help")
async def menu_help(callback: CallbackQuery):
    text = (
        "❓ <b>Помощь</b>\n\n"
        "Я бот для расчёта налоговых вычетов и заполнения декларации 3-НДФЛ.\n\n"
        "<b>Какие вычеты поддерживаются:</b>\n"
        "🏥 Медицинские услуги\n🎓 Обучение\n🏠 Имущественный вычет\n📈 Инвестиционный вычет (в разработке)\n\n"
        "<b>Как пользоваться:</b>\n"
        "1. Нажмите «Заполнить декларацию»\n"
        "2. Выберите способ: загрузить выписку или ответить на вопросы\n"
        "3. Выберите типы вычетов\n4. Введите необходимые данные\n5. Проверьте расчёт и получите декларацию\n\n"
        "<b>Тарифы:</b>\n🆓 Демо — 1 декларация, только расчёт\n📅 Месячный — 1 декларация в месяц, 100₽\n♾️ Безлимит — неограниченно, 500₽\n\n"
        "📩 По вопросам доступа: <b>@silverzen</b>"
    )
    await callback.message.answer(text)
    await callback.answer()


def _access_text(access_type: str) -> str:
    match access_type:
        case "demo": return "Демо"
        case "monthly": return "Месячный"
        case "unlimited": return "Безлимит"
        case _: return "Неизвестно"


def _remaining_text(user: User) -> str:
    if user.access_type == "unlimited" or user.telegram_id in ADMIN_IDS:
        return "∞"
    if user.access_type == "demo":
        return f"{max(0, 1 - user.declarations_used)} из 1"
    if user.access_type == "monthly":
        return f"{max(0, 1 - user.declarations_used)} из 1"
    return "0"