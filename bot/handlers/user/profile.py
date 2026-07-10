from datetime import datetime, timezone
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from core.models import User, Declaration, Profile, get_session
from bot.keyboards.user import profile_kb, profiles_list_kb, profile_detail_kb, profile_delete_confirm_kb
from sqlalchemy import select, func

router = Router()


class ProfileStates(StatesGroup):
    waiting_for_search = State()
    waiting_for_edit_name = State()


@router.callback_query(F.data == "menu_profile")
async def show_profile(callback: CallbackQuery, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    session = next(get_session())
    try:
        total_decls = session.scalar(
            select(func.count(Declaration.id)).where(Declaration.user_id == user.id)
        )
    finally:
        session.close()

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
async def show_history(callback: CallbackQuery, user: User = None):
    if not user:
        await callback.answer("Ошибка")
        return

    session = next(get_session())
    try:
        result = session.execute(
            select(Declaration)
            .where(Declaration.user_id == user.id)
            .order_by(Declaration.created_at.desc())
            .limit(10)
        )
        declarations = result.scalars().all()
    finally:
        session.close()

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


# ==================== УПРАВЛЕНИЕ ПРОФИЛЯМИ ====================

@router.callback_query(F.data == "menu_profiles")
async def show_profiles(callback: CallbackQuery):
    await _show_profiles_page(callback, 0)


@router.callback_query(F.data.startswith("profilespage_"))
async def profiles_page(callback: CallbackQuery):
    page = int(callback.data.replace("profilespage_", ""))
    await _show_profiles_page(callback, page)


async def _show_profiles_page(callback: CallbackQuery, page: int):
    session = next(get_session())
    try:
        total = session.scalar(
            select(func.count(Profile.id)).where(Profile.user_id == callback.from_user.id)
        )
        profiles = session.execute(
            select(Profile)
            .where(Profile.user_id == callback.from_user.id)
            .order_by(Profile.id.desc())
            .offset(page * 5)
            .limit(5)
        )
        profiles = profiles.scalars().all()
    finally:
        session.close()

    total_pages = max(1, (total + 4) // 5)

    if not profiles:
        await callback.message.edit_text(
            "👤 У вас пока нет сохранённых профилей.\n\n"
            "Профили создаются автоматически при заполнении декларации.",
            reply_markup=profiles_list_kb([], 0, 1)
        )
        await callback.answer()
        return

    text = f"👤 <b>Мои профили</b> (стр. {page+1} из {total_pages}):\n\n"
    await callback.message.edit_text(text, reply_markup=profiles_list_kb(profiles, page, total_pages))
    await callback.answer()


@router.callback_query(F.data == "profiles_search")
async def profiles_search_start(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "🔍 Введите фамилию или ИНН (или часть) для поиска профиля:"
    )
    await state.set_state(ProfileStates.waiting_for_search)
    await callback.answer()


@router.message(ProfileStates.waiting_for_search)
async def profiles_search_result(message: Message, state: FSMContext):
    query = message.text.strip()
    session = next(get_session())
    try:
        profiles = session.execute(
            select(Profile)
            .where(
                Profile.user_id == message.from_user.id,
                (Profile.last_name.ilike(f"%{query}%")) | (Profile.inn.ilike(f"%{query}%"))
            )
            .limit(10)
        )
        profiles = profiles.scalars().all()
    finally:
        session.close()

    if not profiles:
        await message.answer("❌ Ничего не найдено.")
        await state.clear()
        return

    text = f"🔍 Найдено профилей: {len(profiles)}:\n\n"
    buttons = []
    for p in profiles:
        text += f"• {p.name} (ИНН: {p.inn})\n"
        buttons.append([InlineKeyboardButton(
            text=f"{p.name}", callback_data=f"profiledetail_{p.id}"
        )])
    buttons.append([InlineKeyboardButton(text="🔙 К списку", callback_data="profilespage_0")])

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    await message.answer(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
    await state.clear()


@router.callback_query(F.data.startswith("profiledetail_"))
async def profile_detail(callback: CallbackQuery):
    profile_id = int(callback.data.replace("profiledetail_", ""))

    session = next(get_session())
    try:
        p = session.get(Profile, profile_id)
    finally:
        session.close()

    if not p:
        await callback.answer("Профиль не найден")
        return

    text = (
        f"👤 <b>{p.name}</b>\n\n"
        f"ИНН: <code>{p.inn}</code>\n"
        f"ФИО: {p.last_name} {p.first_name} {p.middle_name}\n"
        f"Дата рождения: {p.birth_date}\n"
        f"Паспорт: {p.passport}\n"
        f"Код ИФНС: {p.tax_office}\n"
        f"Телефон: {p.phone}\n"
        f"БИК: {p.bik}\n"
        f"Счёт: {p.account}\n"
        f"Карта: {p.card or '—'}\n"
    )

    await callback.message.edit_text(text, reply_markup=profile_detail_kb(profile_id))
    await callback.answer()


@router.callback_query(F.data.startswith("profileedit_"))
async def profile_edit_start(callback: CallbackQuery, state: FSMContext):
    profile_id = int(callback.data.replace("profileedit_", ""))

    await state.update_data(edit_profile_id=profile_id)
    await callback.message.edit_text("Введите новое название профиля (например, «Иванов И.И.»):")
    await state.set_state(ProfileStates.waiting_for_edit_name)
    await callback.answer()


@router.message(ProfileStates.waiting_for_edit_name)
async def profile_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    profile_id = data.get("edit_profile_id")
    new_name = message.text.strip()

    session = next(get_session())
    try:
        p = session.get(Profile, profile_id)
        if p:
            p.name = new_name
            session.commit()
            await message.answer(f"✅ Профиль переименован в «{new_name}».")
            await _show_profiles_page_from_message(message, 0)
    finally:
        session.close()

    await state.clear()


async def _show_profiles_page_from_message(message: Message, page: int):
    session = next(get_session())
    try:
        total = session.scalar(
            select(func.count(Profile.id)).where(Profile.user_id == message.from_user.id)
        )
        profiles = session.execute(
            select(Profile)
            .where(Profile.user_id == message.from_user.id)
            .order_by(Profile.id.desc())
            .offset(page * 5)
            .limit(5)
        )
        profiles = profiles.scalars().all()
    finally:
        session.close()

    total_pages = max(1, (total + 4) // 5)
    text = f"👤 <b>Мои профили</b> (стр. {page+1} из {total_pages}):\n\n"
    await message.answer(text, reply_markup=profiles_list_kb(profiles, page, total_pages))


@router.callback_query(F.data.startswith("profiledelete_"))
async def profile_delete_ask(callback: CallbackQuery):
    profile_id = int(callback.data.replace("profiledelete_", ""))

    await callback.message.edit_text(
        "⚠️ Вы уверены, что хотите удалить этот профиль?\n"
        "Это действие нельзя отменить.",
        reply_markup=profile_delete_confirm_kb(profile_id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("profiledeleteconfirm_"))
async def profile_delete_confirm(callback: CallbackQuery):
    profile_id = int(callback.data.replace("profiledeleteconfirm_", ""))

    session = next(get_session())
    try:
        p = session.get(Profile, profile_id)
        if p:
            session.delete(p)
            session.commit()
    finally:
        session.close()

    await callback.answer("✅ Профиль удалён.")
    await _show_profiles_page(callback, 0)


def _get_remaining(user: User) -> str:
    if user.access_type == "unlimited":
        return "∞"
    if user.access_type == "demo":
        return f"{max(0, 1 - user.declarations_used)} из 1"
    if user.access_type == "monthly":
        return f"{max(0, 1 - user.declarations_used)} из 1"
    return "0"