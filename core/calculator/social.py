from datetime import datetime


def calculate_social_deduction(
    deduction_type: str,
    amount: float,
    institution_name: str,
    institution_inn: str
) -> dict:
    """
    Расчёт социального налогового вычета.
    
    Лимиты (ст. 219 НК РФ):
    - Медицинские услуги: до 120 000 ₽ в год (общий лимит по соц. вычетам)
    - Обучение: до 50 000 ₽ на себя, до 110 000 ₽ на детей (с 2024 г.)
    
    Возвращает словарь с результатами расчёта.
    """
    # Общий лимит по социальным вычетам с 2024 года — 150 000 ₽
    SOCIAL_LIMIT = 150_000
    
    # Применяем лимит
    deductible_amount = min(amount, SOCIAL_LIMIT)
    
    # НДФЛ к возврату (13%)
    tax_return = round(deductible_amount * 0.13, 2)
    
    current_year = datetime.now().year
    
    return {
        "deduction_type": deduction_type,
        "amount": amount,
        "deduction_amount": deductible_amount,
        "tax_return": tax_return,
        "institution_name": institution_name,
        "institution_inn": institution_inn,
        "year": current_year - 1,  # декларация за предыдущий год
        "limit_applied": amount > SOCIAL_LIMIT
    }