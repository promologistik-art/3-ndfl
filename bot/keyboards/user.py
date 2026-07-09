from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📤 Загрузить выписку", callback_data="menu_upload")],
            [InlineKeyboardButton(text="👤 Мой профиль", callback_data="menu_profile")],
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