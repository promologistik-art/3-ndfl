import os
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from bot.config import DATA_TEMP_DIR


# Размеры страницы A4
PAGE_W, PAGE_H = A4  # 595.27 x 841.89 pt


def _find_font():
    """Ищет доступный кириллический шрифт."""
    # Пробуем системные шрифты
    paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
        "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/liberation/LiberationSans-Regular.ttf",
        "DejaVuSans.ttf",
    ]
    for path in paths:
        if os.path.exists(path):
            return path
    return "Helvetica"


def _register_font():
    font_path = _find_font()
    if font_path != "Helvetica":
        try:
            pdfmetrics.registerFont(TTFont("TaxFont", font_path))
            return "TaxFont"
        except Exception:
            pass
    return "Helvetica"


async def generate_pdf(declaration_id: int, data: dict) -> str:
    font_name = _register_font()

    pdf_path = os.path.join(DATA_TEMP_DIR, f"declaration_{declaration_id}.pdf")
    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setFont(font_name, 8)

    # === Титульный лист ===
    _draw_title_page(c, data, font_name)

    # === Раздел 1 ===
    c.showPage()
    _draw_section1(c, data, font_name)

    # === Раздел 2 ===
    c.showPage()
    _draw_section2(c, data, font_name)

    # === Приложение 5 (соц. вычеты) ===
    c.showPage()
    _draw_appendix5(c, data, font_name)

    c.save()
    return pdf_path


def _draw_title_page(c, data, font_name):
    """Титульный лист декларации 3-НДФЛ."""
    y = PAGE_H - 20 * mm

    # Номер корректировки: 0-- (первичная)
    c.setFont(font_name, 10)
    c.drawString(130 * mm, y, "0--")
    # Налоговый период (код 34 — год)
    c.drawString(160 * mm, y, "34")
    # Отчётный год
    year = str(data.get("year", ""))
    c.drawString(180 * mm, y, year)
    # Код налогового органа (пока пусто)
    c.drawString(130 * mm, y - 7 * mm, "____")

    y -= 20 * mm
    # Код страны (643 — Россия)
    c.drawString(20 * mm, y, "643")
    # Код категории налогоплательщика (760 — физ. лицо)
    c.drawString(60 * mm, y, "760")

    y -= 10 * mm
    # ФИО
    c.setFont(font_name, 11)
    c.drawString(25 * mm, y, "___________________________________________")
    c.drawString(25 * mm, y - 3 * mm, "Фамилия, имя, отчество")

    y -= 20 * mm
    # ИНН
    inn = data.get("taxpayer_inn", "")
    c.setFont(font_name, 10)
    c.drawString(25 * mm, y, f"ИНН: {inn}")

    y -= 10 * mm
    # Статус (1 — налоговый резидент РФ)
    c.drawString(25 * mm, y, "Статус: 1")

    y -= 10 * mm
    # Телефон
    phone = data.get("taxpayer_phone", "")
    c.drawString(25 * mm, y, f"Тел: {phone}")


def _draw_section1(c, data, font_name):
    """Раздел 1 — сумма налога к возврату."""
    y = PAGE_H - 20 * mm
    c.setFont(font_name, 10)
    c.drawString(80 * mm, y, "Раздел 1. Сумма налога, подлежащая возврату из бюджета")

    y -= 15 * mm
    # КБК
    c.drawString(20 * mm, y, "КБК: 18210102010011000110")
    # ОКТМО (пока пусто)
    c.drawString(120 * mm, y, "ОКТМО: ____________")

    y -= 12 * mm
    # Сумма к возврату
    tax_return = data.get("tax_return", 0)
    c.setFont(font_name, 12)
    c.drawString(20 * mm, y, f"Сумма налога к возврату: {tax_return:,.2f} руб.")


def _draw_section2(c, data, font_name):
    """Раздел 2 — расчёт налоговой базы и суммы налога."""
    y = PAGE_H - 20 * mm
    c.setFont(font_name, 10)
    c.drawString(80 * mm, y, "Раздел 2. Расчёт налоговой базы и суммы налога")

    y -= 15 * mm
    # Общая сумма дохода (пока заглушка — нужен ввод от пользователя)
    c.setFont(font_name, 9)
    c.drawString(20 * mm, y, "Общая сумма дохода: ____________ руб.")
    y -= 8 * mm
    # Сумма вычета
    deduction = data.get("deduction_amount", 0)
    c.drawString(20 * mm, y, f"Сумма налогового вычета: {deduction:,.2f} руб.")
    y -= 8 * mm
    # Налоговая база
    c.drawString(20 * mm, y, "Налоговая база: ____________ руб.")
    y -= 8 * mm
    # Сумма налога к уплате
    c.drawString(20 * mm, y, "Сумма налога к уплате: 0 руб.")
    y -= 8 * mm
    # Сумма налога к возврату
    tax_return = data.get("tax_return", 0)
    c.drawString(20 * mm, y, f"Сумма налога к возврату: {tax_return:,.2f} руб.")


def _draw_appendix5(c, data, font_name):
    """Приложение 5 — социальные налоговые вычеты."""
    y = PAGE_H - 20 * mm
    c.setFont(font_name, 10)
    c.drawString(60 * mm, y, "Приложение 5. Социальные налоговые вычеты")

    y -= 15 * mm
    deduction_type = data.get("deduction_type", "")
    type_names = {
        "medical": "Медицинские услуги (пп. 3 п. 1 ст. 219 НК РФ)",
        "education": "Обучение (пп. 2 п. 1 ст. 219 НК РФ)",
    }
    c.setFont(font_name, 9)
    c.drawString(20 * mm, y, f"Вид вычета: {type_names.get(deduction_type, deduction_type)}")

    y -= 12 * mm
    # Данные учреждения
    institution = data.get("institution_name", "")
    inn = data.get("institution_inn", "")
    c.drawString(20 * mm, y, f"Учреждение: {institution}")
    y -= 7 * mm
    c.drawString(20 * mm, y, f"ИНН учреждения: {inn}")

    y -= 12 * mm
    # Сумма расходов
    amount = data.get("amount", 0)
    c.drawString(20 * mm, y, f"Сумма расходов: {amount:,.2f} руб.")

    y -= 10 * mm
    # Сумма вычета (с учётом лимита)
    deduction = data.get("deduction_amount", 0)
    c.drawString(20 * mm, y, f"Сумма вычета (с учётом лимита): {deduction:,.2f} руб.")

    y -= 10 * mm
    # НДФЛ к возврату
    tax_return = data.get("tax_return", 0)
    c.setFont(font_name, 10)
    c.drawString(20 * mm, y, f"НДФЛ к возврату: {tax_return:,.2f} руб.")