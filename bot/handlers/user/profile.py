from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery
from core.models import User, Declaration, get_session
from bot.keyboards.user import profile_kb, main_menu_kb
from sqlalchemy import select, func

router = Router()


@router.callback_query(F.data == "menu_profile")
async def show_profile(callback: CallbackQuery):
    user: User = callback.middleware_data.get("user")
    if not user:
        await callback.answer("Ошибка")
        return

    session_gen = get_session()
    session = await anext(session_gen)
    try:
        total_decls = await session.scalar(
            select(func.count(Declaration.id)).where(Declaration.user_id == user.id)
        )
    finally:
        await session.close()

    access_text_map = {
        "demo": "🆓 Демо",
        "monthly": "📅 Месячный",
        "unlimited": "♾️ Безлимит"
    }
    access_text = access_text_map.get(user.access_type, "Неизвестно")

    expires_text = ""
    if user.access_type == "monthly" and user.access_expires:
        now = datetime.now(timezone.utc)
        expires = user.access_expires.replace(tzinfo=timezone.utc)
        days_left = (expires - now).days
        expires_text = f"\n⏳ Дней до конца подписки: <b>{max(0, days_left)}</b>"

    remaining = _get_remaining(user)

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🆔 ID: <code>{user.telegram_id}</code>\n"
        f"📌 Тариф: <b>{access_text}</b>{expires_text}\n"
        f"📄 Деклараций создано: <b>{total_decls}</b>\n"
        f"📝 Осталось в этом месяце: <b>{remaining}</b>\n"
    )

    await callback.message.edit_text(text, reply_markup=profile_kb())
    await callback.answer()


@router.callback_query(F.data == "history")
async def show_history(callback: CallbackQuery):
    user: User = callback.middleware_data.get("user")
    if not user:
        await callback.answer("Ошибка")
        return

    session_gen = get_session()
    session = await anext(session_gen)
    try:
        result = await session.execute(
            select(Declaration)
            .where(Declaration.user_id == user.id)
            .order_by(Declaration.created_at.desc())
            .limit(10)
        )
        declarations = result.scalars().all()
    finally:
        await session.close()

    if not declarations:
        await callback.message.edit_text(
            "📋 У вас пока нет созданных деклараций.",
            reply_markup=profile_kb()
        )
        await callback.answer()
        return

    text = "📋 <b>Последние декларации:</b>\n\n"
    for d in declarations:
        type_map = {
            "medical": "🏥 Медицина",
            "education": "🎓 Обучение",
            "investment": "📈 Инвестиции",
            "property": "🏠 Имущество"
        }
        dtype = type_map.get(d.deduction_type, "—")
        status_map = {
            "draft": "Черновик",
            "calculated": "Рассчитано",
            "generated": "Готово"
        }
        status = status_map.get(d.status, "—")
        created = d.created_at.strftime("%d.%m.%Y %H:%M") if d.created_at else "—"

        text += (
            f"📄 <b>Декларация №{d.id}</b>\n"
            f"   Тип: {dtype}\n"
            f"   Статус: {status}\n"
            f"   Дата: {created}\n\n"
        )

    await callback.message.edit_text(text, reply_markup=profile_kb())
    await callback.answer()


def _get_remaining(user: User) -> str:
    if user.access_type == "unlimited":
        return "∞"
    if user.access_type == "demo":
        return f"{max(0, 1 - user.declarations_used)} из 1"
    if user.access_type == "monthly":
        return f"{max(0, 1 - user.declarations_used)} из 1"
    return "0"