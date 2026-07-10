from datetime import datetime


def calculate_social_deduction(
    deduction_type: str,
    amount: float,
    institution_name: str,
    institution_inn: str,
    payment_date: str = "",
) -> dict:
    SOCIAL_LIMIT = 150_000
    deductible_amount = min(amount, SOCIAL_LIMIT)
    tax_return = round(deductible_amount * 0.13, 2)

    # Год из даты платежа, иначе предыдущий год
    if payment_date and len(payment_date) >= 4:
        try:
            year = int(payment_date.split(".")[-1])
        except (ValueError, IndexError):
            year = datetime.now().year - 1
    else:
        year = datetime.now().year - 1

    return {
        "deduction_type": deduction_type,
        "amount": amount,
        "deduction_amount": deductible_amount,
        "tax_return": tax_return,
        "institution_name": institution_name,
        "institution_inn": institution_inn,
        "year": year,
        "limit_applied": amount > SOCIAL_LIMIT
    }