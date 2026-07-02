from aiogram import Router, F
from aiogram.types import CallbackQuery
from core.models import User, Declaration, Payment, AdminLog, get_session
from bot.config import ADMIN_IDS
from bot.keyboards.admin import admin_panel_kb, admin_back_kb
from sqlalchemy import select, func

router = Router()


@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    await callback.message.edit_text(
        "🔐 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_panel_kb()
    )
    await callback.answer()


@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    session = next(get_session())
    try:
        total_users = session.scalar(select(func.count(User.id)))
        demo_users = session.scalar(
            select(func.count(User.id)).where(User.access_type == "demo")
        )
        monthly_users = session.scalar(
            select(func.count(User.id)).where(User.access_type == "monthly")
        )
        unlimited_users = session.scalar(
            select(func.count(User.id)).where(User.access_type == "unlimited")
        )
        total_declarations = session.scalar(select(func.count(Declaration.id)))
        generated = session.scalar(
            select(func.count(Declaration.id)).where(Declaration.status == "generated")
        )
        calculated = session.scalar(
            select(func.count(Declaration.id)).where(Declaration.status == "calculated")
        )
        total_payments = session.scalar(select(func.sum(Payment.amount)))
    finally:
        session.close()

    text = (
        "📊 <b>Статистика</b>\n\n"
        f"👥 Пользователей всего: <b>{total_users}</b>\n"
        f"   🆓 Демо: {demo_users}\n"
        f"   📅 Месячных: {monthly_users}\n"
        f"   ♾️ Безлимит: {unlimited_users}\n\n"
        f"📄 Деклараций всего: <b>{total_declarations}</b>\n"
        f"   ✅ Готовых: {generated}\n"
        f"   🔢 Рассчитано: {calculated}\n\n"
        f"💰 Сумма платежей: <b>{total_payments or 0:,.2f} ₽</b>"
    )

    await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_logs")
async def admin_logs(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    session = next(get_session())
    try:
        result = session.execute(
            select(AdminLog)
            .order_by(AdminLog.created_at.desc())
            .limit(20)
        )
        logs = result.scalars().all()
    finally:
        session.close()

    if not logs:
        text = "📋 Логов пока нет."
    else:
        text = "📋 <b>Последние действия:</b>\n\n"
        for log in logs:
            created = log.created_at.strftime("%d.%m.%Y %H:%M") if log.created_at else "—"
            text += f"🕐 {created} — {log.action}\n"
            if log.details:
                text += f"   {log.details}\n"
            text += "\n"

    await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    if callback.from_user.id not in ADMIN_IDS:
        await callback.answer("Доступ запрещён", show_alert=True)
        return

    await callback.message.edit_text(
        "🔐 <b>Админ-панель</b>\n\nВыберите действие:",
        reply_markup=admin_panel_kb()
    )
    await callback.answer()