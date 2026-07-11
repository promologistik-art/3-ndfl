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

    text = (
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        f"Я помогу рассчитать налоговый вычет и сформировать декларацию 3-НДФЛ.\n\n"
        f"📌 Ваш тариф: <b>{_access_text(user.access_type)}</b>\n"
        f"📄 Осталось деклараций: <b>{_remaining_text(user)}</b>\n\n"
        f"Загрузите банковскую выписку — я найду подходящие платежи, "
        f"или ответьте на вопросы — я запрошу недостающие данные.\n\n"
        f"Выберите способ заполнения:"
    )
    await message.answer(
        text,
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📄 Загрузить выписку", callback_data="choice_file")],
            [InlineKeyboardButton(text="📝 Ответить на вопросы", callback_data="choice_manual")],
        ])
    )


@router.callback_query(F.data == "choice_file")
async def choice_file(callback: CallbackQuery, state: FSMContext, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    if user.access_type == ACCESS_DEMO and user.declarations_used >= 1:
        await callback.answer("Лимит демо-доступа исчерпан", show_alert=True)
        return
    if user.access_type == "monthly" and user.declarations_used >= 1:
        await callback.answer("Лимит на этот месяц исчерпан", show_alert=True)
        return

    from bot.handlers.user.upload import UploadStates
    await state.set_state(UploadStates.waiting_for_file)
    await callback.message.edit_text(
        "📤 Отправьте банковскую выписку в формате PDF или Excel.\n\n"
        "Я проанализирую её и найду платежи, подходящие для налоговых вычетов.",
        reply_markup=None
    )
    await callback.answer()


@router.callback_query(F.data == "choice_manual")
async def choice_manual(callback: CallbackQuery, state: FSMContext):
    from bot.handlers.user.upload import UploadStates, _deduction_selection_kb
    await state.update_data(
        parsed_payments=[],
        medical_total=0,
        education_total=0,
        property_total=0,
        first_payment_date="",
        selected_deductions={},
    )
    await state.set_state(UploadStates.waiting_for_deduction_selection)
    await callback.message.edit_text(
        "Выберите вычеты, которые хотите заявить:",
        reply_markup=_deduction_selection_kb(0, 0, 0, {})
    )
    await callback.answer()


@router.message(Command("help"))
async def cmd_help(message: Message, user: User = None):
    text = (
        "❓ <b>Помощь</b>\n\n"
        "Я бот для расчёта налоговых вычетов и заполнения декларации 3-НДФЛ.\n\n"
        "<b>Какие вычеты поддерживаются:</b>\n"
        "🏥 Медицинские услуги\n"
        "🎓 Обучение\n"
        "📈 Инвестиционный вычет (в разработке)\n"
        "🏠 Имущественный вычет\n\n"
        "<b>Как пользоваться:</b>\n"
        "1. Выберите способ: загрузить выписку или ответить на вопросы\n"
        "2. Выберите типы вычетов\n"
        "3. Введите необходимые данные\n"
        "4. Проверьте расчёт и получите декларацию\n\n"
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
async def cmd_admin(message: Message, user: User = None):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Доступ запрещён.")
        return

    await message.answer(
        "🔐 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_panel_kb()
    )


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