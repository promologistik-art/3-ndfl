def format_currency(amount: float) -> str:
    """Форматирует число в денежный формат: 15000.00 → 15 000,00 ₽"""
    return f"{amount:,.2f} ₽".replace(",", " ").replace(".", ",").replace(" ", " ", 1)


def validate_inn(inn: str) -> bool:
    """Простая валидация ИНН (10 или 12 цифр)"""
    inn = inn.strip()
    return inn.isdigit() and len(inn) in (10, 12)


def validate_date(date_str: str) -> bool:
    """Проверка формата даты ДД.ММ.ГГГГ"""
    import re
    pattern = r"^\d{2}[./-]\d{2}[./-]\d{4}$"
    return bool(re.match(pattern, date_str))