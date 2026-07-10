from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Загрузить выписку", callback_data="menu_upload")],
            [InlineKeyboardButton(text="👤 Мои профили", callback_data="menu_profiles")],
            [InlineKeyboardButton(text="📊 Мой профиль", callback_data="menu_profile")],
        ]
    )


def deduction_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🏥 Медицинские услуги", callback_data="deduction_medical")],
            [InlineKeyboardButton(text="🎓 Обучение", callback_data="deduction_education")],
            [InlineKeyboardButton(text="📈 Инвестиционный вычет", callback_data="deduction_investment")],
            [InlineKeyboardButton(text="🏠 Имущественный вычет", callback_data="deduction_property")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def confirm_manual_input_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📸 Загрузить фото документа", callback_data="upload_photo")],
            [InlineKeyboardButton(text="✏️ Ввести вручную", callback_data="manual_input")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def confirm_data_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, всё верно", callback_data="confirm_yes")],
            [InlineKeyboardButton(text="❌ Нет, исправить", callback_data="confirm_no")],
        ]
    )


def remember_me_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💾 Да, запомнить", callback_data="remember_yes")],
            [InlineKeyboardButton(text="👤 Нет, только сейчас", callback_data="remember_no")],
        ]
    )


def download_kb(declaration_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📥 Скачать декларацию (Excel)", callback_data=f"download_xlsx_{declaration_id}")],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu_back")],
        ]
    )


def profile_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 История деклараций", callback_data="history")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="menu_back")],
        ]
    )


def profiles_list_kb(profiles: list, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Клавиатура со списком профилей, пагинацией и поиском."""
    buttons = []
    for p in profiles:
        buttons.append([InlineKeyboardButton(
            text=f"{p.name} (ИНН: {p.inn[:4]}...)",
            callback_data=f"profiledetail_{p.id}"
        )])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"profilespage_{page-1}"))
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"profilespage_{page+1}"))
    if nav_buttons:
        buttons.append(nav_buttons)

    buttons.append([InlineKeyboardButton(text="🔍 Поиск профиля", callback_data="profiles_search")])
    buttons.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="menu_back")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def profile_detail_kb(profile_id: int) -> InlineKeyboardMarkup:
    """Клавиатура управления конкретным профилем."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"profileedit_{profile_id}")],
            [InlineKeyboardButton(text="🗑 Удалить", callback_data=f"profiledelete_{profile_id}")],
            [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="profilespage_0")],
        ]
    )


def profile_delete_confirm_kb(profile_id: int) -> InlineKeyboardMarkup:
    """Подтверждение удаления профиля."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"profiledeleteconfirm_{profile_id}")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data=f"profiledetail_{profile_id}")],
        ]
    )