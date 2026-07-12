from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👤 Выдать доступ", callback_data="admin_grant")],
            [InlineKeyboardButton(text="📋 История операций", callback_data="admin_logs")],
            [InlineKeyboardButton(text="🔙 Закрыть", callback_data="menu_back")],
        ]
    )


def admin_grant_type_kb(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🆓 Демо", callback_data=f"grant_demo_{user_id}")],
            [InlineKeyboardButton(text="📅 Месяц (100₽)", callback_data=f"grant_monthly_{user_id}")],
            [InlineKeyboardButton(text="🔬 Тест 14 дней (10 декл.)", callback_data=f"grant_test14_{user_id}")],
            [InlineKeyboardButton(text="♾️ Безлимит (500₽)", callback_data=f"grant_unlimited_{user_id}")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
        ]
    )


def admin_back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
        ]
    )