import os
from datetime import datetime
from openpyxl import load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter
from bot.config import DATA_TEMP_DIR

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(_BASE_DIR, "..", "..", "templates", "ndfl_2025.xlsx")
TEMPLATE_PATH = os.path.abspath(TEMPLATE_PATH)

BASE_SHEETS = ["Титульный лист", "Раздел 1", "Прил-е к Разделу 1", "Раздел 2"]


async def generate_excel(declaration_id: int, data: dict) -> str:
    excel_path = os.path.join(DATA_TEMP_DIR, f"declaration_{declaration_id}.xlsx")
    wb = load_workbook(TEMPLATE_PATH)

    selected = data.get("selected_deductions", {})
    print_sheets = list(BASE_SHEETS)

    if selected.get("education"):
        print_sheets.append("Прил.5")
    if selected.get("medical"):
        print_sheets.append("Прил.5 (продолжение)")
    if selected.get("property"):
        print_sheets.append("Прил.7")
    if selected.get("investment"):
        print_sheets.append("Прил.5")
        print_sheets.append("Расчет к прил.5")

    page_number = 1
    for sheet_name in print_sheets:
        ws = wb[sheet_name]
        ws.sheet_properties.tabColor = "00CC00"
        _write_page_number(ws, str(page_number).zfill(3))
        page_number += 1

    for sheet_name in wb.sheetnames:
        if sheet_name not in print_sheets:
            wb[sheet_name].sheet_properties.tabColor = "C0C0C0"

    _fill_title(wb, data, len(print_sheets))
    _fill_section1(wb, data)
    _fill_return_request(wb, data)
    _fill_section2(wb, data)

    if selected.get("education"):
        _fill_appendix5_education(wb, data)
    if selected.get("medical"):
        _fill_appendix5_medical(wb, data)
    if selected.get("property"):
        _fill_appendix7(wb, data)
    if selected.get("investment"):
        _fill_appendix5_investment(wb, data)
        _fill_calc_appendix5(wb, data)

    wb.save(excel_path)
    return excel_path


def _safe_write(ws, cell_ref, value, font_size=None):
    value = str(value) if value is not None else ""
    cell = ws[cell_ref]
    if isinstance(cell, MergedCell):
        for merged_range in ws.merged_cells.ranges:
            if cell.coordinate in merged_range:
                parent_cell = ws.cell(row=merged_range.min_row, column=merged_range.min_col)
                parent_cell.value = value
                if font_size:
                    parent_cell.font = Font(size=font_size)
                return
    else:
        cell.value = value
        if font_size:
            cell.font = Font(size=font_size)


def _write_fio_field(ws, text, start_col, row):
    text = str(text) if text else ""
    col = start_col
    for char in text:
        if col > 60:
            break
        col_letter = get_column_letter(col)
        _safe_write(ws, f"{col_letter}{row}", char.upper())
        col += 2


def _write_number_field(ws, text, start_col, row):
    text = str(text) if text else ""
    col = start_col
    for char in text:
        col_letter = get_column_letter(col)
        _safe_write(ws, f"{col_letter}{row}", char)
        col += 1


def _write_amount_with_kopeks(ws, amount, start_col, row):
    amount_str = f"{amount:.2f}"
    parts = amount_str.split(".")
    rubles = parts[0]
    kopeks = parts[1]
    _write_number_field(ws, rubles, start_col, row)
    _safe_write(ws, f"AM{row}", kopeks[0])
    _safe_write(ws, f"AN{row}", kopeks[1])


def _write_page_number(ws, number_str):
    number_str = str(number_str).zfill(3)
    _safe_write(ws, "X4", number_str[0])
    _safe_write(ws, "Y4", number_str[1])
    _safe_write(ws, "Z4", number_str[2])


def _write_fio_section_header(ws, data):
    last_name = str(data.get("last_name", ""))
    _safe_write(ws, "E7", last_name.upper())
    first_name = str(data.get("first_name", ""))
    if first_name:
        _safe_write(ws, "AH7", first_name[0].upper())
    middle_name = str(data.get("middle_name", ""))
    if middle_name and middle_name != "-":
        _safe_write(ws, "AK7", middle_name[0].upper())


# ==================== ТИТУЛЬНЫЙ ЛИСТ ====================

def _fill_title(wb, data, total_pages):
    ws = wb["Титульный лист"]
    _write_inn(ws, data.get("taxpayer_inn", ""))
    _safe_write(ws, "K11", "0")
    _safe_write(ws, "M11", "0")
    _safe_write(ws, "O11", "0")
    _safe_write(ws, "AC11", "3")
    _safe_write(ws, "AE11", "4")
    year = str(data.get("year", ""))
    if len(year) >= 4:
        _safe_write(ws, "AU11", year[0])
        _safe_write(ws, "AW11", year[1])
        _safe_write(ws, "AY11", year[2])
        _safe_write(ws, "BA11", year[3])
    tax_office = str(data.get("tax_office", ""))
    if len(tax_office) >= 4:
        _safe_write(ws, "BU11", tax_office[0])
        _safe_write(ws, "BW11", tax_office[1])
        _safe_write(ws, "BY11", tax_office[2])
        _safe_write(ws, "CA11", tax_office[3])
    _safe_write(ws, "K16", "6")
    _safe_write(ws, "M16", "4")
    _safe_write(ws, "O16", "3")
    _safe_write(ws, "AU16", "7")
    _safe_write(ws, "AW16", "6")
    _safe_write(ws, "AY16", "0")
    _write_fio_field(ws, data.get("last_name", ""), 11, 18)
    _write_fio_field(ws, data.get("first_name", ""), 11, 20)
    _write_fio_field(ws, data.get("middle_name", ""), 11, 22)
    birth_date = str(data.get("birth_date", ""))
    if len(birth_date) == 10:
        _safe_write(ws, "K31", birth_date[0])
        _safe_write(ws, "M31", birth_date[1])
        _safe_write(ws, "Q31", birth_date[3])
        _safe_write(ws, "S31", birth_date[4])
        _safe_write(ws, "W31", birth_date[6])
        _safe_write(ws, "Y31", birth_date[7])
        _safe_write(ws, "AA31", birth_date[8])
        _safe_write(ws, "AC31", birth_date[9])
    _safe_write(ws, "Q33", "2")
    _safe_write(ws, "S33", "1")
    passport = str(data.get("passport", ""))
    if len(passport) == 10:
        col = 17
        for digit in passport:
            col_letter = get_column_letter(col)
            _safe_write(ws, f"{col_letter}35", digit)
            col += 2
    _safe_write(ws, "Y37", "1")
    _write_fio_field(ws, data.get("taxpayer_phone", ""), 21, 39)

    pages_str = str(total_pages).zfill(3)
    _safe_write(ws, "S44", pages_str[0])
    _safe_write(ws, "U44", pages_str[1])
    _safe_write(ws, "W44", pages_str[2])

    _safe_write(ws, "BQ44", "0")
    _safe_write(ws, "BS44", "0")
    _safe_write(ws, "BU44", "0")
    _safe_write(ws, "D48", "1")
    _write_fio_field(ws, data.get("last_name", ""), 2, 50)
    _write_fio_field(ws, data.get("first_name", ""), 2, 52)
    _write_fio_field(ws, data.get("middle_name", ""), 2, 54)
    today = datetime.now().strftime("%d%m%Y")
    _safe_write(ws, "V56", today[0])
    _safe_write(ws, "X56", today[1])
    _safe_write(ws, "AB56", today[2])
    _safe_write(ws, "AD56", today[3])
    _safe_write(ws, "AH56", today[4])
    _safe_write(ws, "AJ56", today[5])
    _safe_write(ws, "AL56", today[6])
    _safe_write(ws, "AN56", today[7])


def _write_inn(ws, inn):
    inn = str(inn) if inn else ""
    if len(inn) < 12:
        return
    cols = [25, 27, 29, 31, 33, 35, 37, 39, 41, 43, 45, 47]
    for i, digit in enumerate(inn[:12]):
        col_letter = get_column_letter(cols[i])
        _safe_write(ws, f"{col_letter}1", digit)


# ==================== РАЗДЕЛ 1 ====================

def _fill_section1(wb, data):
    ws = wb["Раздел 1"]
    _write_fio_section_header(ws, data)
    kbk = "18210102010011000110"
    _write_number_field(ws, kbk, 21, 12)

    tax_to_pay = data.get("tax_to_pay", 0)
    tax_return = data.get("tax_return", 0)

    if tax_to_pay > 0:
        _write_number_field(ws, str(round(tax_to_pay)), 21, 16)
    elif tax_return > 0:
        _write_number_field(ws, str(round(tax_return)), 21, 18)

    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V63", today, font_size=8)


# ==================== ПРИЛОЖЕНИЕ К РАЗДЕЛУ 1 ====================

def _fill_return_request(wb, data):
    ws = wb["Прил-е к Разделу 1"]
    _write_fio_section_header(ws, data)

    tax_return = data.get("tax_return", 0)
    _write_number_field(ws, str(round(tax_return)), 13, 11)

    bik = str(data.get("bik", ""))
    if len(bik) == 9:
        _write_number_field(ws, bik, 21, 15)
    account = str(data.get("account", ""))
    if len(account) == 20:
        _write_number_field(ws, account, 21, 17)
    card = str(data.get("card", ""))
    if card:
        _write_number_field(ws, card, 21, 19)
    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V50", today, font_size=8)


# ==================== РАЗДЕЛ 2 ====================

def _fill_section2(wb, data):
    ws = wb["Раздел 2"]
    _write_fio_section_header(ws, data)
    _safe_write(ws, "Y9", "0")
    _safe_write(ws, "Z9", "1")
    income = data.get("income", 0)
    _write_amount_with_kopeks(ws, income, 25, 11)
    deduction = data.get("total_deduction", 0)
    _write_amount_with_kopeks(ws, deduction, 25, 17)
    tax_base = max(0, income - deduction)
    _write_amount_with_kopeks(ws, tax_base, 25, 21)
    tax_calculated = round(tax_base * 0.13)
    _write_number_field(ws, str(tax_calculated), 25, 24)
    tax_paid = data.get("tax_paid", 0)
    _write_number_field(ws, str(round(tax_paid)), 25, 26)

    tax_to_pay = data.get("tax_to_pay", 0)
    tax_return = data.get("tax_return", 0)

    if tax_to_pay > 0:
        _write_number_field(ws, str(round(tax_to_pay)), 25, 38)
    if tax_return > 0:
        _write_number_field(ws, str(round(tax_return)), 25, 40)

    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V59", today, font_size=8)


# ==================== ПРИЛОЖЕНИЕ 5 (ОБУЧЕНИЕ) ====================

def _fill_appendix5_education(wb, data):
    ws = wb["Прил.5"]
    _write_fio_section_header(ws, data)
    education_total = data.get("education_total", 0)
    _write_amount_with_kopeks(ws, education_total, 26, 42)
    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V47", today, font_size=8)


# ==================== ПРИЛОЖЕНИЕ 5 (МЕДИЦИНА) ====================

def _fill_appendix5_medical(wb, data):
    ws = wb["Прил.5 (продолжение)"]
    _write_fio_section_header(ws, data)
    medical_total = data.get("medical_total", 0)
    _write_amount_with_kopeks(ws, medical_total, 26, 9)
    _write_amount_with_kopeks(ws, medical_total, 26, 23)
    _write_amount_with_kopeks(ws, medical_total, 26, 29)
    _write_amount_with_kopeks(ws, medical_total, 26, 31)
    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V54", today, font_size=8)


# ==================== ПРИЛОЖЕНИЕ 5 (ИНВЕСТИЦИИ) ====================

def _fill_appendix5_investment(wb, data):
    ws = wb["Прил.5"]
    _write_fio_section_header(ws, data)
    investment_amount = data.get("investment_amount", 0)
    _write_amount_with_kopeks(ws, investment_amount, 26, 42)
    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V47", today, font_size=8)


def _fill_calc_appendix5(wb, data):
    ws = wb["Расчет к прил.5"]
    _write_fio_section_header(ws, data)
    investment_amount = data.get("investment_amount", 0)
    _write_amount_with_kopeks(ws, investment_amount, 26, 9)
    _safe_write(ws, "D80", "1")
    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V47", today, font_size=8)


# ==================== ПРИЛОЖЕНИЕ 7 (ИМУЩЕСТВО) ====================

def _fill_appendix7(wb, data):
    ws = wb["Прил.7"]
    _write_fio_section_header(ws, data)

    property_price = data.get("property_price", data.get("property_total", 0))
    property_mortgage = data.get("property_mortgage", 0)
    property_object_type = data.get("property_object_type", "5")
    property_cadastral = data.get("property_cadastral", "")
    property_address = data.get("property_address", "")
    property_act_date = data.get("property_act_date", "")
    property_reg_date = data.get("property_reg_date", "")
    income = data.get("income", 0)
    total_deduction = data.get("total_deduction", 0)

    # 010 — код объекта: K10
    _safe_write(ws, "K10", property_object_type)

    # 020 — код признака налогоплательщика: Y10, Z10 = "01"
    _safe_write(ws, "Y10", "0")
    _safe_write(ws, "Z10", "1")

    # 030 — способ приобретения: Y12 = "2"
    _safe_write(ws, "Y12", "2")

    # 032 — кадастровый номер: A14-AN14
    if property_cadastral:
        _write_number_field(ws, property_cadastral, 1, 14)

    # 033 — адрес (разбиваем на строки по 40 символов)
    if property_address:
        lines = [property_address[i:i+40] for i in range(0, len(property_address), 40)]
        for idx, line in enumerate(lines[:7]):
            _safe_write(ws, f"A{16 + idx * 2}", line)

    # 040 — дата акта: AD30, AE30 (день), AG30, AH30 (месяц), AJ30-AM30 (год)
    if property_act_date and len(property_act_date) == 10:
        _safe_write(ws, "AD30", property_act_date[0])
        _safe_write(ws, "AE30", property_act_date[1])
        _safe_write(ws, "AG30", property_act_date[3])
        _safe_write(ws, "AH30", property_act_date[4])
        _safe_write(ws, "AJ30", property_act_date[6])
        _safe_write(ws, "AK30", property_act_date[7])
        _safe_write(ws, "AL30", property_act_date[8])
        _safe_write(ws, "AM30", property_act_date[9])

    # 050 — дата регистрации: строка 32
    if property_reg_date and len(property_reg_date) == 10:
        _safe_write(ws, "AD32", property_reg_date[0])
        _safe_write(ws, "AE32", property_reg_date[1])
        _safe_write(ws, "AG32", property_reg_date[3])
        _safe_write(ws, "AH32", property_reg_date[4])
        _safe_write(ws, "AJ32", property_reg_date[6])
        _safe_write(ws, "AK32", property_reg_date[7])
        _safe_write(ws, "AL32", property_reg_date[8])
        _safe_write(ws, "AM32", property_reg_date[9])

    # 080 — расходы на покупку: AD34-AK34 + копейки AM34, AN34
    ded_price = min(property_price, 2_000_000)
    _write_amount_with_kopeks(ws, ded_price, 30, 34)

    # 090 — проценты по ипотеке: строка 36
    if property_mortgage > 0:
        ded_mortgage = min(property_mortgage, 3_000_000)
        _write_amount_with_kopeks(ws, ded_mortgage, 30, 36)

    # 140 — налоговая база: Z51-AK51 + копейки AM51, AN51
    tax_base = max(0, income - total_deduction)
    _write_amount_with_kopeks(ws, tax_base, 26, 51)

    # 150 — вычет за период: строка 53
    _write_amount_with_kopeks(ws, ded_price, 30, 53)

    # 170 — остаток на следующий год: строка 57
    remaining = max(0, property_price - ded_price)
    _write_amount_with_kopeks(ws, remaining, 30, 57)

    today = datetime.now().strftime("%d.%m.%Y")
    _safe_write(ws, "V63", today, font_size=8)