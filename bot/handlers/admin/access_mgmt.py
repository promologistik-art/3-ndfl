from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from core.models import User, Payment, AdminLog, get_session
from bot.config import ADMIN_IDS, ACCESS_DEMO, ACCESS_MONTHLY, ACCESS_UNLIMITED
from bot.keyboards.admin import admin_grant_type_kb, admin_back_kb
from sqlalchemy import select

router = Router()


class AccessStates(StatesGroup):
    waiting_for_username = State()


@router.callback_query(F.data == "admin_grant")
async def admin_grant(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    await callback.message.edit_text(
        "👤 Введите никнейм пользователя (@username), которому нужно выдать доступ:",
        reply_markup=admin_back_kb()
    )
    await state.set_state(AccessStates.waiting_for_username)
    await callback.answer()


@router.message(AccessStates.waiting_for_username)
async def process_username(message: Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("Доступ запрещён")
        await state.clear()
        return

    raw = message.text.strip()
    # Убираем @ если есть
    username = raw.lstrip("@")

    if not username:
        await message.answer("❌ Введите никнейм.")
        return

    session = next(get_session())
    try:
        result = session.execute(
            select(User).where(User.username == username)
        )
        user = result.scalar_one_or_none()

        if not user:
            await message.answer(
                f"❌ Пользователь с никнеймом <b>@{username}</b> не найден в базе.\n"
                f"Возможно, он ещё не запускал бота или скрыл никнейм."
            )
            await state.clear()
            return

        await state.update_data(target_user_id=user.telegram_id)

        access_text_map = {
            "demo": "🆓 Демо",
            "monthly": "📅 Месячный",
            "unlimited": "♾️ Безлимит"
        }
        current_access = access_text_map.get(user.access_type, "Неизвестно")

        await message.answer(
            f"👤 Пользователь: <b>{user.first_name or '—'}</b> (@{user.username or '—'})\n"
            f"🆔 ID: <code>{user.telegram_id}</code>\n"
            f"📌 Текущий доступ: <b>{current_access}</b>\n\n"
            f"Выберите тип доступа для выдачи:",
            reply_markup=admin_grant_type_kb(user.telegram_id)
        )
    finally:
        session.close()

    await state.clear()


@router.callback_query(F.data.startswith("grant_"))
async def grant_access(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    _, access_type, user_id = callback.data.split("_", 2)
    user_id = int(user_id)

    session = next(get_session())
    try:
        result = session.execute(
            select(User).where(User.telegram_id == user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            await callback.answer("Пользователь не найден", show_alert=True)
            return

        admin_result = session.execute(
            select(User).where(User.telegram_id == callback.from_user.id)
        )
        admin = admin_result.scalar_one()

        amount = 0
        if access_type == ACCESS_MONTHLY:
            amount = 100
            user.access_type = ACCESS_MONTHLY
            user.access_expires = datetime.now(timezone.utc) + timedelta(days=30)
            user.declarations_used = 0
        elif access_type == ACCESS_UNLIMITED:
            amount = 500
            user.access_type = ACCESS_UNLIMITED
            user.access_expires = None
            user.declarations_used = 0
        elif access_type == ACCESS_DEMO:
            amount = 0
            user.access_type = ACCESS_DEMO
            user.access_expires = None
            user.declarations_used = 0

        session.commit()

        payment = Payment(
            user_id=user.id,
            amount=amount,
            access_type=access_type,
            admin_id=admin.id
        )
        session.add(payment)

        log = AdminLog(
            admin_id=admin.id,
            action=f"Выдан доступ {access_type}",
            details=f"Пользователь @{user.username}, сумма={amount}₽"
        )
        session.add(log)

        session.commit()

        access_names = {
            "demo": "🆓 Демо",
            "monthly": "📅 Месячный (100₽)",
            "unlimited": "♾️ Безлимит (500₽)"
        }

        await callback.message.edit_text(
            f"✅ Доступ успешно выдан!\n\n"
            f"👤 Пользователь: <b>{user.first_name or '—'}</b> (@{user.username or '—'})\n"
            f"📌 Новый доступ: <b>{access_names.get(access_type, access_type)}</b>",
            reply_markup=admin_back_kb()
        )

        try:
            await callback.bot.send_message(
                chat_id=user_id,
                text=(
                    f"🎉 Ваш доступ обновлён!\n\n"
                    f"📌 Новый тариф: <b>{access_names.get(access_type, access_type)}</b>\n\n"
                    f"Используйте /start для продолжения."
                )
            )
        except Exception:
            pass

    finally:
        session.close()

    await callback.answer()