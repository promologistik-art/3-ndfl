async def generate_pdf(declaration_id: int, data: dict) -> str:
    """
    Заглушка генерации PDF.
    Будет реализована через reportlab по шаблону 3-НДФЛ.
    Возвращает путь к файлу.
    """
    import os
    from bot.config import DATA_TEMP_DIR

    pdf_path = os.path.join(DATA_TEMP_DIR, f"declaration_{declaration_id}.pdf")
    
    # TODO: реализовать генерацию PDF
    # Пока создаём пустой файл-заглушку
    with open(pdf_path, "w") as f:
        f.write(f"Декларация 3-НДФЛ №{declaration_id}\n")
        f.write(f"Сумма вычета: {data.get('deduction_amount', 0)} руб.\n")
        f.write(f"НДФЛ к возврату: {data.get('tax_return', 0)} руб.\n")

    return pdf_path