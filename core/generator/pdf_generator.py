import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from bot.config import DATA_TEMP_DIR


PAGE_W, PAGE_H = A4
FONT_NAME = "Courier"


async def generate_pdf(declaration_id: int, data: dict) -> str:
    pdf_path = os.path.join(DATA_TEMP_DIR, f"declaration_{declaration_id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)

    _draw_title_page(c, data)
    c.showPage()
    _draw_section1(c, data)
    c.showPage()
    _draw_section2(c, data)
    c.showPage()
    _draw_appendix5(c, data)

    c.save()
    return pdf_path


def _draw_title_page(c, data):
    y = PAGE_H - 20 * mm
    c.setFont(FONT_NAME, 10)

    # Номер корректировки
    c.drawString(130 * mm, y, "0--")
    # Код периода (34 — год)
    c.drawString(155 * mm, y, "34")
    # Отчётный год
    year = str(data.get("year", ""))
    c.drawString(170 * mm, y, year)
    # Код налогового органа
    c.drawString(130 * mm, y - 7 * mm, "________")

    y -= 18 * mm
    # Код страны
    c.drawString(20 * mm, y, "643")
    # Код категории
    c.drawString(55 * mm, y, "760")

    y -= 12 * mm
    # ФИО
    c.setFont(FONT_NAME, 11)
    c.drawString(25 * mm, y, "___________________________________________")
    c.drawString(25 * mm, y - 3 * mm, "(Фамилия, имя, отчество)")

    y -= 18 * mm
    # ИНН
    c.setFont(FONT_NAME, 10)
    inn = data.get("taxpayer_inn", "")
    c.drawString(25 * mm, y, f"ИНН: {inn}")

    y -= 8 * mm
    # Статус
    c.drawString(25 * mm, y, "Статус налогоплательщика: 1 (резидент РФ)")

    y -= 8 * mm
    # Телефон
    phone = data.get("taxpayer_phone", "")
    c.drawString(25 * mm, y, f"Контактный телефон: {phone}")

    y -= 15 * mm
    c.setFont(FONT_NAME, 8)
    c.drawString(25 * mm, y, "Достоверность и полноту сведений подтверждаю.")
    c.drawString(25 * mm, y - 5 * mm, "Заполняется налогоплательщиком лично.")


def _draw_section1(c, data):
    y = PAGE_H - 20 * mm
    c.setFont(FONT_NAME, 10)
    c.drawString(60 * mm, y, "Раздел 1. Сумма налога, подлежащая возврату из бюджета")

    y -= 14 * mm
    c.setFont(FONT_NAME, 9)
    c.drawString(20 * mm, y, "КБК: 18210102010011000110")
    c.drawString(110 * mm, y, "ОКТМО: ____________________")

    y -= 12 * mm
    tax_return = data.get("tax_return", 0)
    c.setFont(FONT_NAME, 11)
    c.drawString(20 * mm, y, f"Сумма налога к возврату из бюджета: {tax_return:,.2f} руб.")


def _draw_section2(c, data):
    y = PAGE_H - 20 * mm
    c.setFont(FONT_NAME, 10)
    c.drawString(50 * mm, y, "Раздел 2. Расчёт налоговой базы и суммы налога")

    y -= 14 * mm
    c.setFont(FONT_NAME, 9)
    c.drawString(20 * mm, y, "Общая сумма дохода (строка 010): ____________________ руб.")

    y -= 8 * mm
    deduction = data.get("deduction_amount", 0)
    c.drawString(20 * mm, y, f"Сумма налоговых вычетов (строка 040): {deduction:,.2f} руб.")

    y -= 8 * mm
    c.drawString(20 * mm, y, "Налоговая база (строка 060): ____________________ руб.")

    y -= 8 * mm
    c.drawString(20 * mm, y, "Сумма налога, удержанная у источника выплаты (строка 100): ___________ руб.")

    y -= 8 * mm
    tax_return = data.get("tax_return", 0)
    c.setFont(FONT_NAME, 10)
    c.drawString(20 * mm, y, f"Сумма налога к возврату из бюджета (строка 160): {tax_return:,.2f} руб.")


def _draw_appendix5(c, data):
    y = PAGE_H - 20 * mm
    c.setFont(FONT_NAME, 10)
    c.drawString(45 * mm, y, "Приложение 5. Социальные налоговые вычеты")

    y -= 14 * mm
    deduction_type = data.get("deduction_type", "")
    type_names = {
        "medical": "Медицинские услуги (пп. 3 п. 1 ст. 219 НК РФ)",
        "education": "Обучение (пп. 2 п. 1 ст. 219 НК РФ)",
    }
    c.setFont(FONT_NAME, 9)
    c.drawString(20 * mm, y, f"Вид вычета: {type_names.get(deduction_type, deduction_type)}")

    y -= 12 * mm
    institution = data.get("institution_name", "")
    inn = data.get("institution_inn", "")
    c.drawString(20 * mm, y, f"Наименование учреждения: {institution}")
    y -= 7 * mm
    c.drawString(20 * mm, y, f"ИНН учреждения: {inn}")

    y -= 12 * mm
    amount = data.get("amount", 0)
    c.drawString(20 * mm, y, f"Сумма расходов: {amount:,.2f} руб.")

    y -= 10 * mm
    deduction = data.get("deduction_amount", 0)
    c.drawString(20 * mm, y, f"Сумма вычета (с учётом лимита 150 000 руб.): {deduction:,.2f} руб.")

    y -= 10 * mm
    tax_return = data.get("tax_return", 0)
    c.setFont(FONT_NAME, 10)
    c.drawString(20 * mm, y, f"НДФЛ к возврату: {tax_return:,.2f} руб.")